# Личный календарь сотрудников

## Обзор изменений

Добавлен третий тип календаря — **Личный календарь сотрудника**. Теперь система поддерживает:

1. **Календарь компании** (company) — глобальные события, доступ только у администраторов
2. **Календарь отдела** (dept) — события отдела, требуется право `MANAGE_CALENDAR`
3. **Личный календарь** (personal) — **НОВОЕ**: индивидуальный календарь каждого сотрудника

## Функциональность

### Личный календарь
- ✅ Каждый сотрудник имеет собственный личный календарь
- ✅ Полный контроль над своими событиями (создание, редактирование, удаление)
- ✅ События личного календаря видны только владельцу
- ✅ Другие пользователи не могут изменять чужие личные события
- ✅ Администраторы также не могут редактировать личные календари (только просмотр)

## Изменения в Backend

### 1. Модель `CalendarEvent`

Добавлено поле `employee`:

```python
employee = models.ForeignKey(
    User,
    on_delete=models.CASCADE,
    related_name="personal_calendar_events",
    verbose_name=_("Сотрудник"),
    null=True,
    blank=True,
    help_text=_("Если задано — личное событие сотрудника."),
)
```

**Логика:**
- `department=None, employee=None` → календарь компании
- `department=set, employee=None` → календарь отдела
- `department=None, employee=set` → личный календарь сотрудника

**Валидация:**
- Событие не может одновременно принадлежать отделу и сотруднику
- Добавлены свойства `is_personal` и обновлён `is_company`

### 2. Сериализаторы

**CalendarEventWriteSerializer:**
- Добавлено поле `employee_id` в `fields`
- Поддержка создания/обновления личных событий

### 3. Views (`CalendarEventsViewSet`)

**Новые методы:**
```python
def _employee_id(self, *, required: bool = False) -> Optional[int]:
    """Извлекает employee_id из kwargs/query/body"""
```

**Обновлённые методы:**

**`get_queryset()`:**
```python
# Приоритет: employee_id > department_id > company
if emp is not None:
    return qs.filter(employee_id=emp, department__isnull=True)
elif dep is not None:
    return qs.filter(department_id=dep, employee__isnull=True)
else:
    return qs.filter(department__isnull=True, employee__isnull=True)
```

**`get_permissions()`:**
```python
# Личный календарь — полный контроль только у владельца
if emp is not None:
    if self.request.user.id == emp:
        return [IsAuthenticated()]
    else:
        return [DenyAll()]  # Другие пользователи не могут изменять
```

**`perform_create()`:**
```python
if emp is not None:
    serializer.save(
        employee_id=emp,
        department_id=None,
        created_by=self.request.user,
    )
```

**`permissions` endpoint:**
```python
elif event.employee_id is not None:
    # Личное событие — редактировать может только владелец
    if event.employee_id == user.id:
        can_edit = True
        can_delete = True
```

## Изменения в Frontend

### 1. Dropdown выбора календаря

**Desktop (`calendar_desktop.html`):**
```html
<li><button class="dropdown-item" type="button" data-cal="personal">Личный</button></li>
<li><hr class="dropdown-divider"></li>
<li><button class="dropdown-item" type="button" data-cal="company">Компания</button></li>
```

**Mobile (`calendar_mobile.html`):** — аналогично

### 2. JavaScript (`calendarWidget.js`)

**State:**
```javascript
const state = { 
    type: 'company',  // 'company' | 'dept' | 'personal'
    deptId: null, 
    employeeId: null 
};
```

**eventsUrl():**
```javascript
const eventsUrl = (deptId = null, employeeId = null) => {
    const u = new URL(API_EVENTS, location.origin);
    if (employeeId != null) {
        u.searchParams.set('employee_id', String(employeeId));
    } else if (deptId != null) {
        u.searchParams.set('department_id', String(deptId));
    }
    return u.pathname + u.search;
};
```

**handleChooserClick():**
```javascript
else if (type === 'personal') {
    state.type = 'personal';
    state.deptId = null;
    const userMeta = document.querySelector('meta[name="user-id"]');
    state.employeeId = userMeta ? userMeta.content : null;
}
```

**fetchEventsCombined():**
```javascript
if (state.type === 'personal' && state.employeeId) {
    params.employee_id = state.employeeId;
}
```

**Form submit:**
```javascript
if (state.type === 'personal') {
    payload.employee_id = Number(state.employeeId);
} else if (state.type === 'dept') {
    payload.department_id = Number(state.deptId);
}
```

### 3. Base Template

Добавлен meta-тег с ID пользователя:
```html
{% if user.is_authenticated %}
    <meta name="user-id" content="{{ user.id }}">
{% endif %}
```

## Миграции

Создана миграция `0010_calendarevent_employee_and_more.py`:
- Добавляет поле `employee` в модель `CalendarEvent`
- Изменяет `help_text` поля `department`

## Тестирование

### Сценарии для проверки:

1. **Переключение на личный календарь:**
   - Открыть dropdown → выбрать "Личный"
   - Должны отобразиться только личные события текущего пользователя

2. **Создание личного события:**
   - В режиме "Личный" создать событие
   - Событие должно сохраниться с `employee_id=текущий_пользователь`

3. **Редактирование личного события:**
   - Владелец может редактировать/удалять свои события
   - ПКМ на событии → контекстное меню должно показывать кнопки

4. **Изоляция календарей:**
   - События личного календаря не должны видеть другие пользователи
   - Администраторы могут видеть, но не редактировать чужие личные события

5. **Проверка прав:**
   - Попытка редактировать чужое личное событие должна вернуть 403
   - API endpoint `/permissions/` должен возвращать `can_edit=false` для чужих событий

## API Примеры

### Получить личные события
```http
GET /api/v1/calendar/events/?employee_id=123&start=2025-11-01&end=2025-11-30
Authorization: Bearer <token>
```

### Создать личное событие
```http
POST /api/v1/calendar/events/?employee_id=123
Content-Type: application/json
Authorization: Bearer <token>

{
    "employee_id": 123,
    "title": "Личная встреча",
    "start_date": "2025-11-29",
    "all_day": true,
    "recurrence": "one_time"
}
```

### Проверить права на событие
```http
GET /api/v1/calendar/events/456/permissions/
Authorization: Bearer <token>

Response:
{
    "can_view": true,
    "can_edit": true,  // true только для владельца
    "can_delete": true
}
```

## Безопасность

✅ **Изоляция данных:** события фильтруются по `employee_id` в QuerySet
✅ **Проверка прав:** `get_permissions()` проверяет владельца перед изменениями
✅ **Валидация:** модель запрещает одновременную привязку к отделу и сотруднику
✅ **API защита:** все endpoints требуют авторизации

## Совместимость

✅ Обратная совместимость сохранена
✅ Существующие события компании/отделов работают без изменений
✅ Миграция безопасна (добавляет nullable поле)

## Файлы изменённые

### Backend:
- `backend/calendar_app/models.py` — добавлено поле `employee`, валидация, свойства
- `backend/api/v1/calendar/serializers.py` — добавлено поле `employee_id`
- `backend/api/v1/calendar/views.py` — логика личных календарей
- `backend/calendar_app/migrations/0010_calendarevent_employee_and_more.py` — миграция

### Frontend:
- `backend/templates/base.html` — meta-тег `user-id`
- `backend/templates/includes/components/calendar_desktop.html` — пункт "Личный"
- `backend/templates/includes/components/calendar_mobile.html` — пункт "Личный"
- `backend/static/js/components/calendarWidget.js` — полная поддержка личных календарей

## Дальнейшие улучшения

- [ ] Возможность "поделиться" личным событием с коллегами
- [ ] Синхронизация с внешними календарями (Google, Outlook)
- [ ] Уведомления о личных событиях
- [ ] Экспорт личного календаря в iCal формат
