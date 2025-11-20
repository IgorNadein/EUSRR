# Улучшения модели мессенджера

## 1. Добавить базовые поля в модель Chat

```python
class Chat(models.Model):
    # Существующие поля...
    type = models.CharField(max_length=16, choices=CHAT_TYPE_CHOICES)
    
    # НОВЫЕ ПОЛЯ:
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
```

## 2. Создать модель для закрепления чатов (персональная настройка)

```python
class ChatUserSettings(models.Model):
    """Персональные настройки пользователя для чата"""
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='user_settings')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    # Закрепление
    is_pinned = models.BooleanField(default=False, verbose_name="Закреплен")
    pinned_at = models.DateTimeField(null=True, blank=True, verbose_name="Время закрепления")
    pin_order = models.IntegerField(default=0, verbose_name="Порядок закрепленных")
    
    # Уведомления
    notifications_enabled = models.BooleanField(default=True, verbose_name="Уведомления")
    
    # Кастомное название (если пользователь переименовал)
    custom_name = models.CharField(max_length=255, blank=True, verbose_name="Свое название")
    
    # Скрыть чат
    is_hidden = models.BooleanField(default=False, verbose_name="Скрыт")
    
    class Meta:
        unique_together = [('chat', 'user')]
        ordering = ['-is_pinned', '-pinned_at']
```

## 3. Расширить типы чатов

```python
class Chat(models.Model):
    CHAT_TYPE_CHOICES = [
        ('private', 'Личный'),           # 1-на-1
        ('group', 'Групповой'),          # Произвольная группа сотрудников
        ('department', 'Отдел'),         # Привязан к отделу
        ('channel', 'Канал'),            # Только админы пишут, все читают
        ('announcement', 'Объявления'),  # Системный канал
    ]
```

## 4. Добавить роли участников

```python
class ChatMembership(models.Model):
    """Участие в чате с ролями"""
    ROLE_CHOICES = [
        ('owner', 'Владелец'),
        ('admin', 'Администратор'),
        ('moderator', 'Модератор'),
        ('member', 'Участник'),
        ('readonly', 'Только чтение'),
    ]
    
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        null=True, 
        on_delete=models.SET_NULL,
        related_name='+'
    )
    
    # Разрешения
    can_send_messages = models.BooleanField(default=True)
    can_add_members = models.BooleanField(default=False)
    can_edit_chat = models.BooleanField(default=False)
    
    class Meta:
        unique_together = [('chat', 'user')]
```

## 5. Расширить модель Message

```python
class Message(models.Model):
    # Существующие поля...
    chat = models.ForeignKey(Chat, related_name="messages", on_delete=models.CASCADE)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # НОВЫЕ ПОЛЯ:
    
    # Ответ на сообщение (упрощенная связь, детали в MessageReply)
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
    
    # Системные сообщения (вступление, выход и т.д.)
    is_system = models.BooleanField(default=False)
    system_type = models.CharField(max_length=50, blank=True)
    # Типы: 'user_joined', 'user_left', 'chat_created', 'chat_renamed', 
    #       'user_promoted', 'user_demoted', 'settings_changed'
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
    
    # Реакции (можно хранить как JSON)
    reactions = models.JSONField(default=dict, blank=True)
    # Формат: {'👍': [user_id1, user_id2], '❤️': [user_id3]}
    
    # Флаги для специальных типов сообщений
    is_forwarded = models.BooleanField(default=False)
    is_cross_chat = models.BooleanField(
        default=False,
        help_text="Сообщение отправлено не участником чата"
    )
    
    # Треды (для организации обсуждений)
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
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['chat', 'created_at']),
            models.Index(fields=['chat', 'is_deleted', 'created_at']),
            models.Index(fields=['author', 'created_at']),
            models.Index(fields=['thread_root', 'created_at']),
            models.Index(fields=['is_pinned', 'chat']),
        ]
```

## 6. Добавить модель вложений

```python
class MessageAttachment(models.Model):
    ATTACHMENT_TYPE_CHOICES = [
        ('image', 'Изображение'),
        ('file', 'Файл'),
        ('video', 'Видео'),
        ('audio', 'Аудио'),
    ]
    
    message = models.ForeignKey(Message, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to='chat_attachments/%Y/%m/%d/')
    file_type = models.CharField(max_length=20, choices=ATTACHMENT_TYPE_CHOICES)
    file_name = models.CharField(max_length=255)
    file_size = models.BigIntegerField()
    mime_type = models.CharField(max_length=100)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Для изображений
    thumbnail = models.ImageField(upload_to='chat_thumbnails/%Y/%m/%d/', null=True, blank=True)
```

## 6a. Улучшить модель пересылки сообщений

```python
class ForwardedMessage(models.Model):
    """Информация о пересланных сообщениях (поддержка цепочки пересылок)"""
    message = models.OneToOneField(
        Message, 
        on_delete=models.CASCADE, 
        related_name='forward_info',
        help_text="Текущее пересланное сообщение"
    )
    
    # Оригинальное сообщение (первое в цепочке)
    original_message = models.ForeignKey(
        Message, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='forwarded_copies',
        help_text="Самое первое сообщение в цепочке пересылок"
    )
    
    # Непосредственный источник (откуда переслали)
    immediate_source = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        related_name='+',
        help_text="Сообщение, которое было непосредственно переслано"
    )
    
    original_chat = models.ForeignKey(
        Chat, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='+'
    )
    original_author = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.SET_NULL, 
        null=True, 
        related_name='+'
    )
    
    forwarded_at = models.DateTimeField(auto_now_add=True)
    forwarded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='forwarded_messages',
        help_text="Кто переслал"
    )
    
    # Счетчик пересылок (для оригинала)
    forward_count = models.IntegerField(default=0, help_text="Сколько раз переслали")
    
    # Сохранить контент на случай удаления оригинала
    preserved_content = models.TextField(blank=True)
    preserved_author_name = models.CharField(max_length=255, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['original_message']),
            models.Index(fields=['forwarded_by', 'forwarded_at']),
        ]
```

## 6b. Добавить модель для отправки сообщений в чужие чаты

```python
class CrossChatMessage(models.Model):
    """Сообщения, отправленные в чаты, где пользователь не является участником"""
    
    message = models.OneToOneField(
        Message,
        on_delete=models.CASCADE,
        related_name='cross_chat_info'
    )
    
    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='cross_chat_messages',
        help_text="Отправитель (не член этого чата)"
    )
    
    target_chat = models.ForeignKey(
        Chat,
        on_delete=models.CASCADE,
        related_name='cross_messages',
        help_text="Чат-получатель"
    )
    
    # Разрешение на отправку
    approved = models.BooleanField(default=False, help_text="Одобрено модератором")
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text="Кто одобрил"
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    
    # Причина/контекст отправки
    reason = models.CharField(
        max_length=500,
        blank=True,
        help_text="Причина отправки сообщения в чужой чат"
    )
    
    # Режим отображения
    DISPLAY_MODE_CHOICES = [
        ('guest', 'Гостевое (с пометкой "Внешнее сообщение")'),
        ('forwarded', 'Как пересланное'),
        ('announcement', 'Как объявление'),
    ]
    display_mode = models.CharField(
        max_length=20,
        choices=DISPLAY_MODE_CHOICES,
        default='guest'
    )
    
    sent_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['target_chat', 'approved']),
            models.Index(fields=['sender', 'sent_at']),
        ]
```

## 7. Улучшить ChatReadState

```python
class ChatReadState(models.Model):
    chat = models.ForeignKey("Chat", on_delete=models.CASCADE, related_name="read_states")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    last_read_at = models.DateTimeField(null=True, blank=True)
    last_read_message = models.ForeignKey(
        Message, 
        null=True, 
        blank=True, 
        on_delete=models.SET_NULL,
        help_text="Последнее прочитанное сообщение"
    )
    
    # Статус набора текста
    is_typing = models.BooleanField(default=False)
    typing_updated_at = models.DateTimeField(null=True, blank=True)
    
    updated_at = models.DateTimeField(auto_now=True)
```

## 8. Добавить модель для ответов на сообщения (расширенная)

```python
class MessageReply(models.Model):
    """Дополнительная информация об ответе на сообщение"""
    
    message = models.OneToOneField(
        Message,
        on_delete=models.CASCADE,
        related_name='reply_info',
        help_text="Сообщение-ответ"
    )
    
    replied_to = models.ForeignKey(
        Message,
        on_delete=models.SET_NULL,
        null=True,
        related_name='replies',
        help_text="Исходное сообщение, на которое отвечают"
    )
    
    # Для ответов через чаты (если отвечаешь в другом чате)
    is_cross_chat_reply = models.BooleanField(default=False)
    original_chat = models.ForeignKey(
        Chat,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='+',
        help_text="Чат оригинального сообщения (если отличается)"
    )
    
    # Сохраненный контент на случай удаления
    preserved_text = models.TextField(blank=True)
    preserved_author_name = models.CharField(max_length=255, blank=True)
    
    # Тип ответа
    REPLY_TYPE_CHOICES = [
        ('inline', 'Обычный ответ'),
        ('quote', 'Цитирование'),
        ('thread', 'В треде'),
    ]
    reply_type = models.CharField(
        max_length=20,
        choices=REPLY_TYPE_CHOICES,
        default='inline'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['replied_to']),
        ]
```

## 9. Добавить права доступа к чатам

```python
class ChatAccessPermission(models.Model):
    """Права пользователей на отправку сообщений в чужие чаты"""
    
    chat = models.ForeignKey(
        Chat,
        on_delete=models.CASCADE,
        related_name='access_permissions'
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='chat_permissions'
    )
    
    # Типы доступа
    PERMISSION_TYPE_CHOICES = [
        ('send_messages', 'Отправка сообщений'),
        ('read_only', 'Только чтение'),
        ('send_with_approval', 'Отправка с модерацией'),
    ]
    permission_type = models.CharField(
        max_length=30,
        choices=PERMISSION_TYPE_CHOICES,
        default='send_with_approval'
    )
    
    # Кто выдал право
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='+'
    )
    granted_at = models.DateTimeField(auto_now_add=True)
    
    # Срок действия
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Когда истекает право доступа"
    )
    
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = [('chat', 'user')]
        indexes = [
            models.Index(fields=['chat', 'is_active']),
            models.Index(fields=['user', 'is_active']),
        ]
```

## 9. Убрать ограничения для гибкости

Удалить constraint'ы:
- `unique_main_global_chat` 
- `unique_main_department_chat`

Заменить на поле `is_default` для автоматического выбора чата по умолчанию.

## 10. Добавить настройки чата

```python
class ChatSettings(models.Model):
    """Глобальные настройки чата"""
    chat = models.OneToOneField(Chat, on_delete=models.CASCADE, related_name='settings')
    
    # Кто может писать
    only_admins_can_post = models.BooleanField(default=False)
    
    # Кто может приглашать
    members_can_invite = models.BooleanField(default=True)
    
    # Автоудаление сообщений
    auto_delete_messages_after = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Автоматически удалять сообщения старше N дней"
    )
    
    # Максимум участников
    max_members = models.IntegerField(null=True, blank=True)
    
    # Запретить личные сообщения между участниками
    disable_dm_between_members = models.BooleanField(default=False)
```

## Пример миграции (поэтапно)

### Этап 1: Базовые поля
```bash
# Добавить name, description, avatar в Chat
python manage.py makemigrations
python manage.py migrate
```

### Этап 2: Персональные настройки
```bash
# Создать ChatUserSettings
python manage.py makemigrations
python manage.py migrate
```

### Этап 3: Роли участников
```bash
# Создать ChatMembership
python manage.py makemigrations
python manage.py migrate
```

### Этап 4: Расширенные сообщения
```bash
# Добавить поля в Message, создать MessageAttachment
python manage.py makemigrations
python manage.py migrate
```

## Итоговая архитектура

```
Chat (базовая информация + настройки)
├── ChatUserSettings (персональные настройки каждого пользователя)
├── ChatMembership (роли и права участников)
├── ChatSettings (глобальные настройки чата)
├── ChatAccessPermission (права внешних пользователей на отправку сообщений)
├── Message
│   ├── MessageAttachment (файлы, изображения)
│   ├── ForwardedMessage (информация о пересылке с цепочкой)
│   ├── MessageReply (расширенная информация об ответах)
│   └── CrossChatMessage (сообщения из чужих чатов)
└── ChatReadState (статус прочтения)
```

## Новые возможности

### 1. Пересылка сообщений
- **Простая пересылка**: отправить сообщение в другой чат с указанием источника
- **Цепочка пересылок**: отслеживание всей истории пересылки (оригинал → промежуточные → текущее)
- **Счетчик пересылок**: сколько раз сообщение было переслано
- **Сохранение контента**: если оригинал удален, контент сохраняется

### 2. Ответы на сообщения
- **Внутри чата**: стандартный reply с цитированием
- **Кросс-чат ответы**: ответить на сообщение из другого чата
- **Типы ответов**: inline (обычный), quote (цитата), thread (тред)
- **Сохранение контекста**: текст и автор сохраняются при удалении оригинала

### 3. Отправка в чужие чаты
- **Режимы доступа**:
  - `send_messages` - свободная отправка
  - `read_only` - только чтение
  - `send_with_approval` - модерация перед публикацией
- **Типы отображения**:
  - `guest` - с пометкой "Внешнее сообщение"
  - `forwarded` - как пересланное
  - `announcement` - как объявление
- **Права доступа**: временные/постоянные, с указанием срока действия
- **Модерация**: одобрение администраторами чата

### 4. Треды (обсуждения)
- Организация дискуссий в отдельные ветки
- Счетчик ответов в треде
- Корневое сообщение треда

## Примеры использования

### Пересылка сообщения
```python
# В views или consumers
def forward_message(original_message_id, target_chat_id, user):
    original = Message.objects.get(id=original_message_id)
    
    # Создаем новое сообщение
    forwarded_msg = Message.objects.create(
        chat_id=target_chat_id,
        author=user,
        content=original.content,
        is_forwarded=True,
        has_attachments=original.has_attachments
    )
    
    # Копируем вложения
    for att in original.attachments.all():
        MessageAttachment.objects.create(
            message=forwarded_msg,
            file=att.file,
            file_type=att.file_type,
            file_name=att.file_name,
            file_size=att.file_size,
            mime_type=att.mime_type
        )
    
    # Находим оригинал в цепочке
    if hasattr(original, 'forward_info'):
        # Это уже пересланное - берем самый первый оригинал
        root_original = original.forward_info.original_message
    else:
        root_original = original
    
    # Создаем информацию о пересылке
    ForwardedMessage.objects.create(
        message=forwarded_msg,
        original_message=root_original,
        immediate_source=original,
        original_chat=root_original.chat,
        original_author=root_original.author,
        forwarded_by=user,
        preserved_content=root_original.content,
        preserved_author_name=root_original.author.get_full_name()
    )
    
    # Увеличиваем счетчик
    if hasattr(root_original, 'forward_info'):
        root_original.forward_info.forward_count += 1
        root_original.forward_info.save()
    
    return forwarded_msg
```

### Отправка в чужой чат
```python
def send_to_external_chat(sender, chat_id, content, reason=''):
    chat = Chat.objects.get(id=chat_id)
    
    # Проверяем права доступа
    permission = ChatAccessPermission.objects.filter(
        chat=chat,
        user=sender,
        is_active=True
    ).first()
    
    if not permission:
        # Создаем запрос на отправку с модерацией
        permission = ChatAccessPermission.objects.create(
            chat=chat,
            user=sender,
            permission_type='send_with_approval',
            granted_by=None
        )
    
    # Создаем сообщение
    message = Message.objects.create(
        chat=chat,
        author=sender,
        content=content,
        is_cross_chat=True
    )
    
    # Создаем метаданные
    CrossChatMessage.objects.create(
        message=message,
        sender=sender,
        target_chat=chat,
        approved=(permission.permission_type == 'send_messages'),
        reason=reason,
        display_mode='guest'
    )
    
    return message
```

### Ответ на сообщение из другого чата
```python
def reply_across_chats(user, original_msg_id, reply_content, target_chat_id):
    original_msg = Message.objects.get(id=original_msg_id)
    
    # Создаем ответ в целевом чате
    reply_msg = Message.objects.create(
        chat_id=target_chat_id,
        author=user,
        content=reply_content,
        reply_to=original_msg
    )
    
    # Создаем расширенную информацию
    MessageReply.objects.create(
        message=reply_msg,
        replied_to=original_msg,
        is_cross_chat_reply=True,
        original_chat=original_msg.chat,
        preserved_text=original_msg.content,
        preserved_author_name=original_msg.author.get_full_name(),
        reply_type='quote'
    )
    
    return reply_msg
```

## Приоритет внедрения (для MVP)

1. **Высокий приоритет:**
   - `name`, `avatar` в Chat
   - `ChatUserSettings` (закрепление, уведомления)
   - Расширение типов чатов (`group`, `channel`)
   - `reply_to`, `is_edited`, `is_forwarded`, `is_cross_chat` в Message
   - `MessageAttachment`
   - `ForwardedMessage` (базовая пересылка)
   - `MessageReply` (ответы в том же чате)

2. **Средний приоритет:**
   - `ChatMembership` (роли)
   - `ChatAccessPermission` (права на отправку в чужие чаты)
   - `CrossChatMessage` (отправка в чужие чаты с модерацией)
   - Кросс-чат ответы
   - Реакции на сообщения
   - Системные сообщения
   - История редактирования

3. **Низкий приоритет:**
   - Треды
   - Автоудаление
   - Расширенные разрешения
   - Статус "печатает"
   - Счетчики пересылок

## Изменения в UI/UX

После внедрения этих улучшений понадобится:

### Основные функции
- Модалка редактирования чата (название, аватар, описание)
- Контекстное меню для закрепления чатов
- Управление участниками (добавить/удалить/изменить роль)
- Загрузка файлов в сообщениях
- Ответы на сообщения (quote UI)
- Реакции на сообщения
- Редактирование/удаление своих сообщений

### Пересылка сообщений
- Кнопка "Переслать" в контекстном меню сообщения
- Модалка выбора чатов для пересылки (с поиском)
- Множественная пересылка (выбрать несколько чатов)
- Отображение "Переслано от [Имя]" в сообщении
- Ссылка на оригинальное сообщение (если доступно)
- Индикатор цепочки пересылок ("Переслано 5 раз")

### Ответы между чатами
- Возможность ответить в другом чате через контекстное меню
- Выбор целевого чата для ответа
- Цитата с указанием чата-источника
- Ссылка "Перейти к оригиналу" (если есть доступ)

### Отправка в чужие чаты
- Модалка "Отправить сообщение в чат"
- Поиск доступных чатов (даже без участия)
- Выбор режима отправки (гостевое/пересланное/объявление)
- Поле "Причина отправки"
- Статус модерации:
  - "Ожидает одобрения" (желтый значок)
  - "Одобрено" (зеленая галочка)
  - "Отклонено" (красный крестик)
- Для модераторов: панель одобрения внешних сообщений

### Визуальные индикаторы
- **Пересланное сообщение**:
  ```
  ┌─────────────────────────────────┐
  │ 📤 Переслано от Иван Петров     │
  │ Оригинал: Чат отдела IT         │
  ├─────────────────────────────────┤
  │ Текст сообщения...              │
  └─────────────────────────────────┘
  ```

- **Внешнее сообщение**:
  ```
  ┌─────────────────────────────────┐
  │ 🔔 Внешнее сообщение            │
  │ От: Мария Сидорова              │
  │ Причина: Важное объявление      │
  ├─────────────────────────────────┤
  │ Текст сообщения...              │
  └─────────────────────────────────┘
  ```

- **Ответ из другого чата**:
  ```
  ┌─────────────────────────────────┐
  │ Иван Петров → Чат отдела IT     │
  │ ↳ В ответ на сообщение из       │
  │   "Общий чат компании"          │
  ├─────────────────────────────────┤
  │ > Исходное сообщение...         │
  │ Ответ...                        │
  └─────────────────────────────────┘
  ```

### Контекстное меню сообщения (расширенное)
- Ответить
- Ответить в другом чате →
- Переслать →
  - В избранное
  - В другой чат...
  - В несколько чатов...
- Отправить в чужой чат →
- Скопировать
- Редактировать (свои)
- Удалить (свои/админ)
- Закрепить (админ)
- Пожаловаться

### Права и разрешения (админ панель чата)
- Настройки чата:
  - Кто может писать (все/только участники/только админы)
  - Разрешить внешние сообщения (да/нет/с модерацией)
  - Кто может приглашать участников
- Управление внешними отправителями:
  - Список пользователей с правами
  - Добавить/удалить права
  - Установить срок действия
  - Модерация ожидающих сообщений

