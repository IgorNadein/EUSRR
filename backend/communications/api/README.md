# Communications REST API

REST API для универсальной системы чатов Django.

## Структура

```
communications/api/
├── __init__.py          # Документация модуля
├── serializers.py       # DRF serializers (Chat, Message, Poll)
├── viewsets.py          # DRF ViewSets (CRUD операции)
└── urls.py              # URL routing с DRF router
```

## Установка

### В текущем проекте (уже настроено):

```python
# api/v1/urls.py
from communications.api.viewsets import ChatViewSet, MessageViewSet, PollViewSet

router.register(r"communications/chats", ChatViewSet, basename="chats")
router.register(r"communications/messages", MessageViewSet, basename="messages")
router.register(r"communications/polls", PollViewSet, basename="polls")
```

### Для standalone использования:

```python
# settings.py
INSTALLED_APPS = [
    'rest_framework',
    'communications',
]

# urls.py
from django.urls import path, include
from communications.api.urls import router as communications_router

urlpatterns = [
    path('api/communications/', include(communications_router.urls)),
]
```

## API Endpoints

### Chats
- `GET /api/v1/communications/chats/` - список чатов
- `GET /api/v1/communications/chats/{id}/` - детали чата
- `POST /api/v1/communications/chats/` - создать чат
- `POST /api/v1/communications/chats/{id}/pin/` - закрепить/открепить
- `POST /api/v1/communications/chats/{id}/notifications/` - вкл/выкл уведомления
- `GET /api/v1/communications/chats/{id}/messages/` - список сообщений (с автоотметкой)
- `GET /api/v1/communications/chats/{id}/messages_around/` - сообщения вокруг (с автоотметкой)

### Messages
- `GET /api/v1/communications/messages/` - список сообщений
- `GET /api/v1/communications/messages/{id}/` - детали сообщения
- `POST /api/v1/communications/messages/` - отправить сообщение
- `PATCH /api/v1/communications/messages/{id}/` - редактировать сообщение
- `DELETE /api/v1/communications/messages/{id}/` - удалить сообщение
- `POST /api/v1/communications/messages/{id}/forward/` - переслать
- `POST /api/v1/communications/messages/{id}/react/` - реакция
- `POST /api/v1/communications/messages/bulk_delete/` - массовое удаление
- `GET /api/v1/communications/messages/search/` - поиск

### Polls
- `GET /api/v1/communications/polls/` - список голосований
- `GET /api/v1/communications/polls/{id}/` - детали голосования
- `POST /api/v1/communications/polls/` - создать голосование
- `POST /api/v1/communications/polls/{id}/vote/` - проголосовать
- `POST /api/v1/communications/polls/{id}/close_poll/` - закрыть голосование

## Serializers

### Chat Serializers
- `ChatListSerializer` - облегченный список чатов
- `ChatDetailSerializer` - детальная информация о чате
- `ChatMembershipSerializer` - членство в чате
- `ChatUserSettingsSerializer` - настройки пользователя

### Message Serializers
- `MessageListSerializer` - список сообщений
- `MessageDetailSerializer` - детали сообщения
- `MessageCreateSerializer` - создание сообщения
- `MessageEditSerializer` - редактирование
- `MessageAttachmentSerializer` - вложения
- `MessageReactionSerializer` - реакции
- `ForwardMessageSerializer` - пересылка
- `BulkDeleteSerializer` - массовое удаление

### Poll Serializers
- `PollSerializer` - голосование
- `PollOptionSerializer` - варианты ответа

## Новые поля (GenericFK)

Все serializers поддерживают универсальную систему с GenericForeignKey:

```python
{
    "id": 1,
    "name": "Чат отдела",
    # NEW: универсальные поля
    "context_object_id": 5,           # ID связанного объекта
    "context_type": "department",     # Тип объекта
    "context_app": "employees",       # Приложение
    "flags": {"is_primary": true},    # JSON флаги
    "extra_data": {},                 # Дополнительные данные
    "include_all_users": false,       # Доступ для всех
    
    # DEPRECATED: для обратной совместимости
    "is_main": true,
    "department": 5
}
```

## Примеры использования

### Получить список чатов:
```python
import requests

response = requests.get(
    'http://localhost:8000/api/v1/communications/chats/',
    headers={'Authorization': 'Bearer <token>'}
)
chats = response.json()
```

### Отправить сообщение:
```python
response = requests.post(
    'http://localhost:8000/api/v1/communications/messages/',
    json={
        'chat': 1,
        'content': 'Привет!',
        'message_type': 'text'
    },
    headers={'Authorization': 'Bearer <token>'}
)
```

### Создать чат с GenericFK:
```python
from communications.api.serializers import ChatDetailSerializer
from communications.models import Chat
from employees.models import Department

dept = Department.objects.get(id=5)
chat = Chat.objects.create(
    name="Новый чат",
    type="department",
    context_object=dept,  # GenericFK
    flags={"is_primary": True}
)
```

## Тестирование

```bash
# System check
python manage.py check

# Запуск тестов
python test_phase3.py

# Unit-тесты (если настроены)
pytest communications/tests/
```

## История

- **11 марта 2026**: Перенесен из `api/v1/communications/` для автономности
- **Январь 2026**: Миграция с FBV на ViewSets
- **Фаза 3**: Добавлена поддержка GenericFK (context_object, flags, extra_data)

## Документация

- [Полная документация рефакторинга](../../docs/completed/API_REFACTORING_STANDALONE.md)
- [Фаза 3: GenericFK](../../docs/completed/CHAT_REFACTORING_PHASE3_COMPLETE.md)
- [Руководство по чатам](../../docs/guides/CHAT_REFACTORING_QUICKSTART.md)

## Поддержка

- Обратная совместимость: ✅ Сохранена для `department`, `is_main`
- Django: 5.2.4+
- DRF: 3.14+
- Python: 3.12+
