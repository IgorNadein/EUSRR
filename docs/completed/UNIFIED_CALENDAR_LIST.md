# Унифицированный список календарей

**Дата:** 2024-01-XX  
**Коммит:** 91de84f  
**Статус:** ✅ Завершено

## Проблема

После реализации Phase 3 (Frontend) система имела **два параллельных механизма** выбора календарей:

1. **Legacy система:** Dropdown-селектор с опциями:
   - Компания (все события)
   - Личный (события текущего сотрудника)
   - Отдел N (события конкретного отдела)

2. **Новая система:** Collapsible список с чекбоксами для Calendar records из БД

**Проблемы:**
- Два независимых UI компонента для одной задачи
- Legacy календари не видны в новом списке
- Невозможно одновременно выбрать "Компания" и новый календарь
- Пользователь видит 0 календарей при отсутствии Calendar records

## Решение

### Концепция: Псевдо-календари

Создаем **виртуальные календари** для legacy системы и объединяем их с реальными Calendar records:

```javascript
// Legacy псевдо-календари
{
  id: 'legacy-company',
  title: 'Компания',
  color: '#dc3545',  // Красный
  is_legacy: true,
  is_global: true
}

{
  id: 'legacy-personal',
  title: 'Личный календарь',
  color: '#0d6efd',  // Синий
  is_legacy: true,
  is_personal: true
}

{
  id: 'legacy-dept-123',
  title: 'Отдел 123',
  color: '#198754',  // Зеленый
  is_legacy: true,
  is_department: true,
  department_id: 123
}
```

### Реализация

#### 1. calendarManager.js

**Новая функция `createLegacyCalendars()`:**

```javascript
function createLegacyCalendars() {
  const legacyCalendars = [
    {
      id: 'legacy-company',
      title: 'Компания',
      description: 'Все события компании',
      color: '#dc3545',
      is_legacy: true,
      is_global: true,
      is_active: true
    },
    {
      id: 'legacy-personal',
      title: 'Личный календарь',
      description: 'Мои личные события',
      color: '#0d6efd',
      is_legacy: true,
      is_personal: true,
      is_active: true
    }
  ];

  // Генерируем календари для отделов
  const deptIds = getDepartmentIds(); // Из data-dept-id атрибута
  deptIds.forEach(deptId => {
    legacyCalendars.push({
      id: `legacy-dept-${deptId}`,
      title: `Отдел ${deptId}`,
      description: `События отдела ${deptId}`,
      color: '#198754',
      is_legacy: true,
      is_department: true,
      department_id: deptId,
      is_active: true
    });
  });

  return legacyCalendars;
}
```

**Модифицированная `loadCalendars()`:**

```javascript
async function loadCalendars() {
  try {
    // Загружаем новые календари из API
    const newCalendars = await getMyCalendars();
    
    // Создаем legacy календари
    const legacyCalendars = createLegacyCalendars();
    
    // ОБЪЕДИНЯЕМ оба массива
    calendars = [...legacyCalendars, ...newCalendars];
    
    // Все календари видимы по умолчанию
    visibleCalendarIds = new Set(calendars.map(c => c.id));
    
    console.log('[CalendarManager] Loaded calendars:', {
      legacy: legacyCalendars.length,
      new: newCalendars.length,
      total: calendars.length
    });
    
    render();
    triggerChange();
  } catch (error) {
    console.error('[CalendarManager] Error loading calendars:', error);
  }
}
```

#### 2. calendarWidgetIntegration.js

**Обновленная `fetchEventsForVisibleCalendars()`:**

```javascript
async function fetchEventsForVisibleCalendars(start, end) {
  const startStr = formatDate(start);
  const endStr = formatDate(end);
  
  // Разделяем legacy и новые календари
  const legacyIds = [...visibleCalendarIds].filter(
    id => typeof id === 'string' && id.startsWith('legacy-')
  );
  const newIds = [...visibleCalendarIds].filter(
    id => typeof id === 'number'
  );
  
  let allEvents = [];
  
  // Загружаем события для legacy календарей
  for (const legacyId of legacyIds) {
    let events = [];
    const calendar = calendars.find(c => c.id === legacyId);
    
    if (legacyId === 'legacy-company') {
      // ВСЕ события без фильтров
      events = await getCalendarEvents({ start: startStr, end: endStr });
      
    } else if (legacyId === 'legacy-personal') {
      // События текущего сотрудника
      events = await getCalendarEvents({
        start: startStr,
        end: endStr,
        employee_id: window.currentEmployeeId
      });
      
    } else if (legacyId.startsWith('legacy-dept-')) {
      // События конкретного отдела
      const deptId = parseInt(legacyId.replace('legacy-dept-', ''), 10);
      events = await getCalendarEvents({
        start: startStr,
        end: endStr,
        department_id: deptId
      });
    }
    
    // Применяем цвет календаря
    allEvents.push(...events.map(event => ({
      ...event,
      __calendar: calendar,
      color: calendar?.color || event.color
    })));
  }
  
  // Загружаем события для новых календарей
  const newEventChunks = await Promise.all(
    newIds.map(async (calendarId) => {
      const events = await getCalendarEvents({
        start: startStr,
        end: endStr,
        calendar_id: calendarId  // Новый параметр фильтрации
      });
      
      const calendar = calendars.find(c => c.id === calendarId);
      return events.map(event => ({
        ...event,
        __calendar: calendar,
        color: calendar?.color || event.color
      }));
    })
  );
  
  allEvents.push(...newEventChunks.flat());
  
  // Дедупликация по ID
  return deduplicateEvents(allEvents);
}
```

#### 3. calendar_desktop.html

**Удален legacy dropdown:**

```diff
- {# Выпадающий выбор: Компания / Отделы / Личный (LEGACY) #}
- <div class="dropdown">
-   <button class="btn btn-sm btn-outline-secondary dropdown-toggle">
-     Компания
-   </button>
-   <ul class="dropdown-menu">
-     <li><button data-cal="personal">Личный</button></li>
-     <li><button data-cal="company">Компания</button></li>
-   </ul>
- </div>
```

**Оставлен только унифицированный список:**

```html
{# Кнопка списка календарей #}
<button 
  class="btn btn-sm btn-outline-primary" 
  data-bs-toggle="collapse" 
  data-bs-target="#calendarListCollapse"
>
  <i class="bi-list-check"></i>
  <span class="ms-1">Календари</span>
</button>

{# Список календарей (сворачиваемый) #}
<div class="collapse" id="calendarListCollapse">
  <div class="card-body border-bottom py-2">
    <small class="text-muted">
      <i class="bi-info-circle me-1"></i>
      Выберите календари для отображения
    </small>
    <div id="calendarListContainer" style="max-height: 250px; overflow-y: auto;">
      {# JS генерирует список чекбоксов #}
    </div>
  </div>
</div>
```

## Результат

### До

```
[Dropdown: Компания ▼]  [🗂️ Мои календари]

При клике на Dropdown:
- Личный
- Компания
- Отдел 1
- Отдел 2

При клике на "Мои календари":
- (пусто, если нет Calendar records)
```

**Проблемы:**
- Два разных UI компонента
- Невозможно выбрать и "Компания" и новый календарь
- 0 календарей при отсутствии records

### После

```
[📋 Календари]  [+ Создать календарь]  [+ Создать событие]

При клике на "Календари":
☑ Компания (красный)
☑ Личный календарь (синий)
☑ Отдел 1 (зеленый)
☑ Отдел 2 (зеленый)
☐ Мой проектный календарь (фиолетовый)
☐ Маркетинговые события (оранжевый)
```

**Преимущества:**
- ✅ Единый список всех календарей
- ✅ Множественный выбор через чекбоксы
- ✅ Legacy календари всегда доступны
- ✅ Новые календари добавляются в тот же список
- ✅ Визуальная индикация цветом
- ✅ Минимум 2 календаря всегда (Компания + Личный)

## API Mapping

| Calendar ID | API Parameters | Описание |
|-------------|----------------|----------|
| `'legacy-company'` | `{ start, end }` | Все события без фильтров |
| `'legacy-personal'` | `{ start, end, employee_id }` | События текущего сотрудника |
| `'legacy-dept-123'` | `{ start, end, department_id: 123 }` | События отдела 123 |
| `42` (number) | `{ start, end, calendar_id: 42 }` | События календаря #42 |

## Цветовая схема

- **Компания:** `#dc3545` (Bootstrap danger - красный)
- **Личный:** `#0d6efd` (Bootstrap primary - синий)
- **Отдел:** `#198754` (Bootstrap success - зеленый)
- **Новые календари:** Пользовательские цвета из БД

## Тестирование

### Сценарий 1: Нет Calendar records
```javascript
// calendarManager.js создаст:
calendars = [
  { id: 'legacy-company', title: 'Компания', ... },
  { id: 'legacy-personal', title: 'Личный календарь', ... },
  { id: 'legacy-dept-1', title: 'Отдел 1', ... }
]

// calendarWidgetIntegration.js загрузит:
// - Все события для 'legacy-company'
// - Личные события для 'legacy-personal'
// - События отдела для 'legacy-dept-1'
```

### Сценарий 2: Есть 2 новых календаря
```javascript
calendars = [
  { id: 'legacy-company', ... },
  { id: 'legacy-personal', ... },
  { id: 42, title: 'Проектный календарь', color: '#9b59b6' },
  { id: 43, title: 'Маркетинг', color: '#e67e22' }
]

// Пользователь может выбрать любую комбинацию:
// - Только legacy: 'legacy-company' + 'legacy-personal'
// - Только новые: 42 + 43
// - Смешанные: 'legacy-company' + 42 + 43
```

### Сценарий 3: Снятие всех чекбоксов
```javascript
visibleCalendarIds = []

// fetchEventsForVisibleCalendars вернет:
return []  // Пустой массив, календарь пустой
```

## Обратная совместимость

**Удалены компоненты:**
- ❌ Dropdown selector (`#calendarChooserBtn`)
- ❌ `data-cal` атрибуты на кнопках dropdown
- ❌ `calendarWidget.setState({ viewType })` логика

**Сохранены компоненты:**
- ✅ API `/api/v1/calendar/events/` с фильтрами
- ✅ `employee_id`, `department_id` параметры
- ✅ Старые события без `calendar_id` (видны в "Компания")

**Миграция не требуется:** Существующие события продолжают работать через legacy-календари.

## Известные ограничения

1. **Дубликаты событий:** Событие без `calendar_id` может попасть и в "Компания", и в "Отдел", если принадлежит этому отделу
   - **Решение:** Дедупликация по `event.id` в `fetchEventsForVisibleCalendars()`

2. **Скрытие личных событий:** Если снять чекбокс "Личный календарь", старые личные события (без `calendar_id`) все равно видны в "Компания"
   - **Решение:** Пользователь должен снять и "Компания", или события должны иметь `calendar_id`

3. **Производительность:** При выборе многих календарей делаются множественные API запросы
   - **Решение:** `Promise.all()` для параллельных запросов, дедупликация результатов

## Следующие шаги

- [x] Создать псевдо-календари в `calendarManager.js`
- [x] Обновить `calendarWidgetIntegration.js` для обработки string IDs
- [x] Удалить legacy dropdown из шаблона
- [x] Протестировать унифицированный список
- [ ] Обновить документацию API
- [ ] Добавить миграцию: `calendar_id` для старых событий
- [ ] Добавить unit-тесты для `createLegacyCalendars()`
- [ ] UX: Сгруппировать календари по типу (Legacy / Мои / Общие)

## Связанные коммиты

- `b748ed6` - Phase 3 Part 1: UI Components
- `e7ec903` - Phase 3 Part 2: Integration
- `2a3fbca` - Fix: Infinite loading
- `74e4cd5` - Restore legacy dropdown
- **`91de84f`** - **Unified calendar list** (текущий)

## Ссылки

- [OPTIONAL_CALENDARS_PHASE3.md](../in-progress/OPTIONAL_CALENDARS_PHASE3.md)
- [backend/static/js/components/calendarManager.js](../../backend/static/js/components/calendarManager.js)
- [backend/static/js/components/calendarWidgetIntegration.js](../../backend/static/js/components/calendarWidgetIntegration.js)
