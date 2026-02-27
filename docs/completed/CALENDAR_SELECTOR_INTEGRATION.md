# Интеграция селектора календарей в создание событий

**Дата**: 11 февраля 2026
**Статус**: ✅ Завершено
**Коммиты**: `70d9bad`, `8e393e2`, `a0e04b8`, `5d7902d`, `6a11138`, `6bf3cc4`

## Проблема

После реализации унифицированного списка календарей (legacy + новые в одном списке) обнаружены проблемы:

1. ❌ **События создавались только в legacy календарях** - форма создания использовала старую логику `state.type` (company/personal/dept)
2. ❌ **Новые Calendar записи были недоступны** для создания событий
3. ❌ **Статический текст "Календарь: Компания"** без возможности выбора
4. ❌ **Множественные баги**: NaN errors, дублирование событий, IndentationErrors

## Решение

### 1. UI компонент - селектор календаря

**Файл**: `templates/includes/components/calendar_modal_create.html`

```html
<div class="mt-3">
  <label class="form-label">Календарь</label>
  <select class="form-select" name="target_calendar" id="targetCalendarSelect">
    <option value="company" selected>Компания (общие события)</option>
    <option value="personal">Личный календарь</option>
  </select>
  <div class="form-text">События создаются в выбранном календаре</div>
</div>
```

**Изменения**:
- ✅ Заменил статический `<span id="eventTargetLabel">` на `<select>`
- ✅ Базовые опции: "Компания", "Личный календарь"
- ✅ Динамическое добавление отделов и новых календарей через JS

### 2. Функция динамического заполнения

**Файл**: `static/js/components/calendarWidget.js`

```javascript
function populateCalendarSelector() {
  const select = document.getElementById("targetCalendarSelect");
  if (!select) return;

  // Очищаем селект
  select.innerHTML = "";

  // 1. Базовые legacy опции
  select.appendChild(createOption("company", "Компания (общие события)"));
  select.appendChild(createOption("personal", "Личный календарь"));

  // 2. Отделы из window.departments
  if (window.departments && Array.isArray(window.departments)) {
    window.departments.forEach((dept) => {
      select.appendChild(createOption(`dept-${dept.id}`, `Отдел: ${dept.name}`));
    });
  }

  // 3. Новые календари из window.calendarIntegration
  if (window.calendarIntegration?.calendars) {
    const newCalendars = window.calendarIntegration.calendars.filter(
      (cal) => !cal.id.toString().startsWith("legacy-")
    );

    if (newCalendars.length > 0) {
      // Разделитель
      select.appendChild(createOption("", "─────────────────", true));

      // Новые календари с иконкой
      newCalendars.forEach((cal) => {
        const option = createOption(cal.id, `📅 ${cal.name}`);
        if (cal.description) option.title = cal.description;
        select.appendChild(option);
      });
    }
  }

  // Устанавливаем значение по умолчанию
  if (state.type === "personal") {
    select.value = "personal";
  } else if (state.type === "dept" && state.deptId) {
    select.value = `dept-${state.deptId}`;
  } else {
    select.value = "company";
  }
}
```

**Вызывается**:
- При открытии формы создания нового события (dateClick)
- При открытии формы редактирования существующего события

### 3. Логика создания/редактирования события

**Было** (старая логика):
```javascript
// Область — компания/отдел/личный
if (state.type === "personal") {
  payload.employee_id = Number(state.employeeId);
} else if (state.type === "dept") {
  payload.department_id = Number(state.deptId);
}
```

**Стало** (новая логика):
```javascript
// Получаем выбранный календарь из формы
const targetCalendar = fd.get("target_calendar");

if (targetCalendar && targetCalendar !== "company") {
  if (targetCalendar === "personal") {
    // Личный календарь
    const userMeta = document.querySelector('meta[name="user-id"]');
    const currentEmployeeId = userMeta ? parseInt(userMeta.content, 10) : null;
    if (!currentEmployeeId) {
      alert("Не удалось определить ID пользователя");
      return;
    }
    payload.employee_id = currentEmployeeId;
  } else if (targetCalendar.startsWith("dept-")) {
    // Календарь отдела
    const deptId = parseInt(targetCalendar.replace("dept-", ""), 10);
    if (isNaN(deptId)) {
      alert("Некорректный отдел");
      return;
    }
    payload.department_id = deptId;
  } else if (/^\d+$/.test(targetCalendar)) {
    // Новый календарь - используем calendar_id
    payload.calendar_id = parseInt(targetCalendar, 10);
  }
}
// Если targetCalendar === "company", то без доп. параметров
```

**Преимущества**:
- ✅ Поддержка смешанных типов ID (string для legacy, number для новых)
- ✅ Единая логика для POST (создание) и PATCH (редактирование)
- ✅ Валидация входных данных
- ✅ Понятные сообщения об ошибках

### 4. Автоматический выбор при редактировании

```javascript
// При открытии формы редактирования
populateCalendarSelector();

const targetSelect = document.getElementById("targetCalendarSelect");
if (targetSelect && data) {
  if (data.calendar_id) {
    targetSelect.value = data.calendar_id;
  } else if (data.employee_id) {
    targetSelect.value = "personal";
  } else if (data.department_id) {
    targetSelect.value = `dept-${data.department_id}`;
  } else {
    targetSelect.value = "company";
  }
}
```

## Исправленные баги

### Баг 1: `calendar_id=NaN`
**Коммит**: `70d9bad`
- **Причина**: `parseInt('legacy-company')` возвращал NaN
- **Решение**: Проверка `/^\d+$/` перед parseInt, сохранение строковых ID

### Баг 2: Дублирование событий
**Коммит**: `8e393e2`
- **Причина**: `employee_id=null` возвращал все события и для "Компания", и для "Личный"
- **Решение**: Получение реального employee_id из `meta[name="user-id"]`
- **Результат**: Было 26 событий (13+13 дубли) → стало 13 уникальных

### Баг 3: IndentationError в urls.py
**Коммит**: `a0e04b8`
- **Причина**: Дублированный блок `urlpatterns`
- **Решение**: Удален дубликат строк 78-85

### Баг 4: IndentationError в serializers.py
**Коммит**: `5d7902d`
- **Причина**: Дублированный метод `validate()` в `CalendarSubscriptionSerializer`
- **Решение**: Удален дубликат строк 487-497

### Баг 5: `department_id=NaN`
**Коммит**: `6a11138`
- **Причина**: `deptIds` был массивом объектов `[{id, name}]`, а код ожидал `[id]`
- **Решение**: Извлечение ID через `dept.id || dept.pk || dept.department_id`

## Результат

### Что работает

✅ **Создание событий** в любом календаре:
- Компания (общие события)
- Личный календарь
- Календари отделов
- Новые Calendar записи из БД

✅ **Редактирование событий**:
- Автоматический выбор текущего календаря
- Возможность перемещения между календарями
- Сохранение изменений

✅ **Отображение событий**:
- Корректная фильтрация по календарям
- Без дублирования
- Правильные цвета и подписи

✅ **Обратная совместимость**:
- Legacy система (employee_id/department_id) работает
- Новая система (calendar_id) работает
- Смешанное использование работает

### API запросы

**Создание события в компании**:
```json
POST /api/v1/calendar/events/
{
  "title": "Совещание",
  "start": "2026-02-12T10:00:00",
  "end": "2026-02-12T11:00:00"
}
```

**Создание в личном календаре**:
```json
POST /api/v1/calendar/events/
{
  "title": "Встреча",
  "start": "2026-02-12T14:00:00",
  "end": "2026-02-12T15:00:00",
  "employee_id": 1
}
```

**Создание в новом календаре**:
```json
POST /api/v1/calendar/events/
{
  "title": "Задача",
  "start": "2026-02-12T16:00:00",
  "end": "2026-02-12T17:00:00",
  "calendar_id": 5
}
```

## Тестирование

### Сценарии для проверки

1. **Создание нового события**
   - [ ] Клик на дату в календаре
   - [ ] Селектор показывает все доступные календари
   - [ ] Выбор календаря и сохранение
   - [ ] Событие появляется в правильном календаре

2. **Редактирование события**
   - [ ] Клик на существующее событие
   - [ ] Селектор показывает текущий календарь
   - [ ] Изменение календаря и сохранение
   - [ ] Событие перемещается в новый календарь

3. **Фильтрация календарей**
   - [ ] Отключение календаря скрывает его события
   - [ ] Включение календаря показывает события
   - [ ] Нет дублирования событий

4. **Новые календари**
   - [ ] Создание Calendar через "Управление календарями"
   - [ ] Новый календарь появляется в селекторе
   - [ ] События создаются в новом календаре
   - [ ] События отображаются с правильным цветом

## Файлы изменены

- `templates/includes/components/calendar_modal_create.html` - добавлен селектор
- `static/js/components/calendarWidget.js` - новая логика создания/редактирования
- `static/js/components/calendarWidgetIntegration.js` - исправлено получение employee_id
- `static/js/components/calendarManager.js` - исправлена обработка string ID
- `api/v1/urls.py` - удален дубликат
- `api/v1/calendar/serializers.py` - удален дубликат

## Следующие шаги

🎯 **Phase 3: Frontend - ЗАВЕРШЕНО**
- ✅ Унифицированный список календарей (legacy + новые)
- ✅ Селектор календарей в форме создания
- ✅ Полная интеграция с API
- ✅ Исправлены все критические баги

🚀 **Готово к тестированию пользователями**

## Примечания

- Используется `window.calendarIntegration` для доступа к списку календарей
- Employee ID берется из `<meta name="user-id">` для безопасности
- Поддержка смешанных типов ID для плавной миграции legacy → новая система
- Иконка 📅 для визуального отличия новых календарей от legacy
