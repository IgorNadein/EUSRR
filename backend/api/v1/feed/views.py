from __future__ import annotations

from typing import Any, List

from django.contrib.auth import get_user_model
from django.db.models import BooleanField, Count, Exists, F, OuterRef, Subquery, Value
from employees.constants import DeptPerm
from feed.constants import TYPE_COMPANY, TYPE_DEPARTMENT, TYPE_EMPLOYEE
from feed.models import Comment, Post, PostLike
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from ..permissions import (
    AdminOrActionOrModelPerms,
    AdminOrDeptAllowed,
    IsSelfOrStaff,
    user_has_dept_perm,
    user_is_dept_head,
    user_is_staffish,
)
from .serializers import CommentSerializer, PostListSerializer, PostSerializer

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
          * type=company    → AdminOrActionOrModelPerms + required_perm_code="feed.publish_company_post"
          * type=department → AdminOrDeptAllowed с кодом DeptPerm.CREATE_POST|publish_department_post
      - update/partial_update/destroy:
          * company         → как для company-create
          * department      → как для department-create
      - pin/unpin — только staff/superuser
    """

    queryset = (
        Post.objects.select_related("author", "department")
        .annotate(comments_count=Count("comments", distinct=True))
        .order_by("-pinned", "-created_at")
    )
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "body"]
    ordering_fields = ["created_at", "pinned", "likes_count"]
    ordering = ["-pinned", "-created_at"]

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
        """Возвращает DRF-пермишены под текущий action (без вызова get_object())."""
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
            dept_code = getattr(DeptPerm, "CREATE_POST", "publish_department_post")
            perm = self.PostDeptPerm()
            perm.required_code = DeptPerm.CREATE_POST
            return [IsAuthenticated(), perm]

        # --- UPDATE/PATCH/DELETE: определяем тип поста из БД, но без get_object() ---
        if self.action in {"update", "partial_update", "destroy"}:
            lookup = getattr(self, "lookup_url_kwarg", None) or getattr(
                self, "lookup_field", "pk"
            )
            pk = self.kwargs.get(lookup)
            info = (
                Post.objects.filter(pk=pk).values("type", "department_id").first() or {}
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

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user

        if user.is_authenticated:
            qs = qs.annotate(
                is_liked=Exists(PostLike.objects.filter(post=OuterRef("pk"), user=user))
            )
        else:
            qs = qs.annotate(is_liked=Value(False, output_field=BooleanField()))

        # последний комментарий (id) — без N+1
        lc = Comment.objects.filter(post_id=OuterRef("pk")).order_by("-created_at")
        qs = qs.annotate(last_comment_id=Subquery(lc.values("id")[:1]))

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
        pinned = qp.get("pinned")
        if pinned in ("true", "1"):
            qs = qs.filter(pinned=True)
        elif pinned in ("false", "0"):
            qs = qs.filter(pinned=False)

        return qs

    def list(self, request, *args, **kwargs):
        """Возвращает список постов с картой последних комментариев без N+1."""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        objects = page if page is not None else queryset

        ids = [getattr(o, "last_comment_id", None) for o in objects]
        ids = [i for i in ids if i]
        last_comments_map = {}
        if ids:
            last_comments_map = Comment.objects.select_related("author").in_bulk(ids)

        serializer = self.get_serializer(
            objects,
            many=True,
            context={
                **self.get_serializer_context(),
                "last_comments_map": last_comments_map,
            },
        )
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
        if not post.pinned:
            Post.objects.filter(pk=post.pk).update(pinned=True)
        return Response({"pinned": True})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def unpin(self, request, pk=None):
        """Снимает пин (только staff/superuser)."""
        post = self.get_object()
        if post.pinned:
            Post.objects.filter(pk=post.pk).update(pinned=False)
        return Response({"pinned": False})

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def like(self, request, pk=None):
        """Ставит лайк текущего пользователя (идемпотентно)."""
        post = self.get_object()
        _, created = PostLike.objects.get_or_create(post=post, user=request.user)
        if created:
            Post.objects.filter(pk=post.pk).update(likes_count=F("likes_count") + 1)
        post.refresh_from_db(fields=["likes_count"])
        return Response(
            {"liked": True, "likes_count": post.likes_count}, status=status.HTTP_200_OK
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAuthenticated])
    def unlike(self, request, pk=None):
        """Снимает лайк текущего пользователя (идемпотентно)."""
        post = self.get_object()
        deleted, _ = PostLike.objects.filter(post=post, user=request.user).delete()
        if deleted:
            Post.objects.filter(pk=post.pk, likes_count__gt=0).update(
                likes_count=F("likes_count") - 1
            )
        post.refresh_from_db(fields=["likes_count"])
        return Response(
            {"liked": False, "likes_count": post.likes_count},
            status=status.HTTP_200_OK,
        )


class CommentViewSet(viewsets.ModelViewSet):
    """
    /api/v1/comments/
      - GET: аутентифицированные
      - POST: аутентифицированные (author = request.user)
      - PATCH/PUT/DELETE: автор или staff/superuser
      Фильтры: ?post=<id>, ?author=<id>
      Сортировка: created_at ASC
    """

    queryset = Comment.objects.select_related("post", "author").all()
    serializer_class = CommentSerializer
    owner_id_attrs = ("author_id",)
    owner_obj_attrs = ("author",)
    permission_classes = [IsAuthenticated, (IsSelfOrStaff | AdminOrActionOrModelPerms)]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["created_at", "id"]
    ordering = ["created_at"]

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)

    def get_queryset(self):
        qs = super().get_queryset()
        qp = self.request.query_params

        pid = _to_id(qp.get("post"))
        if pid is not None:
            qs = qs.filter(post_id=pid)

        aid = _to_id(qp.get("author"))
        if aid is not None:
            qs = qs.filter(author_id=aid)

        return qs
