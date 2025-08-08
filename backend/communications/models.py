# backend\communications\models.py
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from employees.models import Department, EmployeeDepartment
from django.contrib.auth import get_user_model

Employee = get_user_model()


class Chat(models.Model):
    CHAT_TYPE_CHOICES = [
        ("private", "Личный"),
        ("department", "Отдел"),
        ("global", "Глобальный"),
    ]

    type = models.CharField(
        max_length=16, choices=CHAT_TYPE_CHOICES, verbose_name="Тип чата"
    )
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="chats",
        verbose_name="Участники",
        help_text="Используется только для личных чатов",
    )
    department = models.ForeignKey(
        Department,
        null=True,
        blank=True,
        on_delete=models.CASCADE,  # 🔹 теперь при удалении отдела чат удалится
        verbose_name="Отдел",
        help_text="Указывается только для чатов отдела",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    is_main = models.BooleanField(default=False, verbose_name="Основной чат")

    class Meta:
        verbose_name = "Чат"
        verbose_name_plural = "Чаты"
        constraints = [
            models.UniqueConstraint(
                fields=["type"],
                condition=models.Q(is_main=True, type="global"),
                name="unique_main_global_chat",
            ),
            models.UniqueConstraint(
                fields=["type", "department"],
                condition=models.Q(is_main=True, type="department"),
                name="unique_main_department_chat",
            ),
        ]

    def clean(self):
        super().clean()
        # Проверка только для глобального чата
        if self.is_main and self.type == "global":
            exists = (
                Chat.objects.exclude(pk=self.pk)
                .filter(type="global", is_main=True)
                .exists()
            )
            if exists:
                raise ValidationError("Основной глобальный чат уже существует.")

    def delete(self, *args, **kwargs):
        # Запрещаем удалять только глобальный основной чат
        if self.is_main and self.type == "global":
            raise ValidationError("Основной глобальный чат компании нельзя удалить!")
        return super().delete(*args, **kwargs)

    @property
    def get_participants(self):
        """Возвращает QuerySet участников чата"""
        if self.type == "private":
            return self.participants.all()
        elif self.type == "department" and self.department_id:
            employee_ids = EmployeeDepartment.objects.filter(
                department_id=self.department_id, is_active=True
            ).values_list("employee_id", flat=True)
            return Employee.objects.filter(
                models.Q(id__in=employee_ids) | models.Q(id=self.department.head_id)
            ).distinct()
        elif self.type == "global":
            return Employee.objects.filter(is_active=True)
        return Employee.objects.none()

    def __str__(self):
        if self.type == "private":
            return f"Личный чат: {', '.join(str(p) for p in self.participants.all())}"
        elif self.type == "department":
            return f"Чат отдела: {self.department or '—'}"
        return "Глобальный чат"


class Message(models.Model):
    chat = models.ForeignKey(
        Chat, related_name="messages", on_delete=models.CASCADE, verbose_name="Чат"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, verbose_name="Автор"
    )
    content = models.TextField("Текст сообщения")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Время отправки")

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"

    def __str__(self):
        return f"{self.author}: {self.content[:30]}"
