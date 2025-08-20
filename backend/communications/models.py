# backend/communications/models.py
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models
from django.db.models import Q
from django.utils import timezone
from employees.models import Department, EmployeeDepartment

Employee = get_user_model()


class ChatReadState(models.Model):
    chat = models.ForeignKey(
        "Chat", on_delete=models.CASCADE, related_name="read_states"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_read_states",
    )
    last_read_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # заменяем устаревший unique_together на UniqueConstraint
        constraints = [
            models.UniqueConstraint(
                fields=["chat", "user"],
                name="uniq_chatreadstate_chat_user",
            ),
        ]
        indexes = [
            models.Index(fields=["chat", "user"]),
            models.Index(fields=["chat", "last_read_at"]),
        ]

    def __str__(self):
        return f"read:{self.user_id}@{self.chat_id} → {self.last_read_at or '-'}"


class Chat(models.Model):
    CHAT_TYPE_CHOICES = [
        ("private", "Личный"),
        ("department", "Отдел"),
        ("global", "Глобальный"),
    ]

    type = models.CharField(
        max_length=16, choices=CHAT_TYPE_CHOICES, verbose_name="Тип чата", db_index=True
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
        on_delete=models.CASCADE,  # при удалении отдела чат удалится
        verbose_name="Отдел",
        help_text="Указывается только для чатов отдела",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    is_main = models.BooleanField(default=False, verbose_name="Основной чат")

    class Meta:
        verbose_name = "Чат"
        verbose_name_plural = "Чаты"
        constraints = [
            # Ровно один «главный» глобальный чат
            models.UniqueConstraint(
                fields=["type"],
                condition=Q(is_main=True, type="global"),
                name="unique_main_global_chat",
            ),
            # Ровно один «главный» чат на отдел
            models.UniqueConstraint(
                fields=["type", "department"],
                condition=Q(is_main=True, type="department"),
                name="unique_main_department_chat",
            ),
        ]
        indexes = [
            models.Index(fields=["type", "is_main"]),
            models.Index(fields=["department"]),
            models.Index(fields=["created_at"]),
        ]

    def clean(self):
        super().clean()
        # Доп. валидация только для глобального «главного»
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

    def mark_read(self, user):
        """
        Помечает чат прочитанным «до последнего сообщения».
        Сделано без update_or_create — устойчиво для SQLite.
        """
        last = self.messages.order_by("-created_at").only("created_at").first()
        ts = last.created_at if last else timezone.now()
        # обновим, только если новое время больше
        updated = ChatReadState.objects.filter(
            chat=self, user=user, last_read_at__lt=ts
        ).update(last_read_at=ts)
        if not updated:
            try:
                ChatReadState.objects.create(chat=self, user=user, last_read_at=ts)
            except IntegrityError:
                # гонка: запись уже есть — попробуем ещё раз обновить
                ChatReadState.objects.filter(
                    chat=self, user=user, last_read_at__lt=ts
                ).update(last_read_at=ts)

    def unread_count_for(self, user):
        """
        Количество непрочитанных (кроме своих).
        """
        rs = (
            ChatReadState.objects.filter(chat=self, user=user)
            .only("last_read_at")
            .first()
        )
        qs = self.messages.exclude(author=user)
        if rs and rs.last_read_at:
            qs = qs.filter(created_at__gt=rs.last_read_at)
        return qs.count()

    @property
    def get_participants(self):
        """
        Возвращает QuerySet участников чата (по типу).
        Для отдела берём активные связи + руководителя.
        """
        if self.type == "private":
            return self.participants.all()
        if self.type == "department" and self.department_id:
            employee_ids = EmployeeDepartment.objects.filter(
                department_id=self.department_id, is_active=True
            ).values_list("employee_id", flat=True)
            return Employee.objects.filter(
                Q(id__in=employee_ids) | Q(id=self.department.head_id)
            ).distinct()
        if self.type == "global":
            return Employee.objects.filter(is_active=True)
        return Employee.objects.none()

    def __str__(self):
        if self.type == "private":
            # лениво формируем подпись, без лишних запросов
            parts = list(self.participants.values_list("first_name", "last_name")[:3])
            names = ", ".join(f"{ln} {fn}".strip() for fn, ln in parts) or "—"
            more = self.participants.count() - len(parts)
            if more > 0:
                names += f" и ещё {more}"
            return f"Личный чат: {names}"
        if self.type == "department":
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
    created_at = models.DateTimeField(
        auto_now_add=True, verbose_name="Время отправки", db_index=True
    )

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"

    def __str__(self):
        return f"{self.author}: {self.content[:30]}"
