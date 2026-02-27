# Обновление Reply-сообщений при редактировании

## Проблема

Когда пользователь редактирует сообщение A, на которое уже ответили сообщением B, то в сообщении B остаётся старый текст из `reply_to` preview.

### Пример:

```
Сообщение #100 (автор: Игорь)
└─ "Оригинальный текст"

Сообщение #101 (автор: Мария, reply_to=100)
├─ [Reply Preview] → "Оригинальный текст"  ← это цитата
└─ "Согласна!"
```

Если отредактировать сообщение #100:
```
Сообщение #100
└─ "ИЗМЕНЕННЫЙ текст" ✓ (изменено)
```

То в сообщении #101 должен обновиться reply-preview:
```
Сообщение #101
├─ [Reply Preview] → "ИЗМЕНЕННЫЙ текст"  ← должно обновиться!
└─ "Согласна!"
```

## Решение

### 1. Backend: `edit_message` view

**Файл**: `backend/api/v1/communications/views.py`

```python
@csrf_protect
@login_required
@require_POST
def edit_message(request, message_id):
    # ... редактируем сообщение ...
    
    # Отправляем WebSocket уведомление о редактировании САМОГО сообщения
    channel_layer = get_channel_layer()
    payload = serialize_message(message)
    
    async_to_sync(channel_layer.group_send)(
        f'chat_{message.chat_id}',
        {
            'type': 'chat.message_edited',
            'chat_id': message.chat_id,
            'payload': payload
        }
    )
    
    # НОВОЕ: Находим все сообщения, которые ссылаются на это (reply_to)
    reply_messages = Message.objects.filter(
        reply_to=message,  # ← все сообщения, где reply_to указывает на отредактированное
        chat=message.chat
    ).select_related(
        'author',
        'reply_to',        # ← загружаем связанное сообщение (уже с новым content!)
        'reply_to__author',
        'forwarded_from_author',
        'poll'
    ).prefetch_related(
        'attachments',
        'reactions',
        'reactions__user',
        'poll__options'
    )
    
    # Отправляем обновления для каждого reply-сообщения
    for reply_msg in reply_messages:
        reply_payload = serialize_message(reply_msg)
        # reply_payload теперь содержит:
        # {
        #   "id": 101,
        #   "content": "Согласна!",
        #   "reply_to": {
        #     "id": 100,
        #     "content": "ИЗМЕНЕННЫЙ текст",  ← новый контент!
        #     "author_name": "Игорь"
        #   }
        # }
        
        async_to_sync(channel_layer.group_send)(
            f'chat_{message.chat_id}',
            {
                'type': 'chat.message_edited',
                'chat_id': message.chat_id,
                'payload': reply_payload
            }
        )
    
    return JsonResponse({'ok': True, 'message': payload})
```

### 2. Frontend: Полная перерисовка через MessageRenderer

**Файл**: `backend/static/js/components/messageEditing.js`

```javascript
function updateMessageInDOM(message, chatId) {
    const oldMessageEl = document.querySelector(`[data-message-id="${message.id}"]`);
    
    // MessageRenderer.buildMessageHtml генерирует полный HTML включая:
    // - reply_to preview с актуальным content
    // - attachments
    // - poll
    // - reactions
    const renderer = new MessageRenderer({...});
    const newMessageHtml = renderer.buildMessageHtml(message, isOwn);
    
    // Полная замена элемента
    oldMessageEl.replaceWith(newElement);
    
    // Реинициализация компонентов
    reinitMessageComponents(newElement, message.id, currentUserId);
}
```

**Файл**: `backend/static/js/components/messageRenderer.js`

```javascript
buildMessageHtml(msg, isOwn) {
    // ...
    
    // Reply preview использует msg.reply_to.content напрямую
    const replyHtml = msg.reply_to ? `
        <div class="reply-reference small mb-2" 
             style="border-left:3px solid var(--bs-primary);padding-left:8px;">
            <div class="fw-semibold">${msg.reply_to.author_name || 'Пользователь'}</div>
            <div class="text-truncate">${this.escapeHtml(msg.reply_to.content || '[файл]')}</div>
            <!--                             ^^^^^^^^^^^^^^^^^^^^ -->
            <!--                             Берётся из payload! -->
        </div>` : '';
    
    // ...
}
```

## Процесс обновления

```
User edits Message #100
  ↓
POST /api/v1/communications/messages/100/edit/
  ↓
Backend: edit_message()
  ├─ message.content = "ИЗМЕНЕННЫЙ текст"
  ├─ message.save()
  ├─ message = reload with prefetch (reply_to included)
  │
  ├─ Send WebSocket: message_edited (Message #100)
  │   payload.content = "ИЗМЕНЕННЫЙ текст"
  │
  └─ Find reply_messages = Message.objects.filter(reply_to=100)
      ├─ Found: Message #101
      ├─ reload #101 with prefetch (includes reply_to with NEW content!)
      └─ Send WebSocket: message_edited (Message #101)
          payload = {
            id: 101,
            content: "Согласна!",
            reply_to: {
              id: 100,
              content: "ИЗМЕНЕННЫЙ текст"  ← UPDATED!
            }
          }
  ↓
WebSocket → user_consumer.py
  ├─ Receives: message_edited (#100)
  └─ Receives: message_edited (#101)
  ↓
WebSocket → userWebSocket.js
  ├─ handleMessageUpdated() for #100
  │   └─ dispatchEvent('chat:message-edited', payload=#100)
  └─ handleMessageUpdated() for #101
      └─ dispatchEvent('chat:message-edited', payload=#101)
  ↓
messageEditing.js
  ├─ handleMessageEdited(#100)
  │   └─ updateMessageInDOM(#100) → full rerender
  │       └─ "ИЗМЕНЕННЫЙ текст" + "(изменено)"
  │
  └─ handleMessageEdited(#101)
      └─ updateMessageInDOM(#101) → full rerender
          └─ Reply preview shows "ИЗМЕНЕННЫЙ текст"  ✓
```

## Тестирование

### Шаг 1: Подготовка данных

```bash
cd backend
python test_reply_update.py
```

Это создаст:
- Сообщение A (оригинал)
- Сообщение B (ответ на A)

### Шаг 2: Открыть чат

1. Откройте чат с этими сообщениями
2. Откройте консоль браузера (F12)

### Шаг 3: Отредактировать сообщение A

1. Нажмите редактирование на сообщении A
2. Измените текст
3. Сохраните

### Шаг 4: Проверить логи

**Backend (terminal)**:
```
[EDIT_MSG] Message 100 edited, found 1 reply messages
[EDIT_MSG] Updating reply message 101 (reply_to.content='ИЗМЕНЕННЫЙ текст')
```

**Frontend (browser console)**:
```
[UserWebSocket] Received message: message_updated (id=100)
[UserWebSocket] Dispatching chat:message-edited event...
[MessageEditing] Message edited event received
[MessageEditing] message.id: 100

[UserWebSocket] Received message: message_updated (id=101)
[UserWebSocket] Dispatching chat:message-edited event...
[MessageEditing] Message edited event received
[MessageEditing] message.id: 101
[MessageEditing] message.reply_to: {id: 100, content: 'ИЗМЕНЕННЫЙ текст', ...}
```

### Шаг 5: Проверить UI

✅ Сообщение A: новый текст + "(изменено)"
✅ Сообщение B: reply-preview показывает **новый** текст из A

## Граничные случаи

### Множественные ответы

Если на сообщение A ответили 5 раз (сообщения B, C, D, E, F), то все 5 получат обновление:

```python
reply_messages = Message.objects.filter(reply_to=message)  # → 5 messages
for reply_msg in reply_messages:  # → 5 WebSocket events
    send message_edited
```

### Вложенные ответы (reply на reply)

```
Message #100 (A)
  └─ Message #101 (B, reply_to=100)
      └─ Message #102 (C, reply_to=101)
```

При редактировании #100:
- ✅ #101 обновится (reply_to=100)
- ❌ #102 НЕ обновится (reply_to=101, а не 100)

Это **правильное** поведение, так как #102 ссылается на #101, а не на #100.

### Редактирование в другом чате

```python
reply_messages = Message.objects.filter(
    reply_to=message,
    chat=message.chat  # ← только в этом же чате
)
```

Если теоретически reply_to может указывать на сообщение из другого чата (пересланное), то оно **не обновится**. Это безопасное поведение.

## Производительность

### Оптимизация: batch send

Текущая реализация:
```python
for reply_msg in reply_messages:  # N запросов
    send message_edited
```

Можно оптимизировать:
```python
reply_payloads = [serialize_message(m) for m in reply_messages]
async_to_sync(channel_layer.group_send)(
    f'chat_{message.chat_id}',
    {
        'type': 'chat.messages_batch_edited',
        'payloads': reply_payloads  # Одно событие с массивом
    }
)
```

Но для типичных случаев (1-3 ответа) текущая реализация достаточно эффективна.

## Изменённые файлы

1. ✅ `backend/api/v1/communications/views.py`
   - Добавлено: поиск reply_messages
   - Добавлено: отправка message_edited для каждого reply
   - Добавлено: логирование

2. ✅ `backend/static/js/components/userWebSocket.js`
   - Исправлено: dispatch events для messageEditing.js

3. ✅ `backend/static/js/components/messageEditing.js`
   - Используется: полная перерисовка через MessageRenderer

4. ✅ `backend/static/js/components/messageRenderer.js`
   - Использует: `msg.reply_to.content` для preview

## Итог

✅ При редактировании сообщения все ответы на него **автоматически обновляются**
✅ Reply-preview показывает актуальный контент
✅ Работает через существующую систему WebSocket events
✅ Использует полную перерисовку (гарантирует корректность)
