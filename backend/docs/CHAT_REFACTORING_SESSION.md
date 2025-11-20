# Chat Handler Refactoring Session

## Цель
Извлечь все встроенные скрипты чата из `templates/base.html` в отдельные модули.

## Анализ текущего состояния

### Структура chat скриптов в base.html

**Всего: 521 строка JavaScript (строки 95-624)**

Разделяется на 6 логических блоков:

#### 1. Avatar Map (6 строк, 96-101)
```javascript
window.__CHAT_AVATARS__ = {
  "{{ user.id }}": "{{ user.avatar.url }}"
};
```
**Зависимости**: Django template context (user)
**Использование**: WebSocket chat для отображения аватаров

---

#### 2. Chat Detail Handler (186 строк, 104-289)
**Функциональность**:
- Автоскролл к последнему сообщению
- Авто-рост textarea при вводе
- Кнопка "вниз" для скролла
- Разделитель "Новые сообщения"
- Отметка прочитанных (localStorage + API)
- IntersectionObserver для автоматической отметки

**Ключевые элементы**:
```javascript
const box = document.getElementById('chatScroll');
const ta = document.getElementById('id_content');
const form = document.getElementById('chatForm');
const btn = document.getElementById('scrollBtn');
```

**API endpoints**:
- `POST /communications/chat/{id}/mark-read/` - отметка прочитанных

**События**:
- `chat:read` - CustomEvent для обновления глобального счетчика

**Экспортирует**:
```javascript
window.__CHAT_MARK_READ__ = {
  markRead,
  observeLastForeign,
  autoscroll,
  atBottom
};
```

---

#### 3. WebSocket Chat (161 строк, 291-451)
**Функциональность**:
- WebSocket соединение `/ws/chat/{id}/`
- Отправка сообщений
- Получение новых сообщений в реальном времени
- Индикация "печатает..."
- Рендеринг сообщений в DOM

**Зависимости**:
- `window.__CHAT_AVATARS__` - карта аватаров
- `window.__CHAT_MARK_READ__` - методы из блока #2
- `window.esc()` - из stringUtils.js
- Django context: `{{ chat.id }}`, `{{ user.id }}`

**HTML шаблоны**:
- Создает `.msg` элементы динамически
- Создает `.day-divider` разделители

---

#### 4. Chat List Filter (42 строки, 454-495)
**Функциональность**:
- Поиск по названию чата
- Фильтр по типу (all/global/department/private)
- Скрытие пустых секций

**Ключевые элементы**:
```javascript
const search = document.getElementById('chatSearch');
const labels = document.querySelectorAll('[data-filter]');
const sections = {
  global: '.chat-section[data-sec="global"]',
  department: '.chat-section[data-sec="department"]',
  private: '.chat-section[data-sec="private"]'
};
```

**Зависимости**:
- `window.norm()` - из stringUtils.js
- HTML структура списка чатов

---

#### 5. Chat List Realtime (62 строки, 498-559)
**Функциональность**:
- WebSocket соединение `/ws/chats/`
- Обновление preview/времени/счетчика при новом сообщении
- Пересортировка списка по времени последнего сообщения

**Ключевые элементы**:
```javascript
const rows = document.querySelectorAll('.chat-row');
// Атрибуты: data-chat-id, data-last-ts, data-type
```

**Зависимости**:
- Django context: `{{ user.id }}`
- HTML структура `.chat-row`

---

#### 6. Global Badge Updater (60 строк, 560-619)
**Функциональность**:
- Обновление счетчика непрочитанных в сайдбаре
- Карта непрочитанных по всем чатам
- Подписка на WebSocket `/ws/chats/`
- Обработка события `chat:read`

**Ключевые элементы**:
```javascript
const badge = document.getElementById('sidebarChatBadge');
const chatUnread = {}; // карта непрочитанных
```

**События**:
- Слушает: `chat:read` (из блока #2)
- Подписка на WebSocket `/ws/chats/`

---

## План рефакторинга

### Шаг 1: Подготовка
- [x] Анализ зависимостей между блоками
- [ ] Определение публичного API каждого модуля
- [ ] Создание схемы взаимодействия

### Шаг 2: Создание модулей

#### 2.1. `chatAvatars.js` (простой)
```javascript
export function initChatAvatars(userId, avatarUrl) {
  window.__CHAT_AVATARS__ = window.__CHAT_AVATARS__ || {};
  if (userId && avatarUrl) {
    window.__CHAT_AVATARS__[userId] = avatarUrl;
  }
  return window.__CHAT_AVATARS__;
}
```

#### 2.2. `chatDetailHandler.js` (сложный, 186 строк)
**Экспорты**:
```javascript
export function initChatDetailHandler(options = {}) {
  // ... инициализация
  return {
    markRead,
    observeLastForeign,
    autoscroll,
    atBottom,
    destroy
  };
}
```

**Опции**:
```javascript
{
  scrollContainerId: 'chatScroll',
  textareaId: 'id_content',
  formId: 'chatForm',
  scrollBtnId: 'scrollBtn',
  chatId: null,
  meId: null,
  markReadUrl: null // или авто-определение
}
```

#### 2.3. `chatWebSocket.js` (сложный, 161 строка)
**Экспорты**:
```javascript
export function initChatWebSocket(options = {}) {
  // ... WebSocket логика
  return {
    send,
    close,
    reconnect,
    ws // прямой доступ к WebSocket
  };
}
```

**Опции**:
```javascript
{
  chatId: null, // REQUIRED
  meId: null, // REQUIRED
  scrollContainerId: 'chatScroll',
  formId: 'chatForm',
  textareaId: 'id_content',
  typingIndicatorId: 'typing',
  avatars: window.__CHAT_AVATARS__,
  markReadHandler: window.__CHAT_MARK_READ__ // или передать явно
}
```

#### 2.4. `chatListFilter.js` (средний, 42 строки)
**Экспорты**:
```javascript
export function initChatListFilter(options = {}) {
  return {
    applyFilter,
    setActiveType,
    destroy
  };
}
```

#### 2.5. `chatListRealtime.js` (средний, 62 строки)
**Экспорты**:
```javascript
export function initChatListRealtime(options = {}) {
  return {
    ws,
    disconnect,
    reconnect
  };
}
```

#### 2.6. `chatBadgeUpdater.js` (средний, 60 строк)
**Экспорты**:
```javascript
export function initChatBadgeUpdater(options = {}) {
  return {
    setBadge,
    recompute,
    getChatUnread,
    destroy
  };
}
```

### Шаг 3: Интеграция в base.html

Заменить все 6 блоков на:

```django
{% load static %}

{# Chat functionality - только для авторизованных #}
{% if user.is_authenticated %}
<script type="module">
  import { initChatAvatars } from '{% static "js/components/chat/chatAvatars.js" %}';
  import { initChatDetailHandler } from '{% static "js/components/chat/chatDetailHandler.js" %}';
  import { initChatWebSocket } from '{% static "js/components/chat/chatWebSocket.js" %}';
  import { initChatListFilter } from '{% static "js/components/chat/chatListFilter.js" %}';
  import { initChatListRealtime } from '{% static "js/components/chat/chatListRealtime.js" %}';
  import { initChatBadgeUpdater } from '{% static "js/components/chat/chatBadgeUpdater.js" %}';

  document.addEventListener('DOMContentLoaded', () => {
    // 1. Инициализация карты аватаров
    const avatars = initChatAvatars(
      "{{ user.id }}",
      {% if user.avatar %}"{{ user.avatar.url }}"{% else %}""{% endif %}
    );

    // 2. Chat detail (если мы на странице детального чата)
    {% if chat %}
    const chatDetail = initChatDetailHandler({
      chatId: {{ chat.id }},
      meId: {{ user.id }},
      markReadUrl: "{% url 'communications:chat_mark_read' chat.pk %}"
    });

    // 3. WebSocket для сообщений
    const chatWS = initChatWebSocket({
      chatId: {{ chat.id }},
      meId: {{ user.id }},
      avatars: avatars,
      markReadHandler: chatDetail
    });
    {% endif %}

    // 4. Фильтр списка чатов (если есть список)
    const listFilter = initChatListFilter();

    // 5. Realtime обновление списка
    const listRealtime = initChatListRealtime({
      meId: {{ user.id }}
    });

    // 6. Глобальный счетчик непрочитанных
    const badgeUpdater = initChatBadgeUpdater({
      meId: {{ user.id }}
    });

    // Экспорт в window для отладки
    if (chatDetail) window.chatDetail = chatDetail;
    if (chatWS) window.chatWS = chatWS;
    if (listFilter) window.chatListFilter = listFilter;
    if (listRealtime) window.chatListRealtime = listRealtime;
    if (badgeUpdater) window.chatBadgeUpdater = badgeUpdater;
  });
</script>
{% endif %}
```

### Шаг 4: Тестирование

Проверить каждый сценарий:

- [ ] Открытие страницы детального чата
  - [ ] Автоскролл к последнему сообщению
  - [ ] Разделитель "Новые сообщения" появляется
  - [ ] Textarea автоматически растет при вводе
  - [ ] Ctrl+Enter отправляет сообщение
  - [ ] Кнопка "вниз" появляется при скролле вверх

- [ ] Отправка сообщений
  - [ ] Сообщение отправляется через WebSocket
  - [ ] Сообщение появляется в чате
  - [ ] Аватар и имя отображаются правильно
  - [ ] Время форматируется корректно

- [ ] Получение сообщений
  - [ ] Новые сообщения приходят в реальном времени
  - [ ] Автоскролл работает (если в конце списка)
  - [ ] Индикация "печатает..." работает
  - [ ] Отметка прочитанных срабатывает

- [ ] Список чатов
  - [ ] Поиск работает
  - [ ] Фильтр по типу работает
  - [ ] Пустые секции скрываются
  - [ ] Preview/время обновляются при новом сообщении
  - [ ] Счетчик непрочитанных обновляется
  - [ ] Сортировка по времени работает

- [ ] Глобальный счетчик
  - [ ] Бейдж обновляется при новых сообщениях
  - [ ] Бейдж обнуляется при прочтении
  - [ ] События `chat:read` обрабатываются

### Шаг 5: Документация

- [ ] JSDoc для всех публичных функций
- [ ] README.md в `static/js/components/chat/`
- [ ] Примеры использования
- [ ] Описание событий и API

---

## Технические детали

### Зависимости между модулями

```
chatAvatars.js
    ↓
chatWebSocket.js ← chatDetailHandler.js
    ↓                   ↓
chatListRealtime.js → chatBadgeUpdater.js
    ↓
chatListFilter.js
```

### Глобальные объекты (для обратной совместимости)

```javascript
window.__CHAT_AVATARS__ = {}; // карта аватаров
window.__CHAT_MARK_READ__ = {}; // методы chatDetailHandler
```

### События

**Генерируются**:
- `chat:read` - CustomEvent при отметке прочитанного
  ```javascript
  window.dispatchEvent(new CustomEvent('chat:read', {
    detail: { chatId: '123' }
  }));
  ```

**Обрабатываются**:
- `chat:read` - в chatBadgeUpdater для обнуления счетчика

### WebSocket endpoints

1. `/ws/chat/{id}/` - детальный чат (сообщения)
   - Отправка: `{ content: "текст" }` или `{ type: 'typing' }`
   - Получение: `{ type: 'message', payload: {...} }`

2. `/ws/chats/` - список чатов (обновления)
   - Получение: `{ type: 'list_update', chat_id: 123, message: {...} }`

### API endpoints

- `POST /communications/chat/{id}/mark-read/`
  - Body: `upto_ts=1234567890`
  - Response: 200 OK

---

## Оценка сложности

**Время**: ~2-3 часа чистого кодинга + тестирование

**Приоритет модулей** (по сложности):

1. ✅ `chatAvatars.js` - тривиальный (5 минут)
2. ⚠️ `chatListFilter.js` - простой (15 минут)
3. ⚠️ `chatBadgeUpdater.js` - средний (30 минут)
4. ⚠️ `chatListRealtime.js` - средний (30 минут)
5. 🔴 `chatDetailHandler.js` - сложный (60 минут)
6. 🔴 `chatWebSocket.js` - сложный (60 минут)

**Рекомендуемый порядок**:
1. chatAvatars (быстрая победа)
2. chatListFilter (независимый)
3. chatBadgeUpdater (зависит от chatListRealtime событий)
4. chatListRealtime (нужен для badgeUpdater)
5. chatDetailHandler (нужен для WebSocket)
6. chatWebSocket (последний, самый сложный)

---

## Потенциальные проблемы

1. **Порядок инициализации**: chatWebSocket зависит от chatDetailHandler
   - Решение: передавать chatDetail как параметр в chatWebSocket

2. **Django template context**: chatId, meId нужны из контекста
   - Решение: передавать через параметры при инициализации

3. **HTML структура**: модули зависят от конкретных селекторов
   - Решение: делать проверки `if (!element) return null;`

4. **WebSocket reconnect**: при потере соединения нужно перезагрузить страницу
   - Решение: оставить `setTimeout(() => location.reload(), 2000)`

5. **Обратная совместимость**: другие скрипты могут зависеть от `window.__CHAT_MARK_READ__`
   - Решение: экспортировать в window для совместимости

---

## Результат

**До рефакторинга**:
- base.html: 521 строка встроенного JS
- 0 переиспользуемых модулей
- Нет документации
- Невозможно тестировать изолированно

**После рефакторинга**:
- base.html: ~40 строк инициализации
- 6 переиспользуемых модулей (~600 строк с документацией)
- JSDoc для всех публичных функций
- Возможность unit-тестирования
- Четкое разделение ответственности

**Сокращение**: 521 → 40 строк = **92% reduction** 🎉
