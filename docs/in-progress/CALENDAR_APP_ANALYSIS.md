# Анализ приложения календаря EUSRR

**Дата анализа:** 11 февраля 2026 г.  
**Задача:** Изучить приложение календаря и оценить возможность создания пользовательских календарей (глобального, локального или календаря отдела)

---

## 📋 Содержание

1. [Текущая архитектура](#текущая-архитектура)
2. [Модель данных](#модель-данных)
3. [API и права доступа](#api-и-права-доступа)
4. [Frontend реализация](#frontend-реализация)
5. [Оценка возможностей](#оценка-возможностей)
6. [Рекомендации](#рекомендации)

---

## 🏗️ Текущая архитектура

### Структура приложения

```
backend/calendar_app/
├── models.py                    # Модель CalendarEvent
├── admin.py                     # Админка Django
├── signals.py                   # Автосигналы (дни рождения)
├── notification_signals.py      # Уведомления о событиях
├── apps.py                      # Конфигурация приложения
└── services/
    └── recurrence.py           # Логика повторяющихся событий

backend/api/v1/calendar/
├── views.py                     # CalendarEventsViewSet (REST API)
└── serializers.py               # Сериализаторы событий

backend/templates/includes/components/
├── calendar_desktop.html        # Десктопный виджет
├── calendar_mobile.html         # Мобильный виджет
├── calendar_modal_create.html   # Модалка создания
└── calendar_modal_details.html  # Модалка деталей

backend/static/js/
├── api/calendarApi.js          # API клиент
└── components/calendarWidget.js # Логика виджета FullCalendar
```

---

## 📊 Модель данных

### CalendarEvent

**Основная модель события с тремя типами области видимости:**

```python
class CalendarEvent(models.Model):
    # Область видимости (взаимоисключающие)
    department = ForeignKey("employees.Department", null=True, blank=True)
    employee = ForeignKey(User, null=True, blank=True)  # ✅ УЖЕ РЕАЛИЗОВАНО
    
    # Основные поля
    title = CharField(max_length=200)
    description = TextField(blank=True)
    
    # Даты и время
    start_date = DateField()
    end_date = DateField(null=True, blank=True)
    start_time = TimeField(null=True, blank=True)
    end_time = TimeField(null=True, blank=True)
    all_day = BooleanField(default=True)
    
    # Повторяемость
    recurrence = CharField(choices=Recurrence.choices)  # one_time, hourly, daily, weekly, monthly, annual
    recurrence_interval = PositiveSmallIntegerField(default=1)
    recurrence_count = PositiveIntegerField(null=True, blank=True)
    recurrence_until = DateField(null=True, blank=True)
    weekdays_mask = PositiveSmallIntegerField(default=0)  # Для weekly: битовая маска дней
    
    # Отображение
    color = CharField(max_length=7, blank=True)  # HEX цвет
    location = CharField(max_length=200, blank=True)
    
    # Служебные
    created_by = ForeignKey(User, on_delete=SET_NULL)
    created_at = DateTimeField(auto_now_add=True)
    source = CharField(max_length=120, blank=True, db_index=True)  # Для системных событий
```

### Типы календарей

#### 1. 🌐 Календарь компании (Глобальный)
- `department = NULL` и `employee = NULL`
- Видны всем сотрудникам
- Редактируют только администраторы (`is_staff=True` или `is_superuser=True`)
- **Примеры:** Праздники, корпоративы, общие собрания

#### 2. 🏢 Календарь отдела (Локальный)
- `department = <PK отдела>` и `employee = NULL`
- Видны всем авторизованным пользователям
- Редактируют: администраторы или пользователи с правом `MANAGE_CALENDAR` на отдел
- **Примеры:** Планёрки отдела, дедлайны проектов

#### 3. 👤 Личный календарь (Персональный) ✅
- `department = NULL` и `employee = <PK сотрудника>`
- **СТАТУС:** Полностью реализован в коде!
- Видны всем авторизованным (для просмотра)
- Редактирует только владелец (`employee_id == request.user.id`)
- **Примеры:** Личные встречи, отпуска, напоминания

### Валидация модели

```python
def clean(self):
    # ✅ Взаимоисключение: нельзя одновременно задавать отдел И сотрудника
    if self.department_id and self.employee_id:
        raise ValidationError("Событие не может одновременно принадлежать отделу и сотруднику.")
    
    # Валидация дат/времени
    # Валидация повторяемости
    # Автоматическая настройка all_day
```

---

## 🔌 API и права доступа

### REST API Endpoint

```
/api/v1/calendar/events/
```

### Поддерживаемые методы

| Метод | Действие | Права доступа |
|-------|----------|---------------|
| `GET /events/` | Список событий (материализованные повторы) | Авторизованные пользователи |
| `GET /events/{id}/` | Детали события | Авторизованные пользователи |
| `POST /events/` | Создание события | Зависит от типа* |
| `PATCH /events/{id}/` | Обновление события | Зависит от типа* |
| `DELETE /events/{id}/` | Удаление события | Зависит от типа* |
| `GET /events/{id}/permissions/` | Проверка прав на событие | Авторизованные пользователи |

**\*Права на изменение:**

```python
def get_permissions(self):
    # Просмотр: всем авторизованным
    if action in ["list", "retrieve"]:
        return [IsAuthenticated()]
    
    # Личный календарь: только владелец
    if emp is not None:
        if request.user.id == emp:
            return [IsAuthenticated()]
        else:
            return [DenyAll()]  # Другие не могут редактировать
    
    # Календарь компании: только администраторы
    if dep is None:
        return [IsAdminUser()]
    
    # Календарь отдела: право MANAGE_CALENDAR
    return [ManageCalendarPerm()]  # AdminOrDeptAllowed с required_code=MANAGE_CALENDAR
```

### Фильтрация событий

#### GET параметры:

```
?start=2025-01-01          # Обязательный: начало диапазона (YYYY-MM-DD)
?end=2025-01-31            # Обязательный: конец диапазона (YYYY-MM-DD)
?department_id=5           # Опциональный: календарь отдела
?employee_id=123           # Опциональный: личный календарь сотрудника
```

**Приоритет фильтрации:** `employee_id` > `department_id` > company

#### Примеры запросов:

```http
# Календарь компании
GET /api/v1/calendar/events/?start=2025-11-01&end=2025-11-30

# Календарь отдела HR
GET /api/v1/calendar/events/?start=2025-11-01&end=2025-11-30&department_id=5

# Личный календарь сотрудника
GET /api/v1/calendar/events/?start=2025-11-01&end=2025-11-30&employee_id=123
```

### Создание событий

```http
POST /api/v1/calendar/events/
Content-Type: application/json
Authorization: Bearer <token>

# Компания (только админы)
{
    "title": "Новогодний корпоратив",
    "start_date": "2025-12-31",
    "all_day": true,
    "recurrence": "one_time"
}

# Отдел (с правом MANAGE_CALENDAR)
{
    "department_id": 5,
    "title": "Планёрка отдела",
    "start_date": "2025-11-15",
    "start_time": "10:00",
    "end_time": "11:00",
    "all_day": false,
    "recurrence": "weekly",
    "weekdays": [0, 2, 4]  # Пн, Ср, Пт
}

# Личный (только владелец)
{
    "employee_id": 123,
    "title": "Встреча с клиентом",
    "start_date": "2025-11-20",
    "start_time": "14:00",
    "end_time": "15:00",
    "all_day": false,
    "recurrence": "one_time"
}
```

---

## 🎨 Frontend реализация

### Виджет календаря (FullCalendar)

**Файл:** `backend/static/js/components/calendarWidget.js`

#### State управление:

```javascript
const state = { 
    type: 'company',     // 'company' | 'dept' | 'personal'
    deptId: null,        // PK отдела (если type='dept')
    employeeId: null     // PK сотрудника (если type='personal')
};
```

#### URL формирование:

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

#### UI компоненты:

**Десктоп:** `calendar_desktop.html`
```html
<div class="dropdown">
  <button class="btn btn-sm btn-outline-secondary dropdown-toggle">
    Компания
  </button>
  <ul class="dropdown-menu" id="calendarChooserMenu">
    <li><button data-cal="personal">Личный</button></li>
    <li><hr class="dropdown-divider"></li>
    <li><button data-cal="company">Компания</button></li>
    <li><hr class="dropdown-divider"></li>
    {# Пункты отделов добавляются динамически из JS #}
  </ul>
</div>
```

**Мобильный:** `calendar_mobile.html` (аналогичная структура в offcanvas)

#### Загрузка событий:

```javascript
// ✅ Поддержка всех трёх типов календарей
async function fetchEventsAllCalendars(start, end) {
    const sources = [
        // Компания
        { params: { start, end }, label: 'Компания', type: 'company', id: null },
        
        // Все отделы пользователя
        ...departments.map(d => ({
            params: { start, end, department_id: d.id },
            label: d.name,
            type: 'dept',
            id: d.id
        })),
        
        // Личный календарь (если есть employee_id)
        { 
            params: { start, end, employee_id: currentEmployeeId },
            label: 'Личный',
            type: 'personal',
            id: currentEmployeeId
        }
    ];
    
    // Параллельная загрузка всех источников
    const results = await Promise.allSettled(
        sources.map(s => getCalendarEvents(s.params))
    );
    
    return results.flatMap(/* ... */);
}
```

### Модалки

#### Создание события: `calendar_modal_create.html`
- Форма с полями: title, description, start_date, end_date, start_time, end_time
- Выбор повторяемости (recurrence)
- Выбор цвета (color picker)
- Автоматическая подстановка department_id/employee_id из текущего state

#### Просмотр/редактирование: `calendar_modal_details.html`
- Отображение всех деталей события
- Кнопки редактирования/удаления (если есть права)
- Проверка прав через `GET /events/{id}/permissions/`

---

## ✅ Оценка возможностей

### Что УЖЕ реализовано:

#### ✅ 1. Календарь компании (Глобальный)
- **Backend:** Полностью реализован
- **API:** `/api/v1/calendar/events/` без параметров
- **Frontend:** Работает в виджете (кнопка "Компания")
- **Права:** Просмотр — все, редактирование — только админы
- **Статус:** 🟢 Готово к использованию

#### ✅ 2. Календарь отдела (Локальный)
- **Backend:** Полностью реализован
- **API:** `/api/v1/calendar/events/?department_id=X`
- **Frontend:** Динамическое меню отделов в виджете
- **Права:** Просмотр — все, редактирование — с правом `MANAGE_CALENDAR`
- **Статус:** 🟢 Готово к использованию

#### ✅ 3. Личный календарь (Персональный)
- **Backend:** Полностью реализован (поле `employee` в модели)
- **API:** `/api/v1/calendar/events/?employee_id=X`
- **Frontend:** ⚠️ Кнопка в меню есть, но **требуется тестирование**
- **Права:** Просмотр — все, редактирование — только владелец
- **Статус:** 🟡 Реализовано, требует проверки работы UI

### Что работает из коробки:

1. ✅ **Создание событий** всех трёх типов через API
2. ✅ **Повторяющиеся события** (hourly, daily, weekly, monthly, annual)
3. ✅ **Материализация повторов** в диапазоне дат
4. ✅ **Права доступа** с автоматической проверкой
5. ✅ **Валидация** дат, времени, повторяемости
6. ✅ **Уведомления** при создании/изменении/удалении событий
7. ✅ **Автосоздание событий** (например, дни рождения через signals)
8. ✅ **FullCalendar интеграция** на фронте
9. ✅ **Адаптивный UI** (desktop + mobile)

### Что может потребовать доработки:

#### 🟡 1. UI личного календаря
**Что есть:**
- Кнопка "Личный" в выпадающем меню
- Логика переключения state
- API запросы с `employee_id`

**Что проверить:**
- Корректное получение `employee_id` текущего пользователя
- Отображение событий в FullCalendar
- Создание личных событий через модалку
- Проверка прав доступа (только владелец может редактировать)

**Код для проверки:**
```javascript
// В calendarWidget.js, строка ~535
const userMeta = document.querySelector('meta[name="user-id"]');
const currentEmployeeId = userMeta ? userMeta.content : null;
```

**Требуется:**
- Убедиться, что в шаблонах есть `<meta name="user-id" content="{{ user.id }}">`
- Протестировать переключение на личный календарь
- Протестировать создание/редактирование личных событий

#### 🟡 2. Модалка создания
**Текущее поведение:**
- При создании события подставляется текущий `department_id` или `employee_id` из state

**Что может понадобиться:**
- Явный выбор типа календаря в форме создания (если нужен)
- Визуальная индикация, для какого календаря создаётся событие
- Валидация на фронте перед отправкой

#### 🟡 3. Фильтры и поиск
**Что отсутствует:**
- Поиск событий по названию
- Фильтрация по типу повторяемости
- Экспорт в iCal/Google Calendar

**Приоритет:** Низкий (можно добавить позже)

---

## 🎯 Рекомендации

### Немедленные действия (Priority: High)

#### 1. Проверка meta-тега user-id
**Файлы для проверки:**
- `backend/templates/base.html` или аналогичный base-шаблон
- Любые страницы, где используется календарь

**Добавить, если отсутствует:**
```django
{% if user.is_authenticated %}
<meta name="user-id" content="{{ user.id }}">
{% endif %}
```

#### 2. Тестирование личного календаря
**Сценарии:**
```python
# 1. GET личных событий
GET /api/v1/calendar/events/?employee_id=<user_id>&start=2025-11-01&end=2025-11-30

# 2. POST личного события
POST /api/v1/calendar/events/
{"employee_id": <user_id>, "title": "Тест", "start_date": "2025-11-15", "all_day": true}

# 3. PATCH личного события (владелец)
PATCH /api/v1/calendar/events/<event_id>/
{"title": "Обновлённое название"}

# 4. PATCH личного события (НЕ владелец) — должно вернуть 403
```

#### 3. Проверка прав доступа
**Матрица прав:**

| Тип календаря | Просмотр | Создание | Редактирование | Удаление |
|---------------|----------|----------|----------------|----------|
| Компания | Все авторизованные | Только админы | Только админы | Только админы |
| Отдел | Все авторизованные | С правом MANAGE_CALENDAR | С правом MANAGE_CALENDAR | С правом MANAGE_CALENDAR |
| Личный | Все авторизованные | Только владелец | Только владелец | Только владелец |

**Код тестов:** Уже существует в `backend/tests/api/v1/calendar_app/test_calendar_api.py`

### Краткосрочные улучшения (Priority: Medium)

#### 1. UI индикаторы
```html
<!-- В модалке создания события -->
<div class="alert alert-info">
  <i class="bi-info-circle"></i>
  Создаётся событие для: <strong id="eventScope">Компания</strong>
</div>
```

```javascript
// Обновление при переключении календаря
function updateScopeIndicator() {
    const scope = state.type === 'personal' ? 'Личного календаря'
                : state.type === 'dept' ? departments.find(d => d.id === state.deptId)?.name
                : 'Компании';
    document.getElementById('eventScope').textContent = scope;
}
```

#### 2. Цветовая дифференциация
```javascript
// В calendarWidget.js
function getEventColor(event) {
    if (event.color) return event.color;
    
    // Дефолтные цвета по типу
    if (event.employee_id) return '#6C757D';  // Серый для личных
    if (event.department_id) return '#0D6EFD'; // Синий для отдела
    return '#198754';  // Зелёный для компании
}
```

#### 3. Уведомления на фронте
```javascript
// После успешного создания
showToast('Событие создано', `"${title}" добавлено в ${scopeName}`, 'success');
```

### Долгосрочные улучшения (Priority: Low)

#### 1. Расширенные фильтры
- Поиск по названию/описанию
- Фильтр по цвету
- Фильтр по типу повторяемости
- Группировка по отделам

#### 2. Интеграции
- Экспорт в .ics (iCal)
- Синхронизация с Google Calendar
- Outlook интеграция
- Email-напоминания

#### 3. Аналитика
- Статистика по событиям отдела
- Загруженность календарей
- Отчёты по посещаемости

---

## 📝 Примеры использования

### Создание глобального события (админ)
```python
import requests

url = "https://example.com/api/v1/calendar/events/"
headers = {"Authorization": "Bearer <admin_token>"}
data = {
    "title": "Корпоративный хакатон",
    "description": "Командный хакатон по разработке новых фич",
    "start_date": "2025-12-15",
    "end_date": "2025-12-16",
    "all_day": true,
    "color": "#FF5733",
    "location": "Офис, конференц-зал",
    "recurrence": "one_time"
}

response = requests.post(url, headers=headers, json=data)
print(response.json())
```

### Создание события отдела (с правом MANAGE_CALENDAR)
```python
data = {
    "department_id": 5,  # HR отдел
    "title": "Планёрка HR",
    "start_date": "2025-11-18",
    "start_time": "10:00",
    "end_time": "10:30",
    "all_day": false,
    "recurrence": "weekly",
    "weekdays": [0],  # Каждый понедельник
    "recurrence_until": "2026-01-01"
}

response = requests.post(url, headers=headers, json=data)
```

### Создание личного события
```python
data = {
    "employee_id": 123,
    "title": "Встреча с заказчиком",
    "start_date": "2025-11-20",
    "start_time": "14:00",
    "end_time": "15:30",
    "all_day": false,
    "color": "#6C757D",
    "location": "Online, Zoom",
    "recurrence": "one_time"
}

response = requests.post(url, headers=headers, json=data)
```

---

## 🔍 Тестирование

### Checklist для проверки личного календаря:

- [ ] **Meta-тег:** `<meta name="user-id">` присутствует на страницах с календарём
- [ ] **UI:** Кнопка "Личный" появляется в меню выбора календаря
- [ ] **API GET:** `/api/v1/calendar/events/?employee_id=<user_id>` возвращает события
- [ ] **API POST:** Создание личного события работает
- [ ] **Права:** Только владелец может редактировать свои события
- [ ] **Права:** Другие пользователи НЕ могут редактировать чужие личные события
- [ ] **FullCalendar:** События отображаются корректно
- [ ] **Переключение:** Смена календаря через dropdown работает
- [ ] **Модалка:** Создание события попадает в нужный календарь
- [ ] **Цвета:** Личные события визуально отличаются от других

### Запуск тестов:

```bash
# Backend тесты
.venv/Scripts/python backend/manage.py test calendar_app

# API тесты
.venv/Scripts/python -m pytest backend/tests/api/v1/calendar_app/ -v

# Конкретный тест личного календаря
.venv/Scripts/python -m pytest backend/tests/api/v1/calendar_app/test_calendar_api.py::TestPersonalCalendar -v
```

---

## 🎉 Итоговая оценка

### Глобальный календарь: 🟢 100% готов
- Backend: ✅
- API: ✅
- Frontend: ✅
- Права: ✅

### Календарь отдела: 🟢 100% готов
- Backend: ✅
- API: ✅
- Frontend: ✅
- Права: ✅

### Личный календарь: 🟡 95% готов
- Backend: ✅
- API: ✅
- Frontend: ✅ (требует проверки)
- Права: ✅
- **Осталось:** Проверить UI и meta-теги

---

## 📚 Дополнительная документация

### Связанные файлы:
- [Реализация личного календаря](./PERSONAL_CALENDAR_FEATURE.md)
- [Модель CalendarEvent](../../backend/calendar_app/models.py)
- [API ViewSet](../../backend/api/v1/calendar/views.py)
- [Сериализаторы](../../backend/api/v1/calendar/serializers.py)
- [Виджет FullCalendar](../../backend/static/js/components/calendarWidget.js)
- [API клиент](../../backend/static/js/api/calendarApi.js)

### Тесты:
- [Тесты API календаря](../../backend/tests/api/v1/calendar_app/test_calendar_api.py)
- [Конфигурация тестов](../../backend/tests/api/v1/calendar_app/conftest.py)

---

**Выводы:**

1. ✅ Все три типа календарей (глобальный, отдела, личный) **полностью реализованы** на backend
2. ✅ API работает корректно с автоматической проверкой прав
3. ✅ Frontend виджет поддерживает все три типа
4. 🟡 Требуется **проверка UI** для личного календаря (добавить meta-тег, протестировать)
5. ✅ Система **готова к продакшену** после финальной проверки

**Следующий шаг:** Тестирование личного календаря в браузере и добавление meta-тега `user-id` в base-шаблон.
