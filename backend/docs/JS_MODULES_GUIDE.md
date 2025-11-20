# 📘 Руководство по JavaScript модулям EUSRR

**Версия**: 1.0  
**Дата**: 4 ноября 2025 г.

---

## 📚 Содержание

1. [Обзор архитектуры](#обзор-архитектуры)
2. [Утилиты (utils)](#утилиты)
3. [Компоненты (components)](#компоненты)
4. [Примеры использования](#примеры-использования)
5. [Best Practices](#best-practices)

---

## 🏗️ Обзор архитектуры

### Структура файлов

```
static/js/
├── utils/                      # Утилитарные функции
│   ├── stringUtils.js         # Работа со строками
│   ├── timing.js              # Debounce, throttle, delay
│   └── scroll.js              # Управление скроллом
└── components/                 # Переиспользуемые компоненты
    ├── calendarWidget.js      # Виджет календаря
    ├── deptRoleEditor.js      # Редактор ролей отделов
    ├── employeeFormHandler.js # Форма сотрудника
    ├── employeeGroupsManager.js # Группы сотрудника
    ├── groupPickers.js        # Выбор групп должностей
    ├── headPicker.js          # Autocomplete руководителя
    ├── likeHandler.js         # Обработчик лайков
    ├── listFilter.js          # Фильтрация списков
    ├── navbarHeight.js        # CSS переменная navbar
    ├── positionManager.js     # Управление должностями
    ├── roleManager.js         # Управление ролями
    ├── skillsManager.js       # Управление навыками
    ├── teamWheel.js           # Колесо команды
    ├── textareaAutogrow.js    # Автоувеличение textarea
    └── index.js               # Экспорт всех компонентов
```

---

## 🛠️ Утилиты

### `stringUtils.js`

Утилиты для работы со строками и HTML.

#### `esc(s: string): string`
Экранирует HTML-символы для безопасного вывода.

```javascript
import { esc } from '{% static "js/utils/stringUtils.js" %}';

const userInput = '<script>alert("xss")</script>';
const safe = esc(userInput);
// => '&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt;'
```

#### `norm(s: string): string`
Нормализует строку для поиска (lowercase, trim).

```javascript
import { norm } from '{% static "js/utils/stringUtils.js" %}';

const search = norm('  Hello World  ');
// => 'hello world'
```

#### `escAttr(s: string): string`
Экранирует строку для использования в атрибутах.

```javascript
const attr = escAttr('some "quoted" text');
// => 'some &quot;quoted&quot; text'
```

#### `truncate(s: string, maxLen: number): string`
Обрезает строку до указанной длины с добавлением "...".

```javascript
const short = truncate('Very long text here', 10);
// => 'Very lon...'
```

#### `getInitials(name: string): string`
Получает инициалы из имени.

```javascript
const initials = getInitials('Иван Петрович Сидоров');
// => 'ИПС'
```

---

### `timing.js`

Утилиты для управления временем выполнения.

#### `debounce(fn: Function, ms: number): Function`
Откладывает выполнение функции до прекращения вызовов.

```javascript
import { debounce } from '{% static "js/utils/timing.js" %}';

const search = debounce((query) => {
  console.log('Searching for:', query);
}, 300);

input.addEventListener('input', (e) => search(e.target.value));
```

#### `throttle(fn: Function, ms: number): Function`
Ограничивает частоту вызова функции.

```javascript
import { throttle } from '{% static "js/utils/timing.js" %}';

const onScroll = throttle(() => {
  console.log('Scroll position:', window.scrollY);
}, 100);

window.addEventListener('scroll', onScroll);
```

#### `delay(ms: number): Promise<void>`
Промисифицированная задержка.

```javascript
import { delay } from '{% static "js/utils/timing.js" %}';

async function animateSequence() {
  element.classList.add('step1');
  await delay(300);
  element.classList.add('step2');
  await delay(300);
  element.classList.add('complete');
}
```

---

### `scroll.js`

Утилиты для управления скроллом.

#### `smoothScrollTo(element: HTMLElement, options?: Object): void`
Плавно прокручивает к элементу.

```javascript
import { smoothScrollTo } from '{% static "js/utils/scroll.js" %}';

const target = document.getElementById('section');
smoothScrollTo(target, {
  offset: 80,      // Отступ сверху
  duration: 500    // Длительность анимации
});
```

#### `scrollToTop(duration: number = 300): void`
Плавно прокручивает страницу наверх.

```javascript
button.addEventListener('click', () => scrollToTop(500));
```

#### `isElementInViewport(el: HTMLElement): boolean`
Проверяет, виден ли элемент в окне просмотра.

```javascript
if (isElementInViewport(element)) {
  element.classList.add('animate');
}
```

---

## 🎨 Компоненты

### `navbarHeight.js`

Устанавливает CSS-переменную с высотой навбара.

#### API

```javascript
import { initNavbarHeight } from '{% static "js/components/navbarHeight.js" %}';

const navbarHeight = initNavbarHeight();
// Автоматически создаёт CSS переменную --navbar-height
```

**Использование в CSS:**
```css
.content {
  margin-top: var(--navbar-height);
}
```

---

### `likeHandler.js`

Глобальный обработчик лайков для постов и комментариев.

#### API

```javascript
import { initLikeHandler } from '{% static "js/components/likeHandler.js" %}';

const likeHandler = initLikeHandler({
  postUrl: '/api/v1/feed/posts/{id}/like/',
  commentUrl: '/api/v1/feed/comments/{id}/like/'
});
```

#### HTML разметка

```django
<button class="like-btn" 
        data-post-id="{{ post.id }}"
        data-liked="{% if post.i_liked %}1{% endif %}">
  <i class="bi-heart{% if post.i_liked %}-fill{% endif %}"></i>
  <span class="like-count">{{ post.likes_count }}</span>
</button>
```

#### Возвращаемый API

- `refresh()` - переинициализация обработчиков

---

### `textareaAutogrow.js`

Автоматически увеличивает высоту textarea при вводе текста.

#### API

```javascript
import { initTextareaAutogrow } from '{% static "js/components/textareaAutogrow.js" %}';

const autogrow = initTextareaAutogrow({
  selector: '[data-autogrow]',
  minHeight: 40,
  maxHeight: 300
});
```

#### HTML разметка

```html
<textarea data-autogrow 
          data-max-height="200" 
          placeholder="Введите текст..."></textarea>
```

#### Возвращаемый API

- `refresh()` - переинициализация для новых элементов
- `destroy()` - отключение обработчиков

---

### `employeeFormHandler.js`

Управляет формой сотрудника (валидация, изменения, AJAX).

#### API

```javascript
import { initEmployeeForm } from '{% static "js/components/employeeFormHandler.js" %}';

const employeeForm = initEmployeeForm();
```

#### Возможности

- ✅ Отслеживание изменений полей
- ✅ Валидация перед отправкой
- ✅ Предупреждение о несохранённых изменениях
- ✅ AJAX отправка формы
- ✅ Обработка ошибок

#### Возвращаемый API

- `hasChanges()` - проверка наличия изменений
- `resetTracking()` - сброс отслеживания
- `validateForm()` - валидация формы
- `isDirty` - флаг изменений

---

### `positionManager.js`

Управляет CRUD операциями с должностями через модальные окна.

#### API

```javascript
import { initPositionManager } from '{% static "js/components/positionManager.js" %}';

const positionMgr = initPositionManager();
```

#### HTML требования

- `#positionBlock[data-update-url-tpl]` - шаблон URL обновления
- `#positionBlock[data-detail-url-tpl]` - шаблон URL получения
- `#positionBlock[data-create-url]` - URL создания
- Модалы: `#posEditModal`, `#posCreateModal`

#### Возвращаемый API

- `refresh()` - переинициализация
- `openCreateModal()` - открыть модал создания
- `openEditModal(positionId)` - открыть модал редактирования

---

### `groupPickers.js`

Пикеры для выбора групп должностей (создание и редактирование).

#### API

```javascript
import { 
  initPositionGroupPicker, 
  initPositionEditGroupPicker 
} from '{% static "js/components/groupPickers.js" %}';

// Для формы создания должности
const createPicker = initPositionGroupPicker();

// Для формы редактирования должности
const editPicker = initPositionEditGroupPicker();
```

#### Возможности

- ✅ Выбор нескольких групп
- ✅ Отображение чипов выбранных групп
- ✅ Поиск по группам
- ✅ Синхронизация с hidden input'ами

---

### `employeeGroupsManager.js`

Управляет персональными группами прав сотрудника.

#### API

```javascript
import { initEmployeeGroupsManager } from '{% static "js/components/employeeGroupsManager.js" %}';

const groupsMgr = initEmployeeGroupsManager();
```

#### HTML требования

- `#empGroupsAssignBtn` - кнопка назначения групп
- `#empGroupsList` - список текущих групп
- `#empGroupsModal` - модал выбора групп

#### Возвращаемый API

- `refresh()` - обновление списка
- `assignGroups(groupIds)` - назначить группы
- `removeGroup(groupId)` - удалить группу

---

### `skillsManager.js`

Управляет навыками сотрудника (добавление/удаление через AJAX).

#### API

```javascript
import { initSkillsManager } from '{% static "js/components/skillsManager.js" %}';

const skillsManager = initSkillsManager({
  blockId: 'skillsBlock',
  formId: 'skillAddForm',
  collapseId: 'skillsForm',
  removeUrl: '/employees/1/skills/remove/'
});
```

#### Возможности

- ✅ AJAX добавление навыков
- ✅ AJAX удаление по клику на чип
- ✅ Анимация добавления/удаления
- ✅ Валидация дубликатов

#### Возвращаемый API

- `addSkill(name)` - добавить навык (возвращает Promise)
- `refresh()` - переинициализация

---

### `deptRoleEditor.js`

Редактор роли сотрудника в отделе с валидацией изменений.

#### API

```javascript
import { initDeptRoleEditor } from '{% static "js/components/deptRoleEditor.js" %}';

const deptRoleEditor = initDeptRoleEditor();
```

#### HTML разметка

```html
<div data-dept-role-editor>
  <select name="role">...</select>
  <button data-role-ok disabled>OK</button>
</div>
```

#### Возможности

- ✅ Активация кнопки OK только при изменении
- ✅ Инициализация tooltip'ов
- ✅ Множественные экземпляры на странице

#### Возвращаемый API

- `instances` - массив всех редакторов
- `refresh()` - переинициализация

---

### `headPicker.js`

Autocomplete для выбора руководителя отдела по имени или email.

#### API

```javascript
import { initHeadPicker } from '{% static "js/components/headPicker.js" %}';

const headPicker = initHeadPicker({
  selector: '[data-head-picker]'
});
```

#### HTML требования

```html
<div data-head-picker data-choices='[{"id":1,"name":"Иван","email":"ivan@mail.ru"}]'>
  <input type="text" class="form-control" placeholder="Имя или email">
  <input type="hidden" name="head_id">
  <div class="dropdown-menu"></div>
</div>
```

#### Возможности

- ✅ Поиск по имени и email
- ✅ Валидация выбора при submit
- ✅ Автозаполнение при загрузке
- ✅ Клавиатурная навигация (Enter, Escape)

---

### `roleManager.js`

Управление ролями и правами отделов (создание, редактирование, удаление).

#### API

```javascript
import { initRoleManager } from '{% static "js/components/roleManager.js" %}';

const roleManager = initRoleManager();
```

#### Возможности

- ✅ Autocomplete выбора роли
- ✅ Управление правами через чипы
- ✅ Создание новой роли
- ✅ Редактирование существующей роли
- ✅ Удаление роли с подтверждением
- ✅ Модалы с выбором прав (permissions)

#### Возвращаемый API

- `refresh()` - переинициализация
- `getSelectedRole()` - получить выбранную роль
- `getEditPermissions()` - получить выбранные права редактирования
- `getCreatePermissions()` - получить выбранные права создания

---

### `calendarWidget.js`

Полнофункциональный виджет календаря с FullCalendar.js.

#### API

```javascript
import { initCalendarWidget } from '{% static "js/components/calendarWidget.js" %}';

const widget = initCalendarWidget();
```

#### Возможности

- ✅ Отображение событий
- ✅ Создание новых событий
- ✅ Редактирование событий
- ✅ Drag & drop событий
- ✅ Интеграция с модалами
- ✅ AJAX сохранение

---

### `teamWheel.js`

Анимированное колесо команды отдела с автоскроллом.

#### API

```javascript
import { initTeamWheel } from '{% static "js/components/teamWheel.js" %}';

const wheel = initTeamWheel({
  wheelId: 'teamWheel-1',
  dataSourceId: 'teamData-1',
  fallback: {
    avatar: '/static/img/default-avatar.png',
    name: 'Руководитель',
    role: 'Руководитель отдела'
  }
});
```

#### Возвращаемый API

- `start()` - запустить автоскролл
- `stop()` - остановить автоскролл
- `next()` - следующий участник
- `prev()` - предыдущий участник

---

### `listFilter.js`

Универсальный компонент фильтрации списков.

#### API

```javascript
import { ListFilter, createDataAttrMatcher } from '{% static "js/components/listFilter.js" %}';

new ListFilter({
  listSelector: '#empList',
  itemSelector: '.emp-row',
  searchInputSelector: '#empFilter',
  clearButtonSelector: '.ios-search-clear',
  matchFn: createDataAttrMatcher(['name', 'depts']),
  debounceMs: 300
});
```

#### Возможности

- ✅ Debounced поиск
- ✅ Кастомная функция сопоставления
- ✅ Подсчёт результатов
- ✅ Кнопка очистки
- ✅ Клавиатурные события

---

## 💡 Примеры использования

### Пример 1: Базовая инициализация в шаблоне

```django
{% load static %}
<script type="module">
  import { initEmployeeForm } from '{% static "js/components/employeeFormHandler.js" %}';
  
  document.addEventListener('DOMContentLoaded', () => {
    const form = initEmployeeForm();
    
    if (form) {
      console.log('Форма инициализирована');
      window.employeeForm = form; // Для отладки
    }
  });
</script>
```

### Пример 2: Множественная инициализация

```django
<script type="module">
  import { initSkillsManager } from '{% static "js/components/skillsManager.js" %}';
  import { initDeptRoleEditor } from '{% static "js/components/deptRoleEditor.js" %}';
  import { smoothScrollTo } from '{% static "js/utils/scroll.js" %}';

  document.addEventListener('DOMContentLoaded', () => {
    const skills = initSkillsManager({ blockId: 'skillsBlock' });
    const roles = initDeptRoleEditor();
    
    // Скролл к форме на мобильных
    const editWrap = document.getElementById('editFormWrap');
    if (editWrap) {
      editWrap.addEventListener('shown.bs.collapse', () => {
        if (window.innerWidth < 768) {
          smoothScrollTo(editWrap, { offset: 80 });
        }
      });
    }
  });
</script>
```

### Пример 3: Работа с API модуля

```javascript
import { initEmployeeForm } from '/static/js/components/employeeFormHandler.js';

const form = initEmployeeForm();

// Проверка изменений перед уходом со страницы
window.addEventListener('beforeunload', (e) => {
  if (form && form.hasChanges()) {
    e.preventDefault();
    e.returnValue = 'У вас есть несохранённые изменения';
  }
});

// Программная отправка формы
document.getElementById('customSaveBtn').addEventListener('click', async () => {
  if (form && form.validateForm()) {
    try {
      await form.submit();
      alert('Сохранено!');
    } catch (error) {
      alert('Ошибка: ' + error.message);
    }
  }
});
```

---

## ✅ Best Practices

### 1. Всегда проверяйте возвращаемое значение

```javascript
const component = initSomeComponent();
if (component) {
  // Компонент успешно инициализирован
  component.doSomething();
} else {
  // Необходимые элементы не найдены
  console.warn('Component not initialized');
}
```

### 2. Используйте DOMContentLoaded

```javascript
document.addEventListener('DOMContentLoaded', () => {
  // Инициализация после загрузки DOM
  initAllComponents();
});
```

### 3. Экспортируйте в window для отладки

```javascript
const component = initComponent();
if (component) {
  window.debugComponent = component; // Доступ из консоли
}
```

### 4. Группируйте импорты

```javascript
// Utils
import { esc, norm } from '{% static "js/utils/stringUtils.js" %}';
import { debounce } from '{% static "js/utils/timing.js" %}';

// Components
import { initEmployeeForm } from '{% static "js/components/employeeFormHandler.js" %}';
import { initPositionManager } from '{% static "js/components/positionManager.js" %}';
```

### 5. Используйте деструктуризацию

```javascript
// ✅ Хорошо
import { initComponent } from './component.js';

// ❌ Плохо
import * as Component from './component.js';
const init = Component.initComponent;
```

### 6. Обрабатывайте ошибки

```javascript
try {
  const result = await component.someAsyncOperation();
  handleSuccess(result);
} catch (error) {
  console.error('Operation failed:', error);
  handleError(error);
}
```

### 7. Очищайте ресурсы

```javascript
// Если модуль возвращает destroy()
const component = initComponent();

// При удалении со страницы
function cleanup() {
  if (component && component.destroy) {
    component.destroy();
  }
}
```

---

## 🔧 Отладка

### Доступ к компонентам из консоли

Все инициализированные компоненты доступны через `window`:

```javascript
// В консоли браузера
window.employeeForm.hasChanges()  // true/false
window.positionManager.refresh()   // переинициализация
window.likeHandler                 // объект API
```

### Логирование

Модули используют `console.warn()` для предупреждений:

```javascript
// Если элементы не найдены
console.warn('EmployeeForm: required elements not found');
```

### Проверка инициализации

```javascript
// Проверить, был ли модуль инициализирован
if (window.__employeeFormInitialized) {
  console.log('EmployeeForm already initialized');
}
```

---

## 📞 Поддержка

При возникновении вопросов:
1. Проверьте JSDoc в исходном коде модуля
2. Изучите примеры использования в шаблонах
3. Проверьте консоль браузера на предупреждения
4. Используйте `window.componentName` для отладки

---

**Дата актуализации**: 4 ноября 2025 г.  
**Версия**: 1.0
