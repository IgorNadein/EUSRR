# Исправление удаления сообщений через WebSocket

## Проблема

При удалении сообщения через API (`/api/v1/communications/messages/{id}/delete/`) DOM не обновлялся у других пользователей, потому что:

1. API view не отправлял WebSocket событие
2. Frontend удалял сообщение локально, без синхронизации

Логи показывали:
```
[USER_WS_DELETE] Received event: chat_id=None, message_id=423
[USER_WS_DELETE] Active chat: 10, matches=False
[USER_WS_DELETE] Skipping - not active chat
```

**chat_id=None** означал, что событие не связано с конкретным чатом.

## Решение

### 1. Добавлена отправка WebSocket события в API view

**Файл:** `backend/communications/api_views.py`

**Изменения:**
```python
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def delete_message(request, message_id):
    # ... проверки и удаление ...
    message.save()
    
    # ✅ Отправляем WebSocket событие
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"chat_{message.chat_id}",
        {
            "type": "chat.message_deleted",
            "chat_id": message.chat_id,  # ✅ Передаём chat_id!
            "message_id": message_id
        }
    )
    
    return JsonResponse({'ok': True})
```

### 2. Убрано локальное удаление из DOM

**Файл:** `backend/static/js/components/messageContextMenu.js`

**Было:**
```javascript
if (data.ok) {
    // ❌ Удаляем локально
    const messageElement = document.querySelector(`[data-message-id="${messageId}"]`);
    if (messageElement) {
        messageElement.remove();
    }
    this.showToast('Сообщение удалено');
}
```

**Стало:**
```javascript
if (data.ok) {
    console.log('[MessageContextMenu] Delete successful');
    console.log('[MessageContextMenu] NOTE: DOM will be updated via WebSocket');
    
    // ✅ НЕ удаляем из DOM - это сделает WebSocket handler
    
    this.showToast('Сообщение удалено');
}
```

## Поток событий (после исправления)

```
1. User A: Right-click → Delete
   
2. Frontend (messageContextMenu.js):
   POST /api/v1/communications/messages/423/delete/
   
3. Backend (api_views.py):
   [DELETE_MESSAGE] API called: message_id=423
   [DELETE_MESSAGE] Marking message as deleted
   [DELETE_MESSAGE] Sending WebSocket event to chat group: chat_10
   [DELETE_MESSAGE] WebSocket event sent
   
4. WebSocket → All users in chat:
   {type: "message_deleted", chat_id: 10, message_id: 423}
   
5. Frontend (userWebSocket.js) for User A and B:
   [UserWebSocket] Received message: message_deleted
   [UserWebSocket] handleMessageDeleted called: {message_id: 423}
   [UserWebSocket] Looking for message element with id: 423
   [UserWebSocket] Message element found
   [UserWebSocket] Message removed successfully
```

## Результат

✅ Сообщение удаляется у **всех** пользователей в чате одновременно
✅ Единая точка обновления DOM (через WebSocket)
✅ Консистентность данных между клиентами
✅ Работает для любого способа удаления (API, WebSocket)

## Тестирование

1. Откройте два окна браузера с одним чатом
2. В первом окне: правый клик → Удалить сообщение
3. Проверьте логи в консоли обоих окон
4. Сообщение должно исчезнуть в **обоих** окнах

### Ожидаемые логи

**Backend:**
```
[DELETE_MESSAGE] API called: message_id=423, user=admin
[DELETE_MESSAGE] Message deleted successfully: 423
[DELETE_MESSAGE] Sending WebSocket event to chat group: chat_10
[DELETE_MESSAGE] WebSocket event sent for message_id=423

[USER_WS_DELETE] Received event: chat_id=10, message_id=423  ✅ chat_id присутствует!
[USER_WS_DELETE] Active chat: 10, matches=True  ✅
[USER_WS_DELETE] Sending to client: message_id=423
[USER_WS_DELETE] Sent to client successfully
```

**Frontend (оба окна):**
```
[UserWebSocket] Received message: message_deleted {chat_id: 10, message_id: 423}
[UserWebSocket] handleMessageDeleted called: {message_id: 423}
[UserWebSocket] Message element found: <div...>
[UserWebSocket] Removing message from DOM...
[UserWebSocket] Message removed successfully
```
