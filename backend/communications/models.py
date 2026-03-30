# backend/communications/models.py
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models
from django.db.models import Q
from django.utils import timezone

User = get_user_model()


class ChatReadState(models.Model):
    """
    Состояние прочтения чата пользователем.
    
    Использует Telegram-style подход: последнее прочитанное сообщение
    отмечается автоматически при загрузке сообщений через GET запросы.
    """
    chat = models.ForeignKey(
        "Chat", on_delete=models.CASCADE, related_name="read_states"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="chat_read_states",
    )
    updated_at = models.DateTimeField(auto_now=True)
    
    # Последнее прочитанное сообщение (единственный источник истины)
    last_read_message = models.ForeignKey(
        'Message',
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        verbose_name="Последнее прочитанное сообщение",
        help_text="Обновляется автоматически при загрузке сообщений (Telegram-style)"
    )
    
    # Денормализованный счетчик непрочитанных (оптимизация)
    unread_count = models.IntegerField(
        default=0,
        verbose_name="Непрочитанных сообщений",
        help_text="Кешированное значение для производительности. Обновляется при новых сообщениях и прочтении."
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
        constraints = [
            models.UniqueConstraint(
                fields=["chat", "user"],
                name="uniq_chatreadstate_chat_user",
            ),
        ]
        indexes = [
            models.Index(fields=["chat", "user"]),
            models.Index(fields=["chat", "user", "is_typing"]),
            models.Index(fields=["last_read_message"]),  # Для быстрого поиска по message
            models.Index(fields=["user", "unread_count"]),  # Для быстрых запросов непрочитанных
        ]

    def __str__(self):
        msg_id = self.last_read_message_id if self.last_read_message_id else '-'
        return f"read:{self.user_id}@{self.chat_id} → msg#{msg_id}"

    @property
    def last_read_at(self):
        return self.updated_at


class Chat(models.Model):
    CHAT_TYPE_CHOICES = [
        ("private", "Личный"),
        ("group", "Групповой"),
        ("channel", "Канал"),
        ("announcement", "Объявления"),
        ("global", "Глобальный"),
        ("comments", "Комментарии"),
    ]

    type = models.CharField(
        max_length=32,  # Увеличено с 16 для кастомных типов
        choices=CHAT_TYPE_CHOICES,
        verbose_name="Тип чата",
        db_index=True,
        help_text="Chat type: private, group, channel, announcement, global, comments. Use 'group' + context_object for domain-specific chats."
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
    include_all_users = models.BooleanField(
        default=False,
        verbose_name="Включить всех пользователей",
        help_text="Для анонсов и общих чатов"
    )
    
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="chats",
        verbose_name="Участники",
    )
    
    # ===== Universal context (GenericForeignKey) =====
    # Позволяет привязать чат к ЛЮБОЙ модели (Project, Team, Event, Document, etc.)
    context_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name="Context type",
        help_text="Type of related object (e.g., Project, Team, Event, Document)"
    )
    context_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Context object ID"
    )
    context_object = GenericForeignKey(
        'context_content_type',
        'context_object_id'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Создан")
    is_main = models.BooleanField(default=False, verbose_name="Основной чат")
    
    # ===== NEW: Flexible flags & metadata =====
    flags = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Flags",
        help_text="Custom flags: {'is_primary': true, 'is_archived': false, etc.}"
    )
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Extra data",
        help_text="Additional chat metadata (extensible)"
    )
    
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
            # Только 1 announcement на сотрудника
            models.UniqueConstraint(
                fields=["type", "created_by"],
                condition=Q(type="announcement"),
                name="unique_announcement_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["type", "is_main"]),
            models.Index(fields=["created_at"]),
            # Index for GenericForeignKey
            models.Index(fields=["context_content_type", "context_object_id"], name="chat_context_idx"),
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
        # Удаление глобального чата разрешено администраторам и владельцам
        # Проверка прав происходит на уровне API permissions
        return super().delete(*args, **kwargs)

    def mark_read(self, user):
        """
        [DEPRECATED] Помечает чат прочитанным до последнего сообщения.
        
        ВНИМАНИЕ: Этот метод устарел. Используйте автоматическую отметку
        через ChatViewSet._auto_mark_read() при загрузке сообщений.
        """
        last_message = self.messages.order_by("-created_at").first()
        if not last_message:
            return
        
        # Обновляем, только если новое сообщение НОВЕЕ текущего
        read_state, created = ChatReadState.objects.get_or_create(
            chat=self,
            user=user,
            defaults={
                'last_read_message': last_message,
                'unread_count': 0
            }
        )
        
        if not created:
            if read_state.last_read_message_id:
                if last_message.id <= read_state.last_read_message_id:
                    return  # Не откатываем назад
            
            read_state.last_read_message = last_message
            read_state.unread_count = 0
            read_state.save(update_fields=['last_read_message', 'unread_count', 'updated_at'])

    def unread_count_for(self, user):
        """
        Количество непрочитанных сообщений (кроме своих).
        
        ОПТИМИЗИРОВАНО: Использует денормализованное поле unread_count из ChatReadState
        вместо подсчета в реальном времени.
        """
        rs = (
            ChatReadState.objects.filter(chat=self, user=user)
            .only("unread_count")
            .first()
        )
        return rs.unread_count if rs else 0

    def get_participants(self):
        """
        Возвращает QuerySet участников чата.
        
        MIGRATION: Переписано для использования только ChatMembership
        
        Использует callback из settings.COMMUNICATIONS_PARTICIPANT_RESOLVER
        для проектно-специфичной логики.
        
        Fallback логика:
        - private/group/channel/announcement: только активные ChatMembership
        - global: все активные пользователи
        - с include_all_users: все активные пользователи
        """
        # Попытка использовать callback из settings
        from django.conf import settings
        from django.utils.module_loading import import_string
        
        resolver_path = getattr(settings, 'COMMUNICATIONS_PARTICIPANT_RESOLVER', None)
        
        if resolver_path:
            try:
                resolver_func = import_string(resolver_path)
                result = resolver_func(self)
                if result is not None:
                    return result
            except (ImportError, AttributeError) as e:
                # Логируем ошибку, но не падаем
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to import participant resolver '{resolver_path}': {e}")
        
        # Fallback логика (универсальная, без бизнес-специфики)
        if self.type == "global" or self.include_all_users:
            return User.objects.filter(is_active=True)
        
        # Для всех остальных типов - используем только активные memberships
        from communications.models import ChatMembership
        
        membership_user_ids = ChatMembership.objects.filter(
            chat=self,
            is_active=True
        ).values_list("user_id", flat=True)
        
        return User.objects.filter(id__in=membership_user_ids).distinct()

    def __str__(self):
        if self.type == "private":
            # MIGRATION: используем memberships вместо participants
            members = ChatMembership.objects.filter(
                chat=self, 
                is_active=True
            ).select_related('user')[:3]
            names = ", ".join(f"{m.user.last_name} {m.user.first_name}".strip() for m in members) or "—"
            total_count = ChatMembership.objects.filter(chat=self, is_active=True).count()
            more = total_count - len(members)
            if more > 0:
                names += f" и ещё {more}"
            return f"Личный чат: {names}"
        if self.type == "group":
            return self.name or "Групповой чат"
        if self.type == "comments":
            # Comments linked to any object via GenericFK
            context = self.context_object if self.context_object else None
            return f"Комментарии: {context or self.name or '—'}"
        if self.type == "channel":
            return self.name or "Канал"
        if self.type == "announcement":
            return self.name or "Объявления"
        return "Глобальный чат"

    @property
    def include_all_employees(self):
        return self.include_all_users

    @include_all_employees.setter
    def include_all_employees(self, value):
        self.include_all_users = value


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

    def get_reactions_summary(self):
        """
        Получить сводку по реакциям для этого сообщения
        Возвращает словарь вида:
        {
            '👍': {'count': 3, 'users': [1, 2, 3], 'user_names': ['User1', ...]},
            '❤️': {'count': 1, 'users': [4], 'user_names': ['User4']}
        }
        """
        # Используем related_name='reactions' из MessageReaction
        reactions_qs = self.reactions.select_related('user')
        
        summary = {}
        for reaction in reactions_qs:
            emoji = reaction.emoji
            if emoji not in summary:
                summary[emoji] = {
                    'count': 0,
                    'users': [],
                    'user_names': []
                }
            summary[emoji]['count'] += 1
            summary[emoji]['users'].append(reaction.user_id)
            summary[emoji]['user_names'].append(
                reaction.user.get_full_name() or reaction.user.username
            )
        
        return summary


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
        verbose_name="Сообщение",
        null=True,
        blank=True,
        help_text="Может быть null для временных вложений при редактировании"
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
    
    # Размеры для изображений и видео
    width = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Ширина",
        help_text="Ширина изображения или видео в пикселях"
    )
    height = models.IntegerField(
        null=True,
        blank=True,
        verbose_name="Высота",
        help_text="Высота изображения или видео в пикселях"
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
    
    def save(self, *args, **kwargs):
        """
        Автоматически извлекает размеры изображения при сохранении.
        Telegram-подход: размеры всегда известны до рендеринга.
        """
        # Если это изображение и размеры еще не установлены
        if self.file_type == 'image' and self.file and (not self.width or not self.height):
            try:
                from PIL import Image
                from io import BytesIO
                
                # Открываем файл
                file_obj = self.file.file if hasattr(self.file, 'file') else self.file
                
                # Сохраняем позицию курсора
                if hasattr(file_obj, 'seek'):
                    file_obj.seek(0)
                
                # Открываем изображение
                image = Image.open(file_obj)
                self.width, self.height = image.size
                
                # Возвращаем курсор в начало
                if hasattr(file_obj, 'seek'):
                    file_obj.seek(0)
                    
            except Exception as e:
                # Если не удалось извлечь размеры - не критично
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Could not extract image dimensions: {e}")
        
        super().save(*args, **kwargs)


class MessageEditHistory(models.Model):
    """История редактирования сообщения"""
    
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='edit_history_records',
        verbose_name="Сообщение"
    )
    edited_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Время редактирования",
        db_index=True
    )
    previous_content = models.TextField(
        verbose_name="Предыдущий текст"
    )
    edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
        verbose_name="Кто отредактировал"
    )
    
    class Meta:
        verbose_name = "Запись истории редактирования"
        verbose_name_plural = "История редактирования сообщений"
        ordering = ['edited_at']
        indexes = [
            models.Index(fields=['message', 'edited_at']),
        ]
    
    def __str__(self):
        return f"Редактирование сообщения {self.message_id} в {self.edited_at}"


class MessageForwardMetadata(models.Model):
    """Метаданные пересланного сообщения"""
    
    message = models.OneToOneField(
        Message,
        on_delete=models.CASCADE,
        related_name='forward_metadata',
        verbose_name="Пересланное сообщение"
    )
    original_message = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='forwarded_copies',
        verbose_name="Оригинальное сообщение",
        help_text="Самое первое сообщение в цепочке пересылок"
    )
    original_chat = models.ForeignKey(
        Chat,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name="Оригинальный чат"
    )
    original_author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='+',
        verbose_name="Автор оригинала"
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
        help_text="Сколько раз пересылалось"
    )
    original_created_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Дата создания оригинала"
    )
    original_chat_name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Название оригинального чата"
    )
    
    class Meta:
        verbose_name = "Метаданные пересылки"
        verbose_name_plural = "Метаданные пересылок"
        indexes = [
            models.Index(fields=['original_message']),
            models.Index(fields=['forwarded_by', 'forwarded_at']),
        ]
    
    def __str__(self):
        return f"Пересылка {self.message_id}: {self.forward_count}x"


class ChatMembership(models.Model):
    """
    Явное управление участниками чатов
    
    Роли и права:
    - admin: полный доступ к управлению чатом (кроме удаления)
    - moderator: может модерировать контент (закреплять, удалять чужие сообщения)
    - member: обычный участник (может отправлять сообщения)
    - guest: ограниченный доступ (только чтение, может быть отключен can_send_messages)
    
    Примечание: роль 'owner' (владелец) НЕ используется - владелец определяется
    через Chat.created_by и имеет максимальные права через django-rules.
    """
    
    ROLE_CHOICES = [
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
    
    @property
    def can_manage_members(self):
        """Может ли участник управлять другими участниками (добавлять/удалять)"""
        return self.can_add_members and self.can_remove_members
    
    def set_permissions_for_role(self):
        """
        Устанавливает права доступа автоматически на основе роли.
        Вызывается при save() если права не были установлены явно.
        """
        if self.role == 'admin':
            self.can_send_messages = True
            self.can_add_members = True
            self.can_remove_members = True
            self.can_pin_messages = True
        elif self.role == 'moderator':
            self.can_send_messages = True
            self.can_add_members = False
            self.can_remove_members = False
            self.can_pin_messages = True
        elif self.role == 'member':
            self.can_send_messages = True
            self.can_add_members = False
            self.can_remove_members = False
            self.can_pin_messages = False
        elif self.role == 'guest':
            self.can_send_messages = False
            self.can_add_members = False
            self.can_remove_members = False
            self.can_pin_messages = False
    
    def promote_to_admin(self):
        """Повышает участника до администратора"""
        self.role = 'admin'
        self.set_permissions_for_role()
        self.save()
    
    def demote_to_member(self):
        """Понижает участника до обычного члена"""
        self.role = 'member'
        self.set_permissions_for_role()
        self.save()
    
    def save(self, *args, **kwargs):
        # Автоматически устанавливаем права при создании
        if not self.pk:
            self.set_permissions_for_role()
        super().save(*args, **kwargs)


class MessageReaction(models.Model):
    """Реакции на сообщения (эмодзи)"""
    
    message = models.ForeignKey(
        Message,
        on_delete=models.CASCADE,
        related_name='reactions',
        verbose_name="Сообщение"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='message_reactions',
        verbose_name="Пользователь"
    )
    emoji = models.CharField(
        max_length=10,
        verbose_name="Эмодзи",
        help_text="Unicode эмодзи (например: 👍, ❤️, 😂)"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Время добавления"
    )
    
    class Meta:
        verbose_name = "Реакция на сообщение"
        verbose_name_plural = "Реакции на сообщения"
        unique_together = [('message', 'user')]
        indexes = [
            models.Index(fields=['message', 'emoji']),
            models.Index(fields=['message', 'user']),
            models.Index(fields=['created_at']),
        ]
        ordering = ['created_at']
    
    def __str__(self):
        return f"{self.user} {self.emoji} → сообщение {self.message_id}"


class AvailableReaction(models.Model):
    """Доступные реакции для сообщений"""
    
    emoji = models.CharField(
        max_length=10,
        unique=True,
        verbose_name="Эмодзи",
        help_text="Unicode эмодзи (например: 👍, ❤️, 😂)"
    )
    name = models.CharField(
        max_length=50,
        verbose_name="Название",
        help_text="Человекочитаемое название (например: 'Лайк', 'Сердце')"
    )
    order = models.IntegerField(
        default=0,
        verbose_name="Порядок отображения",
        help_text="Меньше = выше в списке"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Активна",
        help_text="Отображать ли эту реакцию пользователям"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Дата добавления"
    )
    
    class Meta:
        verbose_name = "Доступная реакция"
        verbose_name_plural = "Доступные реакции"
        ordering = ['order', 'created_at']
        indexes = [
            models.Index(fields=['is_active', 'order']),
        ]
    
    def __str__(self):
        return f"{self.emoji} {self.name}"


class Poll(models.Model):
    """Голосование в чате"""
    
    message = models.OneToOneField(
        Message,
        on_delete=models.CASCADE,
        related_name='poll',
        verbose_name="Сообщение"
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_polls',
        verbose_name="Автор"
    )
    question = models.CharField(
        max_length=500,
        verbose_name="Вопрос"
    )
    
    # Настройки голосования
    is_anonymous = models.BooleanField(
        default=False,
        verbose_name="Анонимное голосование",
        help_text="Не показывать кто голосовал"
    )
    is_multiple_choice = models.BooleanField(
        default=False,
        verbose_name="Множественный выбор",
        help_text="Можно выбрать несколько вариантов"
    )
    is_quiz = models.BooleanField(
        default=False,
        verbose_name="Викторина",
        help_text="Только один правильный ответ, показывается после голосования"
    )
    allows_custom_answers = models.BooleanField(
        default=False,
        verbose_name="Разрешить свои варианты",
        help_text="Пользователи могут добавить свой вариант ответа"
    )
    
    # Статус
    is_closed = models.BooleanField(
        default=False,
        verbose_name="Голосование закрыто"
    )
    closed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Время закрытия"
    )
    closes_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Автоматическое закрытие",
        help_text="Голосование автоматически закроется в указанное время"
    )
    
    # Метаданные
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Создано"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Обновлено"
    )
    total_voters = models.IntegerField(
        default=0,
        verbose_name="Всего проголосовало",
        help_text="Количество уникальных пользователей, проголосовавших"
    )
    
    class Meta:
        verbose_name = "Голосование"
        verbose_name_plural = "Голосования"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['message']),
            models.Index(fields=['author', 'created_at']),
            models.Index(fields=['is_closed', 'closes_at']),
        ]
    
    def __str__(self):
        return f"Голосование: {self.question[:50]}"
    
    def close(self):
        """Закрыть голосование"""
        if not self.is_closed:
            self.is_closed = True
            self.closed_at = timezone.now()
            self.save(update_fields=['is_closed', 'closed_at'])
    
    def get_results(self):
        """Получить результаты голосования"""
        options = self.options.annotate(
            vote_count_calc=models.Count('votes')
        ).order_by('position')
        
        total_votes = sum(opt.vote_count for opt in options)
        
        results = []
        for option in options:
            percentage = (
                (option.vote_count / total_votes * 100)
                if total_votes > 0 else 0
            )
            results.append({
                'id': option.id,
                'text': option.text,
                'vote_count': option.vote_count,
                'percentage': round(percentage, 1),
                'is_correct': option.is_correct,
                'voters': [] if self.is_anonymous else list(
                    option.votes.select_related('voter').values(
                        'voter__id',
                        'voter__first_name',
                        'voter__last_name',
                        'voter__email'
                    )
                )
            })
        
        return {
            'id': self.id,
            'question': self.question,
            'total_voters': self.total_voters,
            'is_closed': self.is_closed,
            'is_anonymous': self.is_anonymous,
            'is_multiple_choice': self.is_multiple_choice,
            'is_quiz': self.is_quiz,
            'options': results
        }


class PollOption(models.Model):
    """Вариант ответа в голосовании"""
    
    poll = models.ForeignKey(
        Poll,
        on_delete=models.CASCADE,
        related_name='options',
        verbose_name="Голосование"
    )
    text = models.CharField(
        max_length=200,
        verbose_name="Текст варианта"
    )
    position = models.IntegerField(
        default=0,
        verbose_name="Порядковый номер"
    )
    vote_count = models.IntegerField(
        default=0,
        verbose_name="Количество голосов"
    )
    is_correct = models.BooleanField(
        default=False,
        verbose_name="Правильный ответ",
        help_text="Для викторин"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Создан"
    )
    
    class Meta:
        verbose_name = "Вариант ответа"
        verbose_name_plural = "Варианты ответов"
        ordering = ['position', 'id']
        indexes = [
            models.Index(fields=['poll', 'position']),
        ]
    
    def __str__(self):
        return f"{self.poll.question[:30]} - {self.text[:30]}"


class PollVote(models.Model):
    """Голос пользователя в голосовании"""
    
    poll = models.ForeignKey(
        Poll,
        on_delete=models.CASCADE,
        related_name='votes',
        verbose_name="Голосование"
    )
    option = models.ForeignKey(
        PollOption,
        on_delete=models.CASCADE,
        related_name='votes',
        verbose_name="Выбранный вариант"
    )
    voter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='poll_votes',
        verbose_name="Проголосовавший"
    )
    voted_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Время голосования"
    )
    
    class Meta:
        verbose_name = "Голос"
        verbose_name_plural = "Голоса"
        ordering = ['-voted_at']
        constraints = [
            models.UniqueConstraint(
                fields=['poll', 'voter', 'option'],
                name='unique_vote_per_option'
            )
        ]
        indexes = [
            models.Index(fields=['poll', 'voter']),
            models.Index(fields=['option']),
        ]
    
    def __str__(self):
        return f"{self.voter} → {self.option.text}"
