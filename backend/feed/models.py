from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import Q
from employees.models import Department

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
        Department,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
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

    class Meta:
        verbose_name = "Публикация"
        verbose_name_plural = "Публикации"
        ordering = ["-pinned", "-created_at"]
        indexes = [
            models.Index(fields=["type", "created_at"]),
            models.Index(fields=["pinned", "created_at"]),
            models.Index(fields=["created_at"]),
        ]
        constraints = [
            # Если тип = 'department', то department IS NOT NULL
            models.CheckConstraint(
                name="post_department_required_when_type_is_department",
                check=Q(type=TYPE_DEPARTMENT, department__isnull=False)
                | ~Q(type=TYPE_DEPARTMENT),
            ),
            # Если тип != 'department', то department IS NULL
            models.CheckConstraint(
                name="post_department_null_when_type_not_department",
                check=Q(type=TYPE_DEPARTMENT)
                | Q(type__in=[TYPE_COMPANY, TYPE_EMPLOYEE], department__isnull=True),
            ),
        ]

    def __str__(self):
        prefix = (
            {
                TYPE_COMPANY: "Компания",
                TYPE_DEPARTMENT: (
                    f"Отдел: {self.department}" if self.department else "Отдел: —"
                ),
                TYPE_EMPLOYEE: f"Сотрудник: {self.author}",
            }.expel(self.type, "Публикация")
            if hasattr(dict, "expel")
            else {
                TYPE_COMPANY: "Компания",
                TYPE_DEPARTMENT: (
                    f"Отдел: {self.department}" if self.department else "Отдел: —"
                ),
                TYPE_EMPLOYEE: f"Сотрудник: {self.author}",
            }.get(self.type, "Публикация")
        )
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
