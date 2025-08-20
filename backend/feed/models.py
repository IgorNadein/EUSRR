# backend/feed/models.py
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q

from .constants import (TYPE_CHOICES, TYPE_COMPANY, TYPE_DEPARTMENT,
                        TYPE_EMPLOYEE)

Employee = get_user_model()


class Post(models.Model):
    author = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="posts",
        verbose_name="Автор",
    )
    department = models.ForeignKey(
        "employees.Department",  # строковая ссылка → без прямого импорта
        null=True,
        blank=True,
        on_delete=models.PROTECT,  # защищаем посты от удаления отдела
        related_name="posts",
        verbose_name="Отдел",
        help_text="Для новостей отдела укажите отдел. Для других типов оставьте пустым.",
    )
    title = models.CharField("Заголовок", max_length=200)
    body = models.TextField("Текст")
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    pinned = models.BooleanField("Закреплено", default=False)
    type = models.CharField("Тип публикации", max_length=20, choices=TYPE_CHOICES)
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
            models.Index(
                fields=["department", "-created_at"]
            ),  # быстрый список по отделу
            models.Index(fields=["author", "-created_at"]),  # быстрый список по автору
        ]
        constraints = [
            # Если тип = 'department' → department IS NOT NULL
            models.CheckConstraint(
                name="post_department_required_when_type_is_department",
                condition=Q(type=TYPE_DEPARTMENT, department__isnull=False)
                | ~Q(type=TYPE_DEPARTMENT),
            ),
            # Если тип != 'department' → department IS NULL (future-proof)
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


class Comment(models.Model):
    post = models.ForeignKey(
        Post,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="Публикация",
    )
    author = models.ForeignKey(
        Employee,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name="Автор",
    )
    text = models.TextField("Комментарий")
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Комментарий"
        verbose_name_plural = "Комментарии"
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f'Комментарий от {self.author} к "{self.post.title}"'


class PostLike(models.Model):
    post = models.ForeignKey(
        Post, on_delete=models.CASCADE, related_name="likes", verbose_name="Пост"
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
