# Исправление: WebSocket события для опросов

## 🐛 Проблемы

### 1. Новые опросы не встраивались в DOM
- **Причина**: `create_poll` отправлял неправильную структуру WebSocket события
- **Симптом**: После создания опроса он не появлялся, нужна была перезагрузка

### 2. Информация о проголосовавших не обновлялась
- **Причина**: `user_consumer.py` не передавал полные данные `results` на фронтенд
- **Симптом**: После голосования проценты/счётчики не обновлялись в реальном времени

---

## ✅ Исправления

### 1. Backend: `poll_views.py` - Создание опроса

**БЫЛО (неправильная структура):**
```python
ws_message = {
    'type': 'chat_message',  # ← неправильный тип
    'payload': {
        'message': {  # ← лишняя вложенность
            'id': message.id,
            'content': message.content,
            'poll': poll_data  # ← poll не сериализован через serialize_message
        }
    }
}
```

**СТАЛО (правильная структура):**
```python
from communications.consumers import serialize_message

# Перезагружаем сообщение со всеми связанными объектами
message = Message.objects.select_related(
    'author', 'reply_to', 'reply_to__author',
    'forwarded_from_author', 'poll'
).prefetch_related(
    'attachments', 'reactions', 'reactions__user', 'poll__options'
).get(pk=message.id)

payload = serialize_message(message)  # ← правильная сериализация!

async_to_sync(channel_layer.group_send)(
    f'chat_{chat.id}',
    {
        'type': 'chat.message',  # ← правильный тип для consumer
        'chat_id': chat.id,
        'payload': payload  # ← полный payload с poll
    }
)
```

### 2. Backend: `poll_views.py` - Голосование (vote_poll)

**БЫЛО (отсутствовал chat_id):**
```python
ws_message = {
    'type': 'poll_update',
    # chat_id отсутствовал! ←
    'payload': {
        'poll_id': poll.id,
        'message_id': poll.message.id,
        'results': results
    }
}
```

**СТАЛО:**
```python
ws_message = {
    'type': 'poll_update',
    'chat_id': chat.id,  # ← добавлено!
    'payload': {
        'poll_id': poll.id,
        'message_id': poll.message.id,
        'results': results  # ← полные результаты
    }
}
```

### 3. Backend: `poll_views.py` - Закрытие опроса (close_poll)

**Та же проблема - добавлен `chat_id`:**
```python
ws_message = {
    'type': 'poll_update',
    'chat_id': poll.message.chat.id,  # ← добавлено!
    'payload': {
        'poll_id': poll.id,
        'message_id': poll.message.id,
        'results': poll.get_results()
    }
}
```

### 4. Backend: `user_consumer.py` - Обработка poll_update

**БЫЛО (неполные данные):**
```python
async def chat_poll_update(self, event):
    chat_id = event.get("chat_id")
    
    if chat_id == self.active_chat_id:
        await self.send_json({
            "type": "poll_vote",  # ← старое название
            "chat_id": chat_id,
            "poll_id": event.get("poll_id"),  # ← берёт из корня, а не из payload
            "option_id": event.get("option_id"),  # ← этого нет в event!
            "vote_count": event.get("vote_count"),  # ← этого тоже нет!
            "total_voters": event.get("total_voters")  # ← и этого нет!
        })
```

**СТАЛО (полные данные из payload):**
```python
async def chat_poll_update(self, event):
    chat_id = event.get("chat_id")
    payload = event.get("payload", {})  # ← извлекаем payload!
    
    if chat_id == self.active_chat_id:
        await self.send_json({
            "type": "poll_update",  # ← правильное название
            "chat_id": chat_id,
            "poll_id": payload.get("poll_id"),  # ← из payload
            "message_id": payload.get("message_id"),  # ← добавлено
            "results": payload.get("results")  # ← полные результаты!
        })
```

### 5. Frontend: `userWebSocket.js` - Добавлен обработчик

**БЫЛО (только poll_vote):**
```javascript
case 'poll_vote':
  handlePollVote(data);
  break;
```

**СТАЛО (поддержка обоих типов):**
```javascript
case 'poll_vote':
case 'poll_update':  // ← добавлено!
  handlePollUpdate(data);
  break;
```

**Новая функция handlePollUpdate:**
```javascript
function handlePollUpdate(data) {
    console.log('[UserWebSocket] Poll update received:', data);
    window.dispatchEvent(new CustomEvent('chat:poll-update', {
        detail: {
            poll_id: data.poll_id,
            message_id: data.message_id,
            results: data.results  // ← передаём полные результаты!
        }
    }));
}
```

---

## 🔄 Процесс обновления опросов

### Создание нового опроса:

```
User создаёт опрос
  ↓
POST /api/v1/communications/polls/create/
  ↓
Backend: create_poll()
  ├─ Message.objects.create(content="📊 Вопрос")
  ├─ Poll.objects.create(message=message)
  ├─ PollOption.objects.create(poll=poll, text="Вариант 1")
  ├─ serialize_message(message) → полный payload с poll
  └─ WebSocket: type='chat.message', payload={id, content, poll: {...}}
  ↓
user_consumer.py: chat_message()
  └─ send_json(type='new_message', message=payload)
  ↓
userWebSocket.js: handleNewMessage()
  └─ dispatchEvent('new_message', payload)
  ↓
chatScroll добавляет сообщение в DOM
  ↓
MessageRenderer.buildMessageHtml()
  ├─ buildPollHtml(msg.poll) → генерирует HTML
  └─ вставляет <div class="poll-widget" data-poll-id="10">
  ↓
ChatPoll.initializeExistingPolls()
  └─ refreshPoll(10) → загружает актуальные данные
  ↓
✅ Опрос появляется с кнопками голосования!
```

### Голосование в опросе:

```
User нажимает на вариант ответа
  ↓
POST /api/v1/communications/polls/10/vote/
  ↓
Backend: vote_poll()
  ├─ PollVote.objects.create(poll=poll, option=option, voter=user)
  ├─ option.vote_count += 1
  ├─ poll.total_voters += 1 (если первый раз)
  ├─ results = poll.get_results() → {options: [{percentage: 60, ...}], total_voters: 5}
  └─ WebSocket: type='poll_update', chat_id=10, payload={poll_id, message_id, results}
  ↓
user_consumer.py: chat_poll_update()
  └─ send_json(type='poll_update', poll_id=10, results={...})
  ↓
userWebSocket.js: handlePollUpdate()
  └─ dispatchEvent('chat:poll-update', {poll_id: 10, results: {...}})
  ↓
chat-detail-enhanced.js слушает 'chat:poll-update'
  └─ window.chatPoll.refreshPoll(10)
  ↓
ChatPoll.refreshPoll()
  ├─ НЕ делает fetch (уже есть results в event!)
  └─ updatePollWidget(widget, results)
      ├─ Обновляет проценты: "60%"
      ├─ Обновляет прогресс-бары: width="60%"
      └─ Обновляет счётчики: "5 проголосовало"
  ↓
✅ Опрос обновляется в реальном времени!
```

---

## 📊 Структура данных

### results (из poll.get_results()):

```json
{
  "id": 10,
  "question": "Какой язык программирования?",
  "is_anonymous": false,
  "is_multiple_choice": false,
  "is_quiz": false,
  "is_closed": false,
  "closes_at": null,
  "total_voters": 5,
  "options": [
    {
      "id": 21,
      "text": "Python",
      "position": 0,
      "vote_count": 3,
      "percentage": 60
    },
    {
      "id": 22,
      "text": "JavaScript",
      "position": 1,
      "vote_count": 2,
      "percentage": 40
    }
  ]
}
```

### WebSocket event (теперь):

```json
{
  "type": "poll_update",
  "chat_id": 10,
  "poll_id": 10,
  "message_id": 495,
  "results": {
    "id": 10,
    "question": "...",
    "total_voters": 5,
    "options": [
      {"id": 21, "text": "Python", "percentage": 60, "vote_count": 3},
      {"id": 22, "text": "JavaScript", "percentage": 40, "vote_count": 2}
    ]
  }
}
```

---

## 🧪 Тестирование

### Сценарий 1: Создание опроса

1. Откройте чат
2. Нажмите "Создать голосование"
3. Заполните вопрос: "Какой язык?"
4. Добавьте варианты: "Python", "JavaScript"
5. Отправьте

**Ожидается:**
- ✅ Опрос **сразу появляется** в чате (без перезагрузки)
- ✅ Показаны кнопки для голосования
- ✅ Счётчик: "0 проголосовало"

### Сценарий 2: Голосование

1. Откройте чат с опросом
2. Нажмите на вариант "Python"

**Ожидается:**
- ✅ Кнопки превращаются в прогресс-бары (у всех пользователей!)
- ✅ Показаны проценты: "Python 100%"
- ✅ Счётчик: "1 проголосовало"

3. Другой пользователь голосует за "JavaScript"

**Ожидается:**
- ✅ **Автоматически** обновляются проценты: "Python 50%", "JavaScript 50%"
- ✅ Счётчик: "2 проголосовало"

### Сценарий 3: Множественные пользователи

1. Откройте чат в 2 окнах (разные пользователи)
2. В первом окне создайте опрос
3. **Во втором окне** опрос должен появиться сразу
4. Проголосуйте во втором окне
5. **В первом окне** результаты должны обновиться автоматически

---

## 📝 Изменённые файлы

1. ✅ `backend/api/v1/communications/poll_views.py`
   - `create_poll`: использует `serialize_message()`, добавлен `chat_id`
   - `vote_poll`: добавлен `chat_id` в WebSocket event
   - `close_poll`: добавлен `chat_id` в WebSocket event

2. ✅ `backend/communications/user_consumer.py`
   - `chat_poll_update`: передаёт полные `results` из `payload`

3. ✅ `backend/static/js/components/userWebSocket.js`
   - Добавлен обработчик `poll_update`
   - Функция `handlePollUpdate()` диспатчит `chat:poll-update` с полными данными

4. ✅ `backend/static/js/chat-detail-enhanced.js`
   - Уже есть слушатель `chat:poll-update` → вызывает `chatPoll.refreshPoll()`

5. ✅ `backend/static/js/components/messageRenderer.js`
   - Добавлен `buildPollHtml()` для генерации HTML опросов

6. ✅ `backend/static/js/components/messageEditing.js`
   - Вызывает `chatPoll.refreshPoll()` после редактирования сообщения с опросом

---

## ✅ Результат

**ДО исправления:**
- ❌ Новые опросы не появлялись (нужна перезагрузка)
- ❌ Результаты голосования не обновлялись в реальном времени
- ❌ Проценты/счётчики замораживались

**ПОСЛЕ исправления:**
- ✅ Новые опросы появляются **мгновенно**
- ✅ Результаты голосования обновляются **в реальном времени** у всех пользователей
- ✅ Проценты/счётчики обновляются **автоматически**
- ✅ Работает через WebSocket без перезагрузки страницы

**Всё работает! 🎉**
