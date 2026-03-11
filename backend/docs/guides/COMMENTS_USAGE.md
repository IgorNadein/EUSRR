# Использование Communications для комментариев

## Новый тип чата: `comments`

С версии migrations/0036 добавлен специальный тип чата **"comments"** для систем комментариев.

## Быстрый старт

### 1. Создание чата комментариев

```python
from django.contrib.contenttypes.models import ContentType
from communications.models import Chat, Message

# Привязать комментарии к любому объекту
document = Document.objects.get(id=123)

comments_chat = Chat.objects.create(
    type='comments',
    name=f'Комментарии: {document.title}',
    context_object=document,  # GenericFK - работает с ЛЮБОЙ моделью
    created_by=request.user,
    flags={'allow_replies': True, 'allow_reactions': True}
)
```

### 2. Добавление комментария

```python
# Простой комментарий
comment = Message.objects.create(
    chat=comments_chat,
    author=request.user,
    content="Отличный документ!"
)

# Комментарий с вложениями
comment = Message.objects.create(
    chat=comments_chat,
    author=request.user,
    content="См. прикрепленный файл",
    has_attachments=True
)
MessageAttachment.objects.create(
    message=comment,
    file=uploaded_file,
    file_type='file',
    file_name='report.pdf',
    file_size=12345
)
```

### 3. Вложенные комментарии (треды)

```python
# Ответ на комментарий
reply = Message.objects.create(
    chat=comments_chat,
    author=another_user,
    content="Согласен!",
    reply_to=comment,  # Прямой ответ
    thread_root=comment  # Корень треда
)

# Получить все ответы на комментарий
replies = comment.direct_replies.filter(is_deleted=False)

# Получить весь тред
thread = Message.objects.filter(
    thread_root=comment,
    is_deleted=False
).order_by('created_at')
```

### 4. Редактирование и удаление

```python
# Редактировать комментарий
from django.utils import timezone

comment.content = "Отличный документ! (обновлено)"
comment.is_edited = True
comment.edited_at = timezone.now()
comment.save()

# Мягкое удаление
comment.is_deleted = True
comment.deleted_at = timezone.now()
comment.deleted_by = request.user
comment.save()
```

### 5. Реакции (эмодзи)

```python
from communications.models import MessageReaction

# Добавить реакцию
MessageReaction.objects.create(
    message=comment,
    user=request.user,
    emoji='👍'
)

# Получить сводку по реакциям
reactions_summary = comment.get_reactions_summary()
# {
#     '👍': {'count': 3, 'users': [1, 2, 3], 'user_names': ['User1', ...]},
#     '❤️': {'count': 1, 'users': [4], 'user_names': ['User4']}
# }
```

### 6. Уведомления (автоматические)

Модуль автоматически отправляет уведомления при:
- **Упоминаниях**: `@username` в тексте комментария
- **Ответах**: reply_to на чужой комментарий
- **Новых комментариях**: всем участникам чата (кроме автора)

```python
# Упомянуть пользователя
comment = Message.objects.create(
    chat=comments_chat,
    author=request.user,
    content="@john.doe посмотри этот документ"
)
# → john.doe получит уведомление автоматически
```

### 7. Real-time обновления через WebSocket

```javascript
// Frontend: подключение к WebSocket
const ws = new WebSocket('ws://localhost:8000/ws/realtime/');

// Подписаться на комментарии
ws.send(JSON.stringify({
    type: 'chat.subscribe',
    chat_id: commentsChat.id
}));

// Получать обновления в реальном времени
ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    if (data.type === 'chat.message') {
        // Новый комментарий → обновить UI
        addCommentToUI(data.message);
    }
};
```

## API эндпоинты

### Получить список комментариев

```http
GET /api/v1/communications/chats/{chat_id}/messages/?page=1&page_size=20

Response:
{
    "count": 42,
    "next": "...",
    "results": [
        {
            "id": 123,
            "author": {...},
            "content": "Отличный документ!",
            "created_at": "2026-03-11T15:30:00Z",
            "is_edited": false,
            "reply_to": null,
            "thread_root": null,
            "reactions_summary": {
                "👍": {"count": 3, "users": [1,2,3]}
            },
            "attachments": [...]
        }
    ]
}
```

### Создать комментарий

```http
POST /api/v1/communications/chats/{chat_id}/messages/

{
    "content": "Отличный документ!",
    "reply_to": 123  // опционально
}
```

### Редактировать комментарий

```http
PATCH /api/v1/communications/messages/{message_id}/

{
    "content": "Отличный документ! (обновлено)"
}
```

### Удалить комментарий

```http
DELETE /api/v1/communications/messages/{message_id}/
```

### Добавить реакцию

```http
POST /api/v1/communications/messages/{message_id}/react/

{
    "emoji": "👍"
}
```

## Преимущества использования Communications для комментариев

✅ **Треды** - вложенные комментарии "из коробки"  
✅ **Реакции** - эмодзи-реакции на комментарии  
✅ **Вложения** - картинки, файлы, видео  
✅ **Редактирование** - с историей изменений  
✅ **Упоминания** - @username с автоматическими уведомлениями  
✅ **Real-time** - WebSocket обновления  
✅ **Универсальность** - GenericFK работает с любыми моделями  
✅ **Оптимизация** - денормализованные счетчики, prefetch  

## Миграция с "department" на универсальные типы

### ❌ Старый подход (проектно-специфичный)

```python
# Чат отдела (жестко привязан к EUSRR)
chat = Chat.objects.create(
    type='department',  # DEPRECATED!
    department=department_instance
)
```

### ✅ Новый подход (универсальный)

```python
# Используй type='group' + context_object
chat = Chat.objects.create(
    type='group',  # Универсальный тип
    name=f'Чат отдела: {department.name}',
    context_object=department,  # GenericFK
    flags={'is_department_chat': True}
)

# Или для комментариев к объектам отдела
chat = Chat.objects.create(
    type='comments',
    name=f'Обсуждение: {department.name}',
    context_object=department
)
```

## Настройка участников через callback

Для проектно-специфичной логики участников используй callback:

```python
# settings.py
COMMUNICATIONS_PARTICIPANT_RESOLVER = 'myproject.utils.get_chat_participants'

# myproject/utils.py
def get_chat_participants(chat):
    """
    Кастомная логика определения участников.
    
    Возвращает QuerySet пользователей или None для fallback.
    """
    if chat.type == 'comments':
        # Комментарии видят только те, кто имеет доступ к объекту
        if hasattr(chat.context_object, 'get_allowed_users'):
            return chat.context_object.get_allowed_users()
    
    # Для department используй GenericFK
    if chat.flags.get('is_department_chat'):
        from employees.models import EmployeeDepartment
        dept = chat.context_object
        user_ids = EmployeeDepartment.objects.filter(
            department=dept,
            is_active=True
        ).values_list('employee_id', flat=True)
        return User.objects.filter(id__in=user_ids)
    
    return None  # Fallback к стандартной логике
```

## Примеры использования

### Комментарии к документу

```python
document = Document.objects.get(id=123)
chat = Chat.objects.create(
    type='comments',
    name=f'Комментарии: {document.title}',
    context_object=document,
    flags={'allow_anonymous': False}
)
```

### Комментарии к задаче

```python
task = Task.objects.get(id=456)
chat = Chat.objects.create(
    type='comments',
    name=f'Обсуждение: {task.title}',
    context_object=task,
    flags={'notify_assignee': True}
)
```

### Комментарии к посту в соцсети

```python
post = Post.objects.get(id=789)
chat = Chat.objects.create(
    type='comments',
    name='Comments',
    context_object=post,
    flags={'allow_public_comments': True, 'moderation_enabled': True}
)
```

## См. также

- [LDAP_CONFIGURATION.md](LDAP_CONFIGURATION.md) - интеграция с LDAP
- [JS_MODULES_GUIDE.md](JS_MODULES_GUIDE.md) - frontend интеграция
- [REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md) - история рефакторинга
