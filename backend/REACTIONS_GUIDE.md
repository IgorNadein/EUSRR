# Реакции на сообщения - Руководство по использованию

## 📦 Что реализовано

### Backend (✅ Готово)

1. **Модель `MessageReaction`** (`communications/models.py`)
   - ForeignKey к Message и User
   - Поле emoji (CharField)
   - unique_together: один пользователь = одна реакция на сообщение
   - Индексы для оптимизации

2. **API эндпоинты** (`api/v1/communications/views.py`)
   - `POST /api/v1/communications/messages/{id}/react/` - добавить/изменить реакцию
   - `POST /api/v1/communications/messages/{id}/unreact/` - удалить свою реакцию
   - `GET /api/v1/communications/messages/{id}/reactions/` - получить все реакции

3. **WebSocket поддержка** (`communications/consumers.py`)
   - Событие `reaction_added` - реакция добавлена
   - Событие `reaction_removed` - реакция удалена
   - Real-time обновления для всех участников чата

4. **Сериализация** (обновлено в `serialize_message`)
   - Реакции включены в сообщения как `reactions_summary`
   - Формат: `{emoji: {count, users, user_names}}`

### Frontend (✅ Готово)

1. **JavaScript модуль** (`static/js/components/messageReactions.js`)
   - Класс `MessageReactions` для работы с API
   - Рендеринг реакций
   - Emoji пикер
   - WebSocket обработка

2. **CSS стили** (`static/css/message-reactions.css`)
   - Стилизация кнопок реакций
   - Emoji пикер
   - Анимации
   - Темная тема
   - Адаптивность

3. **Интеграция** (`static/js/chat-reactions-integration.js`)
   - Пример подключения к чату
   - MutationObserver для новых сообщений
   - WebSocket setup

---

## 🚀 Быстрый старт

### Шаг 1: Подключите CSS

В вашем HTML шаблоне чата:

```html
<link rel="stylesheet" href="{% static 'css/message-reactions.css' %}">
```

### Шаг 2: Подключите JavaScript

```html
<script type="module" src="{% static 'js/chat-reactions-integration.js' %}"></script>
```

### Шаг 3: Убедитесь что у сообщений есть атрибут data-message-id

```html
<div class="message" data-message-id="{{ message.id }}">
    <div class="message-content">{{ message.content }}</div>
    <!-- Реакции добавятся автоматически -->
</div>
```

### Шаг 4: Передайте ID текущего пользователя

```html
<body data-user-id="{{ request.user.id }}">
```

Или через JavaScript:

```javascript
window.currentUserId = {{ request.user.id }};
```

---

## 🔧 Ручная интеграция

Если автоматическая интеграция не подходит:

```javascript
import MessageReactions from '/static/js/components/messageReactions.js';

// Создать экземпляр
const reactions = new MessageReactions({
    apiBaseUrl: '/api/v1/communications/messages',
    emojis: ['👍', '❤️', '😂', '😮', '😢', '🙏']
});

// Инициализировать для сообщения
const messageElement = document.querySelector('[data-message-id="123"]');
reactions.initMessageReactions(messageElement, 123, currentUserId);

// Обработать WebSocket события
socket.addEventListener('message', (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'reaction_added') {
        reactions.handleReactionAdded(data, currentUserId);
    } else if (data.type === 'reaction_removed') {
        reactions.handleReactionRemoved(data, currentUserId);
    }
});
```

---

## 📡 API Спецификация

### Добавить реакцию

```http
POST /api/v1/communications/messages/{message_id}/react/
Content-Type: application/json

{
    "emoji": "👍"
}
```

**Response:**
```json
{
    "ok": true,
    "created": true,
    "reaction": {
        "id": 1,
        "emoji": "👍",
        "user_id": 5,
        "created_at": "2025-11-30T12:00:00Z"
    },
    "reactions_summary": {
        "👍": {
            "count": 3,
            "users": [1, 2, 5],
            "user_names": ["John", "Jane", "Bob"]
        }
    }
}
```

### Удалить реакцию

```http
POST /api/v1/communications/messages/{message_id}/unreact/
```

**Response:**
```json
{
    "ok": true,
    "reactions_summary": {
        "👍": {
            "count": 2,
            "users": [1, 2],
            "user_names": ["John", "Jane"]
        }
    }
}
```

### Получить реакции

```http
GET /api/v1/communications/messages/{message_id}/reactions/
```

**Response:**
```json
{
    "ok": true,
    "message_id": 123,
    "reactions": {
        "👍": {
            "count": 3,
            "users": [1, 2, 5],
            "user_names": ["John", "Jane", "Bob"]
        },
        "❤️": {
            "count": 1,
            "users": [3],
            "user_names": ["Alice"]
        }
    }
}
```

---

## 🔌 WebSocket События

### Реакция добавлена

```json
{
    "type": "reaction_added",
    "message_id": 123,
    "reaction": {
        "emoji": "👍",
        "user_id": 5,
        "user_name": "Bob"
    },
    "reactions_summary": {
        "👍": {
            "count": 3,
            "users": [1, 2, 5],
            "user_names": ["John", "Jane", "Bob"]
        }
    }
}
```

### Реакция удалена

```json
{
    "type": "reaction_removed",
    "message_id": 123,
    "user_id": 5,
    "reactions_summary": {
        "👍": {
            "count": 2,
            "users": [1, 2],
            "user_names": ["John", "Jane"]
        }
    }
}
```

---

## 🎨 Кастомизация

### Изменить список эмодзи

```javascript
const reactions = new MessageReactions({
    emojis: ['👍', '❤️', '🔥', '💯', '🎉', '🚀', '👏', '😍']
});
```

### Кастомный рендеринг

```javascript
const reactions = new MessageReactions();

// Переопределить метод
reactions.renderReactions = function(reactionsSummary, currentUserId) {
    // Ваша логика рендеринга
    return customHtml;
};
```

### Изменить стили

Отредактируйте `static/css/message-reactions.css` или переопределите CSS классы:

```css
.reaction-button {
    /* Ваши стили */
}

.reaction-button.active {
    /* Стили для активной реакции */
}
```

---

## 🐛 Отладка

### Проверить что API работает

```javascript
// В консоли браузера
const reactions = window.MessageReactions;

// Добавить реакцию
await reactions.addReaction(123, '👍');

// Получить реакции
const data = await reactions.getReactions(123);
console.log(data);
```

### Проверить WebSocket

```javascript
// Проверить подключение
if (window.chatWebSocket) {
    console.log('WebSocket connected:', window.chatWebSocket.readyState);
}

// Послушать события
window.chatWebSocket.addEventListener('message', (event) => {
    const data = JSON.parse(event.data);
    if (data.type.includes('reaction')) {
        console.log('Reaction event:', data);
    }
});
```

---

## ✅ Checklist для интеграции

- [ ] Миграции применены (`python manage.py migrate`)
- [ ] CSS подключен в шаблоне
- [ ] JavaScript модуль подключен (type="module")
- [ ] У сообщений есть `data-message-id`
- [ ] ID текущего пользователя доступен
- [ ] WebSocket подключение работает
- [ ] Протестировано добавление реакции
- [ ] Протестировано удаление реакции
- [ ] Real-time обновления работают

---

## 📝 Примечания

1. **Один пользователь = одна реакция** на сообщение (constraint на уровне БД)
2. **Real-time обновления** через WebSocket для всех участников чата
3. **Emoji picker** появляется при клике на кнопку "➕"
4. **Адаптивный дизайн** работает на мобильных устройствах
5. **Темная тема** поддерживается автоматически

---

## 🚧 Что можно улучшить

- [ ] Добавить больше эмодзи (интеграция emoji-picker-element)
- [ ] Анимация при добавлении/удалении
- [ ] Группировка похожих эмодзи
- [ ] Статистика по реакциям
- [ ] Поиск по реакциям
- [ ] Экспорт реакций
