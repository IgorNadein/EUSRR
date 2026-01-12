# План архитектурного рефакторинга системы загрузки сообщений

**Дата:** 12.01.2026  
**Статус:** 🔴 PROPOSAL (требует согласования)  
**Приоритет:** HIGH - архитектурный долг накопился

---

## Текущая проблема

### Что не так сейчас:

```
❌ ТРИ РАЗНЫХ ПУТИ загрузки:
   1. handleInitialMessages → renderMessages()
   2. chatHistoryLoader → forEach + createMessageElement()
   3. handleNewMessage → renderMessage()

❌ День-разделители создаются в ТРЕХ местах:
   - renderMessages() - автоматически в цикле
   - chatHistoryLoader - вручную
   - renderMessage() - проверка последнего divider'а

❌ НЕТ единого состояния сообщений
   - Сообщения только в DOM
   - Нет кэша
   - Сложно управлять обновлениями

❌ Прямое манипулирование DOM везде
   - Множественные reflow
   - Сложно отследить кто что изменил
   - Нет предсказуемости
```

### Симптомы:

- 🐛 Scroll jumps - прыжки при загрузке
- 🐛 Дубликаты логики по всему коду
- 🐛 Day-dividers иногда не появляются
- 🐛 Сложно добавлять новые фичи
- 🐛 Тяжело дебажить проблемы

---

## Современная архитектура (Telegram, WhatsApp, Discord)

### Ключевые принципы:

```
1. 📦 SINGLE SOURCE OF TRUTH
   Все сообщения в централизованном Store
   
2. 🔄 UNIDIRECTIONAL DATA FLOW
   State → Render → User Action → State Update → Re-render
   
3. 🎯 SEPARATION OF CONCERNS
   Loader ← → Store ← → Renderer
                ↓
           ScrollManager
   
4. ⚡ OPTIMISTIC UPDATES
   Показываем сообщение сразу, обновляем после сервера
   
5. 🚀 VIRTUAL SCROLLING
   Рендерим только видимые сообщения (для больших чатов)
```

---

## Предлагаемая архитектура

### 1. MessageStore (Централизованное хранилище)

```javascript
class MessageStore {
  constructor() {
    this.messages = new Map(); // id → message
    this.chatMessages = new Map(); // chatId → [messageIds] (sorted)
    this.listeners = new Set();
    this.optimisticMessages = new Map(); // tempId → message
  }

  // API для работы с сообщениями
  addMessage(message, optimistic = false)
  addMessages(messages)
  updateMessage(id, updates)
  removeMessage(id)
  getMessage(id)
  getMessagesForChat(chatId, options = {})
  
  // Подписка на изменения
  subscribe(listener)
  unsubscribe(listener)
  
  // Утилиты
  hasMessage(id)
  getMessagesBetween(chatId, startId, endId)
  getOldestMessage(chatId)
  getNewestMessage(chatId)
  
  // Day dividers вычисляются на лету
  getMessagesWithDividers(chatId)
}
```

**Преимущества:**
- ✅ Единственный источник правды
- ✅ Легко искать дубликаты
- ✅ Кэширование из коробки
- ✅ Можно откатывать изменения
- ✅ Day-dividers вычисляются централизованно

---

### 2. MessageLoader (Единый загрузчик)

```javascript
class MessageLoader {
  constructor(store, wsConnection) {
    this.store = store;
    this.ws = wsConnection;
    this.loadingState = new Map(); // chatId → {initial, history, status}
  }

  // ЕДИНСТВЕННЫЙ способ загрузки начальных сообщений
  async loadInitialMessages(chatId) {
    if (this.loadingState.get(chatId)?.initial) return;
    
    const messages = await this.fetchInitialMessages(chatId);
    this.store.addMessages(messages);
    return messages;
  }

  // ЕДИНСТВЕННЫЙ способ загрузки истории
  async loadHistoryBefore(chatId, beforeId) {
    const messages = await this.fetchHistoryMessages(chatId, beforeId);
    this.store.addMessages(messages);
    return messages;
  }

  // ЕДИНСТВЕННЫЙ обработчик новых сообщений из WS
  handleNewMessage(message) {
    // Проверяем - это подтверждение оптимистичного сообщения?
    const optimistic = this.store.getOptimisticMessage(message.temp_id);
    if (optimistic) {
      this.store.confirmOptimisticMessage(message.temp_id, message);
    } else {
      this.store.addMessage(message);
    }
  }

  // Оптимистичная отправка
  sendMessageOptimistically(chatId, content) {
    const tempId = `temp_${Date.now()}`;
    const optimisticMessage = {
      id: tempId,
      chat_id: chatId,
      content,
      author_id: currentUserId,
      created_ts: Date.now(),
      status: 'sending'
    };
    
    this.store.addMessage(optimisticMessage, true);
    
    // Отправляем на сервер
    this.ws.send({ type: 'send_message', ...optimisticMessage });
    
    return tempId;
  }
}
```

**Преимущества:**
- ✅ Все загрузки через один интерфейс
- ✅ Нет дублирования логики
- ✅ Легко добавить retry/offline
- ✅ Оптимистичные обновления

---

### 3. MessageRenderer (Чистый рендеринг)

```javascript
class MessageRenderer {
  constructor(store, containerId) {
    this.store = store;
    this.containerId = containerId;
    this.renderedMessages = new Set(); // messageIds в DOM
  }

  // ЕДИНСТВЕННЫЙ метод рендеринга
  render(chatId, options = {}) {
    const container = document.getElementById(this.containerId);
    const messagesWithDividers = this.store.getMessagesWithDividers(chatId);
    
    // Используем DocumentFragment для батчинга
    const fragment = document.createDocumentFragment();
    
    messagesWithDividers.forEach(item => {
      if (item.type === 'divider') {
        fragment.appendChild(this.createDayDivider(item.text));
      } else {
        fragment.appendChild(this.createMessageElement(item.message));
      }
    });
    
    // ОДНА вставка в DOM
    container.innerHTML = ''; // или умный diff
    container.appendChild(fragment);
    
    this.renderedMessages.clear();
    messagesWithDividers.forEach(item => {
      if (item.type === 'message') {
        this.renderedMessages.add(item.message.id);
      }
    });
  }

  // Incremental update - добавить одно сообщение
  appendMessage(message) {
    if (this.renderedMessages.has(message.id)) return;
    
    const container = document.getElementById(this.containerId);
    const messagesWithDividers = this.store.getMessagesWithDividers(message.chat_id);
    
    // Найти нужно ли добавить divider перед сообщением
    const needsDivider = this.checkNeedsDayDivider(message, messagesWithDividers);
    
    if (needsDivider) {
      container.appendChild(this.createDayDivider(needsDivider.text));
    }
    
    container.appendChild(this.createMessageElement(message));
    this.renderedMessages.add(message.id);
  }

  // Update существующего сообщения (edit, reaction)
  updateMessage(messageId, updates) {
    const element = document.querySelector(`[data-message-id="${messageId}"]`);
    if (!element) return;
    
    // Патчим только измененные части
    if (updates.content) {
      element.querySelector('.message-content').textContent = updates.content;
    }
    if (updates.reactions) {
      this.updateReactions(element, updates.reactions);
    }
  }
}
```

**Преимущества:**
- ✅ Рендерит только из Store
- ✅ Предсказуемый результат
- ✅ Легко тестировать
- ✅ Day-dividers всегда корректны

---

### 4. ScrollManager (Управление прокруткой)

```javascript
class ScrollManager {
  constructor(scrollElement, messageLoader, messageRenderer) {
    this.scrollEl = scrollElement;
    this.loader = messageLoader;
    this.renderer = messageRenderer;
    
    this.setupIntersectionObserver();
    this.setupScrollListener();
  }

  // Автоматическая загрузка истории при scroll up
  setupIntersectionObserver() {
    const firstMessage = this.scrollEl.querySelector('.msg:first-child');
    
    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          this.loadMoreHistory();
        }
      });
    }, { threshold: 0.1 });
    
    if (firstMessage) observer.observe(firstMessage);
  }

  async loadMoreHistory() {
    const chatId = this.getChatId();
    const oldestMessage = this.store.getOldestMessage(chatId);
    
    if (!oldestMessage) return;
    
    const prevHeight = this.scrollEl.scrollHeight;
    
    await this.loader.loadHistoryBefore(chatId, oldestMessage.id);
    
    // Re-render с новыми сообщениями
    this.renderer.render(chatId);
    
    // Восстанавливаем позицию скролла
    const delta = this.scrollEl.scrollHeight - prevHeight;
    this.scrollEl.scrollTop += delta;
  }

  // Умный scroll to bottom БЕЗ прыжков
  scrollToBottom(options = {}) {
    const { instant = false, force = false } = options;
    
    // Не скроллим если пользователь читает историю (если force = false)
    if (!force && !this.isNearBottom()) return;
    
    // Скрываем контейнер
    this.scrollEl.style.visibility = 'hidden';
    
    // Double RAF для гарантии после layout
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        this.scrollEl.scrollTop = this.scrollEl.scrollHeight;
        this.scrollEl.style.visibility = '';
      });
    });
  }

  isNearBottom(threshold = 100) {
    return (
      this.scrollEl.scrollTop + this.scrollEl.clientHeight >=
      this.scrollEl.scrollHeight - threshold
    );
  }
}
```

**Преимущества:**
- ✅ Вся логика скролла в одном месте
- ✅ IntersectionObserver для автозагрузки
- ✅ Умное определение "внизу ли пользователь"
- ✅ Нет прыжков

---

### 5. ChatController (Координатор)

```javascript
class ChatController {
  constructor(chatId) {
    this.chatId = chatId;
    
    // Инициализируем компоненты
    this.store = new MessageStore();
    this.loader = new MessageLoader(this.store, userWebSocket);
    this.renderer = new MessageRenderer(this.store, 'chatScrollContainer');
    this.scrollManager = new ScrollManager(
      document.getElementById('chatScrollContainer'),
      this.loader,
      this.renderer
    );
    
    // Подписываемся на изменения Store
    this.store.subscribe((event, data) => {
      this.handleStoreUpdate(event, data);
    });
    
    // Подписываемся на WebSocket
    this.subscribeToWebSocket();
  }

  async init() {
    // Загружаем начальные сообщения
    await this.loader.loadInitialMessages(this.chatId);
    
    // Рендерим
    this.renderer.render(this.chatId);
    
    // Скроллим вниз
    this.scrollManager.scrollToBottom({ instant: true, force: true });
  }

  handleStoreUpdate(event, data) {
    switch (event) {
      case 'message_added':
        // Новое сообщение - incremental render
        this.renderer.appendMessage(data.message);
        
        // Автоскролл если внизу или наше сообщение
        if (data.message.author_id === currentUserId || this.scrollManager.isNearBottom()) {
          this.scrollManager.scrollToBottom();
        }
        break;
        
      case 'message_updated':
        // Обновление - патчим DOM
        this.renderer.updateMessage(data.messageId, data.updates);
        break;
        
      case 'message_removed':
        // Удаление
        this.renderer.removeMessage(data.messageId);
        break;
    }
  }

  subscribeToWebSocket() {
    userWebSocket.on('new_message', (data) => {
      if (data.message.chat_id === this.chatId) {
        this.loader.handleNewMessage(data.message);
      }
    });
    
    userWebSocket.on('message_edited', (data) => {
      this.store.updateMessage(data.message.id, data.message);
    });
    
    // ... другие события
  }

  sendMessage(content) {
    return this.loader.sendMessageOptimistically(this.chatId, content);
  }
}

// Usage:
const chat = new ChatController(chatId);
await chat.init();
```

---

## Архитектурная диаграмма

```
┌─────────────────────────────────────────────────┐
│               ChatController                     │
│  (координирует все компоненты)                  │
└────────┬────────────────────────────────┬───────┘
         │                                 │
         ▼                                 ▼
┌─────────────────┐              ┌─────────────────┐
│  MessageLoader  │◄────────────►│  MessageStore   │
│                 │              │  (Single Source │
│ - loadInitial() │              │   of Truth)     │
│ - loadHistory() │              │                 │
│ - handleNew()   │              │ Map<id, msg>    │
└────────┬────────┘              └────────┬────────┘
         │                                 │
         │                                 │
         ▼                                 ▼
┌─────────────────┐              ┌─────────────────┐
│   WebSocket     │              │ MessageRenderer │
│                 │              │                 │
│ - new_message   │              │ - render()      │
│ - message_edit  │              │ - append()      │
│ - reaction      │              │ - update()      │
└─────────────────┘              └────────┬────────┘
                                          │
                                          ▼
                                 ┌─────────────────┐
                                 │  ScrollManager  │
                                 │                 │
                                 │ - scrollToBottom│
                                 │ - loadMore()    │
                                 │ - isNearBottom  │
                                 └─────────────────┘

ПОТОК ДАННЫХ (однонаправленный):
WebSocket → Loader → Store → Renderer → DOM
               ↑                ↓
            Controller ← ScrollManager
```

---

## План миграции

### Фаза 1: Подготовка (1-2 дня)
- [ ] Создать MessageStore класс
- [ ] Написать тесты для Store
- [ ] Создать MessageLoader класс (пока без оптимистики)
- [ ] Протестировать совместимость с текущим API

### Фаза 2: Рефакторинг Renderer (1 день)
- [ ] Переписать MessageRenderer для работы со Store
- [ ] Убрать прямые манипуляции DOM
- [ ] Централизовать логику day-dividers в Store

### Фаза 3: Интеграция (2 дня)
- [ ] Создать ChatController
- [ ] Переписать chatDetail.js для использования Controller
- [ ] Удалить старый chatHistoryLoader
- [ ] Удалить дублирующую логику из userWebSocket

### Фаза 4: ScrollManager (1 день)
- [ ] Создать ScrollManager класс
- [ ] Переместить всю логику scroll из разных мест
- [ ] Реализовать IntersectionObserver для автозагрузки

### Фаза 5: Оптимизации (1-2 дня)
- [ ] Реализовать оптимистичные обновления
- [ ] Добавить виртуальный скроллинг (опционально)
- [ ] Оптимизировать re-render (virtual DOM или incremental DOM)

### Фаза 6: Cleanup (1 день)
- [ ] Удалить весь старый код
- [ ] Обновить документацию
- [ ] Написать migration guide

**Общее время: 7-10 дней разработки**

---

## Преимущества новой архитектуры

### Для разработки:
✅ **Предсказуемость** - всегда знаем где находится state  
✅ **Тестируемость** - каждый компонент изолирован  
✅ **Расширяемость** - легко добавлять новые фичи  
✅ **Читаемость** - четкое разделение ответственности  
✅ **Дебаг** - легко отследить откуда пришло изменение  

### Для пользователя:
✅ **Нет прыжков** - scroll управляется централизованно  
✅ **Быстрее** - меньше reflow, умный batching  
✅ **Надежнее** - нет race conditions и дубликатов  
✅ **Плавнее** - оптимистичные обновления  
✅ **Офлайн-режим** - Store позволяет кэшировать  

---

## Риски и митигация

### ⚠️ Риск: Большой объем изменений
**Митигация:** Поэтапная миграция, можно держать старый код параллельно

### ⚠️ Риск: Регрессии в существующих фичах
**Митигация:** Писать тесты для каждого компонента, мануальное тестирование

### ⚠️ Риск: Увеличение размера бандла
**Митигация:** Классы легко минифицируются, можно сделать code splitting

### ⚠️ Риск: Breaking changes для других частей кода
**Митигация:** Сохранить обратную совместимость API где возможно

---

## Альтернатива: Минимальный рефакторинг

Если полный рефакторинг слишком рискованный, можно сделать **минимальный**:

### Вариант "Быстрый фикс":
1. ✅ Создать один метод `addMessageToChat(message, position)`
2. ✅ Все три пути (initial, history, new) используют его
3. ✅ Day-dividers проверяются ВСЕГДА внутри этого метода
4. ✅ Scroll логика в одной функции

**Время: 1-2 дня**  
**Плюсы:** Быстро, низкий риск  
**Минусы:** Не решает архитектурные проблемы полностью  

---

## Решение?

**Предлагаю два варианта:**

### 🚀 Вариант A: Полный рефакторинг (рекомендуется)
- Современная архитектура
- Решает ВСЕ проблемы
- Легко поддерживать в будущем
- **Время: 7-10 дней**

### ⚡ Вариант B: Быстрый фикс
- Минимальные изменения
- Решает текущие баги
- Архитектурный долг остается
- **Время: 1-2 дня**

**Что выбираешь?**

Если согласен на Вариант A - начну с создания MessageStore и тестов.
Если нужен Вариант B - сделаю единый метод `addMessageToChat()` прямо сейчас.
