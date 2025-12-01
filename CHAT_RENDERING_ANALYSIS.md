# Анализ архитектуры рендеринга страницы чата

## Обзор текущей архитектуры

Страница чата состоит из серверного (Django) и клиентского (JavaScript) компонентов, работающих вместе для обеспечения real-time обновлений.

---

## 1. Серверный рендеринг (Django)

### `communications/views.py` → `ChatDetailView`

**Ответственность:**
- Начальная загрузка данных чата и сообщений
- Проверка прав доступа пользователя
- Подготовка контекста для шаблона

**Ключевые методы:**

```python
get_queryset()
├─ Фильтрует чаты по правам доступа
├─ global / department / private / group
└─ membership-based access

get_context_data()
├─ Загружает последние N сообщений (по умолчанию 50)
├─ messages = chat.messages.order_by("-created_at")[:50]
├─ Определяет has_more (есть ли еще история)
├─ Загружает участников
├─ Вычисляет last_read_at
├─ Находит first_unread_id
└─ Проверяет can_send_messages

post()
└─ Обрабатывает отправку сообщений через форму (legacy)
```

**Контекст для шаблона:**
```python
{
    'chat': Chat,
    'messages': [...],              # Последние 50 сообщений
    'messages_has_more': bool,
    'messages_oldest_id': int,
    'messages_oldest_ts': int,
    'messages_page_size': 50,
    'participants': QuerySet,
    'last_read_at': datetime,
    'first_unread_id': int,
    'can_send_messages': bool,
    'is_announcement_creator': bool
}
```

---

## 2. Шаблон HTML

### `templates/communications/chat_detail.html`

**Структура DOM:**

```
.chat-root
└─ .chat-col
   ├─ .section-header           (заголовок чата)
   │  ├─ Иконка + название
   │  └─ Кнопки управления
   │
   └─ .chat-box (article.card)
      ├─ .alert (предупреждения)
      ├─ #scrollBtn               (кнопка "вниз")
      │
      ├─ #chatScroll              (контейнер сообщений)
      │  │  data-me-id="{{ user.id }}"
      │  │  data-chat-id="{{ chat.id }}"
      │  │  data-oldest-id="{{ messages_oldest_id }}"
      │  │  data-has-more="1"
      │  │
      │  ├─ .history-loader       (лоадер истории)
      │  │
      │  └─ {% for message in messages %}
      │     ├─ .day-divider       (разделитель дня)
      │     └─ .msg               (сообщение)
      │        ├─ .mini-ava       (аватар)
      │        ├─ .small          (имя + время)
      │        ├─ .bubble         (тело сообщения)
      │        │  ├─ .forwarded-indicator
      │        │  ├─ текст
      │        │  ├─ .poll-widget
      │        │  └─ .message-attachments
      │        └─ .message-reactions-wrapper
      │
      └─ .chat-composer           (композер)
         ├─ #typing               (индикатор "печатает...")
         └─ #chatForm
            ├─ .message-field
            │  ├─ #attachmentDropdown
            │  ├─ #emojiDropdown
            │  ├─ #id_content       (textarea)
            │  └─ .btn-send
            └─ #attachmentPreview
```

**Data-атрибуты контейнера:**
```html
<div id="chatScroll"
     data-me-id="{{ user.id }}"
     data-chat-id="{{ chat.id }}"
     data-fetch-url="/api/v1/chats/{{ chat.pk }}/messages/"
     data-page-size="50"
     data-oldest-id="{{ messages_oldest_id }}"
     data-oldest-ts="{{ messages_oldest_ts }}"
     data-has-more="1"
     data-last-read-ts="{{ last_read_at|date:'U' }}000">
```

---

## 3. JavaScript модули

### 3.1 Инициализация (base.html)

**Порядок загрузки:**

```javascript
1. initUserWebSocket() (base.html)
   └─ ws://host/ws/
   └─ Подключается СРАЗУ на всех страницах
   
2. {% if chat %} Только на странице чата:
   
   initChatMarkRead()
   ├─ Отслеживает скролл
   ├─ Находит последнее непрочитанное
   └─ Отправляет mark_read
   
3. Дополнительные модули (chat_detail.html):
   
   chatComposer.js
   ├─ Обработка формы отправки
   ├─ Загрузка файлов
   └─ Индикатор "печатает..."
   
   chatHistoryLoader.js
   ├─ IntersectionObserver
   ├─ Подгрузка истории
   └─ Сохранение позиции скролла
   
   chat-detail-enhanced.js
   ├─ MessageReactions
   ├─ MessageContextMenu
   ├─ MessageSelection
   ├─ ChatPoll
   └─ messageEditing
```

---

### 3.2 userWebSocket.js (НОВЫЙ)

**Ответственность:**
- Единое WebSocket соединение
- Получение новых сообщений
- Отправка сообщений
- Реакции, редактирование, удаление
- Индикатор "печатает..."

**Ключевые методы:**

```javascript
initUserWebSocket(options)
├─ connectWebSocket()
│  └─ ws = new WebSocket('ws://host/ws/')
│
├─ handleMessage(data)
│  ├─ case 'new_message':      handleNewMessage()
│  ├─ case 'list_update':      handleListUpdate()
│  ├─ case 'reaction_added':   handleReactionAdded()
│  └─ case 'typing_start':     handleTypingStart()
│
└─ API:
   ├─ openChat(chatId, loadHistory)
   ├─ sendMessage(content)
   ├─ addReaction(messageId, emoji)
   └─ markRead(chatId)
```

**Обработка нового сообщения:**
```javascript
handleNewMessage(data) {
  const { message } = data;
  
  // 1. Проверка разделителя дня
  const msgDay = formatDay(message.created_ts);
  if (msgDay !== lastDay) {
    scrollEl.appendChild(createDayDivider(msgDay));
  }
  
  // 2. Создание элемента сообщения
  const msgEl = createMessageElement(message, {
    meId, avatarMap, profileUrl, detailUrlTemplate
  });
  
  // 3. Добавление в DOM
  scrollEl.appendChild(msgEl);
  
  // 4. Автоскролл (если внизу)
  if (atBottom() || message.author_id === meId) {
    scrollToBottom();
  }
  
  // 5. Инициализация реакций
  window.dispatchEvent(new CustomEvent('chat:message-added', {
    detail: { messageElement: msgEl, messageId: message.id }
  }));
}
```

---

### 3.3 chatMessageTemplates.js

**Ответственность:**
- Создание HTML элементов сообщений
- Форматирование времени/даты
- Рендеринг вложений, пересылок, ответов, голосований

**Ключевые функции:**

```javascript
createMessageElement(msg, options)
├─ Создает обертку .msg
├─ data-id, data-message-id, data-ts, data-author-id
├─ data-reactions (JSON)
│
├─ Форматирует контент:
│  ├─ Имя автора + время
│  ├─ Аватар
│  ├─ .bubble
│  │  ├─ .forwarded-indicator
│  │  ├─ .reply-indicator
│  │  ├─ Текст (с linebreaks)
│  │  ├─ .poll-widget
│  │  └─ .message-attachments
│  └─ .message-reactions-wrapper
│
└─ Возвращает HTMLElement

createDayDivider(dateStr)
└─ <div class="day-divider"><span>DD.MM.YYYY</span></div>

formatTime(ts) → "HH:MM"
formatDay(ts) → "DD.MM.YYYY"
```

**Структура сообщения:**
```html
<div class="d-flex mb-3 msg justify-content-start"
     data-id="123"
     data-message-id="123"
     data-ts="1733059200000"
     data-author-id="456"
     data-reactions='{"👍":{"count":2,"users":[1,2]}}'>
  
  <a href="/employees/456/"><span class="mini-ava">...</span></a>
  
  <div class="d-flex flex-column">
    <div class="small text-secondary">
      <a href="/employees/456/">Иван Иванов</a> · 12:30
    </div>
    
    <div class="bubble bubble-other">
      <!-- Переслано от -->
      <div class="forwarded-indicator">...</div>
      
      <!-- Ответ на -->
      <div class="reply-indicator">...</div>
      
      <!-- Текст -->
      Привет, как дела?
      
      <!-- Голосование -->
      <div class="poll-widget">...</div>
      
      <!-- Вложения -->
      <div class="message-attachments">...</div>
    </div>
    
    <!-- Реакции (заполняется JS) -->
    <div class="message-reactions-wrapper"></div>
  </div>
</div>
```

---

### 3.4 chatHistoryLoader.js

**Ответственность:**
- Подгрузка старых сообщений при скролле вверх
- Сохранение позиции скролла после загрузки
- Управление состоянием "has_more"

**Архитектура:**

```javascript
initChatHistoryLoader()
├─ Читает data-атрибуты:
│  ├─ data-fetch-url
│  ├─ data-oldest-ts
│  ├─ data-has-more
│  └─ data-page-size
│
├─ IntersectionObserver на первом сообщении
│  └─ При появлении в viewport → загружаем
│
└─ loadMoreMessages()
   ├─ fetch('/api/v1/chats/{id}/messages/?before={ts}')
   ├─ Получаем старые сообщения
   ├─ Сохраняем текущую высоту scrollHeight
   ├─ Вставляем в начало chatScroll
   ├─ Восстанавливаем scrollTop
   └─ Обновляем data-oldest-ts, data-has-more
```

**Последовательность загрузки истории:**

```
Пользователь скроллит вверх
         ↓
IntersectionObserver срабатывает
         ↓
const beforeTs = scrollEl.dataset.oldestTs;
fetch(`/api/v1/chats/${chatId}/messages/?before=${beforeTs}&limit=50`)
         ↓
response.json() → { messages: [...], has_more: bool }
         ↓
const oldHeight = scrollEl.scrollHeight;
messages.reverse().forEach(msg => {
  const dayDiv = createDayDivider(msg);
  const msgEl = createMessageElement(msg);
  scrollEl.insertBefore(msgEl, firstMessage);
});
         ↓
const newHeight = scrollEl.scrollHeight;
scrollEl.scrollTop = newHeight - oldHeight;
         ↓
scrollEl.dataset.oldestTs = messages[0].created_ts;
scrollEl.dataset.hasMore = response.has_more;
```

---

### 3.5 chatMarkRead.js

**Ответственность:**
- Отслеживание прочитанных сообщений
- Автоматическая отметка при скролле
- API для ручной отметки

**Архитектура:**

```javascript
initChatMarkRead(options)
├─ IntersectionObserver на чужих сообщениях
│  └─ Когда сообщение видно → markAsRead()
│
├─ observeLastForeign(msgEl)
│  └─ Наблюдает за последним чужим сообщением
│
├─ markRead()
│  ├─ fetch('/communications/chats/{id}/mark-read/')
│  └─ window.dispatchEvent('chat:read', { chatId })
│
└─ API:
   ├─ atBottom() → bool
   ├─ autoscroll(instant)
   └─ markRead()
```

---

### 3.6 chatComposer.js

**Ответственность:**
- Обработка отправки сообщений
- Управление файлами (загрузка через API)
- Автоматическое изменение размера textarea
- Индикатор "печатает..."

**Архитектура:**

```javascript
initChatComposer()
├─ Обработка submit формы
│  ├─ Отключена (сообщения через WebSocket)
│  └─ Файлы через API: POST /api/v1/upload-message/
│
├─ Загрузка файлов:
│  ├─ #attachDocument → documentInput.click()
│  ├─ #attachImage → imageInput.click()
│  ├─ #attachCamera → cameraInput.click()
│  └─ #attachAudio → audioInput.click()
│
├─ onChange file input:
│  ├─ Превью в #attachmentPreview
│  ├─ FormData + fetch(uploadUrl)
│  └─ Добавляет message в DOM (pending)
│
├─ Textarea input:
│  ├─ Auto-expand (textareaAutoExpand.js)
│  └─ Throttled typing indicator (WebSocket)
│
└─ Emoji picker:
   └─ <emoji-picker> (CDN)
```

---

### 3.7 chat-detail-enhanced.js

**Ответственность:**
- Инициализация UI компонентов
- Реакции, контекстное меню, выделение
- Голосования
- MutationObserver для новых сообщений

**Архитектура:**

```javascript
(function() {
  const reactions = new MessageReactions();
  const contextMenu = new MessageContextMenu();
  const messageSelection = new MessageSelection();
  const chatPoll = new ChatPoll();
  initMessageEditing();
  
  // Инициализация существующих сообщений
  initMessageReactions();
  
  // Наблюдатель за новыми
  const messageObserver = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        if (node.dataset && node.dataset.messageId) {
          // Инициализируем реакции
          // Подключаем контекстное меню
        }
      });
    });
  });
  
  messageObserver.observe(chatScroll, {
    childList: true,
    subtree: true
  });
})();
```

---

## 4. Поток данных

### 4.1 Начальная загрузка страницы

```
HTTP GET /communications/chats/123/
         ↓
ChatDetailView.get()
├─ get_queryset() → проверка доступа
├─ get_context_data()
│  ├─ messages = последние 50
│  ├─ has_more = True/False
│  ├─ last_read_at
│  └─ first_unread_id
└─ render(chat_detail.html)
         ↓
HTML с {% for message in messages %}
         ↓
JS: base.html
├─ initUserWebSocket() → ws.connect()
│  └─ send({ action: 'open_chat', chat_id: 123 })
│
├─ initChatMarkRead()
│  └─ IntersectionObserver на сообщениях
│
└─ {% block extra_js %}
   ├─ chatComposer.js
   ├─ chatHistoryLoader.js
   └─ chat-detail-enhanced.js
         ↓
initMessageReactions()
└─ Для каждого .msg:
   ├─ Парсит data-reactions
   ├─ Рендерит кнопки реакций
   └─ Подключает обработчики
```

---

### 4.2 Получение нового сообщения

```
Другой пользователь отправляет сообщение
         ↓
Backend: UserConsumer._handle_send_message()
├─ message = Message.objects.create(...)
├─ msg_data = serialize_message(message)
└─ channel_layer.group_send('chat_123', {
     type: 'chat_message',
     chat_id: 123,
     payload: msg_data
   })
         ↓
Frontend: userWebSocket.handleMessage()
├─ case 'new_message':
│  └─ handleNewMessage(data)
│     ├─ createDayDivider() (если нужно)
│     ├─ createMessageElement(message)
│     ├─ scrollEl.appendChild(msgEl)
│     ├─ scrollToBottom() (если внизу)
│     └─ dispatch 'chat:message-added'
│
└─ case 'list_update':
   └─ badgeManager.incrementChat(chatId)
         ↓
MutationObserver в chat-detail-enhanced.js
├─ Обнаруживает новый .msg
├─ Инициализирует реакции
└─ Подключает контекстное меню
         ↓
IntersectionObserver в chatMarkRead.js
└─ Когда сообщение видно → markAsRead()
```

---

### 4.3 Подгрузка истории

```
Пользователь скроллит к началу чата
         ↓
IntersectionObserver (chatHistoryLoader.js)
└─ Первое сообщение появилось в viewport
         ↓
loadMoreMessages()
├─ const beforeTs = scrollEl.dataset.oldestTs;
├─ fetch(`/api/v1/chats/123/messages/?before=${beforeTs}&limit=50`)
│  └─ Backend: ChatMessagesViewSet.list()
│     └─ messages = Message.objects.filter(
│           chat_id=123,
│           created_at__lt=beforeTs
│         ).order_by('-created_at')[:50]
├─ const oldHeight = scrollEl.scrollHeight;
├─ messages.reverse().forEach(msg => {
│    scrollEl.insertBefore(createMessageElement(msg), firstMsg);
│  });
├─ scrollEl.scrollTop = scrollEl.scrollHeight - oldHeight;
└─ scrollEl.dataset.oldestTs = messages[0].created_ts;
```

---

## 5. Проблемы текущей архитектуры

### 5.1 Дублирование логики

**Проблема:**
- Серверный рендеринг в `chat_detail.html` (Django template)
- Клиентский рендеринг в `chatMessageTemplates.js`
- Два разных HTML шаблона для одного и того же

**Пример:**
```django
{# Django template #}
<div class="bubble">
  {% if message.is_forwarded %}
    <div class="forwarded-indicator">...</div>
  {% endif %}
  {{ message.content|linebreaksbr }}
</div>
```

```javascript
// JavaScript
const bubble = `
  <div class="bubble">
    ${msg.is_forwarded ? '<div class="forwarded-indicator">...</div>' : ''}
    ${text}
  </div>`;
```

**Последствия:**
- Сложность поддержки (изменения в двух местах)
- Риск рассинхронизации
- Дублирование кода

---

### 5.2 Смешанная ответственность

**Проблема:**
- `userWebSocket.js` создает DOM элементы
- `chat-detail-enhanced.js` инициализирует компоненты
- `chatMarkRead.js` отслеживает видимость
- Нет четкого разделения ответственности

**Последствия:**
- Сложность отладки
- Трудно понять, где что происходит
- Зависимости между модулями

---

### 5.3 Imperative DOM manipulation

**Проблема:**
- Прямое создание HTML строк
- `innerHTML`, `appendChild`, `insertBefore`
- Нет виртуального DOM
- Нет реактивности

**Последствия:**
- Сложность управления состоянием
- Проблемы с производительностью при большом количестве сообщений
- Трудно оптимизировать рендеринг

---

### 5.4 Состояние разбросано

**Проблема:**
- `data-` атрибуты на DOM элементах
- `window` глобальные переменные
- Состояние в замыканиях модулей
- Нет единого источника правды

**Пример:**
```javascript
// Состояние в разных местах
scrollEl.dataset.oldestTs = '1733059200000';
scrollEl.dataset.hasMore = '1';
window.chatPoll = chatPoll;
window.chatWebSocketApi = userWs;
const state = { activeChatId: 123 }; // в замыкании
```

---

### 5.5 Отсутствие компонентного подхода

**Проблема:**
- Монолитные скрипты
- Нет переиспользуемых компонентов
- Сложно тестировать

**Последствия:**
- Трудно расширять функциональность
- Дублирование логики
- Сложность рефакторинга

---

## 6. Рекомендации по рефакторингу

### 6.1 Унифицировать рендеринг

**Предложение:**
- Использовать только клиентский рендеринг
- Сервер отдает только JSON с данными
- Один шаблон для всех сообщений

**Архитектура:**
```
Backend:
└─ API endpoint: GET /api/v1/chats/123/
   └─ { chat: {...}, messages: [...] }

Frontend:
└─ renderChat(chatData)
   ├─ renderHeader(chat)
   ├─ renderMessages(messages)
   └─ renderComposer(chat)
```

---

### 6.2 Компонентный подход

**Предложение:**
- React, Vue, или Lit (Web Components)
- Компоненты: Message, MessageList, Composer
- Props и state management

**Структура:**
```
<ChatPage>
  ├─ <ChatHeader chat={chat} />
  ├─ <MessageList 
  │    messages={messages}
  │    onLoadMore={loadMore}
  │  />
  └─ <Composer 
       onSend={sendMessage}
       canSend={permissions.canSend}
     />
```

---

### 6.3 Централизованное состояние

**Предложение:**
- Redux, Zustand, или Pinia
- Единый store для состояния чата

**State shape:**
```javascript
{
  chat: { id, name, type, ... },
  messages: {
    byId: {
      '123': { id, content, author, ... },
      '124': { ... }
    },
    allIds: [123, 124, ...],
    hasMore: true,
    oldestId: 123
  },
  ui: {
    isLoadingHistory: false,
    activeMessageId: null
  }
}
```

---

### 6.4 Оптимизация рендеринга

**Предложение:**
- Виртуальный скролл (react-window, vue-virtual-scroller)
- Lazy loading изображений
- Memo/PureComponent для сообщений

---

### 6.5 TypeScript

**Предложение:**
- Типизация для безопасности
- Интерфейсы для Message, Chat, User

```typescript
interface Message {
  id: number;
  content: string;
  author: User;
  created_at: string;
  is_forwarded: boolean;
  attachments: Attachment[];
  reactions: Reaction[];
}
```

---

## 7. Зависимости модулей

```
base.html
├─ userWebSocket.js
│  └─ chatMessageTemplates.js
│
├─ chatMarkRead.js
│
└─ chatAvatarMap.js

chat_detail.html
├─ chatComposer.js
│  └─ chatFileUpload.js
│
├─ chatHistoryLoader.js
│  └─ chatMessageTemplates.js
│
└─ chat-detail-enhanced.js
   ├─ messageReactions.js
   ├─ messageContextMenu.js
   ├─ messageSelection.js
   ├─ chatPoll.js
   └─ messageEditing.js
```

---

## 8. API endpoints

### Чаты

```
GET  /communications/chats/123/           → HTML страница (view)
GET  /api/v1/chats/123/                   → JSON чата
GET  /api/v1/chats/123/messages/          → JSON сообщений
POST /api/v1/upload-message/              → Загрузка с файлами
POST /communications/chats/123/mark-read/ → Отметка прочитанного
```

### WebSocket

```
ws://host/ws/
├─ open_chat        → Открыть чат
├─ close_chat       → Закрыть чат
├─ send_message     → Отправить сообщение
├─ add_reaction     → Добавить реакцию
└─ typing           → Индикатор печати
```

---

## Итого

**Сильные стороны:**
- ✅ Real-time через WebSocket
- ✅ Модульная архитектура
- ✅ Разделение UI компонентов

**Слабые стороны:**
- ❌ Дублирование рендеринга (Django + JS)
- ❌ Imperative DOM manipulation
- ❌ Разбросанное состояние
- ❌ Нет компонентного подхода
- ❌ Сложность поддержки

**Приоритеты рефакторинга:**
1. Унифицировать рендеринг (только клиент)
2. Внедрить компонентный фреймворк
3. Централизовать состояние
4. Оптимизировать виртуальный скролл
5. Добавить TypeScript
