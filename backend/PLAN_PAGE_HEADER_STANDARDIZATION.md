# План стандартизации шапок страниц

## 📋 Обзор

Создан универсальный компонент `page_header.html` для стандартизации всех шапок страниц списков в приложении.

### Компоненты
- **HTML**: `templates/includes/components/page_header.html`
- **CSS**: `static/css/components/page-header.css`

### Особенности компонента
✅ Полупрозрачный фон с backdrop-filter (как в iOS)
✅ Sticky позиционирование (прилипает к верху при скролле)
✅ Вытянутая кнопка создания на десктопе, круглая иконка на мобильных
✅ Поиск iOS-стиль (интегрируется с существующим ios-search.css)
✅ Кнопка раскрытия фильтров (collapse toggle)
✅ Переключатель области "Мои/Все" (опционально)
✅ Адаптивная верстка (flex-wrap на мобильных)
✅ Счётчик элементов
✅ Слот для дополнительных кнопок

---

## 📊 Анализ текущих шапок

### 1. **employees_list.html** - Список сотрудников
**Текущее состояние:**
```django
<div class="feed-header d-flex align-items-center">
  <i class="bi-people fs-2 text-primary"></i>
  <h2 class="title mb-0">Сотрудники</h2>
  <span class="ms-2 small text-secondary">Всего: {{ employees|length }}</span>
  <div class="ms-auto ios-search">
    <i class="bi-search"></i>
    <input id="empFilter" type="search" ...>
  </div>
</div>
```

**Что нужно:**
- ✅ Иконка
- ✅ Заголовок
- ✅ Счётчик
- ✅ Поиск
- ❌ Кнопка создания (есть, но в отдельной карточке)
- ❌ Фильтры (нет)
- ❌ Переключатель Мои/Все (нет)
- ❌ Полупрозрачный фон

**Приоритет:** 🔴 Высокий

---

### 2. **department_list.html** - Список отделов
**Текущее состояние:**
```django
<div class="feed-header d-flex align-items-center">
  <i class="bi-diagram-3 fs-2 text-primary"></i>
  <h2 class="title mb-0">Отделы</h2>
  <span class="ms-2 small text-secondary">Всего: {{ departments|length }}</span>
  <div class="ms-auto ios-search">...</div>
</div>
```

**Что нужно:**
- ✅ Иконка
- ✅ Заголовок
- ✅ Счётчик
- ✅ Поиск
- ❌ Кнопка создания (есть, но в отдельной карточке)
- ❌ Фильтры (нет)
- ❌ Переключатель Мои/Все (нет)
- ❌ Полупрозрачный фон

**Приоритет:** 🔴 Высокий

---

### 3. **document_list.html** - Список документов
**Текущее состояние:**
```django
<div class="ios-header feed-header d-flex align-items-center gap-2 flex-wrap">
  <i class="bi-file-earmark-text fs-2 text-primary"></i>
  <h2 class="title ios-title mb-0">Документы</h2>
  <div class="ms-auto d-flex align-items-center gap-2 flex-wrap">
    <div class="btn-group scope-switch">
      <a href="{{ scope_urls.mine }}" class="btn ...">Мои</a>
      <a href="{{ scope_urls.all }}" class="btn ...">Все</a>
    </div>
    <button type="button" class="btn btn-primary d-flex align-items-center gap-2" 
            data-bs-toggle="modal" data-bs-target="#docCreateModal">
      <i class="bi-plus-lg"></i><span>Создать документ</span>
    </button>
  </div>
</div>
```

**Что нужно:**
- ✅ Иконка
- ✅ Заголовок
- ✅ Переключатель Мои/Все
- ✅ Кнопка создания (модальное окно)
- ✅ Полупрозрачный фон (.ios-header)
- ❌ Поиск (нет)
- ❌ Фильтры (нет)
- ⚠️ Кнопка НЕ вытянутая (текст всегда виден)

**Приоритет:** 🟡 Средний (почти готово)

---

### 4. **request_list_full.html** - Список заявлений
**Текущее состояние:**
```django
<div class="ios-header feed-header d-flex align-items-center gap-2 flex-wrap">
  <i class="bi-clipboard-check fs-2 text-primary"></i>
  <h2 class="title ios-title mb-0">Заявления</h2>
  <div class="ms-auto d-flex align-items-center gap-2 flex-wrap">
    <div class="btn-group scope-switch">...</div>
    <button type="button" class="btn btn-primary d-flex align-items-center gap-2"
            data-bs-toggle="modal" data-bs-target="#reqCreateModal">
      <i class="bi-plus-lg"></i><span>Новое заявление</span>
    </button>
  </div>
</div>

<!-- Фильтры в отдельном блоке ниже -->
<form class="feed-new mb-3" method="get">
  <div class="row g-2 align-items-center">
    <div class="col-12 col-sm-4">
      <select name="type" class="form-select">...</select>
    </div>
    ...
  </div>
</form>
```

**Что нужно:**
- ✅ Иконка
- ✅ Заголовок
- ✅ Переключатель Мои/Все
- ✅ Кнопка создания
- ✅ Фильтры (но не скрываемые)
- ✅ Полупрозрачный фон
- ❌ Поиск (нет)
- ❌ Кнопка toggle фильтров (фильтры всегда видны)

**Приоритет:** 🟡 Средний

---

### 5. **feed_list.html** - Лента новостей
**Текущее состояние:**
```django
<div class="feed-header d-flex align-items-center gap-3">
  <i class="bi-megaphone fs-2 text-primary"></i>
  <h2 class="title mb-0">Лента</h2>
  {% if user.is_authenticated and user.is_staff %}
    <a class="btn btn-primary ms-auto" href="{% url 'feed:post_create' %}?type=company">
      <i class="bi-plus-circle me-1"></i> Новая публикация
    </a>
  {% endif %}
</div>
```

**Что нужно:**
- ✅ Иконка
- ✅ Заголовок
- ✅ Кнопка создания (переход на другую страницу)
- ❌ Поиск (нет)
- ❌ Фильтры (нет)
- ❌ Счётчик (нет)
- ❌ Полупрозрачный фон

**Приоритет:** 🟢 Низкий (специфичная страница)

---

### 6. **chat_list.html** - Список чатов
**Текущее состояние:**
```django
<div class="feed-header d-flex align-items-center">
  <i class="bi-chat-dots fs-2 text-primary"></i>
  <h2 class="title mb-0">Мои чаты</h2>
  <div class="ms-auto ios-search">
    <i class="bi-search"></i>
    <input type="search" id="chatSearch" ...>
  </div>
</div>

<!-- Фильтры ниже -->
<div class="feed-new mb-3">
  <div class="d-flex align-items-center gap-2 flex-wrap">
    <div class="btn-group" role="group">
      <input type="radio" class="btn-check" name="chatFilter" id="fltAll" checked>
      <label class="btn btn-ghost" for="fltAll">Все</label>
      ...
    </div>
    <a href="..." class="btn btn-ghost ms-auto">
      <i class="bi-person-plus"></i> Новый чат
    </a>
  </div>
</div>
```

**Что нужно:**
- ✅ Иконка
- ✅ Заголовок
- ✅ Поиск
- ✅ Фильтры (но не скрываемые, radio buttons)
- ⚠️ Кнопка создания (но специфичная - "Новый чат")
- ❌ Счётчик (нет)
- ❌ Полупрозрачный фон

**Приоритет:** 🟡 Средний

---

### 7. **search/results.html** - Результаты поиска
**Текущее состояние:**
```django
<div class="feed-header d-flex align-items-center">
  <i class="bi-search fs-2 text-primary"></i>
  <h2 class="title mb-0">Результаты поиска</h2>
</div>
```

**Что нужно:**
- ✅ Иконка
- ✅ Заголовок
- ❌ Все остальное (специфичная страница)

**Приоритет:** 🟢 Низкий (специфичная страница)

---

## 🎯 План внедрения

### Фаза 1: Простые списки (Приоритет 🔴)

#### 1.1. employees_list.html
```django
{% load static %}

{% block extra_css %}
  {{ block.super }}
  <link rel="stylesheet" href="{% static 'css/components/page-header.css' %}">
{% endblock %}

{% block content %}
<div class="container">
  <div class="row gx-0">
    <div class="col-12">
      
      {% include "includes/components/page_header.html" with 
        icon="bi-people"
        title="Сотрудники"
        count=employees|length
        count_label="Всего:"
        search_id="empFilter"
        search_placeholder="Поиск по ФИО, должности или отделу"
        create_url=create_url
        create_text="Создать профиль"
        create_icon="bi-person-plus"
      %}
      
      <!-- Далее список... -->
    </div>
  </div>
</div>
{% endblock %}
```

**Изменения в views.py:**
```python
context = {
    'employees': employees,
    'create_url': reverse('employees:employee_create') if has_perm else None,
}
```

#### 1.2. department_list.html
```django
{% include "includes/components/page_header.html" with 
  icon="bi-diagram-3"
  title="Отделы"
  count=departments|length
  search_id="deptFilter"
  search_placeholder="Поиск по названию или руководителю"
  create_url=create_url
  create_text="Создать отдел"
%}
```

---

### Фаза 2: Списки с областью видимости (Приоритет 🟡)

#### 2.1. document_list.html
```django
{% include "includes/components/page_header.html" with 
  icon="bi-file-earmark-text"
  title="Документы"
  scope=scope
  scope_urls=scope_urls
  create_modal="docCreateModal"
  create_text="Создать документ"
  has_filters=True
  filters_target="docFilters"
%}

<!-- Блок фильтров -->
{% if has_filters %}
  <div class="collapse page-filters-collapse" id="docFilters">
    <div class="page-filters">
      <!-- Фильтры по типу документа, дате и т.д. -->
    </div>
  </div>
{% endif %}
```

**Изменения:**
- Добавить фильтры (тип, дата загрузки, отправитель)
- Фильтры скрываются по умолчанию, открываются кнопкой
- Добавить поиск по названию/описанию

#### 2.2. request_list_full.html
```django
{% include "includes/components/page_header.html" with 
  icon="bi-clipboard-check"
  title="Заявления"
  scope=scope
  scope_urls=scope_urls
  create_modal="reqCreateModal"
  create_text="Новое заявление"
  has_filters=True
  filters_target="reqFilters"
%}

<!-- Существующие фильтры переносим в collapse -->
<div class="collapse page-filters-collapse" id="reqFilters">
  <div class="page-filters">
    <form method="get">
      <div class="row g-2">
        <div class="col-12 col-md-6 col-lg-3">
          <label class="form-label">Тип</label>
          <select name="type" class="form-select">...</select>
        </div>
        <div class="col-12 col-md-6 col-lg-3">
          <label class="form-label">Статус</label>
          <select name="status" class="form-select">...</select>
        </div>
        <div class="col-12 col-lg-6 d-flex align-items-end gap-2">
          <button class="btn btn-primary" type="submit">Применить</button>
          <a class="btn btn-outline-secondary" href="?view={{ scope }}">Сбросить</a>
        </div>
      </div>
    </form>
  </div>
</div>
```

**Изменения:**
- Фильтры перемещаются в collapse блок
- Добавить поиск по названию заявления
- Кнопка фильтров в шапке

---

### Фаза 3: Специфичные страницы (Приоритет 🟡)

#### 3.1. chat_list.html
```django
{% include "includes/components/page_header.html" with 
  icon="bi-chat-dots"
  title="Мои чаты"
  search_id="chatSearch"
  search_placeholder="Поиск по названию или участникам"
  create_url=employees_url
  create_text="Новый чат"
  create_icon="bi-person-plus"
  has_filters=True
  filters_target="chatFilters"
%}

<!-- Фильтры чатов -->
<div class="collapse page-filters-collapse" id="chatFilters">
  <div class="page-filters">
    <div class="btn-group w-100" role="group">
      <input type="radio" class="btn-check" name="chatFilter" id="fltAll" checked>
      <label class="btn btn-outline-secondary" for="fltAll">Все</label>
      
      <input type="radio" class="btn-check" name="chatFilter" id="fltGlobal">
      <label class="btn btn-outline-secondary" for="fltGlobal">Глобальный</label>
      
      <input type="radio" class="btn-check" name="chatFilter" id="fltDepartment">
      <label class="btn btn-outline-secondary" for="fltDepartment">Отделы</label>
      
      <input type="radio" class="btn-check" name="chatFilter" id="fltPrivate">
      <label class="btn btn-outline-secondary" for="fltPrivate">Личные</label>
    </div>
  </div>
</div>
```

**Изменения:**
- Radio-button фильтры переносим в collapse
- Скрываются по умолчанию

---

## 📝 Чеклист внедрения

### Для каждой страницы:

- [ ] **1. Добавить CSS**
  ```django
  {% block extra_css %}
    {{ block.super }}
    <link rel="stylesheet" href="{% static 'css/components/page-header.css' %}">
  {% endblock %}
  ```

- [ ] **2. Заменить существующую шапку**
  - Удалить старый `.feed-header` или `.ios-header`
  - Вставить `{% include "includes/components/page_header.html" with ... %}`

- [ ] **3. Настроить параметры**
  - Определить нужные параметры (icon, title, search_id и т.д.)
  - Передать через `with`

- [ ] **4. Обновить views.py**
  - Добавить `create_url` в context (если нужно)
  - Добавить `scope` и `scope_urls` (если есть Мои/Все)

- [ ] **5. Переместить фильтры в collapse**
  - Если есть фильтры, обернуть в `<div class="collapse" id="...">`
  - Добавить `has_filters=True` и `filters_target="..."`

- [ ] **6. Обновить JavaScript**
  - Если есть поиск - проверить, что ID совпадает с `search_id`
  - Если есть фильтры - добавить обработчики для collapse

- [ ] **7. Тестирование**
  - Проверить на десктопе (1920x1080)
  - Проверить на планшете (768px)
  - Проверить на мобильном (375px)
  - Проверить все интерактивные элементы (поиск, фильтры, создание)

---

## 🎨 Стилистические правила

### 1. Иконки Bootstrap Icons
```
Сотрудники:     bi-people
Отделы:         bi-diagram-3
Документы:      bi-file-earmark-text
Заявления:      bi-clipboard-check
Лента:          bi-megaphone
Чаты:           bi-chat-dots
Календарь:      bi-calendar-event
Поиск:          bi-search
```

### 2. Текст кнопок создания
```
Сотрудники:     "Создать профиль"
Отделы:         "Создать отдел"
Документы:      "Создать документ"
Заявления:      "Новое заявление"
Публикации:     "Новая публикация"
Чаты:           "Новый чат"
```

### 3. Placeholders для поиска
```
Сотрудники:     "Поиск по ФИО, должности или отделу"
Отделы:         "Поиск по названию или руководителю"
Документы:      "Поиск по названию или описанию"
Заявления:      "Поиск по типу или статусу"
Чаты:           "Поиск по названию или участникам"
```

---

## 🔄 Миграция существующего кода

### Маппинг классов

| Старый класс | Новый класс | Примечание |
|--------------|-------------|------------|
| `.feed-header` | `.page-header` | Основной контейнер |
| `.ios-header` | `.page-header` | Уже с полупрозрачностью |
| `.title` | `.page-title` | Заголовок |
| `.ios-title` | `.page-title` | То же самое |
| `.scope-switch` | `.page-scope-switch` | Переключатель Мои/Все |
| `.feed-new` (для фильтров) | `.page-filters` | Блок фильтров |

### Удаляемые блоки

```django
<!-- СТАРЫЙ КОД - УДАЛИТЬ -->
{% if perms.employees.add_employee %}
  <div class="feed-card mb-2">
    <a href="{% url 'employees:employee_create' %}" class="dept-row ...">
      <span class="feed-author">Создать профиль</span>
      <i class="bi-plus-lg"></i>
    </a>
  </div>
{% endif %}

<!-- Кнопка создания теперь в шапке -->
```

---

## 📅 Временные оценки

| Страница | Сложность | Время | Фаза |
|----------|-----------|-------|------|
| employees_list.html | Простая | 30 мин | 1 |
| department_list.html | Простая | 30 мин | 1 |
| document_list.html | Средняя | 1 час | 2 |
| request_list_full.html | Средняя | 1 час | 2 |
| chat_list.html | Средняя | 1 час | 3 |
| feed_list.html | Простая | 30 мин | 3 |

**Итого:** ~4.5 часа чистой разработки

**С тестированием:** ~6-7 часов

---

## 🧪 Примеры использования

### Пример 1: Простой список с поиском
```django
{% include "includes/components/page_header.html" with 
  icon="bi-people"
  title="Сотрудники"
  count=employees|length
  search_id="empFilter"
  search_placeholder="Поиск сотрудников..."
  create_url=create_url
%}
```

### Пример 2: С областью видимости и фильтрами
```django
{% include "includes/components/page_header.html" with 
  icon="bi-file-earmark-text"
  title="Документы"
  scope=scope
  scope_urls=scope_urls
  search_id="docSearch"
  search_placeholder="Поиск документов..."
  has_filters=True
  filters_target="docFilters"
  create_modal="docCreateModal"
  create_text="Создать документ"
%}
```

### Пример 3: Без поиска, с модальным окном
```django
{% include "includes/components/page_header.html" with 
  icon="bi-clipboard-check"
  title="Заявления"
  no_search=True
  create_modal="reqCreateModal"
  create_text="Новое заявление"
%}
```

### Пример 4: Только заголовок (страница деталей)
```django
{% include "includes/components/page_header.html" with 
  icon="bi-person"
  title=employee.get_full_name
  no_search=True
  no_create=True
%}
```

---

## ✅ Преимущества нового компонента

1. **Единообразие** - все страницы списков выглядят одинаково
2. **Адаптивность** - автоматическая работа на всех устройствах
3. **Современный дизайн** - полупрозрачный фон, плавные анимации
4. **Простота использования** - один include вместо 50+ строк кода
5. **Гибкость** - опциональные параметры для разных сценариев
6. **Производительность** - меньше CSS, переиспользование стилей
7. **Поддержка** - исправления в одном месте применяются везде
8. **Доступность** - ARIA-атрибуты, семантическая разметка

---

## 🚀 Следующие шаги

1. ✅ Создать компоненты (page_header.html, page-header.css)
2. ⏳ Протестировать на одной странице (employees_list.html)
3. ⏳ Получить обратную связь от команды
4. ⏳ Внедрить в остальные страницы согласно плану
5. ⏳ Обновить документацию
6. ⏳ Удалить устаревший CSS (.feed-header, .ios-header)

---

## 📚 Документация

После внедрения обновить:
- `README.md` - добавить секцию "Компоненты UI"
- `COMPONENTS.md` - создать документацию по компонентам
- Storybook (если используется) - добавить примеры

---

**Создано:** 4 ноября 2025 г.
**Автор:** GitHub Copilot
**Статус:** 🟡 В разработке
