# Оценка состояния CSS → SCSS миграции

**Дата:** 15 января 2026 г.  
**Статус:** Частично выполнено (30%)

---

## 📊 Текущее состояние

### ✅ Уже в SCSS

**Успешно мигрировано:**
```
scss/
├── custom-bootstrap.scss       ✅ Главный файл сборки Bootstrap
├── abstracts/
│   ├── _variables.scss        ✅ SCSS переменные (220 строк)
│   ├── _css-variables.scss    ✅ CSS custom properties (198 строк)
│   ├── _mixins.scss           ✅ Миксины
│   └── _index.scss            ✅ Экспорт abstracts
├── components/
│   ├── _navbar.scss           ⚠️ Пустой файл
│   ├── _sidebar.scss          ✅ Существует
│   ├── _cards.scss            ✅ Существует
│   ├── _modals.scss           ✅ Существует
│   ├── _badges-bem.scss       ✅ Существует
│   ├── _badges-telegram-style.scss ✅ Существует
│   ├── _comments.scss         ✅ Существует
│   ├── _common.scss           ✅ Существует
│   ├── _page-header.scss      ✅ Существует
│   └── chat/                  ✅ Подпапка для чата
├── layout/
│   └── _chat-layout.scss      ✅ Существует
└── utilities/                  📁 Папка существует
```

**Система сборки:**
```json
{
  "scripts": {
    "build:css": "sass scss/custom-bootstrap.scss css/bootstrap-custom.css --style compressed",
    "watch:css": "sass scss/custom-bootstrap.scss css/bootstrap-custom.css --watch --style compressed",
    "dev": "npm run watch:css",
    "build": "npm run build:css"
  }
}
```

✅ **Работает:** Bootstrap компилируется через SCSS с кастомизацией

---

## ❌ Требуют миграции

### 🔴 Высокий приоритет (используются в base.html)

Эти файлы подключены в базовом шаблоне и используются на **ВСЕХ** страницах:

#### 1. `css/components/buttons.css` (164 строки)
- **Где используется:** `base.html` (строка 33)
- **Функциональность:** 
  - Круглые кнопки (`.btn-circle`, размеры sm/md/lg)
  - Иконочные кнопки (`.btn-icon`)
  - Адаптив для мобильных
  - Кнопки-призраки (`.btn-ghost`)
- **Сложность миграции:** 🟡 Средняя
- **Зависимости:** Bootstrap button classes, CSS variables
- **Готовый SCSS файл:** Не существует

```css
/* Примеры из файла */
.btn-circle { border-radius: 50%; aspect-ratio: 1/1; }
.btn-circle-sm { width: 32px; height: 32px; }
.btn-icon { display: inline-flex; gap: 0.5rem; }
```

#### 2. `css/components/ios-search.css` (194 строки)
- **Где используется:** 
  - `base.html` (строка 34)
  - `communications/chat_list.html`
  - `documents/document_list.html`
  - `employees/employees_list.html`
  - `employees/department_list.html`
  - `requests_app/my_requests.html`
  - `search/results.html`
- **Функциональность:**
  - iOS-стиль поле поиска
  - Иконка лупы
  - Кнопка очистки
  - Анимации и темизация
- **Сложность миграции:** 🟡 Средняя
- **Зависимости:** CSS variables для отступов, темы
- **Переиспользование:** ⭐⭐⭐⭐⭐ Очень высокое (8 шаблонов)

```css
/* Примеры из файла */
.ios-search { position: relative; max-width: 420px; }
.ios-search-input { border-radius: 14px; height: 40px; }
.ios-search-clear { position: absolute; right: 4px; }
```

#### 3. `css/components/base-app.css` (346 строк)
- **Где используется:** `base.html` (строка 35)
- **Функциональность:**
  - Layout grid (navbar, sidebar, content)
  - Базовые стили приложения
  - Адаптивный контейнер `.content-container`
  - Стили для форм и кнопок
  - Медиа-запросы для десктопа/мобильных
- **Сложность миграции:** 🔴 Высокая
- **Зависимости:** Много CSS variables, сложная структура
- **Критичность:** ⚠️ **КРИТИЧНО** - основной layout файл

```css
/* Примеры из файла */
body { padding-top: var(--navbar-h); }
.app-navbar { position: fixed; z-index: 1030; }
.app-layout.with-sidebar { display: grid; }
```

#### 4. `css/components/ios-components.css`
- **Где используется:** `base.html` (строка 36)
- **Функциональность:** iOS-стиль компоненты
- **Сложность миграции:** 🟡 Средняя

---

### 🟡 Средний приоритет (используются в конкретных приложениях)

#### 5. `css/components/card-list.css`
- **Функциональность:** Списки карточек (общий компонент)
- **Переиспользование:** Высокое
- **Сложность:** 🟢 Низкая

#### 6. `css/notifications/notifications.css`
- **Функциональность:** Стили уведомлений
- **Переиспользование:** Среднее
- **Сложность:** 🟢 Низкая

#### 7. `css/components/navbar.css`
- **Функциональность:** Дополнительные стили навбара
- **Сложность:** 🟡 Средняя
- **Примечание:** ⚠️ `scss/components/_navbar.scss` пустой!

#### 8. `css/components/sidebar.css`
- **Функциональность:** Стили сайдбара
- **Сложность:** 🟡 Средняя
- **Примечание:** ✅ Есть `scss/components/_sidebar.scss`

#### 9. `css/components/modal-overrides.css`
- **Функциональность:** Переопределения Bootstrap модалок
- **Сложность:** 🟢 Низкая

#### 10-30. Остальные CSS файлы компонентов
```
css/components/
├── common.css
├── department-controls.css
├── document-list.css
├── employee-modals.css
├── feed-specific.css
├── join-scroller.css
├── layout-spacing.css
├── list-view.css
├── logout-modal.css
├── page-header.css
├── post-form.css
├── recipientPicker.css
├── request-detail.css
├── request-list.css
├── rightbar-calendar.css
├── rightbar-calendar-fullcalendar.css
├── spacing-utils.css
├── team-wheel.css
└── ... (еще ~10 файлов)
```

---

### 📋 `css/components/index.css` - агрегатор

Содержит `@import` для объединения нескольких CSS файлов:

```css
@import '../variables.css';
@import 'common.css';
@import 'feed-specific.css';
@import 'ios-search.css';
@import 'ios-components.css';
```

⚠️ **Проблема:** Используется редко, но создает путаницу с импортами

---

## 🎯 План миграции

### Фаза 1: Критические файлы из base.html (приоритет 🔴)

**Цель:** Мигрировать 4 файла, используемых глобально

**Файлы:**
1. `buttons.css` → `scss/components/_buttons.scss`
2. `ios-search.css` → `scss/components/_ios-search.scss`
3. `base-app.css` → `scss/layout/_base-app.scss`
4. `ios-components.css` → `scss/components/_ios-components.scss`

**Действия:**
1. Создать SCSS файлы с использованием переменных из `abstracts/_variables.scss`
2. Добавить в главный SCSS файл сборки
3. Обновить `base.html` для подключения скомпилированного CSS
4. Тестирование на всех страницах
5. Удалить старые CSS файлы

**Ожидаемое время:** 4-6 часов

**Выгода:**
- ✅ Единая точка сборки стилей
- ✅ Использование SCSS переменных и миксинов
- ✅ Уменьшение количества HTTP запросов
- ✅ Улучшенная поддерживаемость

---

### Фаза 2: Часто используемые компоненты (приоритет 🟡)

**Файлы:**
1. `card-list.css` → `scss/components/_card-list.scss`
2. `navbar.css` → `scss/components/_navbar.scss` (заполнить существующий)
3. `sidebar.css` → объединить с существующим `_sidebar.scss`
4. `modal-overrides.css` → добавить в `_modals.scss`
5. `notifications.css` → `scss/components/_notifications.scss`

**Ожидаемое время:** 3-4 часа

---

### Фаза 3: Специфичные компоненты приложений (приоритет 🟢)

**Файлы:**
- Все остальные `css/components/*.css`
- Группировка по функциональности
- Создание подпапок в `scss/components/`

**Ожидаемое время:** 6-8 часов

---

### Фаза 4: Очистка и оптимизация

**Действия:**
1. Удалить все старые CSS файлы
2. Обновить все шаблоны для использования единого CSS
3. Оптимизировать SCSS структуру
4. Документация

**Ожидаемое время:** 2-3 часа

---

## 🏗️ Новая структура после миграции

```
scss/
├── custom-bootstrap.scss       # Bootstrap сборка
├── main.scss                   # ⭐ НОВЫЙ главный файл приложения
├── abstracts/
│   ├── _variables.scss
│   ├── _css-variables.scss
│   ├── _mixins.scss
│   └── _index.scss
├── layout/
│   ├── _base-app.scss         # 🔄 Мигрировано из CSS
│   ├── _navbar.scss
│   ├── _sidebar.scss
│   ├── _chat-layout.scss
│   └── _index.scss
├── components/
│   ├── _buttons.scss          # 🔄 Мигрировано из CSS
│   ├── _ios-search.scss       # 🔄 Мигрировано из CSS
│   ├── _ios-components.scss   # 🔄 Мигрировано из CSS
│   ├── _cards.scss
│   ├── _card-list.scss        # 🔄 Мигрировано из CSS
│   ├── _modals.scss
│   ├── _navbar.scss           # 🔄 Заполнен
│   ├── _sidebar.scss
│   ├── _notifications.scss    # 🔄 Мигрировано из CSS
│   ├── _badges-bem.scss
│   ├── _badges-telegram-style.scss
│   ├── _comments.scss
│   ├── _common.scss
│   ├── _page-header.scss
│   ├── chat/
│   │   └── ... (подкомпоненты чата)
│   ├── feed/
│   │   ├── _feed-list.scss
│   │   └── _post-card.scss
│   ├── employees/
│   │   ├── _team-wheel.scss
│   │   └── _employee-list.scss
│   ├── documents/
│   │   └── _document-list.scss
│   └── _index.scss
├── utilities/
│   ├── _spacing-utils.scss
│   └── _index.scss
└── pages/
    └── ... (страницо-специфичные стили)
```

**Компиляция:**
```json
{
  "scripts": {
    "build:css": "npm run build:bootstrap && npm run build:app",
    "build:bootstrap": "sass scss/custom-bootstrap.scss css/bootstrap-custom.css --style compressed",
    "build:app": "sass scss/main.scss css/app.css --style compressed",
    "watch:css": "npm run watch:bootstrap & npm run watch:app",
    "watch:bootstrap": "sass scss/custom-bootstrap.scss css/bootstrap-custom.css --watch --style compressed",
    "watch:app": "sass scss/main.scss css/app.css --watch --style compressed",
    "dev": "npm run watch:css",
    "build": "npm run build:css"
  }
}
```

**В шаблонах:**
```django
{# base.html #}
<link rel="stylesheet" href="{% static 'css/bootstrap-custom.css' %}">
<link rel="stylesheet" href="{% static 'css/app.css' %}">  {# Вместо множества файлов #}
```

---

## 📈 Метрики миграции

| Метрика | До миграции | После миграции | Улучшение |
|---------|-------------|----------------|-----------|
| CSS файлов в `base.html` | 6 | 2 | -67% |
| HTTP запросов | ~10 | 2 | -80% |
| Переменных hardcoded | Много | 0 | ✅ |
| Поддерживаемость | Низкая | Высокая | ⬆️ |
| Переиспользование кода | Среднее | Высокое | ⬆️ |
| Время разработки новых компонентов | Долго | Быстро | ⬆️ |

---

## ⚠️ Риски и проблемы

### 1. Ломающие изменения
- **Риск:** Изменение селекторов или структуры может сломать существующие страницы
- **Митигация:** 
  - Тестирование на каждом этапе
  - Сохранение CSS класс-неймов
  - Постепенная миграция по одному файлу

### 2. CSS переменные vs SCSS переменные
- **Проблема:** Сейчас используются и те, и другие
- **Решение:** 
  - CSS variables для runtime значений (темизация, адаптив)
  - SCSS variables для compile-time констант
  - Четкое разделение ответственности

### 3. Порядок импортов
- **Проблема:** CSS каскад зависит от порядка
- **Решение:** Строгая структура импортов в `main.scss`

### 4. Кэширование
- **Проблема:** Браузеры могут кэшировать старые CSS файлы
- **Решение:** Версионирование файлов или cache busting

---

## ✅ Критерии успеха

1. ✅ Все CSS файлы из `base.html` мигрированы в SCSS
2. ✅ Единая точка сборки через `npm run build`
3. ✅ Нет визуальных регрессий на всех страницах
4. ✅ Использование SCSS переменных вместо hardcoded значений
5. ✅ Уменьшение количества HTTP запросов
6. ✅ Документация новой структуры
7. ✅ Удаление старых CSS файлов

---

## 🚀 Следующие шаги

### Немедленно (сегодня)
1. ✅ Создать `scss/main.scss` - главный файл приложения
2. ✅ Мигрировать `buttons.css` → `scss/components/_buttons.scss`
3. ✅ Протестировать сборку
4. ✅ Обновить `package.json` скрипты

### На этой неделе
1. Мигрировать `ios-search.css` → `scss/components/_ios-search.scss`
2. Мигрировать `base-app.css` → `scss/layout/_base-app.scss`
3. Мигрировать `ios-components.css` → `scss/components/_ios-components.scss`
4. Обновить `base.html` для использования скомпилированного CSS
5. Тестирование на всех основных страницах

### В следующие 2 недели
1. Мигрировать остальные часто используемые компоненты (Фаза 2)
2. Мигрировать специфичные компоненты (Фаза 3)
3. Очистка и оптимизация (Фаза 4)
4. Полная документация

---

## 📚 Ресурсы

**Существующая документация:**
- [backend/static/README.md](../../backend/static/README.md) - Текущая структура
- [backend/static/scss/custom-bootstrap.scss](../../backend/static/scss/custom-bootstrap.scss) - Bootstrap конфиг

**Для создания:**
- `backend/static/scss/README.md` - Гид по SCSS структуре
- `docs/guides/SCSS_DEVELOPMENT.md` - Разработка новых компонентов
- `docs/guides/SCSS_MIGRATION_GUIDE.md` - Пошаговый гид миграции

---

**Оценка составлена:** 15 января 2026 г.  
**Планируемое завершение:** 1 февраля 2026 г. (при работе по 2-3 часа в день)
