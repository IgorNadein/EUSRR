# backend/feed/models.py
from __future__ import annotations

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Q
from django.utils.deconstruct import deconstructible

from .constants import (
    TYPE_CHOICES,
    TYPE_COMPANY,
    TYPE_DEPARTMENT,
    TYPE_EMPLOYEE,
)

Employee = get_user_model()


# --- helpers: валидаторы размера файлов ---
def validate_file_size(max_mb: int):
    max_bytes = max_mb * 1024 * 1024

    def _v(f):
        if f and getattr(f, "size", 0) > max_bytes:
            raise ValidationError(f"Файл превышает {max_mb} MB.")

    return _v


IMAGE_EXTS = ["jpg", "jpeg", "png", "gif", "webp"]
FILE_EXTS = [
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "txt",
    "csv",
    "png",
    "jpg",
    "jpeg",
    "gif",
    "zip",
    "rar",
    "7z",
]


@deconstructible
class FileSizeValidator:
    def __init__(self, max_mb: int):
        self.max_mb = int(max_mb)

    def __call__(self, f):
        if f and getattr(f, "size", 0) > self.max_mb * 1024 * 1024:
            raise ValidationError(f"Файл превышает {self.max_mb} MB.")

    def __eq__(self, other):
        return (
            isinstance(other, FileSizeValidator) and self.max_mb == other.max_mb
        )


class Post(models.Model):
    author = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="posts",
        verbose_name="Автор",
    )
    department = models.ForeignKey(
        "employees.Department",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="posts",
        verbose_name="Отдел",
        help_text=(
            "Для новостей отдела укажите отдел. "
            "Для других типов оставьте пустым."
        ),
    )
    title = models.CharField("Заголовок", max_length=200)
    body = models.TextField("Текст")
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    pinned = models.BooleanField("Закреплено", default=False)
    type = models.CharField(
        "Тип публикации", max_length=20, choices=TYPE_CHOICES
    )
    image = models.ImageField(
        "Изображение",
        upload_to="feed/images/%Y/%m/",
        blank=True,
        null=True,
    )
    attachment = models.FileField(
        "Вложение",
        upload_to="feed/attachments/%Y/%m/",
        blank=True,
        null=True,
    )
    likes_count = models.PositiveIntegerField("Лайки", default=0, db_index=True)

    class Meta:
        verbose_name = "Публикация"
        verbose_name_plural = "Публикации"
        ordering = ["-pinned", "-created_at"]
        indexes = [
            models.Index(fields=["type", "created_at"]),
            models.Index(fields=["pinned", "created_at"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["department", "-created_at"]),
            models.Index(fields=["author", "-created_at"]),
        ]
        constraints = [
            models.CheckConstraint(
                name="post_department_required_when_type_is_department",
                condition=Q(type=TYPE_DEPARTMENT, department__isnull=False)
                | ~Q(type=TYPE_DEPARTMENT),
            ),
            models.CheckConstraint(
                name="post_department_null_when_type_not_department",
                condition=Q(type=TYPE_DEPARTMENT) | Q(department__isnull=True),
            ),
            models.CheckConstraint(
                name="post_likes_count_non_negative",
                condition=Q(likes_count__gte=0),
            ),
        ]

    def __str__(self):
        if self.type == TYPE_COMPANY:
            prefix = "Компания"
        elif self.type == TYPE_DEPARTMENT:
            prefix = f"Отдел: {self.department or '—'}"
        elif self.type == TYPE_EMPLOYEE:
            prefix = f"Сотрудник: {self.author}"
        else:
            prefix = "Публикация"
        return f"[{prefix}] {self.title}"

    # --- бизнес-валидация ---
    def clean(self):
        super().clean()
        if not self.type:
            self.type = TYPE_COMPANY
        has_body = bool((self.body or "").strip())
        if not (has_body or self.image or self.attachment):
            raise ValidationError(
                {"body": "Нужно указать текст, изображение или файл."}
            )

    def _delete_file(self, ffield: models.FileField):
        f = getattr(self, ffield.attname)
        if f and hasattr(f, "name"):
            storage, name = f.storage, f.name
            transaction.on_commit(lambda: storage.delete(name))

    def delete(self, *args, **kwargs):
        old_image = self.image
        old_attach = self.attachment
        super().delete(*args, **kwargs)
        if old_image:
            transaction.on_commit(
                lambda: old_image.storage.delete(old_image.name)
            )
        if old_attach:
            transaction.on_commit(
                lambda: old_attach.storage.delete(old_attach.name)
            )

    def save(self, *args, **kwargs):
        skip_validation = kwargs.pop("skip_validation", False)
        if not self.type:
            self.type = TYPE_COMPANY
        if not skip_validation:
            self.full_clean()
        old_image_name = old_attach_name = None
        if self.pk:
            try:
                old = Post.objects.only("image", "attachment").get(pk=self.pk)
                if old.image and old.image.name != (
                    self.image.name if self.image else None
                ):
                    old_image_name = old.image.name
                if old.attachment and old.attachment.name != (
                    self.attachment.name if self.attachment else None
                ):
                    old_attach_name = old.attachment.name
            except Post.DoesNotExist:
                pass

        res = super().save(*args, **kwargs)

        if old_image_name:
            transaction.on_commit(
                lambda: self.image.storage.delete(old_image_name)
            )
        if old_attach_name:
            transaction.on_commit(
                lambda: self.attachment.storage.delete(old_attach_name)
            )

        return res


class PostLike(models.Model):
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="likes",
        verbose_name="Пост",
    )
    user = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="post_likes",
        verbose_name="Пользователь",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Лайк"
        verbose_name_plural = "Лайки"
        constraints = [
            models.UniqueConstraint(
                fields=["post", "user"], name="uq_postlike_post_user"
            ),
        ]
        indexes = [
            models.Index(fields=["user", "created_at"]),
            models.Index(fields=["post", "created_at"]),
        ]

    def __str__(self):
        return f"❤ {self.user} → {self.post_id}"
