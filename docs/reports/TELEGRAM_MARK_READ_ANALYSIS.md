# Анализ реализации mark-as-read в Telegram Web

**Дата:** 21 января 2026  
**Источник:** [Telegram Web (TWeb)](https://github.com/morethanwords/tweb)  
**Цель:** Изучить комбинированный подход к отметке сообщений как прочитанных

---

## 🔗 Ссылки на исходники

### Основные файлы реализации:
1. **[appMessagesManager.ts#L6059-L6201](https://github.com/morethanwords/tweb/tree/main/src/lib/appManagers/appMessagesManager.ts#L6059-L6201)** - Главная логика `readHistory()`
2. **[dialogsStorage.ts#L728-L913](https://github.com/morethanwords/tweb/tree/main/src/lib/storages/dialogs.ts#L728-L913)** - Управление счётчиками unread
3. **[storage.ts](https://github.com/morethanwords/tweb/tree/main/src/lib/storage.ts)** - IndexedDB обёртка для кэширования
4. **[localStorage.ts](https://github.com/morethanwords/tweb/tree/main/src/lib/localStorage.ts)** - LocalStorage прокси
5. **[apiManagerProxy.ts](https://github.com/morethanwords/tweb/tree/main/src/lib/apiManagerProxy.ts)** - Координация между вкладками

### API документация:
- **[messages.readHistory](https://core.telegram.org/method/messages.readHistory)** - Telegram API метод

---

## 🏗️ Архитектура Telegram Web

### 1. Многоуровневое хранилище

```
┌─────────────────────────────────────────┐
│  UI Layer (Chat Component)              │
│  - IntersectionObserver для видимости   │
└────────────┬────────────────────────────┘
             │
┌────────────▼────────────────────────────┐
│  AppMessagesManager                     │
│  - readHistory()                        │
│  - getReadMaxIdIfUnread()               │
│  - Debounce батчинг (33ms)              │
└────────────┬────────────────────────────┘
             │
┌────────────▼────────────────────────────┐
│  Локальный кэш (синхронный)             │
│  ├─ In-memory cache (mirrors)           │
│  ├─ IndexedDB (persistent)              │
│  └─ LocalStorage (settings)             │
└────────────┬────────────────────────────┘
             │
┌────────────▼────────────────────────────┐
│  API Layer                              │
│  ├─ HTTP: messages.readHistory          │
│  └─ Updates: updateReadHistoryInbox     │
└─────────────────────────────────────────┘
```

### 2. Комбинированный подход: HTTP + WebSocket

#### **HTTP (Исходящий - для отправки mark-read):**
```typescript
// src/lib/appManagers/appMessagesManager.ts#L6161-L6188

public readHistory({peerId, maxId = 0, threadId, force = false}: ReadHistoryArgs) {
  const historyStorage = this.getHistoryStorage(peerId, threadId);
  
  // 1. Немедленное локальное обновление (оптимистичное)
  this.apiUpdatesManager.processLocalUpdate({
    _: 'updateReadHistoryInbox',
    max_id: maxId,
    peer: this.appPeersManager.getOutputPeer(peerId),
    still_unread_count: undefined,
    pts: undefined,
    pts_count: undefined
  });
  
  // 2. HTTP запрос к API (если ещё не идёт)
  if(!historyStorage.readPromise) {
    apiPromise = this.apiManager.invokeApi('messages.readHistory', {
      peer: this.appPeersManager.getInputPeerById(peerId),
      max_id: getServerMessageId(maxId)
    }).then((affectedMessages) => {
      this.apiUpdatesManager.processLocalUpdate({
        _: 'updatePts',
        pts: affectedMessages.pts,
        pts_count: affectedMessages.pts_count
      });
    });
  }
  
  // 3. Защита от дублирования
  historyStorage.triedToReadMaxId = maxId;
  
  return historyStorage.readPromise = apiPromise;
}
```

**Ключевые моменты:**
- ✅ **Оптимистичное обновление** - UI обновляется сразу
- ✅ **Дедупликация** - `readPromise` и `triedToReadMaxId` предотвращают дубли
- ✅ **Гарантия доставки** - HTTP запрос с retry логикой

#### **WebSocket (Входящий - для получения уведомлений):**
```typescript
// Telegram отправляет updates через WebSocket когда:
// 1. Другой пользователь прочитал ваши сообщения
// 2. Вы прочитали сообщения на другом устройстве/вкладке

updateReadHistoryInbox: {
  _: 'updateReadHistoryInbox',
  peer: Peer,
  max_id: number,
  still_unread_count: number,
  pts: number,
  pts_count: number
}
```

---

## 💾 Хранение last_read в браузере

### IndexedDB (Основное хранилище)

```typescript
// src/lib/storage.ts
// src/config/databases/state.ts#L38-L76

// База данных для каждого аккаунта
const DATABASE = {
  name: `tweb-account-${accountNumber}`,
  version: 9,
  stores: [
    'session',      // Ключи авторизации
    'dialogs',      // Диалоги с read_inbox_max_id
    'messages',     // Сообщения
    'users',        // Кэш пользователей
    'chats'         // Кэш чатов
  ]
};

// Структура диалога в IndexedDB
interface Dialog {
  _: 'dialog',
  peerId: PeerId,
  top_message: number,
  read_inbox_max_id: number,     // ← Последнее прочитанное входящее
  read_outbox_max_id: number,    // ← Последнее прочитанное исходящее
  unread_count: number,
  unread_mentions_count: number,
  pts?: number
}
```

**[Пример из кода](https://github.com/morethanwords/tweb/tree/main/src/lib/storages/dialogs.ts#L1427-L1466):**
```typescript
public saveDialog({dialog, folderId}: SaveDialogArgs) {
  const historyStorage = this.appMessagesManager.getHistoryStorage(peerId, topicId);
  
  // Сохраняем read_inbox_max_id в historyStorage
  historyStorage.readMaxId = dialog.read_inbox_max_id;
  historyStorage.readOutboxMaxId = dialog.read_outbox_max_id;
  
  // Записываем в IndexedDB
  this.storage.set({
    [peerId]: dialog
  });
}
```

### In-Memory Cache (Быстрый доступ)

```typescript
// src/lib/apiManagerProxy.ts#L979-L1003

class ApiManagerProxy {
  private mirrors = {
    messages: {},      // Кэш сообщений
    dialogs: {},       // Кэш диалогов
    users: {},         // Кэш пользователей
  };
  
  public getMessageFromStorage(key: MessagesStorageKey, mid: number) {
    const cache = this.mirrors.messages[key];
    return cache?.[mid];  // Синхронный доступ без await
  }
}
```

---

## 🔄 Синхронизация между вкладками

### BroadcastChannel + LocalStorage

```typescript
// src/lib/apiManagerProxy.ts#L336-L361

constructor() {
  // Слушаем события из других вкладок
  this.addTaskListener('broadcast', (payload, source, event) => {
    const {name, args, accountNumber} = payload;
    
    // Игнорируем события из своей вкладки
    if(isDifferentAccount) return;
    
    // Применяем обновление локально
    rootScope.dispatchEventSingle(name, ...args);
  });
  
  // Слушаем изменения localStorage
  this.addTaskListener('localStorageProxy', (payload) => {
    return sessionStorage.localStorageProxy(payload.type, ...payload.args);
  });
}
```

**Механизм синхронизации:**
1. **Вкладка A** читает сообщения → вызывает `readHistory()`
2. **Вкладка A** отправляет `broadcast` событие через `BroadcastChannel`
3. **Вкладка B, C, D** получают событие и обновляют свой UI
4. **Сервер** отправляет `updateReadHistoryInbox` через WebSocket всем устройствам

---

## 🚀 Оптимизация: Debounce + Batcher

### Debounce батчинг (33ms окно)

```typescript
// src/lib/appManagers/appMessagesManager.ts#L741-L769

protected after() {
  // Батчер для группировки обновлений
  this.batchUpdatesDebounced = debounce(() => {
    for(const event in this.batchUpdates) {
      const details = this.batchUpdates[event as keyof BatchUpdates];
      delete this.batchUpdates[event as keyof BatchUpdates];
      
      const result = details.callback(details.batch);
      if(result && (!(result instanceof Array) || result.length)) {
        this.rootScope.dispatchEvent(event as keyof BatchUpdates, result as any);
      }
    }
  }, 33, false, true);  // ← 33ms = ~30 FPS
}
```

### Пример батчинга для Stories

```typescript
// src/components/stories/viewer.tsx#L1698-L1726

const readStories = (maxId: number) => {
  if(viewedStories.size) {
    // Отправляем батч просмотров
    rootScope.managers.appStoriesManager.incrementStoryViews(
      props.state.peerId, 
      Array.from(viewedStories)
    );
    viewedStories.clear();
  }
  
  rootScope.managers.appStoriesManager.readStories(props.state.peerId, maxId);
};

const viewedStories: Set<number> = new Set();
const readDebounced = debounce(readStories, 5e3, true, true); // ← 5 секунд
```

---

## 🎯 Проверка: Нужно ли отправлять HTTP?

### Логика проверки unread статуса

```typescript
// src/lib/appManagers/appMessagesManager.ts#L6059-L6077

public readHistory({peerId, maxId = 0, threadId, force = false}: ReadHistoryArgs) {
  // 1. Проверяем: есть ли вообще непрочитанные?
  const readMaxId = this.getReadMaxIdIfUnread(peerId, threadId);
  
  if(!readMaxId && !force) {
    const dialog = this.getDialogOnly(peerId);
    
    if(dialog && !this.isDialogUnread(dialog)) {
      this.log('readHistory: isn\'t unread');
      return Promise.resolve();  // ← Ничего не делаем, всё уже прочитано
    }
  }
  
  // 2. Проверяем: не пытались ли уже прочитать это?
  const historyStorage = this.getHistoryStorage(peerId, threadId);
  
  if(historyStorage.triedToReadMaxId >= maxId) {
    return Promise.resolve();  // ← Уже в процессе или завершено
  }
  
  // 3. Проверяем: не идёт ли уже запрос?
  if(historyStorage.readPromise) {
    return historyStorage.readPromise;  // ← Возвращаем существующий Promise
  }
  
  // 4. Всё ОК - отправляем HTTP
  return this.apiManager.invokeApi('messages.readHistory', {...});
}
```

```typescript
// src/lib/appManagers/appMessagesManager.ts#L3338-L3351

public getReadMaxIdIfUnread(peerId: PeerId, threadId?: number) {
  const historyStorage = this.getHistoryStorage(peerId, threadId);
  const message = this.getMessageByPeer(peerId, historyStorage.maxId);
  const readMaxId = historyStorage.readMaxId;
  
  // Возвращаем readMaxId только если:
  // 1. Сообщение не наше (не исходящее)
  // 2. readMaxId < maxId (есть непрочитанные)
  // 3. readMaxId != 0 (не пустой диалог)
  return !message?.pFlags?.out && readMaxId < historyStorage.maxId 
    && getServerMessageId(readMaxId) ? readMaxId : 0;
}
```

---

## 📋 Алгоритм работы (пошагово)

### Сценарий: Пользователь открывает чат с 50 непрочитанными

```
1. UI рендерится
   └─ IntersectionObserver следит за видимыми сообщениями

2. Пользователь скроллит → видны сообщения #40-50
   └─ Срабатывает observer

3. Проверка: Нужен ли HTTP запрос?
   ├─ Проверяем: historyStorage.readMaxId < 50?
   │  └─ ДА → есть непрочитанные
   ├─ Проверяем: historyStorage.triedToReadMaxId >= 50?
   │  └─ НЕТ → ещё не пытались прочитать
   └─ Проверяем: historyStorage.readPromise существует?
      └─ НЕТ → запроса ещё нет

4. ✅ Отправляем HTTP запрос
   ├─ Немедленно: processLocalUpdate() → UI обновляется
   ├─ Асинхронно: messages.readHistory API call
   └─ Сохраняем: historyStorage.readPromise

5. Пользователь скроллит дальше → видны #45-55
   └─ Снова проверка: triedToReadMaxId >= 55?
      └─ НЕТ → отправляем новый запрос с maxId=55

6. Сервер отвечает на первый запрос
   ├─ Обновляем: historyStorage.readMaxId = 50
   └─ Удаляем: delete historyStorage.readPromise

7. Сервер отправляет update через WebSocket на другие устройства
   └─ updateReadHistoryInbox { max_id: 55 }
```

### Важные детали:

#### 1. Оптимистичное обновление
```typescript
// Сначала обновляем UI
this.apiUpdatesManager.processLocalUpdate({
  _: 'updateReadHistoryInbox',
  max_id: maxId,  // ← UI видит сразу
  // ...
});

// Потом отправляем запрос
apiPromise = this.apiManager.invokeApi('messages.readHistory', {
  max_id: getServerMessageId(maxId)
});
```

#### 2. Дедупликация через Promise
```typescript
// Если запрос уже идёт
if(historyStorage.readPromise) {
  return historyStorage.readPromise;  // ← Все ждут один Promise
}

// Новый запрос
historyStorage.readPromise = apiPromise;

// После завершения
apiPromise.finally(() => {
  delete historyStorage.readPromise;  // ← Разрешаем новые запросы
});
```

#### 3. Догоняющий запрос (catch-up)
```typescript
apiPromise.finally(() => {
  const {readMaxId} = historyStorage;
  
  // Если за время запроса появились новые прочитанные
  if(readMaxId > maxId) {
    this.readHistory({peerId, maxId: readMaxId, force: true});
  }
});
```

---

## 💡 Ключевые находки для нашего проекта

### 1. ✅ Сохранение в памяти браузера

**Telegram использует:**
- **IndexedDB** для persistent хранения `read_inbox_max_id` в объекте диалога
- **In-memory cache** для быстрого синхронного доступа
- **LocalStorage** только для настроек, НЕ для диалогов

**Что применить у нас:**
```javascript
// chatMarkRead.js

const STORAGE_KEY = 'chat_last_read';

function saveLastRead(chatId, timestamp) {
  // 1. Сохраняем в память (синхронно)
  window._chatLastRead = window._chatLastRead || {};
  window._chatLastRead[chatId] = timestamp;
  
  // 2. Сохраняем в localStorage (асинхронно)
  localStorage.setItem(
    `${STORAGE_KEY}_${chatId}`, 
    timestamp
  );
}

function getLastRead(chatId) {
  // Сначала проверяем память
  return window._chatLastRead?.[chatId] 
    || localStorage.getItem(`${STORAGE_KEY}_${chatId}`) 
    || 0;
}
```

### 2. ✅ Проверка перед отправкой HTTP

```javascript
// Добавить в chatMarkRead.js

function markVisibleMessagesAsRead() {
  const newestVisible = /* найти самое новое видимое */;
  const newTs = Number(newestVisible.dataset.ts);
  
  // НОВОЕ: Проверяем сохранённое значение
  const lastReadTs = getLastRead(chatId);
  
  if(newTs <= lastReadTs) {
    console.log('[Mark Read] Уже прочитано:', newTs, 'последнее:', lastReadTs);
    return;  // ← Не отправляем HTTP
  }
  
  // Сохраняем в память ДО отправки (оптимистично)
  saveLastRead(chatId, newTs);
  
  // Отправляем HTTP
  markReadDebounced(newTs);
}
```

### 3. ✅ Обработка входящего события от WebSocket

```python
# communications/consumers.py

async def marked_read(self, event):
    """
    Кто-то (другая вкладка или устройство) прочитал сообщения.
    Проверяем: нужно ли нам синхронизироваться.
    """
    last_read_at = event['last_read_at']
    
    # Отправляем обновление клиенту
    await self.send(text_data=json.dumps({
        'type': 'marked_read',
        'last_read_at': last_read_at.isoformat()
    }))
```

```javascript
// chatController.js

socket.onmessage = function(e) {
  const data = JSON.parse(e.data);
  
  if(data.type === 'marked_read') {
    const remoteTs = new Date(data.last_read_at).getTime() / 1000;
    const localTs = getLastRead(chatId);
    
    // Если удалённое значение НОВЕЕ локального
    if(remoteTs > localTs) {
      console.log('[WS] Синхронизация: обновляем локальный last_read');
      saveLastRead(chatId, remoteTs);
      
      // ОПЦИОНАЛЬНО: Отправляем HTTP для гарантии
      // (если не уверены что другая вкладка успешно отправила)
      fetch('/api/chat-mark-read/', {
        method: 'POST',
        body: JSON.stringify({chat_id: chatId, upto_ts: remoteTs})
      });
    }
  }
};
```

### 4. ✅ Батчинг с debounce (как у Telegram)

```javascript
// Telegram использует 33ms для UI updates
// Для mark-read можно увеличить до 500ms-1000ms

let batchQueue = new Map(); // chatId -> timestamp
let batchTimer = null;

function markReadDebounced(chatId, timestamp) {
  // Добавляем в батч
  batchQueue.set(chatId, Math.max(
    batchQueue.get(chatId) || 0,
    timestamp
  ));
  
  // Сбрасываем таймер
  clearTimeout(batchTimer);
  
  // Ждём 500ms тишины
  batchTimer = setTimeout(() => {
    // Отправляем батч
    const batch = Array.from(batchQueue.entries());
    batchQueue.clear();
    
    batch.forEach(([chatId, ts]) => {
      fetch('/api/chat-mark-read/', {
        method: 'POST',
        body: JSON.stringify({chat_id: chatId, upto_ts: ts})
      });
    });
  }, 500);
}
```

---

## 🏁 Рекомендации по реализации

### Минимальная реализация (MVP)

```javascript
// 1. Добавить localStorage кэш
const CACHE_KEY = 'chat_last_read';
window._chatCache = JSON.parse(localStorage.getItem(CACHE_KEY) || '{}');

function saveLastRead(chatId, ts) {
  window._chatCache[chatId] = ts;
  localStorage.setItem(CACHE_KEY, JSON.stringify(window._chatCache));
}

function getLastRead(chatId) {
  return window._chatCache[chatId] || 0;
}

// 2. Модифицировать markVisibleMessagesAsRead()
function markVisibleMessagesAsRead() {
  const newestVisible = /* ... */;
  const newTs = Number(newestVisible.dataset.ts);
  const oldTs = getLastRead(chatId);
  
  // Проверка: только если новее
  if(newTs <= oldTs) return;
  
  // Сохраняем оптимистично
  saveLastRead(chatId, newTs);
  
  // Отправляем HTTP
  markReadDebounced(newTs);
}

// 3. Обработать WS событие marked_read
socket.onmessage = function(e) {
  const data = JSON.parse(e.data);
  
  if(data.type === 'marked_read') {
    const remoteTs = new Date(data.last_read_at).getTime() / 1000;
    const localTs = getLastRead(data.chat_id);
    
    if(remoteTs > localTs) {
      saveLastRead(data.chat_id, remoteTs);
      // Обновить UI если нужно
    }
  }
};
```

### Полная реализация (как Telegram)

- ✅ IndexedDB вместо localStorage (для больших объёмов)
- ✅ BroadcastChannel для синхронизации вкладок
- ✅ Батчинг с 500ms debounce
- ✅ Оптимистичные обновления
- ✅ Catch-up логика после завершения запроса
- ✅ WebSocket только для уведомлений (не для отправки)

---

## 📊 Сравнение подходов

| Аспект | Telegram Web | Наш текущий | Рекомендация |
|--------|-------------|-------------|--------------|
| **Отправка mark-read** | HTTP POST | HTTP POST ✅ | Оставить HTTP |
| **Получение updates** | WebSocket | WebSocket ✅ | Оставить WS |
| **Кэш last_read** | IndexedDB + In-memory | ❌ Нет | **Добавить localStorage** |
| **Проверка перед HTTP** | 3-уровневая | ❌ Нет | **Добавить проверку** |
| **Debounce** | 33ms (UI), 500ms (API) | 500ms ✅ | ОК |
| **Batch requests** | Да | Частично | Улучшить |
| **Sync между вкладками** | BroadcastChannel | ❌ Нет | **Добавить** |
| **Оптимистичный UI** | Да | Да ✅ | ОК |

---

## 🔚 Выводы

### Почему Telegram использует HTTP для mark-read:

1. **Гарантия доставки** - HTTP с retry, WebSocket может disconnect
2. **Дедупликация** - Server-side батчинг и проверка
3. **Совместимость** - Работает везде (HTTP/1.1, HTTP/2, HTTP/3)
4. **Простота** - Меньше edge cases чем с WebSocket ACK

### Почему WebSocket только для уведомлений:

1. **Мгновенность** - Push от сервера без polling
2. **Экономия** - Меньше HTTP запросов для получения updates
3. **Статусы** - Typing, online, read receipts в реальном времени

### Что внедрить у нас:

**Критично:**
- ✅ localStorage для кэша last_read
- ✅ Проверка `if(newTs <= cachedTs) return;`
- ✅ Обработка WS события `marked_read` с синхронизацией

**Желательно:**
- 📊 BroadcastChannel для синхронизации вкладок
- 🚀 Батчинг с 500ms окном

**Опционально:**
- 💾 IndexedDB вместо localStorage (если много чатов)
- 🔄 Catch-up логика после завершения HTTP

---

## 📚 Дополнительные материалы

### Полезные ссылки:
- [Telegram API Docs](https://core.telegram.org/api/read-history)
- [TWeb GitHub](https://github.com/morethanwords/tweb)
- [TWeb: appMessagesManager](https://github.com/morethanwords/tweb/tree/main/src/lib/appManagers/appMessagesManager.ts)
- [TWeb: DialogsStorage](https://github.com/morethanwords/tweb/tree/main/src/lib/storages/dialogs.ts)
- [TWeb: Storage Layer](https://github.com/morethanwords/tweb/tree/main/src/lib/storage.ts)

### Telegram-специфичные особенности:
- Используют `pts` (persistent timestamp) для синхронизации
- Имеют отдельную логику для каналов vs личных чатов vs форумов
- Батчат не только mark-read, но и все UI updates (33ms окно)
- Используют Service Worker для фоновой синхронизации

---

**Примечание:** Этот анализ основан на открытом исходном коде Telegram Web (TWeb) версии на январь 2026. Фактическая реализация может отличаться в зависимости от версии.
