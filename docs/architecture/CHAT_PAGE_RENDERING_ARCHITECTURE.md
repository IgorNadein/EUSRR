# Архитектура рендеринга и наполнения страницы чата

## 📋 Оглавление
1. [Общая схема](#общая-схема)
2. [Серверная часть (Backend)](#серверная-часть-backend)
3. [Шаблон страницы (Template)](#шаблон-страницы-template)
4. [JavaScript инициализация](#javascript-инициализация)
5. [WebSocket соединение](#websocket-соединение)
6. [Рендеринг сообщений](#рендеринг-сообщений)
7. [Поток данных](#поток-данных)

---

## 🎯 Общая схема

Страница чата работает по следующей архитектуре:

```
HTTP Request → Django View → HTML Template → DOM Ready → WebSocket Connect → Load Messages
                    ↓              ↓              ↓              ↓                  ↓
              Context Data   Initial HTML    Init JS       Real-time        Render to DOM
```

---

## 🔧 Серверная часть (Backend)

### 1. `ChatDetailView` (communications/views.py)

**Класс:** `ChatDetailView(LoginRequiredMixin, DetailView, FormView)`

**Ответственность:**
- Проверка прав доступа пользователя к чату
- Подготовка контекста для шаблона
- Установка заголовков для отключения кэширования

#### Ключевые методы:

```python
def get_object(self):
    """Получает объект чата с проверкой прав доступа"""
    # Фильтрует по типу чата: global/department/private/group
    # Проверяет membership для приватных чатов
```

```python
def get_context_data(self, **kwargs):
    """Подготавливает контекст для шаблона"""
    # 1. Проверка доступа через _user_has_access()
    # 2. Загрузка сообщений (последние 50, в обратном порядке)
    # 3. Определение has_more (есть ли еще история)
    # 4. Вычисление last_read_at и first_unread_id
    # 5. Проверка прав на отправку сообщений
```

**Контекст, передаваемый в шаблон:**
```python
{
    'chat': Chat,                    # Объект чата
    'messages': [...],               # Последние 50 сообщений (УСТАРЕЛО - не рендерятся)
    'messages_has_more': bool,       # Есть ли еще история
    'messages_oldest_id': int,       # ID самого старого сообщения
    'messages_oldest_ts': int,       # Timestamp самого старого сообщения
    'messages_page_size': 50,        # Размер страницы
    'participants': QuerySet,        # Участники чата
    'last_read_at': datetime,        # Время последнего прочтения
    'first_unread_id': int,          # ID первого непрочитанного
    'can_send_messages': bool,       # Может ли отправлять сообщения
    'is_announcement_creator': bool  # Создатель объявления
}
```

#### Отключение кэширования:
```python
def dispatch(self, request, *args, **kwargs):
    response = super().dispatch(request, *args, **kwargs)
    response['Cache-Control'] = 'no-cache, no-store, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    response['Expires'] = '0'
    return response
```

---

## 🖼️ Шаблон страницы (Template)

### `templates/communications/chat_detail.html`

#### Структура DOM:

```html
<div class="container chat-root" id="chatDetailApp" data-chat-id="..." data-user-id="...">
  <div class="row gx-0">
    <div class="col-12 chat-col">
      
      <!-- 1. Заголовок чата -->
      <div class="section-header">
        <!-- Иконка, название, кнопки управления -->
      </div>
      
      <!-- 2. Корпус чата -->
      <article class="card chat-box">
        
        <!-- 2.1 Предупреждения (блокировка, etc) -->
        <div class="alert">...</div>
        
        <!-- 2.2 Кнопка "вниз" -->
        <button id="scrollBtn" class="scroll-to-bottom">...</button>
        
        <!-- 2.3 Контейнер сообщений -->
        <div id="chatScroll" class="chat-scroll" 
             data-me-id="..."
             data-chat-id="..."
             data-fetch-url="..."
             data-oldest-id="..."
             data-has-more="...">
          
          <!-- Индикатор загрузки истории (при скролле вверх) -->
          <div class="history-loader d-none">...</div>
          
          <!-- Индикатор первоначальной загрузки -->
          <div class="initial-loader" id="initialLoader">
            <div class="spinner-border">...</div>
            <p>Загружаем сообщения...</p>
          </div>
          
          <!-- Сообщения добавляются через JavaScript -->
        </div>
        
        <!-- 2.4 Индикатор "печатает..." -->
        <div id="typing" class="d-none">...</div>
        
        <!-- 2.5 Композер (форма ввода) -->
        <div class="chat-composer">
          <form id="chatForm">
            <!-- Кнопки вложений, эмодзи -->
            <!-- Поле ввода textarea -->
            <!-- Кнопка отправки -->
          </form>
        </div>
        
      </article>
    </div>
  </div>
</div>
```

#### Data-атрибуты контейнера:

```html
<div id="chatDetailApp"
     data-chat-id="{{ chat.id }}"
     data-user-id="{{ user.id }}"
     data-user-name="{{ user.get_full_name }}"
     data-user-avatar="{{ user.avatar.url }}"
     data-upload-url="{% url 'api:v1:upload_message' %}"
     data-messages-url="{% url 'api:v1:chat_messages' chat.pk %}"
     data-mark-read-url="{% url 'communications:chat_mark_read' chat.pk %}"
     data-edit-url-template="/api/v1/communications/messages/{id}/edit/">
```

**Важно:** Сообщения из контекста `messages` больше НЕ рендерятся в шаблоне!  
Вместо этого используется **WebSocket для загрузки initial_messages**.

---

## ⚙️ JavaScript инициализация

### `static/js/pages/chatDetail.js`

**Главный файл инициализации страницы чата.**

#### Этапы инициализации:

```javascript
// 1. Загрузка модулей
const modules = await Promise.all([
  import('../components/chatMarkRead.js'),
  import('../components/chatComposer.js'),
  import('../components/chatHistoryLoader.js'),
  import('../components/chatFormManager.js'),
  import('../components/messageRenderer.js'),
  import('../components/initialMessagesLoader.js')  // Не используется
]);

// 2. Ожидание DOM Ready
document.addEventListener('DOMContentLoaded', initWhenReady);

// 3. Чтение конфигурации из data-атрибутов
const config = {
  chatId: Number(appContainer.dataset.chatId),
  userId: Number(appContainer.dataset.userId),
  uploadUrl: appContainer.dataset.uploadUrl,
  messagesUrl: appContainer.dataset.messagesUrl,
  // ... и другие
};

// 4. Ожидание готовности WebSocket
waitForWebSocket().then((userWs) => {
  initializeComponents(config, userWs);
});
```

#### Инициализация компонентов:

```javascript
function initializeComponents(config, userWs) {
  // 1. FormManager - управление формой
  const formManager = initChatFormManager({ ... });
  
  // 2. MarkRead - отметка прочитанных
  const markReadApi = initChatMarkRead({ ... });
  
  // 3. Composer - композер сообщений
  const composer = initChatComposer({ ... });
  
  // 4. HistoryLoader - загрузка старых сообщений
  const historyLoader = initChatHistoryLoader({ ... });
  
  // 5. MessageRenderer - рендеринг сообщений
  const messageRenderer = new MessageRenderer({ ... });
  
  // 6. Конфигурация WebSocket
  userWs.configure({
    scrollContainerId: 'chatScroll',
    messageRenderer: messageRenderer,
    markReadApi: markReadApi,
    // ...
  });
  
  // 7. Открытие чата в WebSocket
  userWs.openChat(config.chatId, true);  // true = загрузить историю
}
```

---

## 🌐 WebSocket соединение

### `static/js/components/userWebSocket.js`

**Единое WebSocket соединение для всех real-time обновлений.**

#### Инициализация в base.html:

```javascript
// templates/base.html
const userWs = initUserWebSocket({
  userId: {{ user.id }},
  badgeManager: badgeManager,
  onListUpdate: (data) => { /* ... */ }
});

window.userWebSocket = userWs;

// Уведомляем модули о готовности
window.dispatchEvent(new CustomEvent('user:ws-ready', {
  detail: { api: userWs }
}));
```

#### Подключение:

```javascript
const proto = location.protocol === 'https:' ? 'wss' : 'ws';
const wsUrl = `${proto}://${location.host}/ws/`;
const ws = new WebSocket(wsUrl);
```

#### Открытие чата:

```javascript
function openChat(chatId, loadHistory = false) {
  send({
    action: 'open_chat',
    chat_id: chatId,
    load_history: loadHistory
  });
}
```

---

## 📨 Загрузка сообщений через WebSocket

### Backend: `communications/consumers.py`

#### `ChatConsumer.connect()`:

```python
async def connect(self):
    # 1. Проверка аутентификации
    user = self.scope.get("user")
    
    # 2. Проверка прав доступа к чату
    chat = await self._get_chat(self.chat_id)
    if not await self._user_can_access(chat, user):
        await self.close(code=4403)
        return
    
    # 3. Подключение к группе
    await self.channel_layer.group_add(self.group_name, self.channel_name)
    await self.accept()
    
    # 4. Отправка начальной истории
    await self._send_initial_messages()
    
    # 5. Отметка как прочитанное
    await self._mark_read(self.chat, user)
    
    # 6. Запуск ping цикла
    self.ping_task = asyncio.create_task(self._ping_loop())
```

#### `_send_initial_messages()`:

```python
async def _send_initial_messages(self):
    """Отправить начальную историю сообщений при подключении"""
    messages = await self._get_initial_messages(self.chat_id, limit=50)
    
    await self.send_json({
        "type": "initial_messages",
        "messages": messages
    })

@database_sync_to_async
def _get_initial_messages(self, chat_id: int, limit: int = 50):
    """Получить последние N сообщений из чата"""
    messages = Message.objects.filter(
        chat_id=chat_id
    ).select_related(
        'author'
    ).prefetch_related(
        'attachments',
        'reactions__user'
    ).order_by('-created_at')[:limit]
    
    # Возвращаем в прямом порядке (старые -> новые)
    return [serialize_message(msg) for msg in reversed(list(messages))]
```

#### Формат сообщения:

```python
def serialize_message(m: Message) -> dict:
    return {
        "id": m.id,
        "chat_id": m.chat_id,
        "author_id": m.author_id,
        "author_name": m.author.get_full_name() or m.author.username,
        "avatar": m.author.avatar.url if hasattr(m.author, 'avatar') and m.author.avatar else None,
        "content": m.content,
        "created_ts": int(m.created_at.timestamp() * 1000),
        "is_edited": m.is_edited,
        "edited_at": m.edited_at.isoformat() if m.edited_at else None,
        "attachments": [
            {
                "id": att.id,
                "file_url": att.file.url if att.file else None,
                "file_name": att.file.name.split('/')[-1] if att.file else "file",
                "file_type": att.file_type or "unknown"
            }
            for att in m.attachments.all()
        ],
        "reactions_summary": m.get_reactions_summary(),
        "is_forwarded": m.is_forwarded,
        "forwarded_from": { ... } if m.is_forwarded else None,
        "reply_to": { ... } if m.reply_to else None,
        "poll": { ... } if hasattr(m, 'poll') else None,
    }
```

---

## 🎨 Рендеринг сообщений

### `static/js/components/messageRenderer.js`

#### Класс `MessageRenderer`:

```javascript
class MessageRenderer {
  constructor(config) {
    this.containerId = config.containerId;
    this.currentUserId = config.currentUserId;
    this.currentUserAvatar = config.currentUserAvatar;
    this.profileUrl = config.profileUrl;
    this.detailUrlTemplate = config.detailUrlTemplate;
  }
  
  /**
   * Рендерит массив сообщений (с разделителями дней)
   */
  renderMessages(messages) {
    const container = document.getElementById(this.containerId);
    
    let lastDay = null;
    messages.forEach(msg => {
      // Добавляем разделитель дня если нужно
      const msgDate = new Date(msg.created_ts);
      const msgDay = this.formatDay(msgDate);
      
      if (msgDay !== lastDay) {
        this.addDayDivider(msgDay, container);
        lastDay = msgDay;
      }
      
      this.renderMessage(msg, container);
    });
  }
  
  /**
   * Рендерит одно сообщение
   */
  renderMessage(msg, container) {
    // Проверка на дубликаты
    const existingMessage = container.querySelector(`[data-message-id="${msg.id}"]`);
    if (existingMessage) {
      console.log('Message already exists, skipping:', msg.id);
      return;
    }
    
    const isOwn = msg.author_id === this.currentUserId;
    const messageHtml = this.buildMessageHtml(msg, isOwn);
    
    // Добавляем в конец контейнера
    container.insertAdjacentHTML('beforeend', messageHtml);
  }
}
```

#### Структура HTML сообщения:

```html
<div class="d-flex mb-3 msg"
     data-id="123"
     data-message-id="123"
     data-ts="1701734400000"
     data-author-id="5"
     data-is-edited="false"
     data-reactions='{"👍": 2, "❤️": 1}'>
  
  <!-- Аватар (только для чужих сообщений слева) -->
  <a class="me-2" href="/employees/5/">
    <span class="mini-ava border">
      <img src="/media/avatars/user.jpg" alt="">
    </span>
  </a>
  
  <div class="d-flex flex-column">
    <!-- Имя и время -->
    <div class="small text-secondary">
      <a href="/employees/5/">Иван Иванов</a> · <time>12:30</time>
    </div>
    
    <!-- Bubble с содержимым -->
    <div class="bubble bubble-other">
      
      <!-- Индикатор пересылки (если есть) -->
      <div class="forwarded-indicator">...</div>
      
      <!-- Ответ на сообщение (если есть) -->
      <div class="reply-reference">...</div>
      
      <!-- Текст сообщения -->
      Привет, как дела?
      
      <!-- Индикатор редактирования -->
      <span class="message-edited-indicator">(изменено)</span>
      
      <!-- Голосование (если есть) -->
      <div class="poll-widget">...</div>
      
      <!-- Вложения (если есть) -->
      <div class="message-attachments">...</div>
    </div>
    
    <!-- Реакции -->
    <div class="message-reactions-wrapper">...</div>
  </div>
  
  <!-- Аватар справа для своих сообщений -->
  <a class="ms-2" href="/employees/profile/">...</a>
</div>
```

---

## 🔄 Поток данных

### 1. Начальная загрузка страницы

```
┌─────────────────────────────────────────────────────────────────┐
│ HTTP GET /communications/chats/123/                             │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ ChatDetailView.get()                                            │
│ ├─ get_queryset() → Проверка доступа                           │
│ ├─ get_context_data()                                           │
│ │  ├─ messages = последние 50 (НЕ ИСПОЛЬЗУЕТСЯ)                │
│ │  ├─ has_more = True/False                                     │
│ │  ├─ last_read_at                                              │
│ │  └─ first_unread_id                                           │
│ └─ render(chat_detail.html)                                     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ HTML с пустым контейнером #chatScroll                           │
│ + индикатор загрузки #initialLoader                             │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ JS: DOMContentLoaded                                            │
│ ├─ chatDetail.js → initWhenReady()                              │
│ ├─ Чтение config из data-атрибутов                             │
│ └─ waitForWebSocket()                                           │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ base.html → initUserWebSocket()                                 │
│ ├─ ws = new WebSocket('ws://host/ws/')                          │
│ └─ dispatchEvent('user:ws-ready')                               │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ chatDetail.js → initializeComponents()                          │
│ ├─ FormManager                                                  │
│ ├─ MarkRead                                                     │
│ ├─ Composer                                                     │
│ ├─ HistoryLoader                                                │
│ ├─ MessageRenderer                                              │
│ └─ userWs.openChat(chatId, true)                                │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ WebSocket → { action: 'open_chat', chat_id: 123 }              │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ Backend: ChatConsumer.connect()                                 │
│ ├─ _send_initial_messages()                                     │
│ │  └─ _get_initial_messages(limit=50)                           │
│ └─ send_json({ type: 'initial_messages', messages: [...] })     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ userWebSocket.js → handleInitialMessages()                      │
│ └─ messageRenderer.renderMessage() для каждого сообщения        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ messageRenderer.js → renderMessage()                            │
│ ├─ Проверка дубликатов                                          │
│ ├─ Добавление разделителей дней                                 │
│ ├─ buildMessageHtml()                                           │
│ └─ container.insertAdjacentHTML('beforeend', html)              │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ DOM обновлён → сообщения видны пользователю                     │
│ ├─ Скролл вниз                                                  │
│ ├─ Удаление #initialLoader                                      │
│ ├─ dispatchEvent('chat:initial-messages-loaded')                │
│ └─ Инициализация poll виджетов                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 2. Получение нового сообщения

```
┌─────────────────────────────────────────────────────────────────┐
│ Другой пользователь отправляет сообщение                        │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ Backend: ChatConsumer → channel_layer.group_send()              │
│ → broadcast в chat_123                                          │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ WebSocket → { type: 'new_message', message: {...} }            │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ userWebSocket.js → handleNewMessage()                           │
│ └─ messageRenderer.renderMessage(message)                       │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ DOM обновлён → новое сообщение появилось в чате                 │
│ ├─ Автоскролл (если внизу)                                      │
│ └─ Отметка как прочитанное (если в viewport)                    │
└─────────────────────────────────────────────────────────────────┘
```

### 3. Загрузка истории (скролл вверх)

```
┌─────────────────────────────────────────────────────────────────┐
│ Пользователь скроллит вверх                                     │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ chatHistoryLoader.js → IntersectionObserver срабатывает         │
│ └─ loadMoreMessages()                                           │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ API Request: GET /api/v1/chats/123/messages/                    │
│ ?before_id=456&limit=50                                         │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ Backend: ChatMessagesAPIView.get()                              │
│ └─ Возвращает { messages: [...], has_more: true }              │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ chatHistoryLoader.js → прикрепляет сообщения в начало           │
│ └─ messageRenderer.prependMessage() для каждого                 │
└───────────────────────────────┬─────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│ DOM обновлён → старые сообщения видны                           │
│ └─ Сохранение позиции скролла                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Компоненты и их взаимодействие

```
┌─────────────────────────────────────────────────────────────────┐
│                         chatDetail.js                           │
│                    (Оркестратор компонентов)                    │
└────────────────┬────────────────────────────────┬───────────────┘
                 │                                │
     ┌───────────▼──────────┐         ┌──────────▼──────────┐
     │   userWebSocket.js   │◄────────┤  messageRenderer.js │
     │ (WebSocket соединение)│         │  (Рендеринг HTML)   │
     └───────────┬──────────┘         └─────────────────────┘
                 │
     ┌───────────▼──────────┐
     │  chatComposer.js     │
     │  (Форма отправки)    │
     └──────────────────────┘
                 │
     ┌───────────▼──────────┐
     │  chatMarkRead.js     │
     │  (Отметка прочитанных)│
     └──────────────────────┘
                 │
     ┌───────────▼──────────┐
     │chatHistoryLoader.js  │
     │ (Загрузка истории)   │
     └──────────────────────┘
```

---

## 🔑 Ключевые особенности

### 1. ✅ Отключен серверный рендеринг сообщений
- Раньше: Django рендерил `messages` через `{% for message in messages %}`
- Сейчас: WebSocket отправляет `initial_messages` после подключения
- Преимущество: Единый механизм рендеринга (JS), меньше дублирования кода

### 2. ✅ Предотвращение дубликатов
```javascript
const existingMessage = container.querySelector(`[data-message-id="${msg.id}"]`);
if (existingMessage) {
  console.log('Message already exists, skipping:', msg.id);
  return;
}
```

### 3. ✅ Автоматические разделители дней
```javascript
let lastDay = null;
messages.forEach(msg => {
  const msgDay = this.formatDay(msgDate);
  if (msgDay !== lastDay) {
    this.addDayDivider(msgDay, container);
    lastDay = msgDay;
  }
  this.renderMessage(msg, container);
});
```

### 4. ✅ Ленивая загрузка истории
- IntersectionObserver отслеживает элемент `.history-loader`
- При видимости → загружает старые сообщения
- Сохраняет позицию скролла

### 5. ✅ Real-time обновления
- Новые сообщения → `new_message`
- Редактирование → `message_updated`
- Удаление → `message_deleted`
- Реакции → `reaction_added/removed`
- Голосования → `poll_update`
- Индикатор печати → `typing_start/stop`

---

## 🛠️ Порядок инициализации

```
1. HTTP Request → ChatDetailView
2. Render HTML Template
3. DOM Ready
4. Load JS Modules (chatDetail.js, components/*)
5. Read Config from data-attributes
6. Wait for WebSocket Ready (user:ws-ready event)
7. Initialize Components:
   ├─ FormManager
   ├─ MarkRead
   ├─ Composer
   ├─ HistoryLoader
   └─ MessageRenderer
8. Configure WebSocket with components
9. Open Chat: userWs.openChat(chatId, true)
10. WebSocket → Backend: { action: 'open_chat' }
11. Backend → WebSocket: { type: 'initial_messages' }
12. Render Messages → DOM
13. Remove #initialLoader
14. Scroll to Bottom
15. Initialize Polls
16. Ready! ✓
```

---

## 📝 Итоговая схема

```
┌──────────────────────────────────────────────────────────────────────┐
│                         СТРАНИЦА ЧАТА                                │
├──────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 1. DJANGO VIEW (Backend)                                    │   │
│  │    - Проверка доступа                                       │   │
│  │    - Подготовка контекста (без messages)                    │   │
│  │    - Рендеринг HTML шаблона                                 │   │
│  └────────────────────────┬────────────────────────────────────┘   │
│                           │                                          │
│                           ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 2. HTML TEMPLATE                                            │   │
│  │    - Пустой контейнер #chatScroll                           │   │
│  │    - Индикатор загрузки #initialLoader                      │   │
│  │    - Data-атрибуты с конфигом                               │   │
│  │    - Форма композера #chatForm                              │   │
│  └────────────────────────┬────────────────────────────────────┘   │
│                           │                                          │
│                           ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 3. JAVASCRIPT INIT (chatDetail.js)                          │   │
│  │    - Загрузка модулей                                       │   │
│  │    - Ожидание WebSocket                                     │   │
│  │    - Инициализация компонентов                              │   │
│  └────────────────────────┬────────────────────────────────────┘   │
│                           │                                          │
│                           ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 4. WEBSOCKET CONNECTION (userWebSocket.js)                  │   │
│  │    - openChat(chatId, loadHistory=true)                     │   │
│  │    - Backend → initial_messages                             │   │
│  └────────────────────────┬────────────────────────────────────┘   │
│                           │                                          │
│                           ▼                                          │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 5. MESSAGE RENDERING (messageRenderer.js)                   │   │
│  │    - renderMessages(messages)                               │   │
│  │    - Разделители дней                                       │   │
│  │    - Проверка дубликатов                                    │   │
│  │    - Вставка в DOM                                          │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │ 6. REAL-TIME UPDATES                                        │   │
│  │    - new_message → добавить                                 │   │
│  │    - message_updated → обновить                             │   │
│  │    - message_deleted → удалить                              │   │
│  │    - reaction_added/removed → обновить реакции              │   │
│  │    - poll_update → обновить голосование                     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 📚 Связанные документы

- `CHAT_RENDERING_ANALYSIS.md` - Подробный анализ архитектуры рендеринга
- `WEBSOCKET_UNIFIED_MIGRATION.md` - Миграция на единое WebSocket соединение
- `CHAT_CACHING_FIX.md` - Отключение кэширования страницы чата
- `MESSAGE_EDITING_ANALYSIS.md` - Механизм редактирования сообщений
- `POLLS_IMPLEMENTATION.md` - Реализация голосований

---

**Документ обновлён:** 4 декабря 2025 г.
