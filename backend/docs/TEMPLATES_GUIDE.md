# 📄 Руководство по шаблонам EUSRR

**Версия**: 1.0  
**Дата**: 4 ноября 2025 г.

---

## 📚 Содержание

1. [Структура шаблонов](#структура-шаблонов)
2. [Базовый шаблон](#базовый-шаблон)
3. [Компоненты сотрудников](#компоненты-сотрудников)
4. [Компоненты календаря](#компоненты-календаря)
5. [Компоненты отделов](#компоненты-отделов)
6. [Best Practices](#best-practices)

---

## 🏗️ Структура шаблонов

### Общая организация

```
templates/
├── base.html                          # Базовый шаблон (631 строка)
├── includes/                          # Общие компоненты
│   ├── navbar.html                   # Навигационная панель
│   ├── sidebar.html                  # Левая боковая панель
│   ├── rightbar_calendar.html        # Правая панель календаря (17 строк)
│   └── components/                   # Компоненты для includes
│       ├── calendar_desktop.html     # Десктопная версия календаря
│       ├── calendar_mobile.html      # Мобильная offcanvas версия
│       ├── calendar_modal_create.html # Модал создания события
│       ├── calendar_modal_details.html # Модал деталей события
│       └── calendar_scripts.html     # JS инициализация календаря
├── employees/                         # Шаблоны сотрудников
│   ├── employees_list.html           # Список сотрудников
│   ├── employee_detail.html          # Детали сотрудника (432 строки)
│   ├── _employee_edit.html           # Форма редактирования (24 строки!)
│   ├── _department_controls.html     # Управление отделом (275 строк)
│   └── components/                   # Компоненты сотрудников
│       ├── employee_form_personal.html
│       ├── employee_form_contacts.html
│       ├── employee_form_position.html
│       ├── employee_form_employment.html
│       ├── employee_form_photo.html
│       ├── employee_form_actions.html
│       ├── employee_form_scripts.html
│       ├── employee_detail_scripts.html
│       ├── department_controls_scripts.html
│       └── department_scripts.html
├── departments/
│   ├── department_detail.html        # Детали отдела (46 строк!)
│   └── components/
│       ├── department_header.html
│       ├── department_wheel.html
│       ├── department_members.html
│       └── department_sidebar.html
├── documents/
│   └── document_list.html            # Список документов (705 строк)
├── search/
│   └── results.html                  # Результаты поиска (335 строк)
└── requests_app/
    └── request_list_full.html        # Список заявок (673 строки)
```

---

## 🎨 Базовый шаблон

### `base.html`

Основной шаблон приложения с трёхколоночной структурой.

#### Структура

```django
<!doctype html>
<html lang="ru">
<head>
  <!-- Meta-теги -->
  <title>{% block title %}HiRo{% endblock %}</title>
  
  <!-- Bootstrap, Icons, FullCalendar -->
  <link href="bootstrap@5.3.3" rel="stylesheet">
  <link href="bootstrap-icons@1.11.3" rel="stylesheet">
  
  <!-- CSS Components -->
  <link rel="stylesheet" href="{% static 'css/variables.css' %}">
  <link rel="stylesheet" href="{% static 'css/components/common.css' %}">
  <link rel="stylesheet" href="{% static 'css/components/feed-cards.css' %}">
  <link rel="stylesheet" href="{% static 'css/components/ios-search.css' %}">
  <link rel="stylesheet" href="{% static 'css/components/base-app.css' %}">
  <link rel="stylesheet" href="{% static 'css/components/ios-components.css' %}">
  
  {% block extra_css %}{% endblock %}
</head>
<body>
  {% include "includes/navbar.html" %}
  
  <div class="container-xxl">
    <div class="app-layout with-sidebar with-rightbar">
      
      {# Левая боковая панель #}
      {% if user.is_authenticated %}
        {% include "includes/sidebar.html" %}
      {% endif %}
      
      {# Основной контент #}
      <main class="main">
        {% block content %}{% endblock %}
      </main>
      
      {# Правая панель с календарём #}
      {% if user.is_authenticated %}
        {% include "includes/rightbar_calendar.html" %}
      {% endif %}
      
    </div>
  </div>
  
  <!-- JS Scripts -->
  <script src="bootstrap@5.3.3/bootstrap.bundle.min.js" defer></script>
  <script src="fullcalendar@6.1.8" defer></script>
  
  <!-- Global JS Modules -->
  <script type="module">
    // Утилиты
    import { esc, norm, escAttr, truncate, getInitials } from '...stringUtils.js';
    import { debounce, throttle, delay } from '...timing.js';
    import { smoothScrollTo, scrollToTop, isElementInViewport } from '...scroll.js';
    
    // Глобальные компоненты
    import { initNavbarHeight } from '...navbarHeight.js';
    import { initLikeHandler } from '...likeHandler.js';
    import { initTextareaAutogrow } from '...textareaAutogrow.js';
    
    document.addEventListener('DOMContentLoaded', () => {
      // Инициализация глобальных компонентов
      const navbarHeight = initNavbarHeight();
      const likeHandler = initLikeHandler();
      const textareaAutogrow = initTextareaAutogrow();
      
      // Экспорт в window для совместимости
      if (navbarHeight) window.navbarHeight = navbarHeight;
      if (likeHandler) window.likeHandler = likeHandler;
      if (textareaAutogrow) window.textareaAutogrow = textareaAutogrow;
    });
  </script>
  
  {% block extra_js %}{% endblock %}
</body>
</html>
```

#### Блоки для переопределения

- `{% block title %}` - заголовок страницы
- `{% block extra_css %}` - дополнительные стили
- `{% block content %}` - основной контент
- `{% block extra_js %}` - дополнительные скрипты

---

## 👥 Компоненты сотрудников

### Форма редактирования сотрудника

#### `_employee_edit.html` (24 строки)

Главный шаблон формы, объединяющий все компоненты.

```django
{% extends "base.html" %}
{% load static %}

{% block content %}
<div class="container ios-page">
  <form method="post" enctype="multipart/form-data" id="employeeForm">
    {% csrf_token %}
    
    <div class="row g-3">
      {# Компоненты формы #}
      {% include "employees/components/employee_form_personal.html" %}
      {% include "employees/components/employee_form_contacts.html" %}
      {% include "employees/components/employee_form_position.html" %}
      {% include "employees/components/employee_form_employment.html" %}
      {% include "employees/components/employee_form_photo.html" %}
      {% include "employees/components/employee_form_actions.html" %}
    </div>
  </form>
</div>

{# JavaScript инициализация #}
{% include "employees/components/employee_form_scripts.html" %}
{% endblock %}
```

---

### Компоненты формы

#### `employee_form_personal.html`

Личные данные сотрудника.

**Поля:**
- Фамилия, Имя, Отчество
- Пол
- Дата рождения

**Особенности:**
- iOS-стайлинг аккордеона
- Валидация обязательных полей
- Автофокус на первое поле

---

#### `employee_form_contacts.html`

Контактная информация.

**Поля:**
- Email (корпоративная почта)
- Телефон (рабочий)
- Внутренний номер

**Особенности:**
- Форматирование телефона
- Валидация email
- Опциональные поля

---

#### `employee_form_position.html` (360 строк)

Управление должностью сотрудника.

**Разделы:**
1. Текущая должность (select/input)
2. Создание новой должности (collapse)
3. Редактирование должности (модал)
4. Назначение групп должностей

**JavaScript:**
- `positionManager.js` - CRUD должностей
- `groupPickers.js` - выбор групп

**Особенности:**
- Динамические модалы
- AJAX операции
- Валидация прав доступа

---

#### `employee_form_employment.html`

Информация о трудоустройстве.

**Поля:**
- Дата приёма на работу
- Статус (работает/уволен)
- Дата увольнения

**Особенности:**
- Datepicker интеграция
- Условное отображение (статус)
- Автозаполнение текущей даты

---

#### `employee_form_photo.html`

Загрузка фотографии.

**Поля:**
- Превью текущей фотографии
- File input для загрузки
- Кнопка удаления фото

**Особенности:**
- Предпросмотр перед загрузкой
- Валидация размера/формата
- Crop функционал (опционально)

---

#### `employee_form_actions.html`

Кнопки действий формы.

**Кнопки:**
- Сохранить изменения
- Отмена (возврат назад)
- Удалить сотрудника (для админов)

**Особенности:**
- Sticky позиционирование на мобильных
- Подтверждение удаления
- Отслеживание изменений

---

#### `employee_form_scripts.html` (22 строки)

JavaScript инициализация для формы.

```django
{% load static %}
<script type="module">
  import { initEmployeeForm } from '{% static "js/components/employeeFormHandler.js" %}';
  import { initPositionManager } from '{% static "js/components/positionManager.js" %}';
  import { initPositionGroupPicker, initPositionEditGroupPicker } from '{% static "js/components/groupPickers.js" %}';
  import { initEmployeeGroupsManager } from '{% static "js/components/employeeGroupsManager.js" %}';
  
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initAll);
  } else {
    initAll();
  }
  
  function initAll() {
    const employeeForm = initEmployeeForm();
    const positionMgr = initPositionManager();
    const groupPicker = initPositionGroupPicker();
    const editGroupPicker = initPositionEditGroupPicker();
    const groupsMgr = initEmployeeGroupsManager();
    
    // Экспорт для отладки
    if (employeeForm) window.employeeForm = employeeForm;
    if (positionMgr) window.positionManager = positionMgr;
    if (groupPicker) window.groupPicker = groupPicker;
    if (editGroupPicker) window.editGroupPicker = editGroupPicker;
    if (groupsMgr) window.employeeGroupsManager = groupsMgr;
  }
</script>
```

---

### Детали сотрудника

#### `employee_detail.html` (432 строки)

Страница просмотра профиля сотрудника.

**Разделы:**
1. Шапка с фото и основной информацией
2. Контактная информация
3. Должность и отделы
4. Навыки (skills)
5. История изменений
6. Форма редактирования (collapse)

**JavaScript:**
```django
{% include "employees/components/employee_detail_scripts.html" %}
```

#### `employee_detail_scripts.html` (47 строк)

```django
{% load static %}
<script type="module">
  import { initSkillsManager } from '{% static "js/components/skillsManager.js" %}';
  import { initDeptRoleEditor } from '{% static "js/components/deptRoleEditor.js" %}';
  import { smoothScrollTo } from '{% static "js/utils/scroll.js" %}';

  document.addEventListener('DOMContentLoaded', () => {
    // 1. Менеджер навыков
    const skillsManager = initSkillsManager({
      blockId: 'skillsBlock',
      formId: 'skillAddForm',
      collapseId: 'skillsForm',
      removeUrl: "{% url 'employees:skill_remove' emp.id %}"
    });

    // 2. Редакторы ролей в отделах
    const deptRoleEditor = initDeptRoleEditor();

    // 3. Smooth scroll к форме редактирования
    const editWrap = document.getElementById('editFormWrap');
    if (editWrap) {
      const isMobile = () => window.matchMedia('(max-width: 767.98px)').matches;
      
      editWrap.addEventListener('shown.bs.collapse', () => {
        if (isMobile()) {
          smoothScrollTo(editWrap, { offset: getHeaderOffset() });
        }
      });
    }

    // Экспорт в window
    if (skillsManager) window.skillsManager = skillsManager;
    if (deptRoleEditor) window.deptRoleEditor = deptRoleEditor;
  });
</script>
```

---

## 📅 Компоненты календаря

### `rightbar_calendar.html` (17 строк)

Основной файл правой панели с календарём.

```django
{% load static %}
{# Правая колонка с календарём - рефакторированная версия #}

<link rel="stylesheet" href="{% static 'css/components/rightbar-calendar.css' %}">

{# Десктопная версия #}
{% include "includes/components/calendar_desktop.html" %}

{# Мобильная версия #}
{% include "includes/components/calendar_mobile.html" %}

{# Модальные окна #}
{% include "includes/components/calendar_modal_create.html" %}
{% include "includes/components/calendar_modal_details.html" %}

{# JavaScript инициализация #}
{% include "includes/components/calendar_scripts.html" %}
```

---

### `calendar_desktop.html` (40 строк)

Десктопная версия календаря в правой панели.

**Элементы:**
- Заголовок "События"
- Контейнер для FullCalendar
- Кнопка создания события
- Список предстоящих событий

**Классы:**
- `.rightbar-calendar` - основной контейнер
- `.calendar-widget` - виджет календаря
- `.event-list` - список событий

---

### `calendar_mobile.html` (23 строки)

Мобильная offcanvas версия календаря.

**Структура:**
```html
<div class="offcanvas offcanvas-end" id="calendarOffcanvas">
  <div class="offcanvas-header">
    <h5>События</h5>
    <button type="button" class="btn-close"></button>
  </div>
  <div class="offcanvas-body">
    <!-- Содержимое календаря -->
  </div>
</div>
```

---

### `calendar_modal_create.html` (132 строки)

Модал для создания нового события.

**Поля формы:**
- Название события
- Описание
- Дата начала
- Дата окончания
- Цвет события
- Тип (личное/рабочее)

**Особенности:**
- Валидация дат
- Color picker
- AJAX отправка

---

### `calendar_modal_details.html` (33 строки)

Модал для просмотра деталей события.

**Отображаемая информация:**
- Название
- Описание
- Дата и время
- Участники
- Кнопки: Редактировать, Удалить

---

### `calendar_scripts.html` (11 строк)

Инициализация виджета календаря.

```django
{% load static %}
<script type="module">
  import { initCalendarWidget } from '{% static "js/components/calendarWidget.js" %}';
  
  const widget = initCalendarWidget();
  if (widget) {
    window.calendarWidget = widget;
  }
</script>
```

---

## 🏢 Компоненты отделов

### `department_detail.html` (46 строк)

Страница деталей отдела.

```django
{% extends "base.html" %}
{% load static %}

{% block content %}
<div class="container ios-page">
  <div class="row g-3">
    {# Заголовок отдела #}
    {% include "departments/components/department_header.html" %}
    
    {# Колесо команды #}
    {% include "departments/components/department_wheel.html" %}
    
    {# Список участников #}
    {% include "departments/components/department_members.html" %}
    
    {# Боковая панель с настройками #}
    {% include "departments/components/department_sidebar.html" %}
  </div>
</div>

{# JavaScript инициализация #}
{% include "employees/components/department_scripts.html" %}
{% endblock %}
```

---

### `_department_controls.html` (275 строк)

Управление отделом (настройки, роли, права).

**Разделы:**
1. Выбор руководителя отдела (headPicker)
2. Управление ролями отдела (roleManager)
3. Создание/редактирование ролей
4. Назначение прав (permissions)

**JavaScript:**
```django
{% include "employees/components/department_controls_scripts.html" %}
```

#### `department_controls_scripts.html` (19 строк)

```django
{% load static %}
<script type="module">
  import { initHeadPicker } from '{% static "js/components/headPicker.js" %}';
  import { initRoleManager } from '{% static "js/components/roleManager.js" %}';

  document.addEventListener('DOMContentLoaded', () => {
    const headPicker = initHeadPicker();
    const roleManager = initRoleManager();

    if (headPicker) window.headPicker = headPicker;
    if (roleManager) window.roleManager = roleManager;
  });
</script>
```

---

## ✅ Best Practices

### 1. Структура компонентов

```
✅ ХОРОШО: Малый размер, одна ответственность
employees/components/
├── employee_form_personal.html     # ~80 строк
├── employee_form_contacts.html     # ~60 строк
└── employee_form_scripts.html      # ~22 строки

❌ ПЛОХО: Монолитный файл
employees/
└── employee_edit.html              # 1391 строка!
```

### 2. Именование файлов

```
✅ ХОРОШО: Префиксы, понятные имена
calendar_modal_create.html
employee_form_personal.html
department_controls_scripts.html

❌ ПЛОХО: Неясные имена
modal.html
form.html
scripts.html
```

### 3. Подключение компонентов

```django
✅ ХОРОШО: Явное включение с комментариями
{# Личные данные #}
{% include "employees/components/employee_form_personal.html" %}

{# Контакты #}
{% include "employees/components/employee_form_contacts.html" %}

❌ ПЛОХО: Неясный порядок без комментариев
{% include "comp1.html" %}
{% include "comp2.html" %}
```

### 4. Разделение JavaScript

```django
✅ ХОРОШО: Отдельный файл инициализации
{% include "employees/components/employee_form_scripts.html" %}

❌ ПЛОХО: Встроенный <script> в HTML
<script>
  // 500 строк JavaScript прямо в шаблоне
</script>
```

### 5. Передача контекста

```django
✅ ХОРОШО: Явная передача параметров
{% include "component.html" with employee=emp can_edit=True %}

❌ ПЛОХО: Неявный контекст
{% include "component.html" %}
{# Компонент зависит от глобальных переменных #}
```

### 6. Блоки и наследование

```django
✅ ХОРОШО: Расширение базового шаблона
{% extends "base.html" %}
{% block content %}
  <!-- Ваш контент -->
{% endblock %}

❌ ПЛОХО: Дублирование структуры
<!DOCTYPE html>
<html>
  <!-- Полная структура заново -->
</html>
```

### 7. CSS подключение

```django
✅ ХОРОШО: Модульные стили в extra_css
{% block extra_css %}
  <link rel="stylesheet" href="{% static 'css/components/custom.css' %}">
{% endblock %}

❌ ПЛОХО: Inline стили
<div style="color: red; font-size: 14px;">...</div>
```

### 8. Условное включение

```django
✅ ХОРОШО: Проверка прав перед включением
{% if user.is_authenticated %}
  {% include "includes/rightbar_calendar.html" %}
{% endif %}

❌ ПЛОХО: Проверка внутри компонента
{# В компоненте: #}
{% if user.is_authenticated %}
  <!-- Весь компонент -->
{% endif %}
```

---

## 🔧 Отладка шаблонов

### Вывод отладочной информации

```django
{# Проверка контекста #}
{% if debug %}
  <pre>{{ employee|pprint }}</pre>
{% endif %}

{# Отладка переменных #}
{{ variable|default:"NOT SET" }}
```

### Комментарии для разработчиков

```django
{# === СЕКЦИЯ: Личные данные === #}
{# TODO: Добавить валидацию email #}
{# FIXME: Баг с датой рождения #}
{# NOTE: Этот компонент используется в 3 местах #}
```

---

## 📞 Поддержка

При создании новых шаблонов:
1. Следуйте структуре существующих компонентов
2. Используйте префиксы в именах файлов
3. Документируйте сложную логику
4. Разделяйте HTML и JavaScript
5. Тестируйте на разных экранах

---

**Дата актуализации**: 4 ноября 2025 г.  
**Версия**: 1.0
