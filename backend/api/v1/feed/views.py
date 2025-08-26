from __future__ import annotations

from django.db.models import Count, F
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAdminUser, IsAuthenticated
from rest_framework.response import Response

from feed.constants import TYPE_COMPANY, TYPE_DEPARTMENT, TYPE_EMPLOYEE
from feed.models import Comment, Post, PostLike

from ..permissions import (
    IsAuthorOrStaffForComments,
    user_has_dept_perm,
    user_is_dept_head,
    user_is_staffish,
)
from .serializers import CommentSerializer, PostListSerializer, PostSerializer


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
    queryset = (
        Post.objects.select_related("author", "department")
        .annotate(comments_count=Count("comments", distinct=True))
        .order_by("-pinned", "-created_at")
    )
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title", "body"]
    ordering_fields = ["created_at", "pinned", "likes_count"]
    ordering = ["-pinned", "-created_at"]

    def get_serializer_class(self):
        return PostListSerializer if self.action == "list" else PostSerializer

    def get_queryset(self):
        qs = super().get_queryset()
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

    # ---- permissions helpers
    def _can_create(self, user, t, dept):
        if not user or not user.is_authenticated:
            return False
        if t == TYPE_EMPLOYEE:
            return False
        if t == TYPE_COMPANY:
            return user_is_staffish(user) or user.has_perm("feed.publish_company_post")
        if t == TYPE_DEPARTMENT and dept:
            # В ролях сравниваем по codename без префикса app:
            return (
                user_is_staffish(user)
                or user_is_dept_head(user, dept)
                or user_has_dept_perm(user, dept, "publish_department_post")
            )
        return False

    def _can_edit(self, user, post: Post):
        if post.type == TYPE_COMPANY:
            return user_is_staffish(user) or user.has_perm("feed.publish_company_post")
        if post.type == TYPE_DEPARTMENT and post.department_id:
            return (
                user_is_staffish(user)
                or user_is_dept_head(user, post.department)
                or user_has_dept_perm(user, post.department, "publish_department_post")
            )
        return False

    # ---- hooks
    def perform_create(self, serializer):
        user = self.request.user
        t = self.request.data.get("type") or serializer.validated_data.get("type")
        dept = serializer.validated_data.get("department")
        if not self._can_create(user, t, dept):
            raise PermissionDenied("Недостаточно прав для публикации.")
        serializer.save(author=user)

    def perform_update(self, serializer):
        if not self._can_edit(self.request.user, self.get_object()):
            raise PermissionDenied("Недостаточно прав для изменения публикации.")
        serializer.save()

    def perform_destroy(self, instance):
        if not self._can_edit(self.request.user, instance):
            raise PermissionDenied("Недостаточно прав для удаления публикации.")
        return super().perform_destroy(instance)

    # ---- actions
    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def pin(self, request, pk=None):
        post = self.get_object()
        if not post.pinned:
            Post.objects.filter(pk=post.pk).update(pinned=True)
        return Response({"pinned": True})

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def unpin(self, request, pk=None):
        post = self.get_object()
        if post.pinned:
            Post.objects.filter(pk=post.pk).update(pinned=False)
        return Response({"pinned": False})

    @action(detail=True, methods=["post"])
    def like(self, request, pk=None):
        post = self.get_object()
        _, created = PostLike.objects.get_or_create(post=post, user=request.user)
        if created:
            Post.objects.filter(pk=post.pk).update(likes_count=F("likes_count") + 1)
        post.refresh_from_db(fields=["likes_count"])
        return Response({"liked": True, "likes_count": post.likes_count}, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"])
    def unlike(self, request, pk=None):
        post = self.get_object()
        deleted, _ = PostLike.objects.filter(post=post, user=request.user).delete()
        if deleted:
            Post.objects.filter(pk=post.pk, likes_count__gt=0).update(likes_count=F("likes_count") - 1)
        post.refresh_from_db(fields=["likes_count"])
        return Response({"liked": False, "likes_count": post.likes_count}, status=status.HTTP_200_OK)


class CommentViewSet(viewsets.ModelViewSet):
    """
    /api/v1/comments/
      - GET list/retrieve — аутентифицированные
      - POST create       — аутентифицированные (author = request.user)
      - PATCH/PUT/DELETE  — автор или staff/superuser
      Фильтры: ?post=<id>, ?author=<id>; сортировка created_at ASC
    """
    queryset = Comment.objects.select_related("post", "author").all()
    serializer_class = CommentSerializer
    permission_classes = [IsAuthenticated, IsAuthorOrStaffForComments]
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
