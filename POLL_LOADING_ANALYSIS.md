# Анализ: Загрузка и встраивание опросов (polls) в DOM

## 🔍 Текущая архитектура

### Backend: Сериализация опросов

**Файл**: `backend/communications/consumers.py`

```python
def serialize_message(m: Message) -> dict:
    # ...
    
    # Голосование
    if hasattr(m, 'poll'):
        poll = m.poll
        poll_data = {
            "id": poll.id,
            "question": poll.question,
            "is_anonymous": poll.is_anonymous,
            "is_multiple_choice": poll.is_multiple_choice,
            "is_quiz": poll.is_quiz,
            "is_closed": poll.is_closed,
            "closes_at": poll.closes_at.isoformat() if poll.closes_at else None,
            "total_voters": poll.total_voters,
            "options": []
        }
        for option in poll.options.all():
            poll_data["options"].append({
                "id": option.id,
                "text": option.text,
                "position": option.position,
                "vote_count": option.vote_count,
                "percentage": 0  # Будет пересчитан на клиенте
            })
        data["poll"] = poll_data
```

✅ **Опросы загружаются** в payload сообщения.

---

### Frontend: Генерация HTML

#### ❌ ПРОБЛЕМА: MessageRenderer НЕ генерировал HTML для опросов

**Файл**: `backend/static/js/components/messageRenderer.js`

**ДО исправления:**
```javascript
buildMessageHtml(msg, isOwn) {
    const attachmentsHtml = msg.attachments?.length ? 
        msg.attachments.map(att => this.buildAttachmentHtml(att)).join('') : '';

    // Опросы НЕ рендерились!

    return `
        <div class="bubble">
            ${msg.content}
            ${attachmentsHtml}
            <!-- ← poll отсутствует! -->
        </div>
    `;
}
```

**ПОСЛЕ исправления:**
```javascript
buildMessageHtml(msg, isOwn) {
    const attachmentsHtml = msg.attachments?.length ? 
        msg.attachments.map(att => this.buildAttachmentHtml(att)).join('') : '';

    // ✅ Добавлена генерация HTML для опроса
    const pollHtml = msg.poll ? this.buildPollHtml(msg.poll) : '';

    return `
        <div class="bubble">
            ${msg.content}
            ${attachmentsHtml}
            ${pollHtml}  ← добавлено!
        </div>
    `;
}

// ✅ Новый метод
buildPollHtml(poll) {
    if (!poll || !poll.id) return '';
    
    const totalVotes = poll.total_voters || 0;
    const isClosed = poll.is_closed || false;
    
    return `
        <div class="poll-widget mt-2" data-poll-id="${poll.id}">
            <div class="poll-question mb-3">
                <strong>${this.escapeHtml(poll.question)}</strong>
            </div>
            <div class="poll-options">
                ${poll.options?.map(option => `
                    <div class="poll-option mb-2" data-option-id="${option.id}">
                        <button type="button" class="btn btn-outline-secondary btn-poll-option w-100 text-start" 
                                data-option-id="${option.id}">
                            ${this.escapeHtml(option.text)}
                        </button>
                    </div>
                `).join('') || ''}
            </div>
            <div class="poll-footer mt-3">
                <div class="small text-muted">
                    ${totalVotes} проголосовало
                    ${poll.is_anonymous ? ' • Анонимное' : ''}
                    ${poll.is_multiple_choice ? ' • Множественный выбор' : ''}
                    ${isClosed ? ' • Закрыто' : ''}
                </div>
            </div>
        </div>`;
}
```

---

### Frontend: Инициализация опросов

**Файл**: `backend/static/js/components/chatPoll.js`

```javascript
class ChatPoll {
    initializeExistingPolls() {
        const pollWidgets = document.querySelectorAll('.poll-widget[data-poll-id]');
        pollWidgets.forEach((widget) => {
            const pollId = widget.dataset.pollId;
            this.refreshPoll(pollId, widget);
        });
    }

    async refreshPoll(pollId, pollWidget = null) {
        const widget = pollWidget || document.querySelector(`[data-poll-id="${pollId}"]`);
        if (!widget) return;

        // Загружает актуальные данные с сервера
        const results = await this.fetchPollResults(pollId);
        if (!results) return;

        // Обновляет HTML опроса (результаты, проценты и т.д.)
        this.updatePollWidget(widget, results);
    }
}
```

✅ `ChatPoll` обрабатывает существующие опросы через `initializeExistingPolls()`.

---

### Frontend: Реинициализация после редактирования

**Файл**: `backend/static/js/components/messageEditing.js`

**ДО исправления:**
```javascript
function reinitMessageComponents(messageEl, messageId, currentUserId) {
    // 4. Голосования (если есть)
    const pollEl = messageEl.querySelector('[data-poll-id]');
    if (pollEl && window.chatPoll) {
        const pollId = pollEl.dataset.pollId;
        // ❌ Только логирование, НЕ инициализация!
        console.log('[MessageEditing] ✓ Poll detected, id:', pollId);
    }
}
```

**ПОСЛЕ исправления:**
```javascript
function reinitMessageComponents(messageEl, messageId, currentUserId) {
    // 4. Голосования (если есть)
    const pollEl = messageEl.querySelector('[data-poll-id]');
    if (pollEl && window.chatPoll) {
        const pollId = pollEl.dataset.pollId;
        console.log('[MessageEditing] Refreshing poll:', pollId);
        // ✅ Явно вызываем refreshPoll для обновления состояния
        window.chatPoll.refreshPoll(pollId, pollEl);
        console.log('[MessageEditing] ✓ Poll reinitialized, id:', pollId);
    }
}
```

---

## 🔄 Процесс загрузки и встраивания

### 1. Первоначальная загрузка сообщений

```
User opens chat
  ↓
Django renders chat_detail.html
  ↓
JavaScript загружает начальные сообщения через API
  ↓
Для каждого сообщения:
  ├─ MessageRenderer.buildMessageHtml(msg) создаёт HTML
  │   ├─ msg.content → текст
  │   ├─ msg.attachments → вложения
  │   ├─ msg.reply_to → ответ на сообщение
  │   └─ msg.poll → ТЕПЕРЬ ГЕНЕРИРУЕТСЯ! ✅
  │       └─ buildPollHtml(poll) → <div class="poll-widget" data-poll-id="...">
  ↓
HTML вставляется в DOM
  ↓
ChatPoll.initializeExistingPolls() находит все [data-poll-id]
  └─ Для каждого: refreshPoll(pollId)
      └─ Загружает актуальные данные с сервера
      └─ Обновляет проценты, результаты
```

### 2. Создание нового опроса через UI

```
User clicks "Создать голосование"
  ↓
Modal открывается
  ↓
User заполняет вопрос, варианты ответов
  ↓
ChatPoll.submitPoll() → POST /api/v1/communications/polls/create/
  ↓
Backend создаёт Poll + PollOption
  ↓
WebSocket → new_message event (с poll в payload)
  ↓
userWebSocket.js → dispatchEvent('new_message')
  ↓
chatScroll добавляет новое сообщение в DOM
  ↓
ChatPoll.initializeExistingPolls() или refreshPoll()
```

### 3. Редактирование сообщения с опросом

```
User edits message with poll
  ↓
POST /api/v1/communications/messages/{id}/edit/
  ↓
Backend: message.save() + prefetch poll/poll__options
  ↓
serialize_message(message) → включает poll data
  ↓
WebSocket → message_edited event
  ↓
userWebSocket.js → dispatchEvent('chat:message-edited')
  ↓
messageEditing.js: handleMessageEdited
  ├─ MessageRenderer.buildMessageHtml(message) → ТЕПЕРЬ включает poll! ✅
  │   └─ buildPollHtml(message.poll) → генерирует HTML
  ├─ oldMessageEl.replaceWith(newMessageEl)
  └─ reinitMessageComponents(newMessageEl)
      └─ window.chatPoll.refreshPoll(pollId, pollEl) ✅
          └─ Обновляет состояние опроса
```

---

## 📊 Структура данных опроса

### Backend (serialize_message)

```json
{
  "id": 495,
  "content": "Выберите вариант",
  "poll": {
    "id": 10,
    "question": "Какой язык программирования вы предпочитаете?",
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
}
```

### Frontend (buildPollHtml)

```html
<div class="poll-widget mt-2" data-poll-id="10">
  <div class="poll-question mb-3">
    <strong>Какой язык программирования вы предпочитаете?</strong>
  </div>
  <div class="poll-options">
    <div class="poll-option mb-2" data-option-id="21">
      <button type="button" class="btn btn-outline-secondary btn-poll-option w-100 text-start" 
              data-option-id="21">
        Python
      </button>
    </div>
    <div class="poll-option mb-2" data-option-id="22">
      <button type="button" class="btn btn-outline-secondary btn-poll-option w-100 text-start" 
              data-option-id="22">
        JavaScript
      </button>
    </div>
  </div>
  <div class="poll-footer mt-3">
    <div class="small text-muted">
      5 проголосовало
    </div>
  </div>
</div>
```

---

## ✅ Исправления

### 1. MessageRenderer теперь генерирует HTML для опросов
- Добавлен метод `buildPollHtml(poll)`
- В `buildMessageHtml` добавлена строка `${pollHtml}`

### 2. reinitMessageComponents явно инициализирует опросы
- Вызывает `window.chatPoll.refreshPoll(pollId, pollEl)`
- Это загружает актуальные данные и обновляет UI

### 3. Полная поддержка редактирования
- При редактировании сообщения с опросом он не теряется
- Опрос корректно отображается после замены DOM

---

## 🧪 Тестирование

### Сценарий 1: Создание опроса
1. Откройте чат
2. Нажмите "Создать голосование"
3. Заполните вопрос и варианты
4. Отправьте
5. **Ожидается**: Опрос появляется в чате с кнопками для голосования

### Сценарий 2: Редактирование сообщения с опросом
1. Создайте сообщение с опросом
2. Отредактируйте **текст** сообщения (сам опрос редактировать нельзя)
3. **Ожидается**: 
   - Текст обновлён ✅
   - Опрос остался на месте ✅
   - Кнопки опроса работают ✅

### Сценарий 3: Голосование
1. Откройте сообщение с опросом
2. Нажмите на вариант ответа
3. **Ожидается**:
   - Голос зарегистрирован
   - Опрос обновлён с результатами
   - Показаны проценты

---

## 📝 Итог

✅ **Опросы загружаются** через `serialize_message` в payload  
✅ **MessageRenderer генерирует HTML** через `buildPollHtml()`  
✅ **ChatPoll инициализирует** через `refreshPoll()`  
✅ **При редактировании опросы сохраняются** через `reinitMessageComponents()`  

**Все проблемы решены!** 🎉
