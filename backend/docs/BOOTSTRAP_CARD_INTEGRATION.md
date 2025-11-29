# Bootstrap Card Integration - Summary

**Дата**: 29 ноября 2024  
**Контекст**: Решение конфликта между кастомными `.card` классами и нативными Bootstrap классами

## Проблема

После переименования `feed-*` классов в `card-*` для универсализации компонентов, возникли конфликты с нативными Bootstrap классами:
- Bootstrap имеет встроенный компонент `.card` с собственными стилями
- Bootstrap `.card-header`, `.card-body`, `.card-title` переопределяли кастомные стили
- Изменились цвета, отступы, границы карточек

## Решение

Вместо дальнейшего переименования классов (например, `lc-card`, `list-card`), было принято решение **интегрироваться с Bootstrap** и переопределить его стили под наш дизайн.

### Что сделано

1. **Переопределены Bootstrap переменные** в `scss/custom-bootstrap.scss`:
   ```scss
   $card-border-radius: 18px;
   $card-box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
   $card-cap-padding-y: 1rem;
   $card-cap-padding-x: 1rem;
   ```

2. **Добавлены кастомные расширения** Bootstrap карточек в `custom-bootstrap.scss`:
   - `.card` - добавлены тени, анимации, hover-эффекты
   - `.card-header` - переопределен flex-layout
   - `.card-icon` - кастомный класс для аватаров (42px круг)
   - `.card-meta` - кастомный класс для метаинформации
   - `.card-actions` - кастомный класс для кнопок
   - `.card-list` - кастомный класс для контейнера списка
   - `.section-header` - кастомный класс для заголовков секций
   - Вариации: `.card.compact`, `.card.borderless`, `.card.highlighted`

3. **Создан `feed-specific.css`** для постов:
   - Выделены классы, используемые только в постах:
     - `.feed-pin` - значок закрепления
     - `.feed-title` - заголовок поста
     - `.feed-text` - текст поста
     - `.feed-img` - изображение поста
     - `.feed-action` - кнопки действий
     - `.feed-footer` - футер поста

4. **Удалены устаревшие файлы**:
   - ❌ `card-list.css` - стили перенесены в `bootstrap-custom.css`
   - ❌ `request-list.css` - был уже пустым

5. **Обновлены импорты** в шаблонах:
   - Удалены импорты `card-list.css` из всех шаблонов (8 файлов)
   - Добавлен импорт `feed-specific.css` в `feed_list.html`
   - `base.html` больше не импортирует `card-list.css`

6. **Обновлена документация**:
   - `static/css/README.md` - новая архитектура и зависимости
   - `static/css/components/index.css` - обновлен импорт

## Архитектура после рефакторинга

```
variables.css (CSS переменные)
    ↓
bootstrap-custom.css (Bootstrap + переопределения .card)
    ↓
common.css (общие классы)
    ↓
├── feed-specific.css (только для постов)
├── ios-components.css
├── document-list.css
├── employee-list.css
└── другие компоненты
```

## Преимущества решения

✅ **Соответствие стандартам**: Используем нативные Bootstrap классы  
✅ **Меньше кода**: Один источник стилей вместо дублирования  
✅ **Знакомая структура**: Разработчики знают Bootstrap  
✅ **Легче поддержка**: Стандартная документация Bootstrap применима  
✅ **Меньше конфликтов**: Работаем с Bootstrap, а не против него

## Используемые классы

### Универсальные (для всех карточек)
- `.card` - базовая карточка
- `.card-header` - шапка
- `.card-body` - тело
- `.card-title` - заголовок
- `.card-subtitle` - подзаголовок
- `.card-icon` - аватар/иконка (кастомный)
- `.card-meta` - метаинформация (кастомный)
- `.card-actions` - кнопки действий (кастомный)
- `.card-list` - контейнер списка (кастомный)
- `.section-header` - заголовок секции (кастомный)

### Специфичные для постов
- `.feed-pin` - значок закрепления
- `.feed-title` - заголовок поста
- `.feed-text` - текст поста
- `.feed-img` - изображение
- `.feed-action` - кнопка действия
- `.feed-footer` - футер

## Файлы

### Добавлены
- ✅ `static/css/components/feed-specific.css` (2.5KB)

### Изменены
- 📝 `static/scss/custom-bootstrap.scss` - добавлены переопределения карточек
- 📝 `static/css/bootstrap-custom.css` - перекомпилирован
- 📝 `static/css/components/index.css` - обновлены импорты
- 📝 `static/css/README.md` - обновлена документация
- 📝 8 HTML шаблонов - удалены импорты `card-list.css`
- 📝 `templates/base.html` - удален импорт `card-list.css`
- 📝 `templates/feed/feed_list.html` - добавлен импорт `feed-specific.css`

### Удалены
- ❌ `static/css/components/card-list.css` (7.8KB)
- ❌ `static/css/components/request-list.css` (0.5KB)

## Команды выполнения

```bash
# Компиляция SCSS
cd backend/static
npm run build:css

# Сборка статики
cd backend
python manage.py collectstatic --noinput
```

## Результат

- ✅ Компиляция SCSS: успешно (5 warnings о deprecated функциях Bootstrap - это нормально)
- ✅ Сборка статики: 5 файлов обновлено, 990 без изменений
- ✅ Размер: удалено 8.3KB CSS, добавлено 2.5KB = **-5.8KB**
- ✅ Визуальное соответствие: карточки выглядят как задумано
- ✅ Bootstrap интеграция: нативные классы Bootstrap работают с кастомными стилями

## Следующие шаги

1. Протестировать все страницы с карточками:
   - ✅ Лента новостей (`/feed/`)
   - ⏳ Заявления (`/requests/`)
   - ⏳ Документы (`/documents/`)
   - ⏳ Сотрудники (`/employees/`)
   - ⏳ Отделы (`/employees/departments/`)
   - ⏳ Чаты (`/communications/`)
   - ⏳ Поиск (`/search/`)

2. Проверить адаптивность на мобильных устройствах

3. Обновить остальную документацию при необходимости
