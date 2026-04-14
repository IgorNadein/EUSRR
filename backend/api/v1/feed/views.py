from __future__ import annotations

from typing import Any, List

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db.models import (
    BooleanField,
    Count,
    Exists,
    F,
    OuterRef,
    Subquery,
    Value,
)
from employees.constants import DeptPerm
from feed.constants import TYPE_COMPANY, TYPE_DEPARTMENT
from feed.models import Post, PostLike
from feed.notifications import notify_post_reaction
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import (
    FormParser,
    JSONParser,
    MultiPartParser,
)
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from ..permissions import (
    AdminOrActionOrModelPerms,
    AdminOrDeptAllowed,
)
from .serializers import PostListSerializer, PostLikerSerializer, PostSerializer

Employee = get_user_model()


def _to_id(val):
    if val is None:
        return None
    if isinstance(val, int):
        return val
    if hasattr(val, "id"):
        return getattr(val, "id")
    try:
        return int(str(val))
    except (TypeError, ValueError):
        return None


class PostViewSet(viewsets.ModelViewSet):
    """CRUD ленты + like/unlike, pin/unpin.

    Доступ (коротко):
      - list/retrieve/like/unlike — IsAuthenticated
      - create:
                    * type=company    → AdminOrActionOrModelPerms
                        + required_perm_code="feed.publish_company_post"
                    * type=department → AdminOrDeptAllowed
                        с кодом DeptPerm.CREATE_POST|publish_department_post
      - update/partial_update/destroy:
          * company         → как для company-create
          * department      → как для department-create
      - pin/unpin — только staff/superuser
    """

    queryset = Post.objects.select_related("author", "department").order_by(
        "-pinned_global", "-created_at"
    )
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "body"]
    ordering_fields = [
        "created_at",
        "pinned_global",
        "pinned_department",
        "likes_count",
    ]
    ordering = ["-pinned_global", "-created_at"]

    class PostDeptPerm(AdminOrDeptAllowed):
        """Департаментные права для операций над постами отдела.

        SAFE-методы разрешены (IsAuthenticated стоит на вьюхе).
        Коды прав подставляются динамически из get_permissions().
        """

        allow_safe_without_code = True

        def has_permission(self, request, view) -> bool:
            """На create, если type=department, но department не указан,
            не режем запрос — даём сериализатору вернуть 400 вместо 403.
            """
            if getattr(view, "action", None) == "create":
                t = (request.data.get("type") or "").strip()
                if t == TYPE_DEPARTMENT:
                    dept_id = self._to_int_or_none(
                        self._extract_dept_id_from_request(request, view)
                    )
                    if dept_id is None:
                        return True  # пропускаем к валидации сериализатора
            return super().has_permission(request, view)

    def get_permissions(self) -> List[Any]:
        """Возвращает DRF-пермишены под текущий action.

        Без вызова get_object().
        """
        if self.action in {"list", "retrieve", "like", "unlike"}:
            return [IsAuthenticated()]

        if self.action in {"pin", "unpin"}:
            return [IsAdminUser()]

        # --- CREATE: смотрим на тип из тела запроса ---
        if self.action == "create":
            t = (self.request.data.get("type") or "").strip()
            if t == TYPE_COMPANY:
                return [IsAuthenticated(), AdminOrActionOrModelPerms()]
            # department → департаментное право на создание
            dept_code = getattr(
                DeptPerm, "CREATE_POST", "publish_department_post"
            )
            perm = self.PostDeptPerm()
            perm.required_code = DeptPerm.CREATE_POST
            return [IsAuthenticated(), perm]

        # --- UPDATE/PATCH/DELETE: определяем тип поста из БД,
        # но без get_object() ---
        if self.action in {"update", "partial_update", "destroy"}:
            lookup = getattr(self, "lookup_url_kwarg", None) or getattr(
                self, "lookup_field", "pk"
            )
            pk = self.kwargs.get(lookup)
            info = (
                Post.objects.filter(pk=pk)
                .values("type", "department_id")
                .first()
                or {}
            )
            if info.get("type") == TYPE_COMPANY:
                return [IsAuthenticated(), AdminOrActionOrModelPerms()]

            # department
            dept_code = DeptPerm.MANAGE_FEED
            perm = self.PostDeptPerm()
            perm.required_code_map = {
                "update": dept_code,
                "partial_update": dept_code,
                "destroy": dept_code,
            }
            return [IsAuthenticated(), perm]

        # дефолт: просто аутентификация
        return [IsAuthenticated()]

    def get_serializer_class(self):
        return PostListSerializer if self.action == "list" else PostSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["pin_scope"] = self._resolve_pin_scope()
        return context

    def _resolve_pin_scope(self, post: Post | None = None) -> str:
        request_data = self.request.data if self.request.method not in {"GET", "HEAD"} else {}
        scope = (
            self.request.query_params.get("pin_scope")
            or self.request.query_params.get("scope")
            or request_data.get("scope")
            or ""
        ).strip()
        if scope in {"global", "department"}:
            return scope

        post_type = (self.request.query_params.get("type") or "").strip()
        department_id = _to_id(self.request.query_params.get("department"))
        if post_type == TYPE_DEPARTMENT and department_id is not None:
            return "department"
        if post is not None and getattr(post, "type", None) == TYPE_DEPARTMENT:
            return "department"
        return "global"

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        # Аннотируем счётчик комментариев через communications.Chat
        from communications.models import Message

        # ContentType для Post
        post_ct = ContentType.objects.get_for_model(Post)

        # Подсчёт сообщений в чате комментариев для каждого поста
        comments_subquery = (
            Message.objects.filter(
                chat__type="comments",
                chat__context_content_type=post_ct,
                chat__context_object_id=OuterRef("pk"),
            )
            .values("chat")
            .annotate(count=Count("id"))
            .values("count")
        )

        qs = qs.annotate(comments_count=Subquery(comments_subquery))

        if user.is_authenticated:
            qs = qs.annotate(
                is_liked=Exists(
                    PostLike.objects.filter(post=OuterRef("pk"), user=user)
                )
            )
        else:
            qs = qs.annotate(is_liked=Value(False, output_field=BooleanField()))

        # фильтры
        qp = self.request.query_params
        t = qp.get("type")
        if t:
            qs = qs.filter(type=t)
        dept_id = _to_id(qp.get("department"))
        if dept_id is not None:
            qs = qs.filter(department_id=dept_id)
        author_id = _to_id(qp.get("author"))
        if author_id is not None:
            qs = qs.filter(author_id=author_id)
        pin_scope = self._resolve_pin_scope()
        pinned_field = (
            "pinned_department" if pin_scope == "department" else "pinned_global"
        )
        pinned = qp.get("pinned")
        if pinned in ("true", "1"):
            qs = qs.filter(**{pinned_field: True})
        elif pinned in ("false", "0"):
            qs = qs.filter(**{pinned_field: False})

        if pin_scope == "department" and dept_id is not None:
            qs = qs.order_by("-pinned_department", "-created_at")
        else:
            qs = qs.order_by("-pinned_global", "-created_at")

        return qs

    def list(self, request, *args, **kwargs):
        """Возвращает список постов."""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        objects = page if page is not None else queryset

        serializer = self.get_serializer(objects, many=True)
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    # --- ВАЖНО: возвращаем perform_create, чтобы заполнить author ---
    def perform_create(self, serializer: PostSerializer) -> None:
        """Сохраняет пост, проставляя автора текущим пользователем.

        Raises:
            ValidationError: если сериализатор невалиден (обрабатывается DRF).
        """
        serializer.save(author=self.request.user)

    # --- actions (pin/unpin и лайки) ---

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def pin(self, request, pk=None):
        """Пинует пост (только staff/superuser)."""
        post = self.get_object()
        scope = self._resolve_pin_scope(post=post)
        if scope == "department":
            if post.type != TYPE_DEPARTMENT or post.department_id is None:
                return Response(
                    {"detail": "Закрепление в ленте отдела доступно только для публикаций отдела."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if not post.pinned_department:
                Post.objects.filter(pk=post.pk).update(pinned_department=True)
            return Response(
                {
                    "scope": "department",
                    "pinned": True,
                    "pinned_global": bool(post.pinned_global),
                    "pinned_department": True,
                }
            )

        if not post.pinned_global:
            Post.objects.filter(pk=post.pk).update(pinned_global=True)
        return Response(
            {
                "scope": "global",
                "pinned": True,
                "pinned_global": True,
                "pinned_department": bool(post.pinned_department),
            }
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def unpin(self, request, pk=None):
        """Снимает пин (только staff/superuser)."""
        post = self.get_object()
        scope = self._resolve_pin_scope(post=post)
        if scope == "department":
            if post.type != TYPE_DEPARTMENT or post.department_id is None:
                return Response(
                    {"detail": "Закрепление в ленте отдела доступно только для публикаций отдела."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if post.pinned_department:
                Post.objects.filter(pk=post.pk).update(pinned_department=False)
            return Response(
                {
                    "scope": "department",
                    "pinned": False,
                    "pinned_global": bool(post.pinned_global),
                    "pinned_department": False,
                }
            )

        if post.pinned_global:
            Post.objects.filter(pk=post.pk).update(pinned_global=False)
        return Response(
            {
                "scope": "global",
                "pinned": False,
                "pinned_global": False,
                "pinned_department": bool(post.pinned_department),
            }
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def like(self, request, pk=None):
        """Ставит лайк текущего пользователя (идемпотентно)."""
        post = self.get_object()
        _, created = PostLike.objects.get_or_create(
            post=post, user=request.user
        )
        if created:
            Post.objects.filter(pk=post.pk).update(
                likes_count=F("likes_count") + 1
            )
            # Отправляем уведомление автору публикации
            notify_post_reaction(post, request.user)
        post.refresh_from_db(fields=["likes_count"])
        return Response(
            {"liked": True, "likes_count": post.likes_count},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def unlike(self, request, pk=None):
        """Снимает лайк текущего пользователя (идемпотентно)."""
        post = self.get_object()
        deleted, _ = PostLike.objects.filter(
            post=post, user=request.user
        ).delete()
        if deleted:
            Post.objects.filter(pk=post.pk, likes_count__gt=0).update(
                likes_count=F("likes_count") - 1
            )
        post.refresh_from_db(fields=["likes_count"])
        return Response(
            {"liked": False, "likes_count": post.likes_count},
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def likers(self, request, pk=None):
        """Возвращает список сотрудников, поставивших лайк посту."""
        post = self.get_object()
        queryset = (
            Employee.objects.filter(post_likes__post=post)
            .order_by("-post_likes__created_at", "-id")
            .distinct()
        )

        page = self.paginate_queryset(queryset)
        objects = page if page is not None else queryset
        serializer = PostLikerSerializer(
            objects,
            many=True,
            context={"request": request},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=["get", "post"],
        permission_classes=[IsAuthenticated],
    )
    def comments(self, request, pk=None):
        """Управление комментариями к посту.

        GET: получение списка комментариев
        POST: создание комментария {"text": "..."}
        """
        from communications import comments_helpers
        from ..employees.serializers import EmployeeBriefSerializer

        post = self.get_object()

        if request.method in {"GET", "HEAD"}:
            # Получаем комментарии через unified system
            messages = comments_helpers.get_comments(post)

            # Форматируем в формат, совместимый со старым API
            comments_data = []
            for msg in messages:
                author_ser = EmployeeBriefSerializer(msg.author)
                comments_data.append(
                    {
                        "id": msg.id,
                        "post": post.id,
                        "post_id": post.id,
                        "author": author_ser.data,
                        "author_id": msg.author.id if msg.author else None,
                        "text": msg.content,
                        "created_at": msg.created_at,
                        "created_at_display": msg.created_at.strftime(
                            "%d.%m.%Y %H:%M"
                        ),
                    }
                )

            return Response(comments_data)

        # POST - создание комментария
        text = request.data.get("text", "").strip()
        if not text:
            return Response(
                {"text": ["Это поле не может быть пустым."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Создаём комментарий через unified system
        message = comments_helpers.create_comment(
            obj=post, author=request.user, content=text
        )

        # Форматируем ответ
        author_ser = EmployeeBriefSerializer(message.author)
        response_data = {
            "id": message.id,
            "post": post.id,
            "post_id": post.id,
            "author": author_ser.data,
            "author_id": message.author.id if message.author else None,
            "text": message.content,
            "created_at": message.created_at,
            "created_at_display": message.created_at.strftime("%d.%m.%Y %H:%M"),
        }

        return Response(response_data, status=status.HTTP_201_CREATED)
