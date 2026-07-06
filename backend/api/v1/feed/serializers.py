# backend/api/v1/feed/serializers.py
from __future__ import annotations

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from feed.constants import TYPE_DEPARTMENT, TYPE_EMPLOYEE
from feed.models import Post, PostLike
from ..utils import build_media_url

Employee = get_user_model()


def _linked_task_payloads(post: Post, user) -> list[dict]:
    if not user or not getattr(user, "is_authenticated", False):
        return []

    try:
        from tasks.access import task_board_access_q
        from tasks.models import (
            TaskBoard,
            TaskLinkedObject,
            TaskLinkedObjectKind,
        )
    except Exception:
        return []

    content_type = ContentType.objects.get_for_model(Post)
    accessible_boards = TaskBoard.objects.filter(
        is_archived=False,
    ).filter(task_board_access_q(user))

    links = (
        TaskLinkedObject.objects.filter(
            kind=TaskLinkedObjectKind.POST,
            content_type=content_type,
            object_id=post.id,
            task__board__in=accessible_boards,
        )
        .select_related("task", "task__board", "task__column")
        .order_by("task__title", "task_id")
    )

    return [
        {
            "link_id": link.id,
            "id": link.task_id,
            "title": link.task.title,
            "board_id": link.task.board_id,
            "board_name": link.task.board.name,
            "column_id": link.task.column_id,
            "column_name": link.task.column.name,
            "column_color": link.task.column.color,
            "priority": link.task.priority,
            "priority_display": link.task.get_priority_display(),
        }
        for link in links
    ]


class AuthorMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = ["id", "first_name", "last_name", "full_name", "avatar"]

    @extend_schema_field(serializers.CharField())
    def get_full_name(self, obj):
        fn = (obj.first_name or "").strip()
        ln = (obj.last_name or "").strip()
        nm = f"{fn} {ln}".strip()
        return nm

    @extend_schema_field(OpenApiTypes.URI)
    def get_avatar(self, obj):
        """Возвращает полный URL для аватара"""
        request = self.context.get("request")
        return build_media_url(obj.avatar, request)


class PostLikerSerializer(AuthorMiniSerializer):
    class Meta(AuthorMiniSerializer.Meta):
        fields = ["id", "first_name", "last_name", "full_name", "avatar"]


class PostListSerializer(serializers.ModelSerializer):
    author_id = serializers.IntegerField(read_only=True)
    author = AuthorMiniSerializer(read_only=True)
    department_name = serializers.CharField(
        source="department.name",
        read_only=True,
        allow_null=True,
    )

    # удoбные представления дат
    created_at_display = serializers.DateTimeField(
        source="created_at", format="%d.%m.%Y %H:%M", read_only=True
    )

    pinned = serializers.SerializerMethodField()
    pinned_global = serializers.BooleanField(read_only=True, default=False)
    pinned_department = serializers.BooleanField(read_only=True, default=False)
    # ожидания фронта
    is_liked = serializers.BooleanField(read_only=True, default=False)
    comments_count = serializers.IntegerField(
        read_only=True, default=0, allow_null=True
    )
    # для ссылок на отдел
    department_id = serializers.IntegerField(read_only=True)

    # Переопределяем поля для полных URL
    image = serializers.SerializerMethodField()
    attachment = serializers.SerializerMethodField()
    linked_tasks = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "type",
            "department",
            "department_id",
            "department_name",
            "title",
            "body",
            "image",
            "attachment",
            "created_at",
            "created_at_display",
            "pinned",
            "pinned_global",
            "pinned_department",
            "likes_count",
            "comments_count",
            "author_id",
            "author",
            "is_liked",
            "linked_tasks",
        ]
        read_only_fields = (
            "created_at",
            "created_at_display",
            "pinned",
            "pinned_global",
            "pinned_department",
            "likes_count",
            "comments_count",
            "author_id",
            "author",
            "department_id",
            "department_name",
            "is_liked",
            "linked_tasks",
        )

    @extend_schema_field(OpenApiTypes.URI)
    def get_image(self, obj):
        """Возвращает полный URL для изображения"""
        request = self.context.get("request")
        return build_media_url(obj.image, request)

    @extend_schema_field(OpenApiTypes.URI)
    def get_attachment(self, obj):
        """Возвращает полный URL для вложения"""
        request = self.context.get("request")
        return build_media_url(obj.attachment, request)

    @extend_schema_field(serializers.BooleanField())
    def get_pinned(self, obj):
        scope = self.context.get("pin_scope") or "global"
        if scope == "department":
            return bool(getattr(obj, "pinned_department", False))
        return bool(getattr(obj, "pinned_global", False))

    def get_linked_tasks(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return _linked_task_payloads(obj, user)


class PostSerializer(PostListSerializer):
    """Сериализатор для деталей поста"""

    body = serializers.CharField(required=False, allow_blank=True)
    image = serializers.ImageField(required=False, allow_null=True, write_only=True)
    attachment = serializers.FileField(required=False, allow_null=True, write_only=True)
    user_has_liked = serializers.SerializerMethodField()

    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + ["user_has_liked"]

    @extend_schema_field(serializers.BooleanField())
    def get_user_has_liked(self, obj):
        """Проверяет, лайкнул ли текущий пользователь этот пост"""
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            return PostLike.objects.filter(post=obj, user=request.user).exists()
        return False

    def to_representation(self, instance):
        data = super().to_representation(instance)
        request = self.context.get("request")
        data["image"] = build_media_url(instance.image, request)
        data["attachment"] = build_media_url(instance.attachment, request)
        return data

    def validate(self, attrs):
        # значения с учётом partial
        t = attrs.get("type", getattr(self.instance, "type", None))
        dept = attrs.get(
            "department", getattr(self.instance, "department", None)
        )

        # личные посты запрещены
        if t == TYPE_EMPLOYEE:
            raise serializers.ValidationError(
                {"type": "Публикация на личной странице запрещена."}
            )

        # связка type/department
        if t == TYPE_DEPARTMENT and not dept:
            raise serializers.ValidationError(
                {"department": "Нужно указать отдел для новостей отдела."}
            )
        if t != TYPE_DEPARTMENT and dept is not None:
            raise serializers.ValidationError(
                {
                    "department": (
                        "Для этого типа публикаций отдел "
                        "указывать нельзя."
                    )
                }
            )
        return attrs
