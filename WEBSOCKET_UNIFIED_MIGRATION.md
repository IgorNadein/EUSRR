# Миграция на единое WebSocket соединение

## Что изменилось

### До (старая архитектура - 2 WebSocket):

```
Пользователь → 2 WebSocket соединения:
├─ ws://host/ws/chats/          (глобальный - для списка чатов и бейджа)
└─ ws://host/ws/chat/123/       (конкретный чат - только если открыт)
```

**Проблемы:**
- Двойная подписка на группы `chat_{id}`
- Дублирование событий
- Больше нагрузка на сервер
- Сложность управления

### После (новая архитектура - 1 WebSocket):

```
Пользователь → 1 WebSocket соединение:
└─ ws://host/ws/                (универсальное для пользователя)
   ├─ Чаты: список + активный чат
   ├─ Уведомления (звонки, события, задачи)
   ├─ Бейджи в sidebar
   ├─ Онлайн-статус
   └─ Другие real-time события
```

**Преимущества:**
- ✅ Одно соединение вместо двух
- ✅ Нет дублирования событий
- ✅ Меньше нагрузка на сервер (50% соединений)
- ✅ Проще отладка
- ✅ Быстрее переключение между чатами
- ✅ Универсальное для всех типов обновлений
- ✅ Масштабируемость (легко добавить новые типы событий)

## Изменения в файлах

### Backend

#### 1. `communications/user_consumer.py` (НОВЫЙ)
Универсальный Consumer для всех real-time операций пользователя.

**Назначение:**
- 🔵 **Чаты**: подписка на все чаты, отслеживание активного
- 🔔 **Уведомления**: (будущее) звонки, события, задачи
- 🔢 **Бейджи**: обновление счетчиков в sidebar
- 🟢 **Статусы**: (будущее) онлайн/офлайн пользователей
- 📅 **События**: (будущее) календарь, документы и др.

**Ключевые особенности:**
- Подписывается на все чаты пользователя при подключении
- Отслеживает активный чат (`active_chat_id`)
- Отправляет полные данные для активного чата
- Отправляет компактные данные для обновления списка
- Управляется через действия: `open_chat`, `close_chat`

#### 2. `communications/routing.py` (ОБНОВЛЕН)
```python
# Универсальный WebSocket endpoint
re_path(r"^ws/$", UserConsumer.as_asgi(), name="ws_user")
```

### Frontend

#### 3. `static/js/components/userWebSocket.js` (НОВЫЙ)
Универсальный клиентский модуль для WebSocket пользователя.

**API:**
```javascript
const api = {
  // Управление чатом
  openChat(chatId, loadHistory),
  closeChat(chatId),
  
  // Отправка сообщений
  sendMessage(content),
  
  // Реакции
  addReaction(messageId, emoji),
  removeReaction(messageId, emoji),
  
  // Редактирование
  editMessage(messageId, content),
  deleteMessage(messageId),
  
  // Отметка прочитанного
  markRead(chatId),
  
  // Голосование
  votePoll(pollId, optionIds),
  
  // Состояние
  getActiveChatId(),
  isConnected()
};
```

#### 4. `templates/base.html` (ОБНОВЛЕН)
- Заменен `initChatWebSocket` на `initUnifiedChatWebSocket`
- Удален отдельный глобальный WebSocket для списка чатов
- Обновлен `initSidebarBadge` для работы с событиями из единого WS

## Протокол WebSocket

### Клиент → Сервер (действия)

```javascript
// Открыть чат
{
  action: "open_chat",
  chat_id: 123,
  load_history: true
}

// Закрыть чат
{
  action: "close_chat",
  chat_id: 123
}

// Отправить сообщение
{
  action: "send_message",
  content: "Привет!"
}

// Добавить реакцию
{
  action: "add_reaction",
  message_id: 456,
  emoji: "👍"
}

// Индикатор печати
{
  action: "typing"
}

// Отметить прочитанным
{
  action: "mark_read",
  chat_id: 123
}
```

### Сервер → Клиент (события)

```javascript
// Новое сообщение (полные данные для активного чата)
{
  type: "new_message",
  chat_id: 123,
  message: { id, content, author_id, ... }
}

// Обновление списка (компактные данные для всех чатов)
{
  type: "list_update",
  chat_id: 123,
  message: { id, content, author_id, created_ts }
}

// Реакция добавлена
{
  type: "reaction_added",
  chat_id: 123,
  message_id: 456,
  emoji: "👍",
  user_id: 789
}

// Пользователь печатает
{
  type: "typing_start",
  chat_id: 123,
  user_id: 789,
  user_name: "Иван"
}

// Ping для keepalive
{
  type: "ping",
  timestamp: "2025-12-01T12:00:00Z"
}
```

## Логика работы

### При загрузке страницы:

1. **Любая страница (авторизованный пользователь):**
   - Создается единое WebSocket соединение: `ws://host/ws/user/`
   - Сервер подписывает на все чаты пользователя
   - Начинается прослушивание событий

2. **Страница чата (/chats/123/):**
   - WebSocket уже открыт
   - Клиент отправляет `open_chat` с `chat_id: 123`
   - Сервер устанавливает `active_chat_id = 123`
   - Сервер отправляет начальную историю (если запрошена)
   - Клиент начинает получать полные данные сообщений

3. **Переход к другому чату:**
   - Клиент отправляет `close_chat` для текущего
   - Клиент отправляет `open_chat` для нового
   - WebSocket остается открытым!

### При получении нового сообщения:

**На сервере (`UnifiedChatConsumer.chat_message`):**
```python
chat_id = event['chat_id']

# Если это активный чат - полные данные
if chat_id == self.active_chat_id:
    send_json({"type": "new_message", "message": full_data})

# Для списка - компактные данные
send_json({"type": "list_update", "message": compact_data})
```

**На клиенте:**
```javascript
// new_message - добавляем в DOM активного чата
handleNewMessage(data) {
  const msgEl = createMessageElement(data.message);
  scrollEl.appendChild(msgEl);
}

// list_update - обновляем карточку чата + бейдж
handleListUpdate(data) {
  updateChatCard(data.chat_id, data.message);
  badgeManager.incrementChat(data.chat_id);
}
```

## Обратная совместимость

Для плавной миграции:

1. **Старые endpoints закомментированы**, но не удалены
2. **API совместимо**: `window.chatWebSocketApi` и `window.chatWebSocket` работают
3. **События совместимы**: `chat:ws-ready`, `chat:list-update` и др.

## План полной миграции

### Этап 1: ✅ Создание (выполнено)
- [x] Создан `UnifiedChatConsumer`
- [x] Создан `unifiedChatWebSocket.js`
- [x] Обновлен routing
- [x] Обновлен base.html

### Этап 2: Тестирование
- [ ] Проверить работу в разных браузерах
- [ ] Проверить переключение между чатами
- [ ] Проверить обновление бейджа
- [ ] Проверить индикатор "печатает..."
- [ ] Проверить реакции и редактирование

### Этап 3: Очистка
- [ ] Удалить `ChatConsumer` и `ChatListConsumer`
- [ ] Удалить `chatWebSocket.js`
- [ ] Удалить старые endpoints из routing
- [ ] Обновить документацию

## Тестирование

### Проверка соединения:

```javascript
// В консоли браузера
console.log(window.chatWebSocketApi);
console.log(window.chatWebSocketApi.isConnected()); // true

// Открыть чат
window.chatWebSocketApi.openChat(123, true);

// Отправить сообщение
window.chatWebSocketApi.sendMessage("Тест");
```

### Проверка в Network DevTools:

1. Открыть DevTools → Network → WS
2. Найти соединение `ws/user/`
3. Проверить входящие/исходящие сообщения
4. Убедиться, что только одно WebSocket соединение активно

## Производительность

### До:
```
1 пользователь = 2 WebSocket (если открыт чат) или 1 (если только список)
100 пользователей с открытыми чатами = 200 WebSocket соединений
```

### После:
```
1 пользователь = 1 WebSocket (всегда)
100 пользователей = 100 WebSocket соединений
```

**Экономия: 50% соединений!**

## Известные ограничения

1. **История сообщений**: Загружается только при `load_history: true`
2. **Переподключение**: Автоматическое переподключение до 5 попыток
3. **Keepalive**: Ping каждые 20 секунд (можно настроить)

## Troubleshooting

### Проблема: WebSocket не подключается

**Решение:**
```javascript
// Проверить URL
console.log(location.host); // должен быть правильный хост

// Проверить авторизацию
console.log(window.currentUserId); // должен быть ID пользователя
```

### Проблема: Сообщения не появляются

**Решение:**
```javascript
// Проверить активный чат
console.log(window.chatWebSocketApi.getActiveChatId()); // должен быть chat_id

// Переоткрыть чат
const chatId = parseInt(document.getElementById('chatScroll').dataset.chatId);
window.chatWebSocketApi.closeChat(chatId);
window.chatWebSocketApi.openChat(chatId, true);
```

### Проблема: Бейдж не обновляется

**Решение:**
Проверить, что события диспатчатся:
```javascript
window.addEventListener('chat:list-update', (e) => {
  console.log('List update:', e.detail);
});
```

## Дополнительные улучшения (будущее)

1. **Redis для typing status** - кэширование статуса печати
2. **Compression** - сжатие WebSocket сообщений
3. **Binary protocol** - для вложений
4. **Presence** - онлайн статус пользователей
5. **Read receipts** - уведомления о прочтении
6. **Message queue** - очередь для offline сообщений

---

**Статус: READY FOR TESTING**
**Дата: 1 декабря 2025 г.**
**Автор: IgorNadein**
