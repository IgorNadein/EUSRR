# WebSocket Integration с ChatController

**Дата:** 12.01.2026  
**Статус:** ✅ Интеграция завершена

---

## Архитектура событий

### Новая система событий

UserWebSocket теперь **dispatch'ит глобальные события** вместо прямого вызова компонентов:

```
WebSocket Server
      ↓
userWebSocket.js (получает JSON)
      ↓
window.dispatchEvent('ws:*')  ← НОВОЕ
      ↓
ChatController (слушает события)
      ↓
MessageLoader → MessageStore
      ↓
Store событие → MessageRenderer
```

---

## События WebSocket

### 1. `ws:initial-messages`

**Когда:** После открытия чата и получения истории

**Данные:**
```javascript
{
  detail: {
    messages: Array,  // Массив сообщений
    chatId: number    // ID чата
  }
}
```

**Обработка:**
```javascript
window.addEventListener('ws:initial-messages', (event) => {
  const { messages, chatId } = event.detail;
  // ChatController автоматически рендерит и скроллит
});
```

---

### 2. `ws:new-message`

**Когда:** Получено новое сообщение в реальном времени

**Данные:**
```javascript
{
  detail: {
    message: Object,      // Полный объект сообщения
    chatId: number,       // ID чата
    isOwnMessage: boolean // true если отправитель - мы
  }
}
```

**Обработка:**
```javascript
window.addEventListener('ws:new-message', (event) => {
  const { message, isOwnMessage } = event.detail;
  // MessageLoader добавит в Store
  // Renderer сделает incremental update
  // Autoscroll если isOwnMessage или nearBottom
});
```

---

### 3. `ws:message-edited`

**Когда:** Сообщение отредактировано

**Данные:**
```javascript
{
  detail: {
    message: Object, // Обновленное сообщение
    chatId: number
  }
}
```

**Обработка:**
```javascript
window.addEventListener('ws:message-edited', (event) => {
  const { message } = event.detail;
  // Store обновит сообщение
  // Renderer сделает DOM patching
});
```

---

### 4. `ws:message-removed`

**Когда:** Сообщение удалено

**Данные:**
```javascript
{
  detail: {
    messageId: number, // ID удаленного сообщения
    chatId: number
  }
}
```

**Обработка:**
```javascript
window.addEventListener('ws:message-removed', (event) => {
  const { messageId } = event.detail;
  // Store удалит сообщение
  // Renderer удалит из DOM с анимацией
});
```

---

### 5. `ws:reaction-added`

**Когда:** Добавлена реакция к сообщению

**Данные:**
```javascript
{
  detail: {
    messageId: number,
    emoji: string,
    userId: number,
    userName: string,
    reactionsSummary: Object, // Полная сводка реакций
    chatId: number
  }
}
```

---

### 6. `ws:reaction-removed`

**Когда:** Удалена реакция

**Данные:**
```javascript
{
  detail: {
    messageId: number,
    emoji: string,
    userId: number,
    reactionsSummary: Object,
    chatId: number
  }
}
```

---

## Backward Compatibility

### Старые события сохранены

Для совместимости со старым кодом, userWebSocket **продолжает dispatch'ить старые события**:

- `chat:initial-messages-loaded`
- `chat:message-added`
- `chat:message-edited`
- `chat:reaction-added`
- `chat:reaction-removed`

### Старый messageRenderer работает

Если `options.messageRenderer` передан в `initUserWebSocket()`, старая логика рендеринга **продолжает работать** параллельно с новой:

```javascript
// В userWebSocket.js
if (options.messageRenderer && messages?.length) {
  console.log('[UserWS] [DEPRECATED] Using old messageRenderer');
  options.messageRenderer.renderMessages(messages);
}
```

**Это временная мера** - удалится после полной миграции на ChatController.

---

## Миграция на ChatController

### До (старый способ):

```javascript
// chatDetail.js - СТАРОЕ
const messageRenderer = new MessageRenderer({...});
userWs.configure({ messageRenderer });

// Прямой вызов методов
messageRenderer.renderMessages(messages);
messageRenderer.renderMessage(message);
```

### После (новый способ):

```javascript
// chatDetail.js - НОВОЕ
import { ChatController } from '../controllers/chatController.js';

const chatController = new ChatController({
  chatId: currentChatId,
  currentUserId: currentUserId,
  scrollElement: document.getElementById('chatScroll'),
  wsConnection: window.userWebSocket
});

await chatController.init();

// Всё автоматически!
// - WebSocket dispatch'ит события
// - ChatController слушает
// - MessageLoader обновляет Store
// - Store dispatch'ит события
// - Renderer обновляет DOM
```

---

## Debugging

### Проверка событий

В консоли браузера:

```javascript
// Слушаем все WS события
['ws:initial-messages', 'ws:new-message', 'ws:message-edited', 
 'ws:message-removed', 'ws:reaction-added', 'ws:reaction-removed']
.forEach(eventName => {
  window.addEventListener(eventName, (e) => {
    console.log(`🔔 ${eventName}:`, e.detail);
  });
});
```

### Проверка ChatController

```javascript
// Получить статус контроллера
window.chatController?.getStatus();
// Вернет:
// {
//   initialized: true,
//   chatId: 123,
//   messageCount: 45,
//   loadingState: {...},
//   scrollPosition: {...}
// }
```

---

## Следующие шаги

1. ✅ userWebSocket интегрирован (DONE)
2. ⏳ Обновить chatDetail.js для использования ChatController
3. ⏳ Удалить старый messageRenderer после миграции
4. ⏳ Удалить старый chatHistoryLoader
5. ⏳ Удалить backward compatibility код из userWebSocket

---

## Преимущества новой архитектуры

### До:
- ❌ userWebSocket напрямую вызывал messageRenderer
- ❌ Tight coupling между модулями
- ❌ Сложно тестировать
- ❌ Нельзя заменить компоненты

### После:
- ✅ Событийная архитектура (Event-Driven)
- ✅ Loose coupling - модули независимы
- ✅ Легко тестировать (mock события)
- ✅ Можно заменить любой компонент
- ✅ Единая точка входа (ChatController)
- ✅ Single Source of Truth (MessageStore)
