# Отладка удаления сообщений

## Проблема
При удалении сообщения из чата DOM не обновляется. Нужно проверить, как события удаления передаются через WebSocket.

## Добавленная отладка

### 1. API View (api_views.py)

**Метод: `delete_message()`**

Логи в `/api/v1/communications/messages/{id}/delete/`:

```python
[DELETE_MESSAGE] API called: message_id=X, user=username
[DELETE_MESSAGE] Message found: chat_id=Y, author=author_name
[DELETE_MESSAGE] User is author, can delete
# или
[DELETE_MESSAGE] User has moderator role: admin/moderator
# или
[DELETE_MESSAGE] Permission denied for user username  # WARNING

[DELETE_MESSAGE] Marking message as deleted
[DELETE_MESSAGE] Message deleted successfully: X
```

### 2. WebSocket Consumer (consumers.py)

**Метод: `_handle_delete_message()`**

Обработка запроса на удаление через WS:

```python
[WS_DELETE] Received delete request: message_id=X, user=username
[WS_DELETE] No message_id provided  # WARNING (если не передан ID)
[WS_DELETE] Delete blocked: announcement chat  # WARNING (для объявлений)
[WS_DELETE] Calling _delete_message
[WS_DELETE] Delete result: True/False
[WS_DELETE] Broadcasting to group: chat_{chat_id}
[WS_DELETE] Broadcast sent for message_id=X
```

**Метод: `_delete_message()` (database operation)**

```python
[WS_DELETE_DB] Looking for message: id=X, author=username
[WS_DELETE_DB] Message found: chat_id=Y
[WS_DELETE_DB] Message marked as deleted: X
# или
[WS_DELETE_DB] Message not found or wrong author: X  # WARNING
```

**Метод: `chat_message_deleted()` (broadcast handler)**

Отправка события клиентам:

```python
[WS_DELETE] chat_message_deleted handler called: {event_data}
[WS_DELETE] Sent to client: message_id=X
```

### 3. User WebSocket Consumer (user_consumer.py)

**Метод: `chat_message_deleted()`**

Обработка события для user WebSocket:

```python
[USER_WS_DELETE] Received event: chat_id=X, message_id=Y
[USER_WS_DELETE] Active chat: Z, matches=True/False
[USER_WS_DELETE] Sending to client: message_id=Y
[USER_WS_DELETE] Sent to client successfully
# или
[USER_WS_DELETE] Skipping - not active chat
```

### 4. Frontend - WebSocket Handler (userWebSocket.js)

**Метод: `handleMessage()`**

Общий обработчик входящих WS сообщений:

```javascript
[UserWebSocket] Received message: message_deleted {data}
[UserWebSocket] Handling message_deleted event
```

**Метод: `handleMessageDeleted()`**

Обработка события удаления:

```javascript
[UserWebSocket] handleMessageDeleted called: {data}
[UserWebSocket] No message_id in delete event  // WARNING
[UserWebSocket] Looking for message element with id: X
[UserWebSocket] Scroll element: chatScroll
[UserWebSocket] Message element found: <div...>
[UserWebSocket] Message element classes: d-flex mb-3 msg...
[UserWebSocket] Removing message from DOM...
[UserWebSocket] Message removed successfully
// или
[UserWebSocket] Message element NOT found for id: X  // WARNING
[UserWebSocket] Available messages: [id1, id2, id3...]
```

### 5. Frontend - Context Menu (messageContextMenu.js)

**Метод: `handleDelete()`**

Удаление через API (правый клик → Удалить):

```javascript
[MessageContextMenu] handleDelete called: X
[MessageContextMenu] Delete cancelled by user
// или
[MessageContextMenu] Sending DELETE request to: /api/v1/...
[MessageContextMenu] CSRF token: present/missing
[MessageContextMenu] Response status: 200
[MessageContextMenu] Response ok: true
[MessageContextMenu] Response data: {ok: true}
[MessageContextMenu] Delete successful, removing from DOM
[MessageContextMenu] Message element found: true
[MessageContextMenu] Removing message element
[MessageContextMenu] Message element removed from DOM
[MessageContextMenu] Toast shown
```

## Путь события при удалении

### Сценарий 1: Удаление через API (Context Menu)

```
1. User: Right-click → Delete
2. Frontend (messageContextMenu.js):
   [MessageContextMenu] handleDelete called
   POST /api/v1/communications/messages/{id}/delete/
   
3. Backend (api_views.py):
   [DELETE_MESSAGE] API called
   [DELETE_MESSAGE] Message found
   [DELETE_MESSAGE] User is author, can delete
   [DELETE_MESSAGE] Marking message as deleted
   [DELETE_MESSAGE] Message deleted successfully
   
4. Frontend (messageContextMenu.js):
   [MessageContextMenu] Delete successful, removing from DOM
   [MessageContextMenu] Message element removed from DOM
   
5. ❌ ПРОБЛЕМА: WebSocket событие НЕ отправляется!
   API view НЕ уведомляет через WebSocket
```

### Сценарий 2: Удаление через WebSocket (если бы работало)

```
1. Frontend → WebSocket: {action: "delete_message", message_id: X}
2. Backend (consumers.py):
   [WS_DELETE] Received delete request
   [WS_DELETE_DB] Looking for message
   [WS_DELETE_DB] Message marked as deleted
   [WS_DELETE] Broadcasting to group
   
3. Backend → All clients in chat:
   {type: "message_deleted", message_id: X}
   
4. Frontend (userWebSocket.js):
   [UserWebSocket] Received message: message_deleted
   [UserWebSocket] Message element found
   [UserWebSocket] Message removed successfully
```

## Обнаруженная проблема

### ❌ API View не отправляет WebSocket события

Файл: `backend/communications/api_views.py`
Метод: `delete_message()`

**Проблема:**
```python
def delete_message(request, message_id):
    # ... удаляет сообщение из БД ...
    message.is_deleted = True
    message.save()
    return JsonResponse({'ok': True})
    # ❌ Нет отправки через WebSocket!
```

**Должно быть:**
```python
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def delete_message(request, message_id):
    # ... удаляет сообщение ...
    message.is_deleted = True
    message.save()
    
    # ✅ Отправляем событие через WebSocket
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"chat_{message.chat_id}",
        {
            "type": "chat.message_deleted",
            "chat_id": message.chat_id,
            "message_id": message_id
        }
    )
    
    return JsonResponse({'ok': True})
```

## Решение

Нужно добавить отправку WebSocket события в `api_views.delete_message()`:

1. Импортировать `channel_layer` и `async_to_sync`
2. После `message.save()` отправить событие в группу чата
3. Убрать удаление из DOM в `messageContextMenu.handleDelete()` - пусть обрабатывается через WS

Тогда:
- Любой пользователь в чате увидит удаление в реальном времени
- Код будет консистентным (одно место обновления DOM)
- Будет работать для всех способов удаления (API, WS)

## Как проверить

1. Откройте два окна браузера с одним чатом
2. Откройте DevTools Console в обоих
3. В первом окне: правый клик → Удалить сообщение
4. Смотрите логи:

**Окно 1 (где удаляли):**
```
[MessageContextMenu] handleDelete called: 123
[MessageContextMenu] Sending DELETE request to: ...
[MessageContextMenu] Response status: 200
[MessageContextMenu] Delete successful, removing from DOM
[MessageContextMenu] Message element removed from DOM
```

**Окно 2 (второй пользователь):**
```
❌ Ничего не происходит - нет WS события!
```

**После исправления (Окно 2):**
```
✅ [UserWebSocket] Received message: message_deleted
✅ [UserWebSocket] handleMessageDeleted called: {message_id: 123}
✅ [UserWebSocket] Message element found
✅ [UserWebSocket] Message removed successfully
```

## Backend логи (Docker/Terminal)

Запустите сервер с отладкой:
```bash
python manage.py runserver 9000
```

При удалении сообщения должны появиться:
```
[DELETE_MESSAGE] API called: message_id=123, user=admin
[DELETE_MESSAGE] Message found: chat_id=5, author=admin
[DELETE_MESSAGE] User is author, can delete
[DELETE_MESSAGE] Marking message as deleted
[DELETE_MESSAGE] Message deleted successfully: 123
```

Если используете WebSocket для удаления:
```
[WS_DELETE] Received delete request: message_id=123, user=admin
[WS_DELETE_DB] Looking for message: id=123, author=admin
[WS_DELETE_DB] Message found: chat_id=5
[WS_DELETE_DB] Message marked as deleted: 123
[WS_DELETE] Broadcasting to group: chat_5
[WS_DELETE] Broadcast sent for message_id=123
```
