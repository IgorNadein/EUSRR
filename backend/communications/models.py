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
    
    # НОВЫЕ ПОЛЯ для расширенной функциональности
    
    # Последнее прочитанное сообщение (явная связь)
    last_read_message = models.ForeignKey(
        'Message',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name="Последнее прочитанное сообщение"
    )
    
    # Упоминания
    unread_mentions_count = models.IntegerField(
        default=0,
        verbose_name="Непрочитанных упоминаний"
    )
    
    # Треды
    unread_thread_replies_count = models.IntegerField(
        default=0,
        verbose_name="Непрочитанных ответов в тредах"
    )
    
    # Статус набора текста
    is_typing = models.BooleanField(
        default=False,
        verbose_name="Набирает сообщение"
    )
    typing_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Последнее обновление статуса набора"
    )

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
            models.Index(fields=["chat", "user", "is_typing"]),
        ]

    def __str__(self):
        return f"read:{self.user_id}@{self.chat_id} → {self.last_read_at or '-'}"


class Chat(models.Model):
    CHAT_TYPE_CHOICES = [
        ("private", "Личный"),
        ("group", "Групповой"),
        ("department", "Отдел"),
        ("channel", "Канал"),
        ("announcement", "Объявления"),
        ("global", "Глобальный"),
    ]

    type = models.CharField(
        max_length=16,
        choices=CHAT_TYPE_CHOICES,
        verbose_name="Тип чата",
        db_index=True
    )
    
    # Новые базовые поля
    name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Название чата",
        help_text="Для групповых/канальных чатов"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Описание чата"
    )
    avatar = models.ImageField(
        upload_to='chat_avatars/%Y/%m/',
        null=True,
        blank=True,
        verbose_name="Аватар чата"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_chats',
        verbose_name="Создатель"
    )
    
    # Для гибкой настройки участников
    include_all_employees = models.BooleanField(
        default=False,
        verbose_name="Включить всех сотрудников",
        help_text="Для анонсов и общих чатов"
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
    
    # Новые поля для announcement и channel
    is_blocked = models.BooleanField(
        default=False,
        verbose_name="Заблокирован",
        help_text="Для announcement: заблокирован администратором, скрыт у всех"
    )
    blocked_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата блокировки"
    )
    blocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='blocked_chats',
        verbose_name="Кто заблокировал"
    )
    can_reply = models.BooleanField(
        default=True,
        verbose_name="Можно отвечать",
        help_text="False для announcement (только реакции)"
    )

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
            # Только 1 announcement на сотрудника
            models.UniqueConstraint(
                fields=["type", "created_by"],
                condition=Q(type="announcement"),
                name="unique_announcement_per_user",
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
        if self.type in ["announcement", "channel"]:
            # Если include_all_employees - все активные сотрудники
            if self.include_all_employees:
                return Employee.objects.filter(is_active=True)
            # Иначе только явно добавленные через participants или ChatMembership
            from .models import ChatMembership
            membership_ids = ChatMembership.objects.filter(
                chat=self
            ).values_list("user_id", flat=True)
            return Employee.objects.filter(
                Q(id__in=self.participants.values_list('id', flat=True)) |
                Q(id__in=membership_ids)
            ).distinct()
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
        if self.type == "group":
            return self.name or "Групповой чат"
        if self.type == "department":
            return f"Чат отдела: {self.department or '—'}"
        if self.type == "channel":
            return self.name or "Канал"
        if self.type == "announcement":
            return self.name or "Объявления"
        return "Глобальный чат"


class ChatUserSettings(models.Model):
    """Персональные настройки пользователя для чата"""
    chat = models.ForeignKey(
        Chat,
        on_delete=models.CASCADE,
        related_name='user_settings'
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_settings'
    )
    
    # Закрепление
    is_pinned = models.BooleanField(default=False, verbose_name="Закреплен")
    pinned_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Время закрепления"
    )
    pin_order = models.IntegerField(default=0, verbose_name="Порядок")
    
    # Уведомления
    notifications_enabled = models.BooleanField(
        default=True,
        verbose_name="Уведомления"
    )
    
    # Кастомное название
    custom_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Свое название"
    )
    
    # Скрыть чат
    is_hidden = models.BooleanField(default=False, verbose_name="Скрыт")
    
    class Meta:
        verbose_name = "Настройки чата"
        verbose_name_plural = "Настройки чатов"
        unique_together = [('chat', 'user')]
        ordering = ['-is_pinned', '-pinned_at']
        indexes = [
            models.Index(fields=['user', 'is_pinned']),
            models.Index(fields=['chat', 'user']),
        ]
    
    def __str__(self):
        return f"{self.user} → {self.chat}"


class Message(models.Model):
    chat = models.ForeignKey(
        Chat,
        related_name="messages",
        on_delete=models.CASCADE,
        verbose_name="Чат"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Автор"
    )
    content = models.TextField("Текст сообщения")
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Время отправки",
        db_index=True
    )
    
    # НОВЫЕ ПОЛЯ
    
    # Ответ на сообщение (упрощенная связь)
    reply_to = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='direct_replies',
        help_text="Простая связь для быстрого доступа"
    )
    
    # Редактирование
    is_edited = models.BooleanField(default=False)
    edited_at = models.DateTimeField(null=True, blank=True)
    edit_history = models.JSONField(
        default=list,
        blank=True,
        help_text="История редактирования [{timestamp, old_content}, ...]"
    )
    
    # Удаление
    is_deleted = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text="Кто удалил (может отличаться от автора)"
    )
    
    # Вложения
    has_attachments = models.BooleanField(default=False)
    
    # Системные сообщения
    is_system = models.BooleanField(default=False)
    system_type = models.CharField(max_length=50, blank=True)
    system_metadata = models.JSONField(
        default=dict,
        blank=True,
        help_text="Дополнительные данные для системных сообщений"
    )
    
    # Важные/закрепленные
    is_pinned = models.BooleanField(default=False)
    pinned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+'
    )
    pinned_at = models.DateTimeField(null=True, blank=True)
    
    # Реакции
    reactions = models.JSONField(
        default=dict,
        blank=True,
        help_text="Формат: {'👍': [user_id1, user_id2], '❤️': [user_id3]}"
    )
    
    # Флаги для специальных типов сообщений
    is_forwarded = models.BooleanField(default=False)
    is_cross_chat = models.BooleanField(
        default=False,
        help_text="Сообщение отправлено не участником чата"
    )
    
    # Треды
    thread_root = models.ForeignKey(
        'self',
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='thread_messages',
        help_text="Корневое сообщение треда"
    )
    thread_reply_count = models.IntegerField(default=0)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Сообщение"
        verbose_name_plural = "Сообщения"
        indexes = [
            models.Index(fields=['chat', 'created_at']),
            models.Index(fields=['chat', 'is_deleted', 'created_at']),
            models.Index(fields=['author', 'created_at']),
            models.Index(fields=['thread_root', 'created_at']),
            models.Index(fields=['is_pinned', 'chat']),
        ]

    def __str__(self):
        return f"{self.author}: {self.content[:30]}"


class MessageAttachment(models.Model):
    """Вложения в сообщениях"""
    
    FILE_TYPE_CHOICES = [
        ('image', 'Изображение'),
        ('video', 'Видео'),
        ('audio', 'Аудио'),
        ('file', 'Файл'),
    ]
    
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='attachments',
        verbose_name="Сообщение"
    )
    file = models.FileField(
        upload_to='chat_attachments/%Y/%m/%d/',
        verbose_name="Файл"
    )
    file_type = models.CharField(
        max_length=10,
        choices=FILE_TYPE_CHOICES,
        verbose_name="Тип файла"
    )
    file_name = models.CharField(
        max_length=255,
        verbose_name="Название файла"
    )
    file_size = models.BigIntegerField(
        verbose_name="Размер файла (байты)"
    )
    mime_type = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="MIME тип"
    )
    uploaded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Время загрузки"
    )
    thumbnail = models.ImageField(
        upload_to='chat_attachments/thumbnails/%Y/%m/%d/',
        null=True,
        blank=True,
        verbose_name="Миниатюра",
        help_text="Для изображений и видео"
    )
    
    class Meta:
        verbose_name = "Вложение"
        verbose_name_plural = "Вложения"
        ordering = ['uploaded_at']
        indexes = [
            models.Index(fields=['message', 'file_type']),
            models.Index(fields=['uploaded_at']),
        ]
    
    def __str__(self):
        return f"{self.file_name} ({self.get_file_type_display()})"


class ForwardedMessage(models.Model):
    """Информация о пересылке сообщения"""
    
    message = models.OneToOneField(
        Message,
        on_delete=models.CASCADE,
        related_name='forward_info',
        verbose_name="Пересланное сообщение"
    )
    original_message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='forwarded_copies',
        verbose_name="Самое первое сообщение в цепочке"
    )
    immediate_source = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name="Непосредственный источник пересылки",
        help_text="Откуда переслали (может отличаться от original)"
    )
    original_chat = models.ForeignKey(
        Chat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name="Исходный чат"
    )
    original_author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name="Автор оригинального сообщения"
    )
    forwarded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='forwarded_messages',
        verbose_name="Кто переслал"
    )
    forwarded_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Время пересылки"
    )
    forward_count = models.IntegerField(
        default=1,
        verbose_name="Количество пересылок",
        help_text="Сколько раз это сообщение пересылалось"
    )
    preserved_content = models.TextField(
        blank=True,
        verbose_name="Сохранённый текст",
        help_text="На случай удаления оригинала"
    )
    preserved_author_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Имя автора оригинала"
    )
    
    class Meta:
        verbose_name = "Информация о пересылке"
        verbose_name_plural = "Информация о пересылках"
        indexes = [
            models.Index(fields=['original_message']),
            models.Index(fields=['forwarded_by', 'forwarded_at']),
        ]
    
    def __str__(self):
        return f"Пересылка: {self.message_id} от {self.forwarded_by}"


class MessageReply(models.Model):
    """Расширенная информация об ответе на сообщение"""
    
    REPLY_TYPE_CHOICES = [
        ('inline', 'В потоке'),
        ('quote', 'С цитатой'),
        ('thread', 'В треде'),
    ]
    
    message = models.OneToOneField(
        Message,
        on_delete=models.CASCADE,
        related_name='reply_info',
        verbose_name="Сообщение-ответ"
    )
    replied_to = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='extended_replies',
        verbose_name="На какое сообщение ответ"
    )
    is_cross_chat_reply = models.BooleanField(
        default=False,
        verbose_name="Ответ из другого чата"
    )
    original_chat = models.ForeignKey(
        Chat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name="Исходный чат",
        help_text="Если ответ был из другого чата"
    )
    preserved_text = models.TextField(
        blank=True,
        verbose_name="Сохранённый текст оригинала"
    )
    preserved_author_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Имя автора оригинала"
    )
    reply_type = models.CharField(
        max_length=10,
        choices=REPLY_TYPE_CHOICES,
        default='inline',
        verbose_name="Тип ответа"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Время создания ответа"
    )
    
    class Meta:
        verbose_name = "Информация об ответе"
        verbose_name_plural = "Информация об ответах"
        indexes = [
            models.Index(fields=['replied_to']),
            models.Index(fields=['is_cross_chat_reply']),
        ]
    
    def __str__(self):
        return f"Ответ: {self.message_id} → {self.replied_to_id}"


class ChatAccessPermission(models.Model):
    """Права доступа к чату для внешних пользователей"""
    
    ACCESS_LEVEL_CHOICES = [
        ('read', 'Только чтение'),
        ('write', 'Чтение и отправка'),
        ('moderate', 'Модерация'),
    ]
    
    chat = models.ForeignKey(
        Chat,
        on_delete=models.CASCADE,
        related_name='access_permissions',
        verbose_name="Чат"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_access_permissions',
        verbose_name="Пользователь"
    )
    access_level = models.CharField(
        max_length=10,
        choices=ACCESS_LEVEL_CHOICES,
        default='write',
        verbose_name="Уровень доступа"
    )
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name="Кто предоставил доступ"
    )
    granted_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Когда предоставлен доступ"
    )
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Срок действия",
        help_text="Если не указано - бессрочно"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен"
    )
    
    class Meta:
        verbose_name = "Право доступа к чату"
        verbose_name_plural = "Права доступа к чатам"
        unique_together = [('chat', 'user')]
        indexes = [
            models.Index(fields=['chat', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]
    
    def __str__(self):
        return f"{self.user} → {self.chat} ({self.get_access_level_display()})"


class CrossChatMessage(models.Model):
    """Сообщения, отправленные в чаты, где пользователь не является участником"""
    
    STATUS_CHOICES = [
        ('pending', 'На модерации'),
        ('approved', 'Одобрено'),
        ('rejected', 'Отклонено'),
    ]
    
    message = models.OneToOneField(
        Message,
        on_delete=models.CASCADE,
        related_name='cross_chat_info',
        verbose_name="Сообщение"
    )
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='sent_cross_chat_messages',
        verbose_name="Отправитель"
    )
    target_chat = models.ForeignKey(
        Chat,
        on_delete=models.CASCADE,
        related_name='cross_chat_messages',
        verbose_name="Целевой чат"
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name="Статус"
    )
    requires_moderation = models.BooleanField(
        default=True,
        verbose_name="Требует модерации"
    )
    moderated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name="Модератор"
    )
    moderated_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Время модерации"
    )
    moderation_note = models.TextField(
        blank=True,
        verbose_name="Заметка модератора"
    )
    sent_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Время отправки"
    )
    
    class Meta:
        verbose_name = "Кросс-чат сообщение"
        verbose_name_plural = "Кросс-чат сообщения"
        indexes = [
            models.Index(fields=['target_chat', 'status']),
            models.Index(fields=['sender', 'sent_at']),
            models.Index(fields=['status', 'requires_moderation']),
        ]
    
    def __str__(self):
        return f"CrossChat: {self.sender} → {self.target_chat} ({self.status})"


class ChatMembership(models.Model):
    """Явное управление участниками чатов"""
    
    ROLE_CHOICES = [
        ('owner', 'Владелец'),
        ('admin', 'Администратор'),
        ('moderator', 'Модератор'),
        ('member', 'Участник'),
        ('guest', 'Гость'),
    ]
    
    chat = models.ForeignKey(
        Chat,
        on_delete=models.CASCADE,
        related_name='memberships',
        verbose_name="Чат"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_memberships',
        verbose_name="Пользователь"
    )
    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default='member',
        verbose_name="Роль"
    )
    joined_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата вступления"
    )
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name="Кто пригласил"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активен",
        help_text="False если вышел из чата"
    )
    left_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата выхода"
    )
    can_send_messages = models.BooleanField(
        default=True,
        verbose_name="Может отправлять сообщения"
    )
    can_add_members = models.BooleanField(
        default=False,
        verbose_name="Может добавлять участников"
    )
    can_remove_members = models.BooleanField(
        default=False,
        verbose_name="Может удалять участников"
    )
    can_pin_messages = models.BooleanField(
        default=False,
        verbose_name="Может закреплять сообщения"
    )
    
    class Meta:
        verbose_name = "Участник чата"
        verbose_name_plural = "Участники чатов"
        unique_together = [('chat', 'user')]
        indexes = [
            models.Index(fields=['chat', 'is_active']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['chat', 'role']),
        ]
    
    def __str__(self):
        return f"{self.user} в {self.chat} ({self.get_role_display()})"
