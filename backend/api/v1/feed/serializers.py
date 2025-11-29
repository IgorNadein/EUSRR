# backend/api/v1/feed/serializers.py
from __future__ import annotations

from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model
from rest_framework import serializers

from feed.constants import TYPE_COMPANY, TYPE_DEPARTMENT, TYPE_EMPLOYEE
from feed.models import Comment, Post, PostLike
from ..serializers import Base64ImageField

Employee = get_user_model()


class AuthorMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    avatar = Base64ImageField(read_only=True)

    class Meta:
        model = Employee
        fields = ["id", "first_name", "last_name", "full_name", "avatar"]

    def get_full_name(self, obj):
        fn = (obj.first_name or "").strip()
        ln = (obj.last_name or "").strip()
        nm = f"{fn} {ln}".strip()
        return nm


class CommentMiniSerializer(serializers.ModelSerializer):
    author = AuthorMiniSerializer(read_only=True)
    created_at_display = serializers.DateTimeField(
        source="created_at", format="%d.%m.%Y %H:%M", read_only=True
    )

    class Meta:
        model = Comment
        fields = ["id", "text", "created_at", "created_at_display", "author"]


class PostListSerializer(serializers.ModelSerializer):
    author_id = serializers.IntegerField(read_only=True)
    author = AuthorMiniSerializer(read_only=True)

    # удoбные представления дат
    created_at_display = serializers.DateTimeField(
        source="created_at", format="%d.%m.%Y %H:%M", read_only=True
    )

    # ожидания фронта
    is_liked = serializers.BooleanField(read_only=True, default=False)
    comments_count = serializers.IntegerField(read_only=True, default=0)
    # для ссылок на отдел
    department_id = serializers.IntegerField(read_only=True)
    last_comment = serializers.SerializerMethodField()

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
            "last_comment",
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

    def get_last_comment(self, obj):
        # Берём готовую мапу из контекста, собранную во viewset.list()
        lc_map = self.context.get("last_comments_map") or {}
        lc = None
        lc_id = getattr(obj, "last_comment_id", None)
        if lc_id:
            lc = lc_map.get(lc_id)
        if not lc:
            return None
        return CommentMiniSerializer(lc, context=self.context).data


class PostSerializer(PostListSerializer):
    """Сериализатор для деталей поста с комментариями"""
    comments = serializers.SerializerMethodField()
    user_has_liked = serializers.SerializerMethodField()

    class Meta(PostListSerializer.Meta):
        fields = PostListSerializer.Meta.fields + [
            "comments",
            "user_has_liked"
        ]

    def get_comments(self, obj):
        """Возвращает список комментариев к посту"""
        comments = obj.comments.select_related("author").order_by(
            "created_at"
        )
        return CommentSerializer(
            comments, many=True, context=self.context
        ).data

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


class CommentSerializer(serializers.ModelSerializer):
    post_id = serializers.IntegerField(read_only=True)
    author_id = serializers.IntegerField(read_only=True)
    author = AuthorMiniSerializer(read_only=True)
    image = serializers.FileField(allow_null=True, required=False)
    attachment = serializers.FileField(allow_null=True, required=False)
    created_at_display = serializers.DateTimeField(
        source="created_at", format="%d.%m.%Y %H:%M", read_only=True
    )
    is_post_author = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "post",
            "post_id",
            "author_id",
            "author",
            "text",
            "image",
            "attachment",
            "created_at",
            "created_at_display",
            "is_post_author",
        ]
        extra_kwargs = {
            "post": {"write_only": True},
            "text": {"required": False, "allow_blank": True},
        }

    def get_is_post_author(self, obj):
        """Проверяет, является ли автор комментария автором поста"""
        if not obj.author or not obj.post or not obj.post.author:
            return False
        return obj.author.id == obj.post.author.id

    def validate(self, attrs):
        text = (attrs.get("text") or "").strip()
        if not (text or attrs.get("image") or attrs.get("attachment")):
            raise serializers.ValidationError(
                {"text": "Нужно указать текст, изображение или файл."}
            )
        return attrs

    def create(self, validated_data):
        # author выставляется во view
        instance = Comment(**validated_data)
        instance.save(skip_validation=True)
        return instance

    def update(self, instance, validated_data):
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save(skip_validation=True)
        return instance
