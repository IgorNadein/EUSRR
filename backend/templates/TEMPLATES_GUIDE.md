# Руководство по шаблонам EUSRR

## Статус рефакторинга

**Версия**: 2.1  
**Дата обновления**: январь 2025  
**Завершено**: Фазы 0-5 (85%)

---

## Архитектура шаблонов

### Базовая структура

```
templates/
├── base.html                     # Корневой шаблон с navbar/sidebar
├── includes/                     # Общие компоненты
│   ├── navbar.html              # Верхняя навигация
│   ├── sidebar.html             # Боковое меню
│   ├── rightbar_calendar.html   # Календарь (237 строк, было 996)
│   └── messages.html            # Django messages
│
├── admin/                        # Административные override
├── auth/                         # Авторизация, регистрация
├── communications/               # Чаты
├── documents/                    # Документы
├── emails/                       # Email-шаблоны
├── employees/                    # Сотрудники, отделы
│   ├── components/              # Переиспользуемые компоненты
│   │   ├── department_controls.html
│   │   ├── department_info.html
│   │   ├── department_modals.html
│   │   └── department_sidebar.html
│   ├── _employee_edit.html      # 24 строки (было 1391)
│   ├── department_detail.html   # 46 строк (было 1025)
│   ├── employees_list.html
│   └── ...
│
├── feed/                         # Лента новостей
├── requests_app/                 # Заявления сотрудников
└── search/                       # Поиск
```

---

## Статические файлы

### JavaScript

**Утилиты** (`static/js/utils/`):
- `stringUtils.js` (115 строк) - esc(), norm(), escAttr(), truncate(), getInitials()
- `timing.js` (173 строки) - debounce(), throttle(), delay(), poll(), once()
- `scroll.js` (205 строк) - smoothScrollTo(), scrollToTop(), isElementInViewport()
- `index.js` - Центральная точка экспорта

**Компоненты** (`static/js/components/`):
- `listFilter.js` (279 строк) - Универсальная фильтрация списков
- `teamWheel.js` (308 строк) - Вращающийся виджет команды
- `calendarWidget.js` (1002 строки) - FullCalendar + CRUD событий
- `index.js` - Центральная точка экспорта (v1.1.0)

### CSS

**Компоненты** (`static/css/components/`):
- `chat-detail.css` - Чат
- `department-list.css` - Список отделов
- `department-sidebar.css` - Боковая панель отдела
- `document-list.css` - Список документов
- `employee-detail.css` - Детали сотрудника
- `cards.css` - Карточки в ленте
- `login.css` - Страница входа
- `logout.css` - Страница выхода
- `navbar.css` - Верхняя навигация
- `password-forms.css` - Формы паролей
- `register.css` - Регистрация
- `request-list.css` - Список заявлений
- `rightbar-calendar.css` - Календарь
- `search-results.css` - Результаты поиска
- `sidebar.css` - Боковое меню
- `team-wheel.css` - Виджет команды
- И другие...

**Общие стили**:
- `common.css` (245 строк) - Переиспользуемые классы
- `variables.css` - CSS-переменные и цвета

---

## Использование компонентов

### JavaScript утилиты

#### В base.html (глобальный импорт)

```django
<script type="module">
  import { esc, norm, escAttr, truncate, getInitials } from '{% static "js/utils/stringUtils.js" %}';
  import { debounce, throttle, delay, poll, once } from '{% static "js/utils/timing.js" %}';
  import { smoothScrollTo, scrollToTop, scrollToBottom, isElementInViewport } from '{% static "js/utils/scroll.js" %}';

  // Экспорт в window для обратной совместимости
  window.esc = esc;
  window.norm = norm;
  window.debounce = debounce;
  // ... и т.д.
</script>
```

#### В шаблонах

```django
{% block extra_js %}
<script type="module">
  import { ListFilter, createDataAttrMatcher } from '{% static "js/components/listFilter.js" %}';

  document.addEventListener('DOMContentLoaded', () => {
    new ListFilter({
      listSelector: '#empList',
      itemSelector: '.emp-row',
      searchInputSelector: '#empFilter',
      matchFn: createDataAttrMatcher(['name', 'depts']),
      clearButtonSelector: '#clearBtn',
      emptyMessageSelector: '.empty-msg',
      debounceMs: 300
    });
  });
</script>
{% endblock %}
```

### CSS компоненты

#### Подключение в шаблоне

```django
{% block extra_css %}
<link rel="stylesheet" href="{% static 'css/components/cards.css' %}">
<link rel="stylesheet" href="{% static 'css/components/department-sidebar.css' %}">
{% endblock %}
```

#### Использование общих классов (common.css)

```html
<!-- Кнопки с иконками -->
<button class="btn-icon btn-icon-primary">
  <i class="bi-plus"></i>
</button>

<!-- Пустое состояние -->
<div class="empty-state">
  <div class="empty-icon">📋</div>
  <div class="empty-msg">Документов пока нет</div>
</div>

<!-- iOS-стиль модалок -->
<div class="ios-overlay">
  <div class="ios-sheet">
    <h1>Удалить сотрудника?</h1>
    <p>Это действие необратимо</p>
    <button class="btn btn-danger">Удалить</button>
  </div>
</div>

<!-- Feed карточки -->
<div class="card">
  <div class="card-header">
    <img src="..." class="card-icon">
    <div class="card-meta">
      <div class="card-title">Иван Петров</div>
      <div class="feed-ts">2 минуты назад</div>
    </div>
  </div>
  <div class="card-body">
    <p>Текст поста...</p>
  </div>
</div>
```

---

## Именование файлов

### Шаблоны

- `{model}_list.html` - Списки (employees_list, document_list)
- `{model}_detail.html` - Детальные страницы (employee_detail, department_detail)
- `{model}_form.html` - Формы создания/редактирования
- `{model}_confirm_delete.html` - Подтверждение удаления
- `_{partial}.html` - Партиалы (начинаются с `_`)

### Компоненты

- `components/{name}.html` - Переиспользуемые компоненты приложения
- `includes/{name}.html` - Глобальные компоненты

---

## Лучшие практики

### 1. Структура шаблона

```django
{% extends "base.html" %}
{% load static %}

{% block title %}Название страницы{% endblock %}

{% block extra_css %}
<link rel="stylesheet" href="{% static 'css/pages/my-page.css' %}">
{% endblock %}

{% block content %}
  {# Основной контент #}
{% endblock %}

{% block extra_js %}
<script type="module">
  import { MyComponent } from '{% static "js/components/myComponent.js" %}';
  new MyComponent();
</script>
{% endblock %}
```

### 2. Использование компонентов

```django
{# С параметрами #}
{% include "employees/components/department_info.html" with department=dept %}

{# С контекстом #}
{% with user=employee %}
  {% include "includes/components/user_card.html" %}
{% endwith %}
```

### 3. Стили и скрипты

✅ **ПРАВИЛЬНО**:
```django
{# Стили в extra_css блоке #}
{% block extra_css %}
<link rel="stylesheet" href="{% static 'css/components/cards.css' %}">
{% endblock %}

{# Скрипты в extra_js блоке #}
{% block extra_js %}
<script type="module">
  import { ListFilter } from '{% static "js/components/listFilter.js" %}';
  new ListFilter({ /* ... */ });
</script>
{% endblock %}
```

❌ **НЕПРАВИЛЬНО**:
```django
{# Встроенные стили в body #}
<style>
  .my-class { /* ... */ }
</style>

{# Встроенные скрипты в body #}
<script>
  function myFunc() { /* ... */ }
</script>
```

### 4. Безопасность

```django
{# Всегда используйте CSRF-защиту #}
<form method="post">
  {% csrf_token %}
  {# ... поля формы ... #}
</form>

{# Экранирование HTML (по умолчанию включено) #}
{{ user.bio }}  {# Безопасно #}

{# Если нужен HTML (используйте с осторожностью!) #}
{{ user.bio|safe }}  {# Только для доверенного контента! #}
```

---

## Компоненты и их использование

### ListFilter (универсальная фильтрация)

**Импорт**:
```javascript
import { ListFilter, createDataAttrMatcher, createSelectorMatcher } from '{% static "js/components/listFilter.js" %}';
```

**Базовое использование**:
```javascript
new ListFilter({
  listSelector: '.employees-list',
  itemSelector: '.employee-card',
  searchInputSelector: '#searchInput'
});
```

**С пользовательской функцией поиска**:
```javascript
new ListFilter({
  listSelector: '#empList',
  itemSelector: '.emp-row',
  searchInputSelector: '#empFilter',
  matchFn: createDataAttrMatcher(['name', 'email', 'department']),
  clearButtonSelector: '#clearBtn',
  emptyMessageSelector: '.no-results',
  debounceMs: 300
});
```

### TeamWheel (вращающийся виджет команды)

**Импорт**:
```javascript
import { initTeamWheel } from '{% static "js/components/teamWheel.js" %}';
```

**Использование**:
```javascript
initTeamWheel({
  wheelId: 'teamWheel',
  columns: 4,
  speed: 30,
  pauseOnHover: true
});
```

### CalendarWidget (календарь событий)

**Импорт**:
```javascript
import { initCalendarWidget } from '{% static "js/components/calendarWidget.js" %}';
```

**Использование**:
```javascript
window.calendarWidget = initCalendarWidget({
  deskContainerId: 'calendarRight',
  mobContainerId: 'calendarRightMobile',
  apiEventsUrl: '/api/v1/calendar/events/',
  apiMyDeptsUrl: '/api/v1/departments/my-departments/',
  defaultColor: '#0d6efd'
});
```

**API виджета**:
```javascript
// Обновить списки недели
window.calendarWidget.updateWeekLists();

// Перезагрузить события
window.calendarWidget.refetchEvents();

// Получить список отделов
const departments = window.calendarWidget.getDepartments();

// Получить текущее состояние
const state = window.calendarWidget.getState(); // { type: 'company'|'dept', deptId: number|null }
```

---

## Отладка и тестирование

### Проверка подключения модулей

```javascript
// В консоли браузера
console.log(window.esc);      // function esc(str) { ... }
console.log(window.debounce); // function debounce(fn, ms) { ... }
```

### Проверка работы компонентов

```javascript
// ListFilter
const filter = new ListFilter({ /* ... */ });
filter.filter('test');  // Применить фильтр
filter.refresh();       // Обновить список элементов
filter.clear();         // Очистить фильтр

// CalendarWidget
window.calendarWidget.refetchEvents(); // Перезагрузить события
```

### Django тесты

```python
from django.test import TestCase
from django.template.loader import get_template

class TemplateRenderingTests(TestCase):
    def test_employee_list_renders(self):
        template = get_template('employees/employees_list.html')
        self.assertIsNotNone(template)
    
    def test_no_inline_styles(self):
        """Проверка отсутствия встроенных стилей"""
        template = get_template('employees/employees_list.html')
        content = template.render({})
        self.assertNotIn('<style>', content)
```

---

## История рефакторинга

### Фаза 0: Инфраструктура ✅
- Создана структура папок для статики
- Настроена система тестирования

### Фаза 1: Устранение дубликатов ✅
- Удалены неиспользуемые файлы (logout_confirm.html, password_reset_form.html)
- Объединены папки requests/ и requests_app/
- Сокращено файлов: 61 → 58

### Фаза 2: JavaScript утилиты ✅
- Созданы модули: stringUtils.js, timing.js, scroll.js
- Создан компонент ListFilter.js (279 строк)
- Все утилиты импортированы в base.html
- Замена дублирующих функций в 20+ файлах

### Фаза 3: CSS extraction ✅
- Создано 22 CSS-файла в components/
- Создан common.css (245 строк) с переиспользуемыми классами
- Унифицирован variables.css
- Удалено ~1500 строк встроенных стилей
- **Результат**: 0 встроенных `<style>` блоков во всех шаблонах

### Фаза 4: JavaScript extraction ✅
- Создан teamWheel.js (308 строк)
- Создан calendarWidget.js (1002 строки)
- rightbar_calendar.html сокращён с 996 до 237 строк (76% редукция)
- Обновлён components/index.js (v1.1.0)

### Фаза 5: HTML decomposition (частично) 🔄
- ✅ _employee_edit.html: 1391 → 24 строки (98.3% редукция)
- ✅ department_detail.html: 1025 → 46 строк (95.5% редукция)
- ⏳ rightbar_calendar.html: В процессе дальнейшей декомпозиции

### Фаза 6: Документация (текущая) 🔄
- Создан TEMPLATES_GUIDE.md
- Обновлён REFACTORING_PLAN.md
- Создана документация по компонентам

---

## Метрики рефакторинга

### До рефакторинга
- HTML файлов: 61
- Встроенного CSS: ~1500 строк
- Встроенного JavaScript: ~4500 строк
- Файлов > 1000 строк: 3

### После рефакторинга
- HTML файлов: 58
- Встроенного CSS: **0 строк** ✅
- Встроенного JavaScript: ~200 строк (только page-specific)
- Файлов > 1000 строк: **0** ✅
- CSS компонентов: 22 файла
- JS модулей: 6 файлов (3 utilities + 3 components)

### Сокращение кода
- `_employee_edit.html`: -98.3% (1391 → 24)
- `department_detail.html`: -95.5% (1025 → 46)
- `rightbar_calendar.html`: -76% (996 → 237)

### Переиспользование
- CSS классов: 45+ общих классов в common.css
- JS функций: 14 утилит, 3 компонента
- Компонентов форм: 4 переиспользуемых партиала

---

## Roadmap (что дальше)

### Краткосрочные цели
- [ ] Декомпозировать rightbar_calendar.html HTML структуру
- [ ] Создать компоненты календаря (calendar_widget, calendar_toolbar, etc.)
- [ ] Оптимизировать CSS (минификация, удаление unused)
- [ ] Финальное тестирование всех страниц

### Долгосрочные цели
- [ ] Создать Storybook для компонентов
- [ ] Настроить CSS/JS минификацию для production
- [ ] Создать визуальные регрессионные тесты
- [ ] Документировать все API компонентов

---

## Поддержка

**Вопросы и предложения**: Создавайте issue в репозитории  
**Документация**: `templates/TEMPLATES_GUIDE.md` (этот файл)  
**План рефакторинга**: `templates/REFACTORING_PLAN.md`  
**CSS документация**: `static/css/README.md`  
**JavaScript документация**: Inline JSDoc в модулях

---

**Версия документа**: 2.1  
**Последнее обновление**: январь 2025  
**Авторы**: GitHub Copilot, команда разработки EUSRR
