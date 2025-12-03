# Realtime App

WebSocket consumers для real-time функциональности приложения.

## Архитектура

### UserConsumer (`consumers.py`)

Универсальный WebSocket consumer, обрабатывающий все real-time события для одного пользователя через одно соединение.

**URL:** `ws://domain/ws/`

**Функциональность:**
- ✅ Чаты и сообщения
- ✅ Реакции на сообщения
- ✅ Индикатор "печатает..."
- ✅ Редактирование/удаление сообщений
- ✅ Уведомления
- ✅ Обновления счетчиков (бейджи)
- 🔄 Онлайн-статус (TODO)
- 🔄 Календарь события (TODO)

### Keepalive

- Ping каждые **20 секунд**
- Автоматическое переподключение при обрыве
- Nginx таймауты: **7 дней**

## Подключение

Consumer автоматически подписывается на:
1. **Группы чатов** - все чаты пользователя (`chat_{chat_id}`)
2. **Личный канал** - для direct updates (`user_{user_id}`)
3. **Канал уведомлений** - для notifications (`notifications_{user_id}`)

## События от клиента

```javascript
// Открыть чат
ws.send(JSON.stringify({
    action: "open_chat",
    chat_id: 123,
    load_history: true
}));

// Отправить сообщение
ws.send(JSON.stringify({
    action: "send_message",
    content: "Hello!"
}));

// Добавить реакцию
ws.send(JSON.stringify({
    action: "add_reaction",
    message_id: 456,
    emoji: "👍"
}));

// Индикатор печати
ws.send(JSON.stringify({
    action: "typing"
}));
```

## События к клиенту

```javascript
// Новое сообщение в активном чате
{
    type: "new_message",
    chat_id: 123,
    message: {...}
}

// Обновление списка чатов
{
    type: "list_update",
    chat_id: 123,
    message: {...}
}

// Реакция добавлена
{
    type: "reaction_added",
    chat_id: 123,
    message_id: 456,
    emoji: "👍",
    user_id: 10,
    user_name: "John Doe"
}

// Уведомление
{
    type: "notification",
    notification: {...}
}

// Ping для keepalive
{
    type: "ping",
    timestamp: "2025-12-03T10:00:00Z"
}
```

## Зависимости

- `communications.models` - Chat, Message, MessageReaction
- `communications.consumers` - serialize_message()
- `notifications.models` - для уведомлений (планируется)

## Миграция с старой архитектуры

Ранее использовались:
- `communications/user_consumer.py` - чаты
- `notifications/consumers.py` - уведомления

Теперь все в одном месте: `realtime/consumers.py`

## TODO

- [ ] Добавить онлайн-статус пользователей
- [ ] Интеграция с календарем для real-time событий
- [ ] Кэширование статуса "печатает..." через Redis
- [ ] Метрики и мониторинг WebSocket соединений
