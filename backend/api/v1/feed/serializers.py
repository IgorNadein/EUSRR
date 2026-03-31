# backend/api/v1/feed/serializers.py
from __future__ import annotations

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from django.contrib.auth import get_user_model
from rest_framework import serializers

from feed.constants import TYPE_DEPARTMENT, TYPE_EMPLOYEE
from feed.models import Post, PostLike
from ..utils import build_media_url

Employee = get_user_model()


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
        request = self.context.get('request')
        return build_media_url(obj.avatar, request)


class PostListSerializer(serializers.ModelSerializer):
    author_id = serializers.IntegerField(read_only=True)
    author = AuthorMiniSerializer(read_only=True)

    # удoбные представления дат
    created_at_display = serializers.DateTimeField(
        source="created_at", format="%d.%m.%Y %H:%M", read_only=True
    )

    # ожидания фронта
    is_liked = serializers.BooleanField(read_only=True, default=False)
    comments_count = serializers.IntegerField(
        read_only=True, default=0, allow_null=True)
    # для ссылок на отдел
    department_id = serializers.IntegerField(read_only=True)

    # Переопределяем поля для полных URL
    image = serializers.SerializerMethodField()
    attachment = serializers.SerializerMethodField()

    class Meta:
        model = Post
        fields = [
            "id",
            "type",
            "department",
            "department_id",
            "title",
            "body",
            "image",
            "attachment",
            "created_at",
            "created_at_display",
            "pinned",
            "likes_count",
            "comments_count",
            "author_id",
            "author",
            "is_liked",
        ]
        read_only_fields = (
            "created_at",
            "created_at_display",
            "pinned",
            "likes_count",
            "comments_count",
            "author_id",
            "author",
            "department_id",
            "is_liked",
        )

    @extend_schema_field(OpenApiTypes.URI)
    def get_image(self, obj):
        """Возвращает полный URL для изображения"""
        request = self.context.get('request')
        return build_media_url(obj.image, request)

    @extend_schema_field(OpenApiTypes.URI)
    def get_attachment(self, obj):
        """Возвращает полный URL для вложения"""
        request = self.context.get('request')
        return build_media_url(obj.attachment, request)


class PostSerializer(PostListSerializer):
    """Сериализатор для деталей поста"""
    user_has_liked = serializers.SerializerMethodField()

    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + [
            "user_has_liked"
        ]

    @extend_schema_field(serializers.BooleanField())
    def get_user_has_liked(self, obj):
        """Проверяет, лайкнул ли текущий пользователь этот пост"""
        request = self.context.get("request")
        if request and request.user and request.user.is_authenticated:
            return PostLike.objects.filter(
                post=obj, user=request.user
            ).exists()
        return False

    def validate(self, attrs):
        # значения с учётом partial
        t = attrs.get("type", getattr(self.instance, "type", None))
        dept = attrs.get("department", getattr(self.instance, "department", None))

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
                {"department": "Для этого типа публикаций отдел указывать нельзя."}
            )
        return attrs
