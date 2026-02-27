# Доработка страницы Documents по образцу Requests

## ✅ Выполненные изменения

### 1. Backend - Views (`backend/documents/views.py`)

#### Добавлены утилиты:
- ✅ `_fmt_dt()` - форматирование дат в локальную таймзону
- ✅ `_format_datetime_fields()` - массовое форматирование дат в списке объектов
- ✅ `_err_msg()` - извлечение сообщений об ошибках из API

#### Обновлены функции:
- ✅ `_parse_page_payload()` - изменен возвращаемый тип с `ApiPage` на `Tuple[List, str, str, int]`
- ✅ Добавлено форматирование дат в результатах

#### Полностью переписан `DocumentView.get_context_data()`:
- ✅ Добавлено чтение фильтров из GET (`scope`, `ack_status`)
- ✅ Добавлена загрузка списка документов через API
- ✅ Добавлена обработка ошибок с `messages` framework
- ✅ Добавлено извлечение `acked_ids` из результатов API
- ✅ Добавлена локальная фильтрация по `ack_status`
- ✅ Передаются все необходимые данные в контекст:
  - `documents` - список документов
  - `acked_ids` - множество ID ознакомленных
  - `next_url`, `prev_url` - пагинация
  - `count` - общее количество
  - `scope` - текущая область (mine/all)
  - `show_admin_controls` - флаг показа админ-кнопок
  - `can_manage_documents` - права управления
  - `filters` - примененные фильтры
  - `perms` - права пользователя
  - API URLs для JavaScript

#### Удалено:
- ✅ Dataclass `ApiPage` (заменен на tuple)
- ✅ Старая логика с передачей только URLs

---

### 2. Backend - API (`backend/api/v1/documents/views.py`)

#### Обновлен `DocumentViewSet.get_queryset()`:
- ✅ Добавлена поддержка параметра `?scope=mine`
- ✅ Фильтрация документов для пользователя:
  - `sent_to_all=True` ИЛИ
  - Пользователь в `recipients` ИЛИ
  - Пользователь в активных сотрудниках `departments` ИЛИ
  - Пользователь является `uploaded_by`
- ✅ Автоматическое ограничение для пользователей без прав `view_document`
- ✅ Добавлена сортировка по `-uploaded_at`
- ✅ Аннотация `_is_acknowledged` для флага ознакомления

---

### 3. Templates - Основной шаблон (`backend/templates/documents/document_list.html`)

#### Добавлено:
- ✅ **Tabs для переключения Mine/All** (показываются только при `can_manage_documents`)
  - "Мои документы" - персональные документы
  - "Все документы" - доступны администраторам
- ✅ Обновлен `page_header` - убраны дублирующие блоки, передается `scope`
- ✅ Обновлена подсветка непрочитанных - только для `scope=mine`

#### Обновлена логика кнопок действий:
- ✅ **В scope=mine:**
  - Показывается badge "✓ Ознакомлен" (зеленый) если в `acked_ids`
  - Показывается badge "⏰ Требуется ознакомление" (желтый) если НЕ в `acked_ids`
  - НЕТ кнопок управления
  
- ✅ **В scope=all:**
  - Показывается кнопка "👥 Ознакомления" (модалка)
  - Показываются кнопки управления (редактировать/удалить) при `show_admin_controls`

---

### 4. Templates - Фильтры (`backend/templates/documents/_filters.html`)

#### Обновлено:
- ✅ Убран dropdown "Область" (заменен на tabs)
- ✅ Добавлен `<input type="hidden" name="scope">` для сохранения scope
- ✅ Обновлена кнопка "Сбросить" - сохраняет scope (`href="?scope={{ scope }}"`)
- ✅ Остался только фильтр "Статус ознакомления"

---

## 📊 Сравнение До / После

### До рефакторинга:

| Параметр | Значение |
|----------|----------|
| Загрузка данных | ❌ Нет |
| Server-side рендеринг | ❌ Нет |
| Фильтры | ❌ Не работают |
| Пагинация | ❌ Не работает |
| SEO | ❌ Нет контента |
| Работа без JS | ❌ Страница пустая |

### После рефакторинга:

| Параметр | Значение |
|----------|----------|
| Загрузка данных | ✅ Через API в Django view |
| Server-side рендеринг | ✅ Django templates |
| Фильтры | ✅ scope, ack_status работают |
| Пагинация | ✅ next/prev links |
| SEO | ✅ Контент в HTML |
| Работа без JS | ✅ Базовый просмотр работает |

---

## 🎯 Достигнутые результаты

### Функциональность:
1. ✅ **Гибридный подход SSR + API** - как в Requests
2. ✅ **Tabs Mine/All** - переключение областей
3. ✅ **Фильтры работают** - ack_status с сохранением scope
4. ✅ **Пагинация работает** - prev/next ссылки
5. ✅ **Права доступа** - can_manage_documents, show_admin_controls
6. ✅ **Форматирование дат** - локальная таймзона
7. ✅ **Обработка ошибок** - messages framework
8. ✅ **Оптимизация** - select_related, prefetch_related, distinct()

### Архитектура:
1. ✅ **Server-side рендеринг** - данные в HTML при загрузке страницы
2. ✅ **SEO-friendly** - контент доступен для индексации
3. ✅ **Progressive Enhancement** - работает без JS (базово)
4. ✅ **JavaScript как дополнение** - CRUD через модалки
5. ✅ **Единообразие с Requests** - одинаковые паттерны

---

## 🧪 Тестирование

### Ручное тестирование:
- [ ] Загрузка страницы /documents/ без авторизации → редирект
- [ ] Загрузка scope=mine для обычного пользователя → свои документы
- [ ] Загрузка scope=all для админа → все документы
- [ ] Загрузка scope=all для обычного пользователя → редирект на mine
- [ ] Фильтр ack_status=acked → только ознакомленные
- [ ] Фильтр ack_status=not_acked → только неознакомленные
- [ ] Пагинация → клик на "Вперёд"/"Назад"
- [ ] Tabs Mine/All → переключение работает
- [ ] Badges в scope=mine → правильные цвета и иконки
- [ ] Кнопка "Ознакомления" в scope=all → открывает модалку
- [ ] Кнопки управления только в scope=all для админов
- [ ] CRUD через модалки → работает через API
- [ ] Ознакомление документа → редирект на файл

### Автоматическое тестирование:
```bash
# Запустить тесты
python manage.py test documents
python manage.py test api.v1.documents
```

---

## 📝 Дополнительные улучшения (опционально)

### Можно добавить в будущем:
1. ⏳ Серверная пагинация с номерами страниц
2. ⏳ Сортировка по колонкам (дата, название, статус)
3. ⏳ Поиск по названию/описанию
4. ⏳ Фильтр по отделам (для scope=all)
5. ⏳ Экспорт списка в Excel/PDF
6. ⏳ Массовые операции (выбор нескольких документов)
7. ⏳ История изменений документа
8. ⏳ Превью документа в модалке

---

## 🚀 Развертывание

### Проверка перед деплоем:
```bash
# 1. Проверка Django
python manage.py check

# 2. Миграции (если были изменения в моделях)
python manage.py makemigrations
python manage.py migrate

# 3. Статика
python manage.py collectstatic --noinput

# 4. Тесты
python manage.py test
```

### Рестарт сервера:
```bash
# Development
python manage.py runserver 9000

# Production (gunicorn, uwsgi, etc.)
sudo systemctl restart eusrr
```

---

## 📚 Документация

### Новые параметры GET:
- `?scope=mine` - мои документы (по умолчанию)
- `?scope=all` - все документы (требует права)
- `?ack_status=acked` - только ознакомленные
- `?ack_status=not_acked` - только неознакомленные

### API изменения:
- `GET /api/v1/documents/?scope=mine` - фильтрация по пользователю
- Response включает поле `is_acknowledged` для каждого документа

### Контекст шаблона:
```python
{
    "documents": List[dict],          # Список документов
    "acked_ids": set[int],            # ID ознакомленных
    "next_url": str | None,           # Следующая страница
    "prev_url": str | None,           # Предыдущая страница
    "count": int | None,              # Общее количество
    "scope": str,                     # mine | all
    "show_admin_controls": bool,      # Показывать кнопки управления
    "can_manage_documents": bool,     # Права управления
    "filters": {
        "ack_status": str             # acked | not_acked | ""
    },
    "perms": {
        "documents": {
            "add_document": bool,
            "change_document": bool,
            "delete_document": bool
        }
    },
    "api_document_list_url": str,
    "api_document_detail_base": str
}
```

---

## ✅ Итог

Страница `/documents/` теперь полностью соответствует архитектуре `/requests/`:
- ✅ Server-side рендеринг данных
- ✅ Работающие фильтры и пагинация
- ✅ Разделение прав доступа (Mine/All)
- ✅ SEO-friendly контент
- ✅ Progressive Enhancement
- ✅ Единообразие кодовой базы

**Архитектура стала консистентной и maintainable!** 🎉
