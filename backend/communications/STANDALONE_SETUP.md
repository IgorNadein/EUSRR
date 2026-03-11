# Django Communications - Standalone Setup Guide

## О приложении

`django-communications` - универсальная система чатов для Django с поддержкой:
- 🔌 **WebSocket** (Django Channels) - real-time messaging
- 💬 **Типы чатов**: private, group, channel, announcement, global, comments
- 🔗 **GenericForeignKey** - привязка к любой модели
- 📎 **Вложения**, реакции, голосования, пересылка сообщений
- 🔔 **Уведомления** (опционально через django-notifications-hq)
- 🔐 **Permissions** (django-rules)
- 📱 **REST API** (Django REST Framework)

---

## Быстрая установка

### 1. Установка пакета

```bash
# Из локальной копии
pip install -e /path/to/communications/

# ИЛИ из PyPI (когда будет опубликован)
pip install django-communications

# С опциональными зависимостями
pip install django-communications[all]
```

### 2. Добавить в INSTALLED_APPS

```python
# settings.py
INSTALLED_APPS = [
    # Django apps
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    
    # Third-party apps (обязательные)
    'rest_framework',
    'channels',
    'rules',
    
    # Communications
    'communications',
    
    # Опциональные (рекомендуется)
    'notifications',  # для уведомлений
]
```

### 3. Настройка

```python
# settings.py

# ===== Django REST Framework =====
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

# ===== Django Channels (WebSocket) =====
ASGI_APPLICATION = 'your_project.asgi.application'

CHANNEL_LAYERS = {
    'default': {
        # Для разработки - In-Memory
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
        
        # Для продакшена - Redis (раскомментируйте)
        # 'BACKEND': 'channels_redis.core.RedisChannelLayer',
        # 'CONFIG': {
        #     "hosts": [('127.0.0.1', 6379)],
        # },
    },
}

# ===== django-rules (Permissions) =====
AUTHENTICATION_BACKENDS = (
    'rules.permissions.ObjectPermissionBackend',
    'django.contrib.auth.backends.ModelBackend',
)

# ===== Communications Settings =====

# URL для профиля автора (ОБЯЗАТЕЛЬНО настроить под ваш проект)
COMMUNICATIONS_AUTHOR_URL_PATTERN = '/users/{id}/'  # По умолчанию: '/api/v1/employees/{id}/'

# Функция сжатия изображений (опционально)
COMMUNICATIONS_IMAGE_COMPRESSOR = None  # Отключает сжатие
# COMMUNICATIONS_IMAGE_COMPRESSOR = 'myapp.utils.compress_avatar'  # Ваша функция

# Resolver для определения участников чата (опционально)
# COMMUNICATIONS_PARTICIPANT_RESOLVER = 'myapp.utils.get_chat_participants'

# Автоматические уведомления (по умолчанию True)
COMMUNICATIONS_AUTO_NOTIFY = True
```

### 4. URL routing

```python
# urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from communications.api.viewsets import ChatViewSet, MessageViewSet, PollViewSet

router = DefaultRouter()
router.register(r'chats', ChatViewSet, basename='chats')
router.register(r'messages', MessageViewSet, basename='messages')
router.register(r'polls', PollViewSet, basename='polls')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/communications/', include(router.urls)),
]
```

### 5. ASGI routing (WebSocket)

```python
# asgi.py
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'your_project.settings')

django_asgi_app = get_asgi_application()

from your_project.routing import websocket_urlpatterns

application = ProtocolTypeRouter({
    "http": django_asgi_app,
    "websocket": AuthMiddlewareStack(
        URLRouter(websocket_urlpatterns)
    ),
})
```

```python
# routing.py (создайте файл)
from django.urls import path
from your_app.consumers import YourConsumer  # Ваш consumer с ChatConsumerMixin

websocket_urlpatterns = [
    path('ws/', YourConsumer.as_asgi()),
]
```

### 6. WebSocket Consumer

```python
# consumers.py
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from communications.consumers import ChatConsumerMixin

class YourConsumer(ChatConsumerMixin, AsyncJsonWebsocketConsumer):
    """
    WebSocket consumer с поддержкой чатов.
    
    ChatConsumerMixin предоставляет все методы для работы с чатами.
    """
    
    async def connect(self):
        self.user = self.scope["user"]
        if not self.user.is_authenticated:
            await self.close()
            return
        
        self.active_chat_id = None
        await self.accept()
        
        # Подключение к персональному каналу
        await self.channel_layer.group_add(
            f"user_{self.user.id}",
            self.channel_name
        )
    
    async def disconnect(self, close_code):
        if hasattr(self, 'user') and self.user.is_authenticated:
            await self.channel_layer.group_discard(
                f"user_{self.user.id}",
                self.channel_name
            )
    
    async def receive_json(self, content):
        """
        Обработка сообщений от клиента.
        ChatConsumerMixin автоматически обрабатывает chat_* actions.
        """
        action = content.get('action')
        
        # Chat actions (обрабатываются автоматически ChatConsumerMixin)
        if action in ['open_chat', 'close_chat', 'send_message', 'edit_message',
                      'delete_message', 'add_reaction', 'remove_reaction',
                      'typing', 'stop_typing', 'mark_read', 'vote_poll']:
            # Вызов соответствующего метода из mixin
            handler = getattr(self, f'_handle_{action}', None)
            if handler:
                await handler(content)
            return
        
        # Ваша дополнительная логика
        await self.send_json({
            'type': 'error',
            'error': f'Unknown action: {action}'
        })
```

### 7. Миграции

```bash
python manage.py migrate
```

### 8. Создать главный глобальный чат (опционально)

```python
# В Django shell или через signal
from communications.models import Chat

Chat.objects.create(
    type='global',
    name='Общий чат',
    flags={'is_primary': True},
    is_main=True  # backward compatibility
)
```

---

## Настройка (детально)

### COMMUNICATIONS_AUTHOR_URL_PATTERN

Шаблон URL для профиля автора сообщения. Используется в `serialize_message()`.

```python
# Настройка по умолчанию (проектно-специфичная)
COMMUNICATIONS_AUTHOR_URL_PATTERN = '/api/v1/employees/{id}/'

# Для standalone проекта
COMMUNICATIONS_AUTHOR_URL_PATTERN = '/users/{id}/'

# Отключить URL (пустая строка)
COMMUNICATIONS_AUTHOR_URL_PATTERN = None
```

**Placeholder `{id}`** заменяется на `author.id`.

---

### COMMUNICATIONS_IMAGE_COMPRESSOR

Функция для сжатия аватаров чатов. Вызывается в pre_save signal.

```python
# Отключить сжатие
COMMUNICATIONS_IMAGE_COMPRESSOR = None

# Использовать свою функцию
COMMUNICATIONS_IMAGE_COMPRESSOR = 'myapp.utils.compress_avatar'

# По умолчанию (backward compatibility)
COMMUNICATIONS_IMAGE_COMPRESSOR = 'common.image_utils.compress_avatar'
```

**Сигнатура функции:**
```python
def compress_avatar(image_bytes: bytes) -> bytes:
    """
    Принимает байты изображения, возвращает сжатые байты.
    """
    from PIL import Image
    import io
    
    img = Image.open(io.BytesIO(image_bytes))
    # ... ваша логика сжатия ...
    return compressed_bytes
```

---

### COMMUNICATIONS_PARTICIPANT_RESOLVER

Callback для определения участников чата. Используется в `Chat.get_participants()`.

```python
# Не использовать callback (использовать fallback логику)
# COMMUNICATIONS_PARTICIPANT_RESOLVER = None  # (по умолчанию)

# Использовать проектно-специфичную логику
COMMUNICATIONS_PARTICIPANT_RESOLVER = 'employees.utils.get_chat_participants'
```

**Сигнатура функции:**
```python
from django.db.models import QuerySet
from communications.models import Chat

def get_chat_participants(chat: Chat) -> QuerySet | None:
    """
    Возвращает QuerySet участников или None (использовать fallback).
    
    Примеры специфичной логики:
    - Для department чата - все сотрудники департамента
    - Для project чата - все участники проекта
    - И т.д.
    """
    if chat.type == 'group' and chat.context_object:
        # Пример: context связан с Project
        if hasattr(chat.context_object, 'members'):
            return chat.context_object.members.all()
    
    return None  # Использовать fallback
```

---

### COMMUNICATIONS_AUTO_NOTIFY

Включает/отключает автоматические уведомления при новых сообщениях.

```python
# Включить (по умолчанию)
COMMUNICATIONS_AUTO_NOTIFY = True

# Отключить (управлять уведомлениями вручную)
COMMUNICATIONS_AUTO_NOTIFY = False
```

**Требует:** `django-notifications-hq` (опционально)

---

## API Endpoints

После настройки доступны следующие endpoints:

### Chats
- `GET /api/communications/chats/` - список чатов
- `GET /api/communications/chats/{id}/` - детали чата
- `POST /api/communications/chats/` - создать чат
- `POST /api/communications/chats/{id}/pin/` - закрепить
- `POST /api/communications/chats/{id}/notifications/` - настроить уведомления
- `GET /api/communications/chats/{id}/messages/` - сообщения (с автоотметкой)

### Messages
- `GET /api/communications/messages/` - список сообщений
- `POST /api/communications/messages/` - отправить сообщение
- `PATCH /api/communications/messages/{id}/` - редактировать
- `DELETE /api/communications/messages/{id}/` - удалить
- `POST /api/communications/messages/{id}/react/` - добавить реакцию
- `POST /api/communications/messages/{id}/forward/` - переслать
- `GET /api/communications/messages/search/` - поиск

### Polls
- `GET /api/communications/polls/` - список голосований
- `POST /api/communications/polls/` - создать голосование
- `POST /api/communications/polls/{id}/vote/` - проголосовать
- `POST /api/communications/polls/{id}/close_poll/` - закрыть

**Документация:** См. [api/README.md](api/README.md)

---

## WebSocket Events

### От клиента (action)
```json
{"action": "open_chat", "chat_id": 1}
{"action": "send_message", "chat_id": 1, "content": "Hello"}
{"action": "typing", "chat_id": 1}
{"action": "add_reaction", "message_id": 123, "emoji": "👍"}
```

### От сервера (type)
```json
{"type": "chat_message", "message": {...}}
{"type": "chat_user_typing", "user_id": 5, "chat_id": 1}
{"type": "chat_reaction_added", "message_id": 123, "emoji": "👍"}
```

**Детали:** См. [consumers.py](consumers.py) docstring

---

## Celery Tasks (опционально)

Если используете Celery, добавьте периодическую задачу:

```python
# celery.py
from celery import Celery
from celery.schedules import crontab

app = Celery('your_project')

app.conf.beat_schedule = {
    'cleanup-orphaned-attachments': {
        'task': 'communications.tasks.cleanup_orphaned_attachments',
        'schedule': crontab(hour='*/1'),  # Каждый час
    },
}
```

---

## Примеры использования

### Создание чата

```python
from communications.models import Chat
from django.contrib.auth import get_user_model

User = get_user_model()

# Личный чат
chat = Chat.objects.create(type='private')
chat.participants.add(user1, user2)

# Групповой чат
chat = Chat.objects.create(
    type='group',
    name='Команда разработки',
    created_by=request.user
)
chat.participants.add(user1, user2, user3)

# Чат привязанный к объекту (GenericFK)
from myapp.models import Project
project = Project.objects.get(id=1)

chat = Chat.objects.create(
    type='comments',
    context_object=project,  # GenericForeignKey
    name=f'Комментарии: {project.name}'
)
```

### Отправка сообщения

```python
from communications.models import Message

message = Message.objects.create(
    chat=chat,
    author=request.user,
    content='Привет всем!'
)
```

### Проверка прав доступа

```python
# В view
from rules.contrib.views import PermissionRequiredMixin

class ChatDetailView(PermissionRequiredMixin, DetailView):
    model = Chat
    permission_required = 'communications.can_view_chat'
```

---

## Миграция с других систем

Если у вас уже есть проектно-специфичные чаты, используйте:
1. GenericForeignKey для привязки к существующим моделям
2. `COMMUNICATIONS_PARTICIPANT_RESOLVER` для логики участников
3. Миграции данных через management команды

---

## Troubleshooting

### Ошибка импорта `common.image_utils`
**Решение:** Установите `COMMUNICATIONS_IMAGE_COMPRESSOR = None` в settings.py

### Ошибка импорта `employees.models`
**Решение:** Команда `verify_chat_migration` автоматически пропустит проверку

### WebSocket не работает
**Проверьте:**
1. ASGI_APPLICATION настроен
2. CHANNEL_LAYERS настроен
3. Redis запущен (для продакшена)
4. routing.py содержит websocket_urlpatterns

### Уведомления не приходят
**Проверьте:**
1. `django-notifications-hq` установлен
2. `COMMUNICATIONS_AUTO_NOTIFY = True`
3. `notifications` в INSTALLED_APPS

---

## Лицензия

MIT License

---

## Поддержка

- **Issues:** https://github.com/yourusername/django-communications/issues
- **Documentation:** https://github.com/yourusername/django-communications
