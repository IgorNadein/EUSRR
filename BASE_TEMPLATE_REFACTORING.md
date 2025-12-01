# Рефакторинг base.html

## Проблема
`base.html` содержит много chat-специфичной логики, которая должна быть только на страницах чатов.

## Принципы рефакторинга

### ✅ Что ДОЛЖНО быть в base.html (универсальное):
1. **Базовая структура** - navbar, sidebar, rightbar, main
2. **Глобальные утилиты** - stringUtils, timing, scroll
3. **Глобальные переменные** - `window.currentUserId`
4. **Универсальный WebSocket** - подключение к `ws/`, но БЕЗ chat-специфичной логики
5. **Notification Manager** - уведомления нужны везде
6. **Theme Initializer** - тема нужна везде
7. **Bootstrap, Icons** - базовые библиотеки

### ❌ Что НУЖНО убрать из base.html (chat-специфичное):
1. **chatAvatarMap** - нужен только на страницах чатов
2. **chatMarkRead** - только для chat_detail.html
3. **chatListFilter** - только для chat_list.html
4. **chatBadgeManager** - только для страниц с чатами
5. **chatListRealtime** - только для chat_list.html
6. **Sidebar badge logic** - должна быть в отдельном модуле
7. **Chat-специфичные обработчики в userWebSocket** - `onListUpdate`, `markReadApi`

## План действий

### Шаг 1: Создать chat-специфичные include файлы

**`includes/chat_scripts.html`** - общие скрипты для всех страниц чатов:
```django
{# Загружается на chat_list.html и chat_detail.html #}
- chatAvatarMap
- chatBadgeManager
- userWebSocket инициализация с chat-обработчиками
- Sidebar badge logic
```

**`includes/chat_detail_scripts.html`** - только для chat_detail.html:
```django
- chatMarkRead
- chatComposer
- chatHistoryLoader
- chat-detail-enhanced
```

**`includes/chat_list_scripts.html`** - только для chat_list.html:
```django
- chatListFilter
- chatListRealtime
```

### Шаг 2: Упростить base.html

**Что остаётся:**
```javascript
// Глобальные утилиты
import { esc, norm, ... } from 'stringUtils.js';
import { debounce, throttle } from 'timing.js';
import { smoothScrollTo, ... } from 'scroll.js';

// Базовые компоненты
import { initNavbarHeight } from 'navbarHeight.js';
import { initLikeHandler } from 'likeHandler.js';

// Универсальный WebSocket (БЕЗ chat-специфики)
import { initUserWebSocket } from 'userWebSocket.js';

// Базовая инициализация
const userWs = initUserWebSocket({
  userId: {{ user.id }}
});
window.userWebSocket = userWs;
```

### Шаг 3: Обновить chat_detail.html

```django
{% extends "base.html" %}

{% block extra_js %}
  {% include "includes/chat_scripts.html" %}
  {% include "includes/chat_detail_scripts.html" %}
{% endblock %}
```

### Шаг 4: Обновить chat_list.html

```django
{% extends "base.html" %}

{% block extra_js %}
  {% include "includes/chat_scripts.html" %}
  {% include "includes/chat_list_scripts.html" %}
{% endblock %}
```

## Результат

### До:
- ❌ base.html: 250 строк, много chat-логики
- ❌ Все chat-модули загружаются на всех страницах
- ❌ Сложно понять, что где используется

### После:
- ✅ base.html: ~120 строк, только универсальное
- ✅ Chat-модули загружаются только на нужных страницах
- ✅ Чёткое разделение ответственности
- ✅ Легко добавлять новые модули

## Архитектура модулей

```
base.html (универсальные модули)
├─ stringUtils.js
├─ timing.js
├─ scroll.js
├─ navbarHeight.js
├─ likeHandler.js
├─ userWebSocket.js (базовое подключение)
└─ notification-manager.js

includes/chat_scripts.html (общее для всех chat-страниц)
├─ chatAvatarMap.js
├─ chatBadgeManager.js
├─ sidebarBadge.js (новый модуль)
└─ userWebSocket.js (расширенная инициализация с chat-обработчиками)

includes/chat_detail_scripts.html (только для chat_detail.html)
├─ chatMarkRead.js
├─ chatComposer.js
├─ chatHistoryLoader.js
└─ chat-detail-enhanced.js
   ├─ messageReactions.js
   ├─ messageContextMenu.js
   ├─ messageSelection.js
   ├─ chatPoll.js
   └─ messageEditing.js

includes/chat_list_scripts.html (только для chat_list.html)
├─ chatListFilter.js
└─ chatListRealtime.js
```
