# Card List Refactoring - Универсализация стилей карточек

## Что изменилось

### Переименование файла CSS
- **Было**: `cards.css` (название специфично для новостей)
- **Стало**: `card-list.css` (универсальное название)

### Назначение
Файл `card-list.css` теперь официально документирован как **универсальный компонент** для любых типов списков:
- ✅ Новости (feed)
- ✅ Заявления (requests)
- ✅ Документы (documents)
- ✅ Сотрудники (employees)
- ✅ Отделы (departments)
- ✅ Чаты (communications)
- ✅ Результаты поиска (search)

### Классы остались без изменений
Классы `feed-*` сохранены для обратной совместимости:
- `.card` - контейнер карточки
- `.card-header` - шапка карточки
- `.card-icon` - аватар/иконка
- `.card-meta` - метаинформация
- `.card-title` - автор/заголовок
- `.card-subtitle` - дополнительная информация
- `.card-body` - тело карточки
- `.card-actions` - кнопки действий
- `.card-list` - контейнер потока карточек

**Примечание**: `feed` здесь означает "поток данных" (data feed), что подходит для любых списков контента.

## Изменения в файлах

### HTML шаблоны (10 файлов)
Обновлен импорт CSS:
```diff
- <link rel="stylesheet" href="{% static 'css/components/cards.css' %}">
+ <link rel="stylesheet" href="{% static 'css/components/card-list.css' %}">
```

**Затронутые файлы**:
- `base.html`
- `feed/feed_list.html`
- `requests_app/request_list_full.html`
- `documents/document_list.html`
- `communications/chat_list.html`
- `search/results.html`
- `employees/employees_list.html`
- `employees/employees_list_NEW_EXAMPLE.html`
- `employees/department_list.html`

### CSS файлы
Обновлены ссылки и зависимости:
- `components/index.css` - изменен импорт
- `components/request-list.css` - обновлены комментарии
- `components/document-list.css` - обновлены комментарии
- `components/list-view.css` - обновлены комментарии

### Документация
- `static/css/README.md` - полностью обновлена секция о card-list.css
- `docs/CARD_LIST_REFACTORING.md` - создан этот документ

## Преимущества изменений

1. **Семантика**: Название файла `card-list.css` точно отражает его назначение
2. **Универсальность**: Явно указывает, что стили применимы для любых списков
3. **Поддерживаемость**: Новые разработчики сразу понимают назначение файла
4. **Обратная совместимость**: Классы не изменились, весь существующий код работает

## Миграция проекта

### Что НЕ требуется менять
- ❌ HTML классы (`card`, `card-header`, и т.д.) - оставить как есть
- ❌ JavaScript селекторы - работают без изменений
- ❌ Существующие компоненты - не требуют рефакторинга

### Что нужно обновить (уже сделано)
- ✅ Импорты CSS в шаблонах
- ✅ Ссылки в других CSS файлах
- ✅ Документация

## Использование

### В новых шаблонах
```html
{% block extra_css %}
<link rel="stylesheet" href="{% static 'css/components/card-list.css' %}">
{% endblock %}
```

### В новых компонентах
```html
<div class="card mb-3">
  <header class="card-header">
    <div class="card-icon">
      <i class="bi-icon-name"></i>
    </div>
    <div class="card-meta">
      <div class="card-title">Заголовок</div>
      <div class="card-subtitle">Дополнительная информация</div>
    </div>
  </header>
  <div class="card-body">
    Контент карточки
  </div>
  <footer class="card-actions">
    <button class="btn btn-ghost">Действие</button>
  </footer>
</div>
```

## Дата изменений
29 ноября 2025 г.
