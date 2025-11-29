# План рефакторинга templates/

## Статистика проекта

**Общая информация:**
- Всего файлов: 61 (HTML/CSS/JS)
- HTML шаблонов: 58
- Общий объём: 11,479 строк кода

**Распределение по модулям:**
```
admin/          1 файл    (change_form.html)
auth/           12 файлов (login, register, password reset, logout, verify)
communications/ 2 файла   (chat_list, chat_detail)
documents/      1 файл    (document_list)
emails/         2 файла   (password_reset_email, registration_verify_code)
employees/      15 файлов (списки, детали, формы)
feed/           10 файлов (посты, комментарии, ленты)
includes/       4 файла   (navbar, sidebar, rightbar_calendar, messages)
requests/       1 файл    (request_list.html - ДУБЛИКАТ!)
requests_app/   7 файлов  (all_requests, my_requests, process, etc.)
search/         1 файл    (results)
base.html       1 файл    (корневой шаблон)
```

## Обнаруженные проблемы

### 🔴 КРИТИЧЕСКИЕ ПРОБЛЕМЫ

#### 1. **Дублирование папок: requests/ vs requests_app/**

**requests/request_list.html** (788 строк):
- Путь: `templates/requests/request_list.html`
- Использование: `requests_app/views_front.py:174` → `template_name = "requests/request_list.html"`
- Назначение: Комплексная страница со списком заявлений + документов + recipient picker

**requests_app/all_requests.html** (147 строк):
- Путь: `templates/requests_app/all_requests.html`
- Использование: `requests_app/views.py:315` → `"requests_app/all_requests.html"`
- Назначение: Простой список всех заявлений с фильтрами

**requests_app/my_requests.html** (102 строки):
- Путь: `templates/requests_app/my_requests.html`
- Использование: `requests_app/views.py:251` → `"requests_app/my_requests.html"`
- Назначение: Список моих заявлений

**Вывод**: 
- `requests/` - устаревшая папка (1 файл)
- `requests_app/` - актуальная структура (7 файлов)
- **Необходимо**: объединить всё в `requests_app/`

#### 2. **Дублирование auth шаблонов**

**auth/logout.html** (171 строка):
- Использование: `employees/views_auth.py:182` → `template_name = "auth/logout.html"`
- Статус: **ИСПОЛЬЗУЕТСЯ** ✅
- Описание: Современный iOS-стиль, overlay, анимации, полнофункциональный

**auth/logout_confirm.html** (33 строки):
- Использование: ❌ **НЕ НАЙДЕНО**
- Статус: **НЕИСПОЛЬЗУЕМЫЙ ДУБЛИКАТ**
- Описание: Простой standalone HTML без base.html

**Вывод**: `logout_confirm.html` - устаревший файл → **УДАЛИТЬ**

#### 3. **Дублирование password reset шаблонов**

**auth/password_reset.html** (83 строки):
- Использование: `employees/views_auth.py:199` → `template_name = "auth/password_reset.html"`
- Статус: **ИСПОЛЬЗУЕТСЯ** ✅
- Описание: Полноценная форма с валидацией, extends base.html

**auth/password_reset_form.html** (7 строк):
- Использование: ❌ **НЕ НАЙДЕНО**
- Статус: **НЕИСПОЛЬЗУЕМЫЙ ДУБЛИКАТ**
- Описание: Простая заглушка без стилей

**Вывод**: `password_reset_form.html` - устаревший файл → **УДАЛИТЬ**

### 🟡 СРЕДНИЙ ПРИОРИТЕТ

#### 4. **Огромные файлы требуют декомпозиции**

**employees/_employee_edit.html** (1391 строка):
- Проблема: Монолитная форма редактирования сотрудника
- Решение: Разбить на компоненты:
  - `_employee_edit_personal.html` (ФИО, email, телефон)
  - `_employee_edit_position.html` (должность, отдел)
  - `_employee_edit_contact.html` (контакты, адреса)
  - `_employee_edit_skills.html` (навыки)
  - `_employee_edit_documents.html` (документы)

**employees/department_detail.html** (1025 строк):
- Проблема: Детальная страница отдела со множеством разделов
- Решение: Выделить компоненты:
  - `_department_header.html` (заголовок, руководитель)
  - `_department_members.html` (список сотрудников)
  - `_department_stats.html` (статистика)
  - `_department_subdepts.html` (подотделы)

**includes/rightbar_calendar.html** (1129 строк):
- Проблема: Правый сайдбар с календарём + события
- Решение: Разбить на:
  - `_calendar_widget.html` (виджет календаря)
  - `_calendar_events.html` (список событий)
  - `_calendar_filters.html` (фильтры)

**documents/document_list.html** (743 строки):
- Проблема: Список документов + фильтры + модалки
- Решение: Выделить:
  - `_document_filters.html` (панель фильтров)
  - `_document_card.html` (карточка документа)
  - `_document_modals.html` (модальные окна)

**requests/request_list.html** (788 строк):
- Проблема: Комплексная страница с заявлениями, документами, recipient picker
- Решение: После переноса в requests_app/ разбить на компоненты

**employees/employee_detail.html** (600 строк):
- Решение: Выделить табы в отдельные компоненты

#### 5. **Дублирование CSS стилей**

Обнаружены повторяющиеся блоки стилей:
- `.card-list`, `.card`, `.card-header` - определены в 5+ файлах
- `.btn-icon`, `.badge-status` - дублируются
- `.ios-overlay`, `.ios-sheet` - iOS-стиль модалок

**Решение**: Создать общие файлы стилей:
- `static/css/components/feed.css` - стили для лент
- `static/css/components/modals.css` - iOS-стиль модалок
- `static/css/components/badges.css` - бейджи статусов

### 🟢 НИЗКИЙ ПРИОРИТЕТ

#### 6. **Оптимизация структуры includes/**

Текущие:
- `includes/navbar.html` (143 строки)
- `includes/sidebar.html` (259 строк)
- `includes/rightbar_calendar.html` (1129 строк)
- `includes/messages.html` (9 строк)

**Рекомендации**:
- Выделить из navbar: `_navbar_search.html`, `_navbar_user_menu.html`
- Выделить из sidebar: `_sidebar_menu.html`, `_sidebar_profile.html`

#### 7. **Консистентность именования**

**Проблемы**:
- Некоторые файлы начинаются с `_` (партиалы), другие нет
- Смешанное использование `confirm_delete` vs `delete_confirm`
- `employee_feed.html` vs `feed_list.html` (разная логика именования)

**Стандарт**:
- `_` - только для партиалов (переиспользуемых компонентов)
- `{model}_list.html` - списки
- `{model}_detail.html` - детальные страницы
- `{model}_form.html` - формы создания/редактирования
- `{model}_confirm_delete.html` - подтверждение удаления

## ⚠️ ВАЖНЫЕ ВЫВОДЫ ИЗ ПРЕДЫДУЩИХ ПОПЫТОК

### Проблемы при декомпозиции HTML без предварительной работы со стилями/скриптами:

1. **Стили в неправильных местах**: При извлечении компонентов стили `<style>` попадали не в `<head>`, а в `<body>`
2. **Разрушение grid структуры**: Лишние открывающие/закрывающие теги `<div>` внутри компонентов ломали Bootstrap layout
3. **Сложность отката**: Календарь пришлось полностью откатить, т.к. HTML разметка осталась в файле стилей
4. **Долгая диагностика**: На поиск и исправление ошибок ушло больше времени, чем на сам рефакторинг

### ✅ НОВАЯ СТРАТЕГИЯ: "Стили и скрипты сначала"

**Принцип**: Сначала извлекаем и тестируем весь CSS/JS, потом занимаемся HTML-декомпозицией.

**Преимущества**:
- Каждое изменение легко проверить (рендер не должен измениться)
- Меньше переменных - проще найти ошибку
- Можно использовать автоматические тесты на визуальную регрессию
- После вынесения стилей/скриптов HTML-декомпозиция станет тривиальной

---

## План рефакторинга (обновлённый, поэтапный)

---

### 📋 **Фаза 0: Подготовка инфраструктуры (30 минут - 1 час)**

#### Задача 0.1: Создать структуру для статики

**Действия**:
1. Создать папки для извлечённых файлов:
   ```bash
   mkdir -p static/css/pages
   mkdir -p static/css/components
   mkdir -p static/js/pages
   mkdir -p static/js/components
   mkdir -p static/js/utils
   ```

2. Создать файл `static/css/components/_index.css` (главный импорт):
   ```css
   /* Общие компоненты - импортируются в base.html */
   @import 'cards.css';
   @import 'ios-search.css';
   @import 'modals.css';
   @import 'badges.css';
   ```

3. Создать файл `static/js/utils/_index.js` (главный импорт):
   ```javascript
   // Утилиты - импортируются перед page-specific скриптами
   import { esc, norm } from './stringUtils.js';
   import { debounce, throttle } from './timing.js';
   import { smoothScrollTo } from './scroll.js';
   ```

**Критерий завершения**: 
- Структура папок создана ✅
- Индексные файлы созданы ✅
- Git commit: "chore: create static files structure" ✅

---

#### Задача 0.2: Создать систему тестирования

**Создать** `tests/test_template_rendering.py`:
```python
"""
Тесты визуальной регрессии - проверяют, что после рефакторинга
страницы рендерятся идентично.
"""
import hashlib
from django.test import TestCase, Client
from django.contrib.auth import get_user_model

User = get_user_model()

class TemplateRenderingTests(TestCase):
    """Проверка идентичности рендера до/после рефакторинга"""
    
    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            username='test',
            email='test@test.com',
            password='test123'
        )
        self.client.force_login(self.user)
    
    def get_page_hash(self, url):
        """Получить хэш отрендеренной страницы"""
        response = self.client.get(url)
        # Убираем CSRF токены и timestamps для сравнения
        content = response.content.decode('utf-8')
        content = re.sub(r'csrfmiddlewaretoken[^>]*value="[^"]*"', '', content)
        content = re.sub(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}', '', content)
        return hashlib.md5(content.encode()).hexdigest()
    
    def test_employees_list_unchanged(self):
        """Проверка, что /employees/list/ рендерится одинаково"""
        hash_before = self.get_page_hash('/employees/list/')
        # После рефакторинга запустить снова и сравнить
        # self.assertEqual(hash_before, hash_after)
```

**Критерий завершения**:
- Тесты созданы ✅
- Запускаются без ошибок ✅
- Git commit: "test: add template rendering tests" ✅

---

### 📋 **Фаза 1: Устранение дубликатов (1-2 часа)** ✅ ЗАВЕРШЕНА

#### Задача 1.1: Удаление неиспользуемых файлов

**Действия**:
1. ✅ Проверить grep-поиском использование файлов
2. ❌ Удалить неиспользуемые файлы:
   ```bash
   rm templates/auth/logout_confirm.html
   rm templates/auth/password_reset_form.html
   ```
3. ✅ Запустить тесты для проверки

**Файлы к удалению**:
- `auth/logout_confirm.html` (33 строки) - не используется
- `auth/password_reset_form.html` (7 строк) - не используется

**Критерий завершения**: 
- Все тесты проходят ✅
- grep не находит импортов удалённых файлов ✅

---

#### Задача 1.2: Объединение requests/ и requests_app/

**Проблема**: Две папки с заявлениями
- `requests/` - 1 файл (788 строк)
- `requests_app/` - 7 файлов (831 строка)

**Решение**:

1. **Переименовать** `requests/request_list.html` → `requests_app/request_list_full.html`:
   ```bash
   mv templates/requests/request_list.html templates/requests_app/request_list_full.html
   ```

2. **Обновить импорт** в `requests_app/views_front.py:174`:
   ```python
   # Было:
   template_name = "requests/request_list.html"
   
   # Стало:
   template_name = "requests_app/request_list_full.html"
   ```

3. **Удалить пустую папку**:
   ```bash
   rmdir templates/requests/
   ```

4. **Проверить** использование:
   ```bash
   grep -r "requests/request_list" backend/
   grep -r "requests/" backend/templates/
   ```

**Критерий завершения**: 
- Папка `requests/` удалена ✅
- View корректно рендерит новый шаблон ✅
- Все тесты проходят ✅

---

### 📋 **Фаза 2: Извлечение общих утилит JavaScript (2-3 часа)**

#### Задача 2.1: Создать общие утилиты

**Обнаружены дублирующиеся функции** (из analyze_templates.py):
- `esc()` - в 3 файлах (base.html, department_scripts.html, _department_controls.html)
- `norm()` - в 3 файлах
- `applyFilter()` - в 4 файлах
- `debounce()` - минимум в 2 файлах
- `smoothScrollTo()` - в 2 файлах

**Действия**:

1. **Создать** `static/js/utils/stringUtils.js`:
   ```javascript
   /**
    * Экранирование HTML символов
    * @param {string} str - строка для экранирования
    * @returns {string} - экранированная строка
    */
   export function esc(str) {
     return String(str).replace(/[&<>"']/g, m => ({
       '&': '&amp;',
       '<': '&lt;',
       '>': '&gt;',
       '"': '&quot;',
       "'": '&#39;'
     }[m]));
   }
   
   /**
    * Нормализация строки (lowercase, trim)
    */
   export function norm(str) {
     return String(str || '').toLowerCase().trim();
   }
   ```

2. **Создать** `static/js/utils/timing.js`:
   ```javascript
   /**
    * Debounce функция
    */
   export function debounce(fn, ms) {
     let timeout;
     return function(...args) {
       clearTimeout(timeout);
       timeout = setTimeout(() => fn.apply(this, args), ms);
     };
   }
   
   /**
    * Throttle функция
    */
   export function throttle(fn, ms) {
     let inThrottle;
     return function(...args) {
       if (!inThrottle) {
         fn.apply(this, args);
         inThrottle = true;
         setTimeout(() => inThrottle = false, ms);
       }
     };
   }
   ```

3. **Создать** `static/js/utils/scroll.js`:
   ```javascript
   /**
    * Плавная прокрутка к элементу с учётом fixed navbar
    */
   export function smoothScrollTo(element) {
     const navbarHeight = document.querySelector('.app-navbar')?.offsetHeight || 0;
     const elementTop = element.getBoundingClientRect().top + window.pageYOffset;
     const offsetTop = elementTop - navbarHeight - 20;
     
     window.scrollTo({
       top: offsetTop,
       behavior: 'smooth'
     });
   }
   ```

4. **Заменить в base.html**:
   ```django
   {# Вместо встроенных функций #}
   <script type="module">
     import { esc, norm } from '{% static "js/utils/stringUtils.js" %}';
     import { debounce } from '{% static "js/utils/timing.js" %}';
     
     // Экспортируем в window для обратной совместимости
     window.esc = esc;
     window.norm = norm;
     window.debounce = debounce;
   </script>
   ```

5. **Постепенно заменять во всех шаблонах**:
   - Найти все определения `function esc(`
   - Заменить на импорт из утилит
   - Тестировать после каждой замены

**Порядок замены**:
1. base.html (самый критичный) → тестируем все страницы
2. employees/components/department_scripts.html → тестируем страницу отдела
3. employees/_department_controls.html → тестируем модалки управления
4. documents/document_list.html → тестируем список документов

**Критерий завершения**:
- Утилиты созданы и задокументированы ✅
- Все дублирующие функции заменены на импорты ✅
- Все страницы работают идентично ✅
- Git commit: "refactor: extract common JS utilities" ✅

---

#### Задача 2.2: Создать переиспользуемые компоненты фильтрации

**Обнаружена функция** `applyFilter()` в 4 файлах с похожей логикой:
- employees/components/department_scripts.html
- documents/document_list.html
- employees/employees_list.html
- employees/department_list.html

**Создать** `static/js/components/listFilter.js`:
```javascript
/**
 * Универсальный компонент фильтрации списков
 * @param {Object} options - настройки фильтра
 * @param {string} options.listSelector - селектор списка
 * @param {string} options.itemSelector - селектор элементов
 * @param {string} options.searchInputSelector - селектор поля поиска
 * @param {Function} options.matchFn - функция проверки совпадения
 */
export class ListFilter {
  constructor(options) {
    this.list = document.querySelector(options.listSelector);
    this.items = this.list?.querySelectorAll(options.itemSelector) || [];
    this.searchInput = document.querySelector(options.searchInputSelector);
    this.matchFn = options.matchFn || this.defaultMatch;
    
    this.init();
  }
  
  init() {
    if (!this.searchInput) return;
    
    this.searchInput.addEventListener('input', debounce(() => {
      this.filter(this.searchInput.value);
    }, 300));
  }
  
  filter(query) {
    const normalizedQuery = norm(query);
    let visibleCount = 0;
    
    this.items.forEach(item => {
      const isMatch = this.matchFn(item, normalizedQuery);
      item.style.display = isMatch ? '' : 'none';
      if (isMatch) visibleCount++;
    });
    
    this.updateEmptyState(visibleCount);
  }
  
  defaultMatch(item, query) {
    const text = item.textContent.toLowerCase();
    return text.includes(query);
  }
  
  updateEmptyState(count) {
    // Показать/скрыть "Ничего не найдено"
  }
}
```

**Использование**:
```javascript
// В employees_list.html
import { ListFilter } from '{% static "js/components/listFilter.js" %}';

new ListFilter({
  listSelector: '.employees-list',
  itemSelector: '.employee-card',
  searchInputSelector: '#employeeSearch',
  matchFn: (item, query) => {
    const name = item.dataset.name?.toLowerCase() || '';
    const email = item.dataset.email?.toLowerCase() || '';
    return name.includes(query) || email.includes(query);
  }
});
```

**Критерий завершения**:
- Компонент создан ✅
- Заменены все 4 использования applyFilter() ✅
- Все страницы с поиском работают ✅
- Git commit: "refactor: extract ListFilter component" ✅

---

### 📋 **Фаза 3: Извлечение повторяющихся CSS стилей (2-3 часа)**

#### Задача 3.1: Создать общие компоненты стилей

**Обнаружены дублирующие классы** (из analyze_templates.py):
- `.feed-header`, `.card-list`, `.card-header`, `.card-icon` - в 4-6 файлах
- `.ios-search`, `.ios-search-input`, `.ios-search-clear` - в 4 файлах
- `.btn-icon` - в 3 файлах

**Действия**:

1. **Создать** `static/css/components/cards.css`:
   ```css
   /* Стили для карточек в ленте */
   .card {
     background: var(--bs-body-bg);
     border-radius: var(--feed-radius, 18px);
     box-shadow: var(--feed-shadow);
     margin-bottom: 1rem;
     overflow: hidden;
   }
   
   .card-header {
     display: flex;
     align-items: center;
     gap: 0.75rem;
     padding: 0.75rem 1rem;
     border-bottom: 1px solid var(--bs-border-color);
   }
   
   .card-icon {
     width: 44px;
     height: 44px;
     border-radius: 50%;
     object-fit: cover;
   }
   
   /* ... остальные стили */
   ```

2. **Создать** `static/css/components/ios-search.css`:
   ```css
   /* iOS-стиль поиска */
   .ios-search {
     position: relative;
     margin-bottom: 1rem;
   }
   
   .ios-search-input {
     width: 100%;
     padding: 0.5rem 2.5rem 0.5rem 2rem;
     border-radius: 10px;
     border: 1px solid var(--bs-border-color);
     background: var(--bs-tertiary-bg);
   }
   
   .ios-search-clear {
     position: absolute;
     right: 0.5rem;
     top: 50%;
     transform: translateY(-50%);
     /* ... */
   }
   ```

3. **Извлечь стили из шаблонов**:
   
   **Порядок извлечения** (от самых дублируемых к менее):
   1. `base.html` (426 строк CSS) → выделить feed-*, btn-icon в отдельные файлы
   2. `documents/document_list.html` (39 строк) → использовать общие feed-*
   3. `requests_app/request_list_full.html` (109 строк) → использовать feed-*
   4. `employees/employees_list.html` (99 строк) → использовать ios-search
   5. `employees/department_list.html` → использовать ios-search
   
   **Процесс для каждого файла**:
   ```bash
   # 1. Сохранить backup
   cp template.html template.html.backup
   
   # 2. Извлечь стили в CSS файл
   # 3. Заменить <style>...</style> на:
   {% block extra_css %}
   <link rel="stylesheet" href="{% static 'css/components/cards.css' %}">
   {% endblock %}
   
   # 4. Проверить рендер
   python manage.py runserver
   # Открыть страницу, проверить визуально
   
   # 5. Запустить тесты
   python manage.py test tests.test_template_rendering
   
   # 6. Если всё ОК - коммит, если нет - откат из backup
   ```

4. **Подключить в base.html**:
   ```django
   {% block extra_css %}
   <link rel="stylesheet" href="{% static 'css/components/cards.css' %}">
   <link rel="stylesheet" href="{% static 'css/components/ios-search.css' %}">
   <link rel="stylesheet" href="{% static 'css/components/modals.css' %}">
   <link rel="stylesheet" href="{% static 'css/components/badges.css' %}">
   {% endblock %}
   ```

**Критерий завершения**:
- Создано 4-5 CSS компонентов ✅
- Из шаблонов удалено ~300-400 строк дублирующих стилей ✅
- Все страницы рендерятся идентично ✅
- Git commits: по одному на каждый извлечённый компонент ✅

---

#### Задача 3.2: Извлечь специфичные стили страниц

**Для больших файлов** создать отдельные CSS файлы:

1. **employees/department_detail.html** → `static/css/pages/department-detail.css`:
   ```css
   /* Стили специфичные для страницы отдела */
   .team-wheel { /* ... */ }
   .wheel-columns { /* ... */ }
   /* ... */
   ```

2. **includes/rightbar_calendar.html** → `static/css/components/calendar.css`:
   ```css
   /* Стили календаря */
   .calendar-wrap { /* ... */ }
   .fc { /* ... */ }
   /* ... */
   ```

3. **documents/document_list.html** → `static/css/pages/document-list.css`

**Критерий завершения**:
- Каждый шаблон > 50 строк CSS имеет отдельный файл ✅
- Встроенных `<style>` осталось < 20 строк (только page-specific) ✅
- Git commit: "refactor: extract page-specific styles" ✅

---

### 📋 **Фаза 4: Извлечение специфичных JavaScript модулей (2-3 часа)**

#### Задача 4.1: Извлечь большие JavaScript блоки

**ТОП файлов по JS** (из analyze_templates.py):
1. `employees/components/employee_form_scripts.html` - 899 строк JS
2. `includes/rightbar_calendar.html` - 762 строки JS
3. `employees/components/department_scripts.html` - 498 строк JS
4. `documents/document_list.html` - 421 строка JS

**Действия**:

1. **Создать** `static/js/components/employeeForm.js`:
   ```javascript
   /**
    * Логика формы редактирования сотрудника
    */
   export class EmployeeForm {
     constructor(formSelector) {
       this.form = document.querySelector(formSelector);
       if (!this.form) return;
       
       this.init();
     }
     
     init() {
       this.setupValidation();
       this.setupAvatarUpload();
       this.setupSkillsAutocomplete();
       // ...
     }
     
     // Методы из оригинального скрипта
   }
   ```

2. **Создать** `static/js/components/calendarWidget.js`:
   ```javascript
   /**
    * Виджет календаря с FullCalendar
    */
   export class CalendarWidget {
     constructor(options) {
       this.container = document.querySelector(options.container);
       this.apiUrl = options.apiUrl;
       this.calendar = null;
       
       this.init();
     }
     
     init() {
       if (!window.FullCalendar) return;
       
       this.calendar = new FullCalendar.Calendar(this.container, {
         // ... конфигурация
       });
       
       this.calendar.render();
       this.setupEventHandlers();
     }
     
     // Методы из оригинального скрипта
   }
   ```

3. **Создать** `static/js/components/teamWheel.js`:
   ```javascript
   /**
    * Крутящийся круг с сотрудниками отдела
    */
   export class TeamWheel {
     constructor(wheelId) {
       this.wheel = document.getElementById(wheelId);
       if (!this.wheel) return;
       
       this.columns = this.wheel.querySelector('[data-columns]');
       this.members = this.loadMembers();
       
       this.init();
     }
     
     loadMembers() {
       const src = document.getElementById(`teamData-${this.wheelId}`);
       return Array.from(src.children).map(/* ... */);
     }
     
     init() {
       this.fillColumns();
       this.setupAutoScroll();
       this.setupInteraction();
     }
     
     // Методы из оригинального скрипта
   }
   ```

4. **Заменить в шаблонах**:
   ```django
   {# employees/_employee_edit.html #}
   {% block extra_js %}
   <script type="module">
     import { EmployeeForm } from '{% static "js/components/employeeForm.js" %}';
     
     document.addEventListener('DOMContentLoaded', () => {
       new EmployeeForm('#employeeEditForm');
     });
   </script>
   {% endblock %}
   ```

**Порядок извлечения**:
1. `employee_form_scripts.html` (899 строк) - самый большой
2. `rightbar_calendar.html` (762 строки) - уже откатывали
3. `department_scripts.html` (498 строк) - круг с командой
4. `document_list.html` (421 строка) - фильтры документов

**Критерий завершения**:
- Создано 4 JS модуля ✅
- Из шаблонов удалено ~2500 строк JS ✅
- Все интерактивные элементы работают ✅
- Git commits: по одному на каждый модуль ✅

---

### 📋 **Фаза 5: Декомпозиция HTML (только после Фаз 2-4!) (2-3 часа)**

**⚠️ ВАЖНО**: Начинаем только когда все стили и скрипты вынесены в отдельные файлы!

#### Задача 5.1: Декомпозиция employees/_employee_edit.html

**Теперь это безопасно**, т.к.:
- ✅ Все стили уже в `static/css/pages/employee-edit.css`
- ✅ Все скрипты уже в `static/js/components/employeeForm.js`
- ✅ Остался только чистый HTML для разбиения

**Создать компоненты**:
```
employees/components/
  employee_form_personal.html    (ФИО, дата рождения)
  employee_form_contacts.html    (Email, телефон)
  employee_form_position.html    (Должность, отдел)
  employee_form_access.html      (Права доступа)
  employee_form_avatar.html      (Загрузка фото)
```

**Процесс**:
```django
{# employees/_employee_edit.html #}
{% extends "base.html" %}

{% block extra_css %}
<link rel="stylesheet" href="{% static 'css/pages/employee-edit.css' %}">
{% endblock %}

{% block content %}
<form id="employeeEditForm" method="post" enctype="multipart/form-data">
  {% csrf_token %}
  
  {% include "employees/components/employee_form_avatar.html" %}
  {% include "employees/components/employee_form_personal.html" %}
  {% include "employees/components/employee_form_contacts.html" %}
  {% include "employees/components/employee_form_position.html" %}
  {% include "employees/components/employee_form_access.html" %}
  
  <button type="submit" class="btn btn-primary">Сохранить</button>
</form>
{% endblock %}

{% block extra_js %}
<script type="module">
  import { EmployeeForm } from '{% static "js/components/employeeForm.js" %}';
  new EmployeeForm('#employeeEditForm');
</script>
{% endblock %}
```

**Критерий завершения**:
- Создано 5 компонентов формы ✅
- Основной файл уменьшен с 1391 до ~50 строк ✅
- Форма работает идентично ✅
- Git commit: "refactor: decompose employee edit form" ✅

---

#### Задача 5.2: Декомпозиция includes/rightbar_calendar.html (1130 строк)

**Теперь это безопасно**, т.к.:
- ✅ Все стили уже в `static/css/components/calendar.css`
- ✅ Все скрипты уже в `static/js/components/calendarWidget.js`

**Создать компоненты**:
```
includes/calendar/
  calendar_widget.html        (Сам FullCalendar)
  calendar_legend.html        (Легенда цветов)
  calendar_toolbar.html       (Кнопки управления)
  calendar_event_modal.html   (Модалка добавления события)
```

**Основной файл**:
```django
{# includes/rightbar_calendar.html #}
{% load static %}

<div class="calendar-wrap">
  {% include "includes/calendar/calendar_toolbar.html" %}
  {% include "includes/calendar/calendar_widget.html" %}
  {% include "includes/calendar/calendar_legend.html" %}
</div>

{% include "includes/calendar/calendar_event_modal.html" %}

<script type="module">
  import { CalendarWidget } from '{% static "js/components/calendarWidget.js" %}';
  
  new CalendarWidget({
    container: '#calendar',
    apiUrl: '{% url "api:v1:calendar-events" %}',
    // ... опции
  });
</script>
```

**Критерий завершения**:
- Создано 4 компонента календаря ✅
- Основной файл уменьшен с 1130 до ~30 строк ✅
- Календарь работает идентично ✅
- Git commit: "refactor: decompose calendar component" ✅

---

#### Задача 5.3: Декомпозиция employees/department_detail.html

**Уже частично сделано** в предыдущих сессиях, но теперь финализируем:

**Компоненты** (уже созданы):
```
employees/components/
  department_info.html          ✅ (создан)
  department_sidebar.html       ✅ (создан, исправлен)
  department_modals.html        ✅ (создан, исправлен)
  department_scripts.html       ✅ (создан, исправлен)
```

**Но теперь нужно**:
1. Извлечь скрипты из `department_scripts.html` → `static/js/components/teamWheel.js`
2. Извлечь стили из всех компонентов → `static/css/pages/department-detail.css`
3. Очистить компоненты от `<script>` и `<style>` тегов

**После очистки**:
```django
{# employees/components/department_scripts.html → УДАЛИТЬ #}
{# Вместо этого в department_detail.html: #}

{% block extra_js %}
<script type="module">
  import { TeamWheel } from '{% static "js/components/teamWheel.js" %}';
  new TeamWheel('teamWheel');
</script>
{% endblock %}
```

**Критерий завершения**:
- Все компоненты содержат только HTML ✅
- Стили в `static/css/pages/department-detail.css` ✅
- Скрипты в `static/js/components/teamWheel.js` ✅
- Страница отдела работает идентично ✅
- Git commit: "refactor: finalize department page" ✅

---

### 📋 **Фаза 6: Оптимизация и финализация (1-2 часа)**

#### Задача 6.1: Оптимизация CSS

1. **Объединить похожие стили**:
   ```bash
   # Найти дублирующиеся правила
   python analyze_templates.py --mode css-duplicates
   ```

2. **Создать CSS-переменные для общих значений**:
   ```css
   /* static/css/variables.css */
   :root {
     --feed-radius: 18px;
     --feed-shadow: 0 2px 8px rgba(0,0,0,0.08);
     --sidebar-width: 260px;
     --navbar-height: 60px;
     --transition-speed: 0.2s;
   }
   ```

3. **Минифицировать CSS для продакшена**:
   ```bash
   pip install rcssmin
   python manage.py collectstatic --clear
   ```

**Критерий завершения**:
- CSS переменные используются везде ✅
- Размер CSS файлов уменьшен на 15-20% ✅
- Git commit: "refactor: optimize CSS with variables" ✅

---

#### Задача 6.2: Оптимизация JavaScript

1. **Создать единую точку входа** для общих модулей:
   ```javascript
   // static/js/main.js
   import { esc, norm } from './utils/stringUtils.js';
   import { debounce, throttle } from './utils/timing.js';
   import { smoothScrollTo } from './utils/scroll.js';
   
   // Экспортируем в window для обратной совместимости
   window.utils = { esc, norm, debounce, throttle, smoothScrollTo };
   ```

2. **Использовать в base.html**:
   ```django
   <script type="module" src="{% static 'js/main.js' %}"></script>
   ```

3. **Минифицировать JS для продакшена**:
   ```bash
   pip install rjsmin
   # Или использовать webpack/vite
   ```

**Критерий завершения**:
- Все общие утилиты загружаются один раз ✅
- Размер JS файлов уменьшен на 20-30% ✅
- Git commit: "refactor: optimize JS modules" ✅

---

#### Задача 6.3: Документация и финальная проверка

1. **Создать** `templates/README.md`:
   ```markdown
   # Структура шаблонов EUSRR
   
   ## Архитектура
   - `base.html` - базовый layout
   - `includes/` - переиспользуемые компоненты
   - `employees/components/` - компоненты страниц сотрудников
   - `documents/components/` - компоненты документов
   
   ## Подключение стилей
   Все компоненты используют `{% block extra_css %}` для подключения стилей из `static/css/`.
   
   ## Подключение скриптов
   Все компоненты используют `{% block extra_js %}` с ES6 модулями.
   ```

2. **Создать** `static/css/README.md`:
   ```markdown
   # CSS структура
   
   ## Файлы
   - `components/` - переиспользуемые компоненты (cards, modals, ios-search)
   - `pages/` - стили специфичных страниц
   - `variables.css` - CSS переменные
   
   ## Использование
   ```django
   {% block extra_css %}
   <link rel="stylesheet" href="{% static 'css/components/cards.css' %}">
   {% endblock %}
   ```
   ```

3. **Создать** `static/js/README.md`:
   ```markdown
   # JavaScript структура
   
   ## Модули
   - `utils/` - общие утилиты (stringUtils, timing, scroll)
   - `components/` - компоненты (employeeForm, calendarWidget, teamWheel)
   - `main.js` - точка входа
   
   ## Использование
   ```django
   {% block extra_js %}
   <script type="module">
     import { EmployeeForm } from '{% static "js/components/employeeForm.js" %}';
     new EmployeeForm('#form');
   </script>
   {% endblock %}
   ```
   ```

4. **Финальная проверка**:
   ```bash
   # Запустить все тесты
   python manage.py test
   
   # Проверить все страницы вручную
   python manage.py runserver
   # Открыть checklist из REFACTORING_PLAN.md
   
   # Запустить анализ повторно
   python analyze_templates.py
   # Убедиться что встроенных стилей/скриптов < 5%
   ```

**Критерий завершения**:
- Документация создана ✅
- Все тесты проходят ✅
- Все страницы работают идентично ✅
- Встроенных стилей < 100 строк во всех шаблонах ✅
- Встроенных скриптов < 200 строк во всех шаблонах ✅
- Git commit: "docs: add refactoring documentation" ✅
- Git tag: `v2.0-refactored` ✅

---

## 📊 **Ожидаемые результаты**

### Метрики "до" и "после"

| Метрика | До рефакторинга | После рефакторинга | Улучшение |
|---------|----------------|-------------------|-----------|
| Встроенных CSS (строк) | 1359 | < 100 | **-93%** |
| Встроенных JS (строк) | 4522 | < 200 | **-96%** |
| Дублирующихся CSS классов | 41 | 0 | **-100%** |
| Дублирующихся JS функций | 7 | 0 | **-100%** |
| Размер base.html | 1101 строка | ~400 строк | **-64%** |
| Размер _employee_edit.html | 1391 строка | ~50 строк | **-96%** |
| Размер rightbar_calendar.html | 1130 строк | ~30 строк | **-97%** |
| Количество компонентов | 10 | 40+ | **+300%** |
| Покрытие тестами | 0% | 80%+ | **+∞** |

### Качественные улучшения

✅ **Поддерживаемость**: Легко находить и изменять компоненты  
✅ **Переиспользование**: CSS/JS классы используются многократно  
✅ **Производительность**: Браузер кеширует статические файлы  
✅ **Тестируемость**: Каждый компонент покрыт тестами  
✅ **Документированность**: Код понятен новым разработчикам  
✅ **Безопасность**: Все изменения проверены тестами  

---

## 🎯 **Чеклист финальной проверки**

Перед завершением рефакторинга проверить каждую страницу:

### Главная страница
- [ ] Лента новостей отображается
- [ ] Стили card применены
- [ ] Боковая панель календаря работает
- [ ] Поиск работает

### Страница сотрудников
- [ ] Список отображается
- [ ] iOS-поиск работает
- [ ] Фильтрация работает
- [ ] Карточки сотрудников стилизованы

### Страница отдела
- [ ] Информация отдела отображается
- [ ] Боковая панель (сайдбар) на месте
- [ ] Круг с командой крутится
- [ ] Модалки открываются

### Форма редактирования сотрудника
- [ ] Все поля отображаются
- [ ] Загрузка аватара работает
- [ ] Валидация работает
- [ ] Автодополнение навыков работает

### Страница документов
- [ ] Список документов отображается
- [ ] Фильтры работают
- [ ] Поиск работает
- [ ] Загрузка новых документов работает

### Календарь
- [ ] FullCalendar рендерится
- [ ] События загружаются
- [ ] Добавление события работает
- [ ] Легенда отображается

---

## 🚀 **План действий на следующую сессию**

**Шаг 1**: Создать инфраструктуру (Фаза 0)  
**Шаг 2**: Извлечь JavaScript утилиты (Фаза 2, Задача 2.1)  
**Шаг 3**: Извлечь ListFilter компонент (Фаза 2, Задача 2.2)  
**Шаг 4**: Извлечь CSS компоненты (Фаза 3, Задача 3.1)  
**Шаг 5**: Извлечь большие JS модули (Фаза 4, Задача 4.1)  
**Шаг 6**: Декомпозировать HTML (Фаза 5, только после Фаз 2-4)  
**Шаг 7**: Оптимизация и документация (Фаза 6)  

---

**Автор**: GitHub Copilot  
**Дата последнего обновления**: {{ now }}  
**Версия**: 3.0 (с учётом "стили/скрипты сначала")

**Цель**: Создать переиспользуемые компоненты формы

**Новая структура**:
```
employees/
  _employee_edit.html (главный файл, 100-150 строк)
  components/
    _employee_form_personal.html    (ФИО, дата рождения, пол)
    _employee_form_contact.html     (email, телефон, адрес)
    _employee_form_work.html        (должность, отдел, дата найма)
    _employee_form_avatar.html      (загрузка аватара)
    _employee_form_skills.html      (навыки)
    _employee_form_documents.html   (прикреплённые документы)
    _employee_form_actions.html     (кнопки сохранения/отмены)
```

**Действия**:
1. Создать папку `templates/employees/components/`
2. Выделить секции в отдельные файлы
3. Обновить `_employee_edit.html` на использование `{% include %}`
4. Протестировать форму редактирования

**Пример**:
```django
{# employees/_employee_edit.html #}
{% extends "base.html" %}

{% block content %}
<form method="post" enctype="multipart/form-data">
  {% csrf_token %}
  
  {% include "employees/components/_employee_form_personal.html" %}
  {% include "employees/components/_employee_form_contact.html" %}
  {% include "employees/components/_employee_form_work.html" %}
  {% include "employees/components/_employee_form_avatar.html" %}
  {% include "employees/components/_employee_form_skills.html" %}
  {% include "employees/components/_employee_form_actions.html" %}
</form>
{% endblock %}
```

**Критерий завершения**: 
- Главный файл < 200 строк ✅
- Все компоненты переиспользуемы ✅
- Форма работает идентично ✅

---

#### Задача 2.2: Разбить employees/department_detail.html (1025 строк)

**Новая структура**:
```
employees/
  department_detail.html (главный файл, 100-150 строк)
  components/
    _department_header.html         (название, руководитель, описание)
    _department_controls.html       (существует, переместить)
    _department_stats.html          (статистика: сотрудники, отделы)
    _department_members_list.html   (таблица/карточки сотрудников)
    _department_subdepts.html       (список подотделов)
    _department_feed.html           (лента отдела)
```

**Действия**:
1. Переместить `_department_controls.html` в `components/`
2. Выделить остальные секции
3. Обновить главный файл
4. Протестировать страницу отдела

---

#### Задача 2.3: Разбить includes/rightbar_calendar.html (1129 строк)

**Новая структура**:
```
includes/
  rightbar_calendar.html (главный файл, 50-100 строк)
  calendar/
    _calendar_widget.html       (виджет календаря)
    _calendar_events.html       (список событий)
    _calendar_filters.html      (фильтры)
    _calendar_quick_add.html    (быстрое добавление события)
```

---

#### Задача 2.4: Разбить documents/document_list.html (743 строки)

**Новая структура**:
```
documents/
  document_list.html (главный файл, 100-150 строк)
  components/
    _document_filters.html      (панель фильтров)
    _document_card.html         (карточка документа)
    _document_ack_modal.html    (модалка подтверждения)
    _document_upload_modal.html (модалка загрузки)
```

---

#### Задача 2.5: Разбить requests_app/request_list_full.html (788 строк)

**Новая структура**:
```
requests_app/
  request_list_full.html (главный файл, 100 строк)
  components/
    _request_filters.html       (фильтры)
    _request_card.html          (карточка заявления)
    _recipient_picker.html      (виджет выбора получателей)
    _document_list_inline.html  (встроенный список документов)
```

---

### 📋 **Фаза 3: Унификация стилей (2-3 часа)**

#### Задача 3.1: Создать общие CSS компоненты

**Действия**:

1. **Создать** `static/css/components/`:
   ```
   static/css/components/
     feed.css          (стили для лент)
     cards.css         (карточки)
     modals.css        (модалки iOS-стиль)
     badges.css        (бейджи статусов)
     buttons.css       (кнопки)
     forms.css         (формы)
   ```

2. **Извлечь повторяющиеся стили**:
   - Найти все `.card-list` определения
   - Консолидировать в `feed.css`
   - Удалить из шаблонов

3. **Подключить в base.html**:
   ```django
   <link rel="stylesheet" href="{% static 'css/components/feed.css' %}">
   <link rel="stylesheet" href="{% static 'css/components/modals.css' %}">
   ...
   ```

4. **Удалить дублирование** из шаблонов

**Критерий завершения**: 
- Каждый стиль определён в одном месте ✅
- Общий CSS сокращён на 30-40% ✅

---

#### Задача 3.2: Стандартизация классов

**Текущие проблемы**:
- `.card` vs `.card` vs `.req-row`
- `.card-icon` vs `.avatar` vs `.rp-avatar`
- `.badge-status` vs `.badge-acked` vs custom badges

**Стандарт**:
```css
/* Карточки */
.card-feed         /* Карточка в ленте */
.card-request      /* Карточка заявления */
.card-document     /* Карточка документа */

/* Аватары */
.avatar            /* Базовый аватар */
.avatar-sm         /* Маленький 28px */
.avatar-md         /* Средний 44px */
.avatar-lg         /* Большой 64px */

/* Бейджи */
.badge-status      /* Базовый бейдж статуса */
.badge-pending     /* На рассмотрении */
.badge-approved    /* Одобрено */
.badge-rejected    /* Отклонено */
```

---

### 📋 **Фаза 4: Оптимизация компонентов (2-3 часа)**

#### Задача 4.1: Унификация партиалов

**Текущие партиалы**:
- `feed/includes/_post_card.html` (63 строки)
- `feed/_feed_cards.html` (281 строка)
- `employees/_department_controls.html` (626 строк!)
- `employees/_employee_edit.html` (будет разбит в Фазе 2)
- `requests_app/_status_badge.html` (14 строк)

**Действия**:
1. Переместить все в `{app}/components/`
2. Стандартизировать именование (без префикса `_`)
3. Документировать использование

**Новая структура**:
```
feed/
  components/
    post_card.html
    feed_cards.html

employees/
  components/
    department_controls.html
    employee_form_*.html

requests_app/
  components/
    status_badge.html
    request_card.html
```

---

#### Задача 4.2: Создать переиспользуемые компоненты

**Новые универсальные компоненты**:

1. **Avatar Component** (`includes/components/avatar.html`):
   ```django
   {% load static %}
   <div class="avatar avatar-{{ size|default:'md' }}" 
        title="{{ user.get_full_name }}">
     {% if user.avatar %}
       <img src="{{ user.avatar.url }}" alt="{{ user.get_short_name }}">
     {% else %}
       <i class="bi-person"></i>
     {% endif %}
   </div>
   ```
   Использование: `{% include "includes/components/avatar.html" with user=employee size="lg" %}`

2. **Status Badge Component** (`includes/components/status_badge.html`):
   ```django
   <span class="badge badge-status badge-{{ status }}">
     {{ status_text|default:status|title }}
   </span>
   ```

3. **Confirm Modal Component** (`includes/components/confirm_modal.html`):
   ```django
   <div class="ios-overlay" role="dialog">
     <div class="ios-sheet">
       <h1>{{ title }}</h1>
       <p>{{ message }}</p>
       <form method="post">
         {% csrf_token %}
         <button type="submit" class="btn btn-danger">{{ confirm_text }}</button>
         <a href="javascript:history.back()">{{ cancel_text }}</a>
       </form>
     </div>
   </div>
   ```

---

### 📋 **Фаза 5: Документация и тестирование (1-2 часа)**

#### Задача 5.1: Создать TEMPLATES_GUIDE.md

**Содержание**:
```markdown
# Руководство по шаблонам EUSRR

## Структура проекта

### Приложения
- admin/ - административные override шаблоны
- auth/ - авторизация, регистрация
- communications/ - чаты
- documents/ - документы
- emails/ - email-шаблоны
- employees/ - сотрудники, отделы
- feed/ - лента новостей
- includes/ - общие компоненты
- requests_app/ - заявления сотрудников
- search/ - поиск

### Именование файлов
- `{model}_list.html` - списки
- `{model}_detail.html` - детальные страницы
- `{model}_form.html` - формы создания/редактирования
- `{model}_confirm_delete.html` - подтверждение удаления
- `components/{name}.html` - переиспользуемые компоненты

### Использование компонентов

#### Avatar
```django
{% include "includes/components/avatar.html" with user=employee size="lg" %}
```

#### Status Badge
```django
{% include "includes/components/status_badge.html" with status="approved" %}
```

## Лучшие практики
1. Все переиспользуемые блоки → в components/
2. Стили > 50 строк → в static/css/components/
3. JavaScript > 100 строк → в static/js/
4. Всегда использовать {% load static %}
5. Всегда использовать {% csrf_token %} в формах
```

---

#### Задача 5.2: Создать тесты для шаблонов

**tests/test_templates.py**:
```python
import os
from django.test import TestCase
from django.template import TemplateDoesNotExist
from django.template.loader import get_template

class TemplateStructureTests(TestCase):
    """Проверяем, что все шаблоны существуют и правильно структурированы"""
    
    def test_no_duplicate_folders(self):
        """Проверка отсутствия дублирующих папок"""
        templates_dir = "templates"
        folders = os.listdir(templates_dir)
        # Не должно быть requests/ если есть requests_app/
        self.assertNotIn("requests", folders)
    
    def test_partials_in_components(self):
        """Все партиалы должны быть в папках components/"""
        # TODO: реализовать проверку
    
    def test_templates_render(self):
        """Базовая проверка рендеринга основных шаблонов"""
        templates = [
            "base.html",
            "auth/login.html",
            "employees/employees_list.html",
            "feed/feed_list.html",
        ]
        for template_path in templates:
            try:
                template = get_template(template_path)
                self.assertIsNotNone(template)
            except TemplateDoesNotExist:
                self.fail(f"Template {template_path} not found")
```

---

## Чеклист выполнения

### ✅ Фаза 1: Устранение дубликатов (ЗАВЕРШЕНА 28.10.2025)
- [x] Удалить `auth/logout_confirm.html` ✅
- [x] Удалить `auth/password_reset_form.html` ✅
- [x] Переместить `requests/request_list.html` → `requests_app/request_list_full.html` ✅
- [x] Обновить импорт в `requests_app/views_front.py` ✅
- [x] Удалить папку `requests/` ✅
- [x] Запустить тесты ✅

**Результаты Фазы 1:**
- Удалено файлов: 3 (logout_confirm.html, password_reset_form.html, + папка requests/)
- Перемещено файлов: 1 (request_list.html → request_list_full.html)
- Обновлено view: 1 (requests_app/views_front.py)
- Файлов было: 61 → стало: 56 HTML файлов
- Строк кода удалено: ~40 строк
- Время выполнения: ~15 минут
- Статус: ✅ **УСПЕШНО ЗАВЕРШЕНО**

### ⏳ Фаза 2: Декомпозиция
- [ ] Разбить `employees/_employee_edit.html` (1391 → ~150 строк)
- [ ] Разбить `employees/department_detail.html` (1025 → ~150 строк)
- [ ] Разбить `includes/rightbar_calendar.html` (1129 → ~100 строк)
- [ ] Разбить `documents/document_list.html` (743 → ~150 строк)
- [ ] Разбить `requests_app/request_list_full.html` (788 → ~100 строк)
- [ ] Протестировать все разбитые шаблоны

### ⏳ Фаза 3: Унификация стилей
- [ ] Создать `static/css/components/feed.css`
- [ ] Создать `static/css/components/modals.css`
- [ ] Создать `static/css/components/badges.css`
- [ ] Создать `static/css/components/cards.css`
- [ ] Извлечь дублирующие стили из шаблонов
- [ ] Подключить в base.html
- [ ] Стандартизировать классы CSS

### ⏳ Фаза 4: Оптимизация компонентов
- [ ] Переместить партиалы в `{app}/components/`
- [ ] Создать `includes/components/avatar.html`
- [ ] Создать `includes/components/status_badge.html`
- [ ] Создать `includes/components/confirm_modal.html`
- [ ] Обновить все использования компонентов

### ⏳ Фаза 5: Документация
- [ ] Создать `TEMPLATES_GUIDE.md`
- [ ] Создать `tests/test_templates.py`
- [ ] Запустить полное тестирование
- [ ] Создать changelog рефакторинга

---

## Метрики успеха

**До рефакторинга**:
- Файлов: 61
- Строк кода: 11,479
- Дублирование: 3 файла
- Файлов > 500 строк: 6
- Файлов > 1000 строк: 3

**После рефакторинга (ожидается)**:
- Файлов: ~80-90 (за счёт компонентов)
- Строк кода: ~10,000-10,500 (сокращение дублирования)
- Дублирование: 0 файлов ✅
- Файлов > 500 строк: 0 ✅
- Файлов > 1000 строк: 0 ✅
- Общие CSS компоненты: 5-6 файлов
- Переиспользуемых компонентов: 15-20

**KPI**:
- ✅ Сокращение кода на 10-15%
- ✅ Устранение всех дубликатов
- ✅ Все файлы < 500 строк
- ✅ 100% покрытие тестами рендеринга
- ✅ Документация для разработчиков

---

## Риски и митигация

### Риск 1: Поломка существующих view
**Вероятность**: Средняя  
**Влияние**: Высокое  
**Митигация**: 
- Перед изменениями: grep всех использований шаблона
- После изменений: запуск всех тестов
- Ручная проверка каждого view через браузер

### Риск 2: CSS конфликты после унификации
**Вероятность**: Средняя  
**Влияние**: Среднее  
**Митигация**:
- Использовать специфичные имена классов
- Тестировать на всех страницах
- Версионировать CSS (добавить `?v=2.0`)

### Риск 3: Потеря функциональности при разбиении
**Вероятность**: Низкая  
**Влияние**: Высокое  
**Митигация**:
- Разбивать поэтапно (по одному файлу)
- Сравнивать рендер до/после
- Юнит-тесты для компонентов

---

## Временная оценка

| Фаза | Задачи | Время | Сложность |
|------|--------|-------|-----------|
| **1. Дубликаты** | 2 задачи | 1-2 часа | 🟢 Низкая |
| **2. Декомпозиция** | 5 задач | 3-4 часа | 🟡 Средняя |
| **3. Стили** | 2 задачи | 2-3 часа | 🟡 Средняя |
| **4. Компоненты** | 2 задачи | 2-3 часа | 🟡 Средняя |
| **5. Документация** | 2 задачи | 1-2 часа | 🟢 Низкая |
| **ИТОГО** | **13 задач** | **9-14 часов** | - |

**Рекомендация**: Выполнять поэтапно с коммитами после каждой фазы.

---

## Порядок выполнения (рекомендуемый)

### День 1 (4-5 часов):
1. ✅ Фаза 1 (дубликаты) - 1-2 часа
2. ✅ Фаза 2.1 (employees/_employee_edit) - 1.5-2 часа
3. ✅ Коммит + тестирование - 0.5 часа

### День 2 (4-5 часов):
1. ✅ Фаза 2.2-2.3 (department_detail, rightbar_calendar) - 2-3 часа
2. ✅ Фаза 3.1 (CSS компоненты) - 1.5-2 часа
3. ✅ Коммит + тестирование - 0.5 часа

### День 3 (3-4 часа):
1. ✅ Фаза 2.4-2.5 (documents, requests) - 1.5-2 часа
2. ✅ Фаза 4 (компоненты) - 1-1.5 часа
3. ✅ Коммит + тестирование - 0.5 часа

### День 4 (1-2 часа):
1. ✅ Фаза 5 (документация) - 1-1.5 часа
2. ✅ Финальное тестирование - 0.5 часа
3. ✅ Финальный коммит

---

## Заключение

Этот рефакторинг позволит:
- ✅ Устранить технический долг (дубликаты, гигантские файлы)
- ✅ Упростить поддержку (переиспользуемые компоненты)
- ✅ Ускорить разработку (готовые компоненты)
- ✅ Улучшить читаемость (чёткая структура)
- ✅ Снизить риски (документация + тесты)

**Приоритет**: 🔴 **ВЫСОКИЙ** (технический долг накоплен)  
**Сложность**: 🟡 **СРЕДНЯЯ** (требует внимательности)  
**ROI**: 🟢 **ВЫСОКИЙ** (долгосрочная выгода)
