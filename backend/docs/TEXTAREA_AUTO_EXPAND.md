# Унификация автоматического расширения textarea

## Описание изменений

Создан универсальный модуль `textareaAutoExpand.js`, который автоматически обрабатывает расширение всех textarea с `rows="1"` в формах комментариев и сообщений по всему приложению.

## Реализация

### Новый модуль: textareaAutoExpand.js

**Путь:** `backend/static/js/components/textareaAutoExpand.js`

**Функциональность:**
- Автоматически находит все textarea с атрибутом `rows="1"` или классом `composer-textarea`
- Расширяет textarea при вводе текста до максимум 6 строк (144px)
- Использует MutationObserver для отслеживания динамически добавляемых textarea
- Работает со всеми формами комментариев: лента, заявки, модальные окна, чат

**Принцип работы:**
```javascript
// Сбрасываем высоту для корректного вычисления scrollHeight
textarea.style.height = 'auto';

// Устанавливаем новую высоту, но не больше максимальной (6 строк)
const newHeight = Math.min(textarea.scrollHeight, MAX_HEIGHT);
textarea.style.height = newHeight + 'px';
```

### Поддерживаемые селекторы

Модуль автоматически работает с:
- `.comment-form-quick textarea` - быстрые комментарии в ленте
- `.comment-form-modal textarea` - комментарии в модальном окне
- `.request-comment-form textarea` - комментарии к заявкам
- `.comment-new textarea` - новые комментарии в списке заявок
- `.composer-textarea` - поле ввода в чате
- `.message-input` - общий класс для всех полей ввода

### Условия применения

Авторасширение применяется **только** к textarea, которые удовлетворяют условию:
- Имеют атрибут `rows="1"` **ИЛИ**
- Имеют класс `composer-textarea`

Это означает, что textarea в модальных окнах редактирования (с `rows="3"` или `rows="4"`) **не будут** автоматически расширяться.

## Удалённые файлы

### 1. textareaAutogrowHandler.js
- **Причина удаления:** Использовался только в `post_form.html`, функциональность заменена универсальным модулем
- **Зависимости:** Удалён импорт из `backend/templates/feed/post_form.html`

### 2. textareaAutogrow.js
- **Причина удаления:** Требовал явного атрибута `data-autogrow`, менее универсален
- **Зависимости:** Удалён импорт из `backend/templates/base.html`

## Изменённые файлы

### 1. backend/templates/base.html
```diff
- import { initTextareaAutogrow } from '{% static "js/components/textareaAutogrow.js" %}';
+ {# Универсальный модуль для автоматического расширения textarea #}
+ <script src="{% static 'js/components/textareaAutoExpand.js' %}" defer></script>
```

Удалена инициализация:
```diff
- const textareaAutogrow = initTextareaAutogrow();
- if (textareaAutogrow) window.textareaAutogrow = textareaAutogrow;
```

### 2. backend/templates/feed/post_form.html
```diff
- import { initTextareaAutogrow } from "{% static 'js/components/textareaAutogrowHandler.js' %}";
- 
- // Автоматическое изменение размера textarea
- initTextareaAutogrow({ selector: 'form.card textarea' });
```

### 3. backend/static/js/components/chatMarkRead.js
```diff
  function autosize() {
    if (!ta) return;
-   ta.style.height = 'auto';
-   ta.style.height = Math.min(ta.scrollHeight, 6 * 24) + 'px';
+   // Авторасширение теперь обрабатывается textareaAutoExpand.js
+   // Оставляем только autoscroll логику
    if (atBottom()) autoscroll();
  }
```

### 4. backend/static/js/components/requestCommentsHandler.js
Удалена функция `initTextareaAutosize()` и её вызов:
```diff
- function initTextareaAutosize() {
-   // ... закомментированный код
- }
- 
- document.addEventListener('DOMContentLoaded', () => {
-   autoloadAllCounts();
-   initTextareaAutosize();
- });
+ document.addEventListener('DOMContentLoaded', autoloadAllCounts);
```

### 5. backend/static/scss/components/_message-inputs.scss
Удалены конфликтующие `min-height` и `max-height`, которые мешали автоматическому расширению:
```diff
  .message-input,
  .composer-textarea {
    flex: 1 1 auto;
-   min-height: 44px;
-   max-height: 260px;
    border: none !important;
    ...
  }

  .message-field--compact .message-input {
-   min-height: 32px;
    font-size: 0.95rem;
+   // min-height удален - управляется textareaAutoExpand.js
  }
```

### 6. backend/static/css/components/request-list.css
Удалены специфичные стили для `.comment-new textarea`, которые перебивали универсальное поведение:
```diff
- /* ─────────────────────────────────────────────────────────────
-    COMMENT TEXTAREA
- ────────────────────────────────────────────────────────────── */
- .comment-new textarea {
-   resize: vertical;
-   max-height: 220px;
-   min-height: 44px;
-   overflow-y: auto;
- }
```

## Преимущества новой реализации

1. **Единообразие:** Все textarea с `rows="1"` работают одинаково по всему приложению
2. **Автоматичность:** Не требует явной инициализации в каждом модуле
3. **Динамичность:** Автоматически обрабатывает textarea, добавленные через AJAX/модальные окна
4. **Простота поддержки:** Один файл вместо трёх разных реализаций
5. **Производительность:** Единая инициализация вместо множественных обработчиков

## Тестирование

Необходимо протестировать автоматическое расширение в:
- ✅ Быстрые комментарии в ленте (feed)
- ✅ Комментарии в модальном окне поста
- ✅ Комментарии к заявкам (request_detail.html)
- ✅ Комментарии в обработке заявок (request_process.html)
- ✅ Комментарии в списке заявок (request_list_full.html)
- ✅ Поле ввода в чате (composer-textarea)

**Ожидаемое поведение:**
- Начальная высота: 1 строка (~38px)
- Максимальная высота: 6 строк (144px)
- После 6 строк появляется скроллбар
- При удалении текста высота уменьшается

## Обратная совместимость

Модуль экспортирует API в `window.textareaAutoExpand`:
```javascript
window.textareaAutoExpand = {
  init: initAllTextareas,      // Пересканировать все textarea
  initTextarea: initAutoExpand, // Инициализировать конкретный textarea
  autoExpand: autoExpand        // Применить расширение к textarea
};
```

Это позволяет вручную инициализировать textarea, если требуется:
```javascript
// Пример использования
const textarea = document.querySelector('#myTextarea');
window.textareaAutoExpand.initTextarea(textarea);
```

## Дата изменения
2025-01-XX
