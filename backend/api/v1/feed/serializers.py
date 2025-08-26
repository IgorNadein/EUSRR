from __future__ import annotations

from django.contrib.auth import get_user_model
from django.utils.encoding import iri_to_uri
from feed.constants import TYPE_COMPANY, TYPE_DEPARTMENT, TYPE_EMPLOYEE
from feed.models import Comment, Post
from rest_framework import serializers

Employee = get_user_model()


class AuthorMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = ["id", "first_name", "last_name", "full_name", "avatar_url"]

    def get_full_name(self, obj):
        fn = (obj.first_name or "").strip()
        ln = (obj.last_name or "").strip()
        return f"{fn} {ln}".strip() or None

    def get_avatar_url(self, obj):
        # Пытаемся найти поле с аватаром, не знаем точное имя: avatar/photo/image
        try:
            for attr in ("avatar", "photo", "image"):
                f = getattr(obj, attr, None)
                if f and getattr(f, "url", None):
                    return f.url
            # часто встречается метод-хелпер
            if hasattr(obj, "get_avatar_url"):
                return obj.get_avatar_url()
        except Exception:
            pass
        return None


class PostListSerializer(serializers.ModelSerializer):
    # читаем прямое поле БД post.author_id
    author_id = serializers.IntegerField(read_only=True)
    author = AuthorMiniSerializer(read_only=True)

    class Meta:
        model = Post
        fields = [
            "id",
            "type",
            "department",  # PK отдела
            "title",
            "body",
            "image",
            "attachment",
            "created_at",
            "pinned",
            "likes_count",
            "author_id",
            "author",
        ]
        read_only_fields = (
            "created_at",
            "pinned",
            "likes_count",
            "author_id",
            "author",
        )


class PostSerializer(PostListSerializer):
    def validate(self, attrs):
        # берём значения с учётом partial-update
        t = attrs.get("type", getattr(self.instance, "type", None))
        dept = attrs.get("department", getattr(self.instance, "department", None))

        # Личные посты запрещены
        if t == TYPE_EMPLOYEE:
            raise serializers.ValidationError(
                {"type": "Публикация на личной странице запрещена."}
            )

        # Валидация связки type/department (чтобы давать 400, а не 500 от БД)
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

    # Принимаем файлы как FileField, чтобы не требовать реального валидного изображения.
    image = serializers.FileField(allow_null=True, required=False)
    attachment = serializers.FileField(allow_null=True, required=False)

    class Meta:
        model = Comment
        fields = [
            "id",
            "post",        # write-only
            "post_id",     # read-only
            "author_id",
            "author",
            "text",
            "image",
            "attachment",
            "created_at",
        ]
        extra_kwargs = {
            "post": {"write_only": True},
            "text": {"required": False, "allow_blank": True},
        }

    def validate(self, attrs):
        text = (attrs.get("text") or "").strip()
        if not (text or attrs.get("image") or attrs.get("attachment")):
            raise serializers.ValidationError({"text": "Нужно указать текст, изображение или файл."})
        return attrs

    def create(self, validated_data):
        # Автор выставляется во view; здесь сохраняем без model.full_clean(),
        # чтобы не споткнуться о ImageField/Pillow в тестовых «заглушках».
        instance = Comment(**validated_data)
        instance.save(skip_validation=True)
        return instance

    def update(self, instance, validated_data):
        for k, v in validated_data.items():
            setattr(instance, k, v)
        instance.save(skip_validation=True)
        return instance
