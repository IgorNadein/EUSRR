# Исправление Drag & Drop для перемещения событий

## Дата: 12 февраля 2026 г.

## Проблемы

### 1. Пустой модал выбора события
**Симптом**: При перетаскивании badge календаря модальное окно открывалось, но список событий был пустым.

**Причина**:
- В HTML модала элемент `#eventPickerLoading` имел класс без `d-none`, а `#eventPickerEmpty` имел `d-none`
- Это приводило к тому, что крутилка показывалась постоянно и скрывала список событий
- Не было логирования для отладки

### 2. Drag & Drop не работал для стандартных (legacy) календарей
**Симптом**: Badge событий в стандартных календарях (Компания, Личный, Отделы) не перетаскивался.

**Причина**:
- Legacy календари рендерятся как `.calendar-folder` с `data-folder-id`, а не как `.calendar-list-item` с `data-calendar-id`
- Функция `initDragDropForCalendar()` искала только `data-calendar-id`
- Селектор badge искал только `.badge.bg-secondary-subtle` (для дочерних календарей), но не `.badge.bg-info-subtle` (для папок)
- Функция `refreshDragDrop()` искала только `.calendar-list-item`, пропуская `.calendar-folder`

## Исправления

### Файл: `backend/static/js/components/calendarEventDragDrop.js`

#### 1. Исправлен HTML модала (строки 47-56)
```javascript
<div id="eventPickerList" class="list-group"></div>
<div id="eventPickerEmpty" class="text-center text-muted py-4 d-none">
  <i class="bi-inbox fs-1 d-block mb-2"></i>
  <p>Нет событий для перемещения</p>
</div>
<div id="eventPickerLoading" class="text-center py-4 d-none">
  <div class="spinner-border text-primary" role="status">
    <span class="visually-hidden">Загрузка...</span>
  </div>
</div>
```
**Изменение**: Оба элемента теперь имеют `d-none` по умолчанию, управляются через JS.

#### 2. Добавлено логирование в `loadCalendarEvents()` (строки 95-125)
```javascript
console.log("[EventDragDrop] Loading events for calendar:", calendarId);
// ...
console.log("[EventDragDrop] Received events:", events);
console.log("[EventDragDrop] Upcoming events:", upcomingEvents.length);
```
**Цель**: Отладка загрузки событий, проверка фильтрации.

#### 3. Поддержка legacy календарей в `initDragDropForCalendar()` (строки 240-250)
```javascript
// Поддержка как data-calendar-id (новые календари), так и data-folder-id (legacy)
const calendarId = calendarElement.dataset.calendarId || calendarElement.dataset.folderId;

// Ищем badge с количеством событий
const badge = calendarElement.querySelector(
  ".badge.bg-secondary-subtle.text-secondary, .badge.bg-info-subtle.text-info",
);
```
**Изменения**:
- Поддержка обоих атрибутов: `data-calendar-id` и `data-folder-id`
- Расширенный селектор badge для обоих типов (secondary для календарей, info для папок)

#### 4. Расширенная логика drop zone (строки 270-310)
```javascript
const targetCalendarId = calendarElement.dataset.calendarId || calendarElement.dataset.folderId;
// Убираем подсветку для всех типов элементов
document.querySelectorAll(".calendar-list-item, .calendar-folder").forEach((el) => {
  el.classList.remove("drop-target-active");
});
```
**Изменения**: Поддержка обоих типов элементов в drag-end и drop handlers.

#### 5. Обновлена функция `refreshDragDrop()` (строки 315-327)
```javascript
function refreshDragDrop() {
  // Новые календари (внутри папок)
  const calendarItems = document.querySelectorAll(".calendar-list-item");
  calendarItems.forEach(initDragDropForCalendar);

  // Legacy календари (отображаются как папки)
  const folderHeaders = document.querySelectorAll(".calendar-folder");
  folderHeaders.forEach(initDragDropForCalendar);

  console.log("[EventDragDrop] Initialized drag-drop for:", {
    calendars: calendarItems.length,
    folders: folderHeaders.length
  });
}
```
**Изменения**:
- Отдельная инициализация для `.calendar-list-item` (новые календари)
- Отдельная инициализация для `.calendar-folder` (legacy календари)
- Логирование количества инициализированных элементов

## Результат

### ✅ Исправлено
1. **Модал выбора события теперь показывает список событий** - правильное управление видимостью элементов
2. **Drag & Drop работает для стандартных календарей** - badge в папках перетаскивается
3. **Drag & Drop работает для новых календарей** - badge в дочерних календарях перетаскивается
4. **Добавлено логирование** - в консоли видны этапы работы drag-drop

### 🔍 Отладка
При открытии страницы в консоли должны появиться логи:
```
[EventDragDrop] Initialized drag-drop for: {calendars: N, folders: M}
```

При перетаскивании badge:
```
[EventDragDrop] Drag started: <calendar_id>
[EventDragDrop] Drop event: {from: <source_id>, to: <target_id>}
[EventDragDrop] Loading events for calendar: <calendar_id>
[EventDragDrop] Received events: [...]
[EventDragDrop] Upcoming events: N
```

## Тестирование

### Сценарий 1: Перемещение из стандартного календаря
1. Открыть календарь
2. Перетащить badge событий из "Компания" или "Личный календарь" на другой календарь
3. Должен открыться модал с списком будущих событий
4. Выбрать событие → оно переместится

### Сценарий 2: Перемещение из нового календаря
1. Создать новый календарь внутри папки
2. Добавить событие в этот календарь
3. Перетащить badge этого календаря на другой календарь
4. Должен открыться модал с событием
5. Выбрать событие → оно переместится

### Сценарий 3: Пустой календарь
1. Перетащить badge календаря без событий
2. Должен открыться модал с текстом "Нет событий для перемещения"

## API

### GET /api/v1/calendar/events/?calendar_id={id}
Используется для загрузки списка событий календаря.

**Параметры**:
- `calendar_id` - ID календаря (поддерживается как числовой, так и legacy строковый ID)

**Ответ**: Массив событий с полями `id`, `title`, `description`, `start_date`, `start_time`

### PATCH /api/v1/calendar/events/{event_id}/
Используется для перемещения события в другой календарь.

**Body**:
```json
{
  "calendar": 123
}
```

**Ответ**: Обновленное событие

## Архитектура

### Legacy календари (is_legacy: true)
- Рендерятся как `.calendar-folder` с `data-folder-id`
- Имеют badge с классом `.badge.bg-info-subtle.text-info`
- ID формата: `"company"`, `"personal"`, `"dept_123"`

### Новые календари
- Рендерятся как `.calendar-list-item` внутри `.calendar-folder-children`
- Имеют `data-calendar-id` (числовой)
- Имеют badge с классом `.badge.bg-secondary-subtle.text-secondary`

### Drag & Drop поток
1. **dragstart** → сохранить `draggedCalendarId`
2. **dragover** → проверить, что target ≠ source, добавить `drop-target-active`
3. **dragleave** → убрать `drop-target-active`
4. **drop** → сохранить `dropTargetCalendar`, загрузить события, показать модал
5. **dragend** → убрать подсветку, очистить состояние
6. **event click** → PATCH запрос, закрыть модал, обновить список

## Файлы

### Изменены
- `backend/static/js/components/calendarEventDragDrop.js` - основная логика drag-drop

### Связанные файлы (не изменялись)
- `backend/static/js/components/calendarManager.js` - рендеринг списка календарей
- `backend/static/js/api/calendarApi.js` - API для получения событий
- `backend/api/v1/calendar/views.py` - backend ViewSet с фильтрацией по `calendar_id`

## Следующие шаги

### Опционально
1. **Добавить проверку прав**: Нельзя перемещать события в календари, на которые нет прав редактирования
2. **Показывать прошедшие события**: Добавить чекбокс "Показать прошедшие события" в модал
3. **Множественное перемещение**: Добавить чекбоксы для выбора нескольких событий сразу
4. **Подтверждение перемещения**: Добавить модал подтверждения "Переместить событие из [A] в [B]?"
5. **Анимация перемещения**: Визуальный эффект при успешном перемещении
