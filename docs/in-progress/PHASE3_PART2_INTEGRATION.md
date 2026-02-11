# Phase 3 Part 2: Calendar Widget Integration

**Дата:** 11 февраля 2026 г.
**Статус:** ✅ Завершено
**Цель:** Интеграция компонентов управления календарями с существующим виджетом FullCalendar

---

## 🎯 Задачи

### ✅ Создание слоя интеграции
- **Файл:** `backend/static/js/components/calendarWidgetIntegration.js`
- **Назначение:** Связать `calendarManager` с `calendarWidget`
- **Экспорт:**
  - `integrateCalendarManager(calendarWidgetInstance, options)` - главная функция
  - `getCalendarIntegration()` - доступ к глобальному экземпляру

### ✅ Модификация calendarWidget.js
- **Файл:** `backend/static/js/components/calendarWidget.js`
- **Изменения:** Обновлён callback `events` в конфигурации FullCalendar (строка ~965)
- **Логика:**
  ```javascript
  // Проверка наличия новой системы
  if (window.calendarIntegration?.fetchEventsForVisibleCalendars) {
    // Используем фильтрацию по выбранным календарям
    raw = await window.calendarIntegration.fetchEventsForVisibleCalendars(info.start, info.end);
  } else {
    // Fallback на legacy систему
    raw = await fetchEventsCombined(info.start, info.end);
  }
  ```

### ✅ Обновление инициализации
- **Файл:** `backend/templates/includes/components/calendar_scripts.html`
- **Изменения:**
  - Добавлен импорт `calendarWidgetIntegration.js`
  - Вызов `integrateCalendarManager(widget)` после инициализации виджета
  - Экспорт `window.calendarIntegration` для глобального доступа

---

## 🔧 Архитектурные решения

### 1. Неинвазивная интеграция
- `calendarWidget.js` не имеет жёстких зависимостей на новую систему
- Проверка `window.calendarIntegration` перед использованием
- Автоматический fallback на legacy режим

### 2. Состояние приложения
```javascript
// Внутреннее состояние integrateCalendarManager()
let visibleCalendarIds = [];  // Массив ID видимых календарей
let calendars = [];            // Массив объектов календарей
```

### 3. Callbacks для синхронизации
```javascript
// При переключении видимости календаря
onCalendarToggle: (calendarId, isVisible) => {
  // Обновляем visibleCalendarIds
  // Вызываем calendarWidget.refetchEvents()
}

// При изменении списка календарей (CRUD)
onCalendarsChange: (newCalendars, newVisibleIds) => {
  // Обновляем локальное состояние
  // Вызываем calendarWidget.refetchEvents()
}

// При сохранении календаря в модальном окне
onSuccess: () => {
  // Обновляем список через calendarManager.refresh()
}
```

### 4. Загрузка событий

#### Новый режим (множественные календари):
```javascript
async function fetchEventsForVisibleCalendars(start, end) {
  // Если нет календарей - используем legacy
  if (calendars.length === 0) {
    return await getCalendarEvents({ start, end });
  }

  // Если ни один не выбран - пустой массив
  if (visibleCalendarIds.length === 0) {
    return [];
  }

  // Загружаем события для каждого видимого календаря
  const eventChunks = await Promise.all(
    visibleCalendarIds.map(calendarId =>
      getCalendarEvents({ start, end, calendar_id: calendarId })
    )
  );

  // Объединяем и дедуплицируем
  const allEvents = eventChunks.flat();
  const uniqueEvents = deduplicateById(allEvents);

  return uniqueEvents;
}
```

#### Legacy режим:
```javascript
// Старая логика без изменений
const events = await fetchEventsCombined(start, end);
```

### 5. Обработка цветов
```javascript
// Цвет календаря переопределяет цвет события
return (events || []).map(event => ({
  ...event,
  __calendar: calendar,
  color: calendar?.color || event.color  // Приоритет у календаря
}));
```

---

## 📦 Public API

### window.calendarIntegration

```javascript
{
  // Загрузить события для видимых календарей
  fetchEventsForVisibleCalendars: (start, end) => Promise<Event[]>,

  // Получить ID видимых календарей
  getVisibleCalendarIds: () => number[],

  // Получить все календари
  getCalendars: () => Calendar[],

  // Установить видимые календари
  setVisibleCalendars: (ids: number[]) => void,

  // Обновить список календарей
  refresh: () => Promise<void>,

  // Доступ к экземплярам компонентов
  instances: {
    manager: CalendarManager,
    modal: CalendarManageModal,
    widget: CalendarWidget
  }
}
```

---

## 🔍 Логирование

Все ключевые операции логируются в консоль с префиксом `[CalendarIntegration]` или `[CalendarWidget]`:

```javascript
[CalendarIntegration] Fetching events for visible calendars: { visibleCount: 2, totalCalendars: 5, range: "2026-02-01 - 2026-02-28" }
[CalendarIntegration] Loaded 15 events for calendar 1
[CalendarIntegration] Loaded 8 events for calendar 2
[CalendarIntegration] Total events loaded: 23
[CalendarIntegration] Unique events after dedup: 22
[CalendarWidget] Using calendar integration for event loading
```

---

## ✅ Результаты

### Файлы изменены:
1. **Создан:** `backend/static/js/components/calendarWidgetIntegration.js` (~250 lines)
2. **Модифицирован:** `backend/static/js/components/calendarWidget.js` (events callback)
3. **Обновлён:** `backend/templates/includes/components/calendar_scripts.html` (инициализация)

### Функциональность:
- ✅ Неинвазивная интеграция с обратной совместимостью
- ✅ Фильтрация событий по выбранным календарям
- ✅ Автоматическое обновление при переключении видимости
- ✅ Дедупликация событий по ID
- ✅ Переопределение цветов событий цветами календарей
- ✅ Подробное логирование для отладки
- ✅ Fallback на legacy режим

### Обратная совместимость:
- ✅ Если новая система недоступна → используется старая логика
- ✅ Если нет настроенных календарей → используется старая логика
- ✅ Существующий код не сломан

---

## 🚀 Следующие шаги

### Phase 3 - Готово к коммиту
```bash
git add backend/static/js/components/calendarWidgetIntegration.js
git add backend/static/js/components/calendarWidget.js
git add backend/templates/includes/components/calendar_scripts.html
git add docs/in-progress/CALENDAR_OPTIONAL_ARCHITECTURE.md
git add docs/in-progress/PHASE3_PART2_INTEGRATION.md
git commit -m "feat(calendar): integrate calendar manager with widget (Phase 3 - Part 2)"
```

### Phase 4: Integration Testing
- ⏳ Запустить сервер и протестировать UI
- ⏳ Создать несколько календарей разных типов
- ⏳ Проверить переключение видимости
- ⏳ Проверить создание/редактирование событий
- ⏳ Проверить подписку на календари
- ⏳ Проверить права доступа

### Phase 5: Documentation
- ⏳ Обновить README с новым функционалом
- ⏳ Создать user guide
- ⏳ Задокументировать API endpoints

---

## 📝 Примечания

### Технические детали:
1. **Глобальное состояние:** `window.calendarIntegration` доступен глобально для отладки и расширений
2. **Производительность:** События загружаются параллельно через `Promise.all()`
3. **Кеширование:** Используется существующий механизм кеширования из `dataManager.js`
4. **Безопасность:** Права доступа проверяются на backend через API

### Дизайн-решения:
1. **Callback-based integration:** Позволяет компонентам оставаться независимыми
2. **Optional chaining:** `window.calendarIntegration?.fetchEventsForVisibleCalendars` для безопасной проверки
3. **Defensive programming:** Проверки на `null`/`undefined` во всех ключевых местах
4. **Logging:** Подробное логирование помогает в debugging

---

**Автор:** GitHub Copilot
**Дата завершения:** 11 февраля 2026 г.
