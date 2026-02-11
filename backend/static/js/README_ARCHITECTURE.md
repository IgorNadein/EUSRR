# Архитектура JavaScript модулей календарной системы

## 📁 Структура директорий

```
static/js/
├── api/                        # API обёртки с кешированием
│   ├── calendarApi.js         # События календаря (GET)
│   └── calendarsApi.js        # CRUD календарей + подписки
│
├── components/                 # UI компоненты
│   ├── calendarWidget/        # Модули основного виджета (планируется)
│   ├── calendarWidget.js      # Основной виджет FullCalendar
│   ├── calendarWidgetIntegration.js  # Интеграция виджета с менеджером
│   ├── calendarManager.js     # Управление списком календарей
│   └── calendarManageModal.js # Модальное окно CRUD календаря
│
├── constants/                  # Константы и энумы
│   ├── calendarTypes.js       # Типы календарей, цвета
│   └── apiUrls.js            # URL эндпоинтов API
│
├── utils/                     # Утилитные функции
│   ├── authUtils.js          # Авторизация (токены, headers)
│   ├── dateUtils.js          # Работа с датами
│   └── calendarTypeResolver.js # Определение типа календаря
│
└── managers/                  # Менеджеры (уже существуют)
    └── dataManager.js        # Кеширование данных
```

## 🔧 Модули

### API Layer (`api/`)

#### `calendarApi.js`
**Назначение:** Работа с событиями календаря (чтение)

**Экспорт:**
- `getCalendarEvents(params, ttl)` - получить события
- `getCalendarEvent(eventId, ttl)` - получить событие по ID
- `invalidateCalendarEvents(params)` - инвалидировать кеш
- `preloadCalendarEvents(params, events)` - предзагрузка

**Зависимости:**
```javascript
import { dataManager } from '../managers/dataManager.js';
import { authHeaders } from '../utils/authUtils.js';
import { API_URLS, API_DEFAULTS } from '../constants/apiUrls.js';
```

#### `calendarsApi.js`
**Назначение:** CRUD операции с календарями + подписки

**Экспорт:**
- `getMyCalendars(ttl)` - получить мои календари
- `getCalendar(calendarId, ttl)` - получить календарь по ID
- `createCalendar(calendarData)` - создать календарь
- `updateCalendar(calendarId, updates)` - обновить календарь
- `deleteCalendar(calendarId)` - удалить календарь
- `subscribeToCalendar(calendarId, options)` - подписаться
- `unsubscribeFromCalendar(calendarId)` - отписаться
- `invalidateCalendarsCache()` - инвалидировать кеш

**Зависимости:**
```javascript
import { dataManager } from '../managers/dataManager.js';
import { authHeaders, getCsrfToken } from '../utils/authUtils.js';
import { API_URLS, API_DEFAULTS } from '../constants/apiUrls.js';
```

---

### Constants Layer (`constants/`)

#### `calendarTypes.js`
**Назначение:** Типы календарей, цвета, утилиты

**Экспорт:**
```javascript
// Енумы
export const CALENDAR_TYPES = {
  LEGACY_COMPANY: 'legacy-company',
  LEGACY_PERSONAL: 'legacy-personal',
  LEGACY_DEPT_PREFIX: 'legacy-dept-',
  COMPANY: 'company',
  PERSONAL: 'personal',
  DEPARTMENT: 'department',
  PUBLIC: 'public',
  PRIVATE: 'private',
  CUSTOM: 'custom',
};

export const CALENDAR_COLORS = {
  COMPANY: '#dc3545',
  PERSONAL: '#0d6efd',
  DEPARTMENT: '#198754',
  PUBLIC: '#6c757d',
  DEFAULT: '#0d6efd',
};

// Утилиты
export function isLegacyCalendar(id)
export function getLegacyCalendarType(id)
export function extractDepartmentId(legacyId)
export function createLegacyDeptId(departmentId)
```

#### `apiUrls.js`
**Назначение:** URL эндпоинтов API, дефолтные параметры

**Экспорт:**
```javascript
export const API_URLS = {
  EVENTS: '/api/v1/calendar/events/',
  EVENT_DETAIL: (id) => `/api/v1/calendar/events/${id}/`,
  CALENDARS: '/api/v1/calendar/calendars/',
  CALENDAR_DETAIL: (id) => `/api/v1/calendar/calendars/${id}/`,
  CALENDAR_SUBSCRIBE: (id) => `/api/v1/calendar/calendars/${id}/subscribe/`,
  CALENDAR_UNSUBSCRIBE: (id) => `/api/v1/calendar/calendars/${id}/unsubscribe/`,
  MY_DEPARTMENTS: '/api/v1/departments/my-departments/',
};

export const API_DEFAULTS = {
  TTL: {
    EVENTS: 30000,        // 30 секунд
    EVENT_DETAIL: 60000,  // 1 минута
    CALENDARS: 60000,     // 1 минута
    DEPARTMENTS: 300000,  // 5 минут
  },
  TIMEOUT: {
    DEFAULT: 10000,
    UPLOAD: 30000,
  },
};

export function getApiUrl(path, baseUrl)
```

---

### Utils Layer (`utils/`)

#### `authUtils.js`
**Назначение:** Работа с токенами и авторизацией

**Экспорт:**
```javascript
export function getAccessToken()        // Получить Bearer токен
export function getCsrfToken()          // Получить CSRF токен
export function getCookie(name)         // Получить cookie
export function authHeaders(includeContentType) // Заголовки для API
export function hasValidToken()         // Проверка наличия токена
```

**Использование:**
```javascript
import { authHeaders } from '../utils/authUtils.js';

const response = await fetch('/api/v1/events/', {
  headers: authHeaders()
});
```

#### `dateUtils.js`
**Назначение:** Работа с датами и временем

**Экспорт:**
```javascript
export function formatDate(date)              // YYYY-MM-DD
export function ymdLocal(date)                // YYYY-MM-DD (локальное время)
export function fmtDate(date)                 // ДД.ММ.ГГГГ
export function fmtTime(date)                 // ЧЧ:ММ
export function formatEventPeriod(event)      // Период события
export function addDateRangeToUrl(url, start, end)
export function parseDate(dateStr)            // Парсинг даты
export function startOfDay(date)              // Начало дня
export function endOfDay(date)                // Конец дня
```

**Использование:**
```javascript
import { formatDate, formatEventPeriod } from '../utils/dateUtils.js';

const startStr = formatDate(new Date());
const period = formatEventPeriod(event);
```

#### `calendarTypeResolver.js`
**Назначение:** Определение типа календаря и параметров запросов

**Экспорт:**
```javascript
export function resolveCalendarParams(calendarId, baseParams)
  // Определить параметры для API запроса
  
export function resolveEventPayload(calendarId, eventData)
  // Определить payload для создания/обновления события
  
export function getCalendarTypeName(calendarId, calendars)
  // Получить человекочитаемое имя типа
  
export function canEditCalendar(calendarId, calendars)
  // Проверить права на редактирование
  
export function isValidCalendarId(calendarId)
  // Валидация ID календаря
```

**Использование:**
```javascript
import { resolveCalendarParams, resolveEventPayload } from '../utils/calendarTypeResolver.js';

// Загрузка событий
const params = resolveCalendarParams(calendarId, { start, end });
const events = await getCalendarEvents(params);

// Создание события
const payload = resolveEventPayload(calendarId, eventData);
await createEvent(payload);
```

---

### Components Layer (`components/`)

#### `calendarWidget.js` (1821 строка)
**Статус:** 🔴 Требует рефакторинга

**Планируется декомпозиция на:**
```
components/calendarWidget/
├── index.js                  # Главный экспорт + инициализация
├── fullcalendarConfig.js     # Конфигурация FullCalendar
├── eventHandlers.js          # Submit, click, context menu
├── eventRendering.js         # eventDidMount, eventContent
├── weekListRenderer.js       # renderVertical, updateWeekLists
├── formHelpers.js            # syncByRecurrence, initColorPicker
└── permissions.js            # checkEventPermissions
```

#### `calendarWidgetIntegration.js` (340 строк)
**Статус:** ✅ Хорошо

**Назначение:** Связка calendarWidget с calendarManager

**Зависимости:**
```javascript
import { initCalendarManager } from "./calendarManager.js";
import { initCalendarManageModal } from "./calendarManageModal.js";
import { getCalendarEvents } from "../api/calendarApi.js";
import { formatDate } from "../utils/dateUtils.js";
import { resolveCalendarParams } from "../utils/calendarTypeResolver.js";
```

#### `calendarManager.js` (398 строк)
**Статус:** ✅ Отлично

**Назначение:** UI-компонент для списка календарей

**Зависимости:**
```javascript
import {
  getMyCalendars,
  subscribeToCalendar,
  unsubscribeFromCalendar,
  invalidateCalendarsCache,
} from "../api/calendarsApi.js";
import {
  CALENDAR_TYPES,
  CALENDAR_COLORS,
  createLegacyDeptId,
} from "../constants/calendarTypes.js";
```

#### `calendarManageModal.js` (290 строк)
**Статус:** ✅ Эталон качества

**Назначение:** Модальное окно создания/редактирования календаря

---

## 🔄 Миграция и обратная совместимость

### Legacy система

Поддержка старой системы календарей через legacy ID:
- `legacy-company` - корпоративный календарь
- `legacy-personal` - личный календарь
- `legacy-dept-{id}` - календарь отдела

### Новая система

Календари с числовым ID из модели `Calendar`:
- `123` - новый календарь (number)

### Автоматическое определение

```javascript
import { resolveCalendarParams } from '../utils/calendarTypeResolver.js';

// Автоматически определяет тип и добавляет нужные параметры
const params = resolveCalendarParams(calendarId, { start, end });

// legacy-company → { start, end }
// legacy-personal → { start, end, employee_id }
// legacy-dept-5 → { start, end, department_id: 5 }
// 123 → { start, end, calendar_id: 123 }
```

---

## 📦 Импорты и зависимости

### Правила импортов

1. **Всегда используйте относительные пути**
   ```javascript
   import { authHeaders } from '../utils/authUtils.js';
   ```

2. **Группируйте импорты**
   ```javascript
   // 1. Сторонние библиотеки (если есть)
   import { Calendar } from '@fullcalendar/core';
   
   // 2. API слой
   import { getCalendarEvents } from '../api/calendarApi.js';
   
   // 3. Константы
   import { CALENDAR_TYPES } from '../constants/calendarTypes.js';
   
   // 4. Утилиты
   import { authHeaders } from '../utils/authUtils.js';
   import { formatDate } from '../utils/dateUtils.js';
   
   // 5. Компоненты
   import { initCalendarManager } from './calendarManager.js';
   ```

3. **Не создавайте циклические зависимости**
   - ❌ `utils → components → utils`
   - ✅ `components → utils → constants`

### Граф зависимостей

```
┌─────────────────┐
│   constants/    │ ◄─── Базовый слой (нет зависимостей)
└────────┬────────┘
         │
┌────────▼────────┐
│     utils/      │ ◄─── Зависит только от constants
└────────┬────────┘
         │
┌────────▼────────┐
│   managers/     │ ◄─── Зависит от utils
└────────┬────────┘
         │
┌────────▼────────┐
│      api/       │ ◄─── Зависит от utils, constants, managers
└────────┬────────┘
         │
┌────────▼────────┐
│  components/    │ ◄─── Зависит от api, utils, constants
└─────────────────┘
```

---

## 🎯 Следующие шаги

### P0 - Критично (Sprint 1)

- [x] ✅ Создать `utils/authUtils.js`
- [x] ✅ Создать `utils/dateUtils.js`
- [x] ✅ Создать `constants/calendarTypes.js`
- [x] ✅ Создать `constants/apiUrls.js`
- [x] ✅ Создать `utils/calendarTypeResolver.js`
- [x] ✅ Обновить `api/calendarApi.js` (использовать новые утилиты)
- [x] ✅ Обновить `api/calendarsApi.js` (использовать новые утилиты)
- [x] ✅ Обновить `components/calendarWidgetIntegration.js`
- [x] ✅ Обновить `components/calendarManager.js`
- [ ] 🔧 Обновить `components/calendarWidget.js` (частично)
- [ ] 🔧 Тестирование новой структуры

### P1 - Важно (Sprint 2)

- [ ] 📦 Разделить `calendarWidget.js` на модули
- [ ] 📦 Создать `components/calendarWidget/` директорию
- [ ] 📦 Переместить eventDidMount логику в отдельный файл
- [ ] 📦 Переместить form handlers в отдельный файл

### P2 - Желательно (Sprint 3)

- [ ] 📝 Добавить unit-тесты для utils
- [ ] 📝 Добавить integration-тесты для API
- [ ] 📝 TypeScript миграция (.js → .ts)

---

## 🧪 Тестирование

### Ручное тестирование

1. **Проверка импортов**
   ```bash
   # Проверить нет ли ошибок в консоли
   grep -r "import.*from" static/js/
   ```

2. **Проверка работы календаря**
   - Открыть страницу с календарём
   - Проверить загрузку событий
   - Создать новое событие
   - Отредактировать событие
   - Удалить событие

3. **Проверка legacy режима**
   - Переключить на legacy-company
   - Переключить на legacy-personal
   - Переключить на legacy-dept-X

### Автоматическое тестирование (TODO)

```javascript
// tests/utils/authUtils.test.js
import { authHeaders, getAccessToken } from '../utils/authUtils.js';

describe('authUtils', () => {
  it('should return headers with Bearer token', () => {
    const headers = authHeaders();
    expect(headers).toHaveProperty('Authorization');
  });
});
```

---

## 📝 Соглашения о коде

### JSDoc комментарии

```javascript
/**
 * Краткое описание функции
 * @param {Type} paramName - Описание параметра
 * @param {Type} [optionalParam] - Опциональный параметр
 * @returns {ReturnType} Описание возвращаемого значения
 * @throws {Error} Когда выбрасывается ошибка
 * @example
 * const result = myFunction('value');
 */
export function myFunction(paramName, optionalParam) {
  // ...
}
```

### Именование

- **Функции:** `camelCase` (`getCalendarEvents`, `formatDate`)
- **Константы:** `UPPER_SNAKE_CASE` (`CALENDAR_TYPES`, `API_URLS`)
- **Приватные функции:** начинаются с `_` (если нужно)
- **Компоненты:** `PascalCase` в названии файла (`CalendarManager.js`)

### Файловая структура модуля

```javascript
// 1. JSDoc для всего модуля
/**
 * @fileoverview Краткое описание модуля
 * @module путь/к/модулю
 */

// 2. Импорты (сгруппированные)
import { ... } from '...';

// 3. Приватные константы и функции
const PRIVATE_CONST = ...;
function _privateFunction() { ... }

// 4. Экспортируемые функции
export function publicFunction() { ... }

// 5. Дефолтный экспорт (если есть)
export default { ... };
```

---

## 🔍 Диагностика проблем

### Ошибка: "Cannot find module"

**Причина:** Неправильный относительный путь импорта

**Решение:**
```javascript
// ❌ Неправильно
import { authHeaders } from 'utils/authUtils.js';

// ✅ Правильно
import { authHeaders } from '../utils/authUtils.js';
```

### Ошибка: "X is not defined"

**Причина:** Забыли импортировать функцию/константу

**Решение:**
```javascript
// Добавить импорт
import { CALENDAR_TYPES } from '../constants/calendarTypes.js';
```

### Ошибка: "Circular dependency"

**Причина:** Циклическая зависимость между модулями

**Решение:** Вынести общую логику в отдельный модуль

---

## 📚 Дополнительные ресурсы

- [ES6 Modules Guide](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide/Modules)
- [JSDoc Documentation](https://jsdoc.app/)
- [Clean Code JavaScript](https://github.com/ryanmcdermott/clean-code-javascript)

---

**Последнее обновление:** 11 февраля 2026  
**Версия:** 1.0.0  
**Автор:** GitHub Copilot
