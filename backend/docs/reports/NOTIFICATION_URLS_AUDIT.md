# Аудит URL в уведомлениях

**Дата проверки:** 26 декабря 2025 г.
**Статус:** ✅ Все URL проверены и исправлены
**Обновлено:** 26.12.2025 - добавлена поддержка RequestDetailView

## 🔍 Цель проверки

Сверить URL-адреса, которые генерируются в `action_url` уведомлений, с реальными эндпоинтами проекта.

---

## ❌ Найденные проблемы

### 1. **Feed (Лента новостей)** - НЕКОРРЕКТНЫЕ URL

#### Проблема в файле: `backend/feed/notification_signals.py`

**Генерируемые URL:**
```python
action_url=f'/feed/post/{post.id}/'  # ❌ НЕПРАВИЛЬНО (строки 61, 99, 175)
```

**Реальные эндпоинты:**
- ✅ `/post/{pk}/` - правильный URL (согласно `feed/urls_front.py`)

**Необходимое исправление:**
```python
action_url=f'/post/{post.id}/'  # ✅ ПРАВИЛЬНО
```

**Файлы для исправления:**
- `backend/feed/notification_signals.py` (строки 61, 99, 175)

---

### 2. **Calendar (Календарь)** - СПЕЦИФИЧНАЯ ЛОГИКА

#### Файл: `backend/calendar_app/notification_signals.py`

**Генерируемый URL:**
```python
action_url=f'/?event_id={event.id}'  # Редирект на главную с параметром
```

**Реальные API эндпоинты:**
- API: `/api/v1/calendar/events/` (ViewSet)
- Frontend: Нет отдельных frontend views для календаря

**Статус:** ⚠️ **УСЛОВНО ПРАВИЛЬНО**
- Календарь не имеет отдельной frontend страницы
- Используется модальное окно на главной странице
- URL корректен для текущей реализации
- **Рекомендация:** Если в будущем добавится страница календаря, изменить на `/calendar/?event_id={event.id}`

---

### 3. **Documents (Документы)** - URL МОГУТ БЫТЬ НЕТОЧНЫМИ

#### Файл: `backend/documents/notification_signals.py`

**Генерируемые URL:**
```python
action_url=f'/documents/{document.id}/'  # ❌ ВОЗМОЖНО НЕПРАВИЛЬНО (строки 345, 464)
```

**Реальные эндпоинты:**
- ✅ `/documents/` - список документов
- ✅ `/documents/ack/{pk}/` - подтверждение ознакомления
- ❌ `/documents/{pk}/` - **НЕ СУЩЕСТВУЕТ**

**Проблема:**
Нет эндпоинта для просмотра отдельного документа. Есть только список.

**Возможные решения:**

1. **Вариант А:** Вести на список документов с якорем
   ```python
   action_url=f'/documents/#document-{document.id}'
   ```

2. **Вариант Б:** Создать view для детального просмотра документа
   ```python
   # В documents/urls.py добавить:
   path('<int:pk>/', DocumentDetailView.as_view(), name='document_detail'),
   ```

3. **Вариант В:** Открывать модальное окно с параметром
   ```python
   action_url=f'/documents/?doc_id={document.id}'
   ```

**Статус:** ❌ **ТРЕБУЕТ ИСПРАВЛЕНИЯ**

---

### 4. **Requests (Заявки)** - НЕКОРРЕКТНЫЕ URL

#### Файл: `backend/requests_app/notification_signals.py`

**Генерируемые URL:**
```python
action_url=f'/requests/{request_obj.id}/'  # ❌ НЕПРАВИЛЬНО (строки 122, 231, 315)
```

**Реальные эндпоинты:**
- ✅ `/requests/` - главная страница заявок (RequestsView)
- ✅ `/requests/my/` - мои заявки
- ✅ `/requests/all/` - все заявки
- ✅ `/requests/{pk}/` - ✅ **ПРАВИЛЬНО** - детали заявки (request_detail)

**Статус:** ✅ **ПРАВИЛЬНО**
Эндпоинт существует согласно `requests_app/urls.py` (строка в urls_front.py: path("<int:pk>/", ...))

---

### 5. **Communications (Мессенджер)** - ПРАВИЛЬНЫЕ URL

#### Файл: `backend/communications/notification_signals.py`

**Генерируемые URL:**
```python
action_url=f'/communications/chats/{chat.id}/?message={instance.id}'  # ✅ (строки 63, 87)
action_url=f'/communications/chats/{chat.id}/'  # ✅ (строки 117, 136, 180)
```

**Реальные эндпоинты:**
- ✅ `/communications/chats/{pk}/` - детали чата (ChatDetailView)

**Статус:** ✅ **ПРАВИЛЬНО**

---

## 📊 Сводная таблица проверки

| Приложение | Генерируемый URL | Реальный эндпоинт | Статус | Действие |
|------------|------------------|-------------------|--------|----------|
| **feed** | ~~`/feed/post/{id}/`~~ → `/post/{id}/` | `/post/{id}/` | ✅ | **Исправлено** |
| **calendar** | `/?event_id={id}` | Нет отдельной страницы | ⚠️ | Мониторить |
| **documents** | ~~`/documents/{id}/`~~ → `/documents/` | `/documents/` (список) | ✅ | **Исправлено** |
| **requests** | `/requests/{id}/` | `/requests/{pk}/` | ✅ | Нет действий |
| **communications** | `/communications/chats/{id}/` | `/communications/chats/{pk}/` | ✅ | Нет действий |

---

## 🔧 Требуемые исправления

### ✅ ИСПРАВЛЕНО: Критичные ошибки

#### ✅ 1.1 Feed - Исправлены URL постов

**Файл:** `backend/feed/notification_signals.py`

**Выполненные замены:**
- ✅ Строка 61: `'/feed/post/{post.id}/'` → `'/post/{post.id}/'`
- ✅ Строка 99: `'/feed/post/{post.id}/'` → `'/post/{post.id}/'`
- ✅ Строка 175: `'/feed/post/{post.id}/'` → `'/post/{post.id}/'`

**Статус:** ✅ ВЫПОЛНЕНО

#### ✅ 1.2 Documents - Исправлены URL документов

**Выбрано решение:** Изменить на список документов (так как DetailView не существует)

**Файл:** `backend/documents/notification_signals.py`

**Выполненные замены:**
- ✅ Строка 345: `'/documents/{document.id}/'` → `'/documents/'`
- ✅ Строка 464: `'/documents/{document.id}/'` → `'/documents/'`

**Обоснование:**
- У Documents нет отдельной страницы для просмотра одного документа
- Список документов показывает все доступные документы
- Пользователь сможет найти нужный документ в списке

**Статус:** ✅ ВЫПОЛНЕНО

---

## ✅ Проверенные и корректные модули

1. **Communications** - все URL корректны
2. **Requests** - все URL корректны (есть view для детального просмотра)
3. **Calendar** - работает через модальные окна на главной странице

---

## 📝 Рекомендации

### 1. Централизованное управление URL

Создать утилиту для генерации URL уведомлений:

```python
# notifications/url_builders.py

def get_post_url(post_id):
    """Генерирует URL для поста в ленте"""
    return f'/post/{post_id}/'

def get_document_url(document_id):
    """Генерирует URL для документа"""
    return f'/documents/?doc_id={document_id}'

def get_request_url(request_id):
    """Генерирует URL для заявки"""
    return f'/requests/{request_id}/'

def get_chat_url(chat_id, message_id=None):
    """Генерирует URL для чата"""
    url = f'/communications/chats/{chat_id}/'
    if message_id:
        url += f'?message={message_id}'
    return url
```

**Преимущества:**
- Единая точка изменения URL
- Проще тестировать
- Легче поддерживать

### 2. Автоматическая проверка URL

Добавить тесты для проверки корректности URL в уведомлениях:

```python
# notifications/tests/test_urls.py

def test_notification_urls_are_valid():
    """Проверяет, что URL в уведомлениях существуют"""
    from django.urls import resolve, Resolver404

    test_urls = [
        '/post/1/',
        '/documents/',
        '/requests/1/',
        '/communications/chats/1/',
    ]

    for url in test_urls:
        try:
            resolve(url)
        except Resolver404:
            assert False, f"URL {url} не существует"
```

### 3. Документация URL паттернов

Создать файл с описанием всех URL паттернов для уведомлений в `docs/`.

---

## 🎯 План действий

### ✅ Выполнено:
1. ✅ Исправлены URL в `feed/notification_signals.py` (3 места)
2. ✅ Исправлены URL в `documents/notification_signals.py` (2 места)

### В ближайшее время:
3. ⚠️ Создать утилиту для генерации URL (`notifications/url_builders.py`)
4. ⚠️ Добавить тесты для проверки URL
5. ⚠️ Обновить все signals для использования новой утилиты

### Долгосрочно:
6. 📝 Добавить проверку URL в CI/CD
7. 📝 Создать документацию по URL паттернам
8. 📝 Рассмотреть создание DetailView для documents (если потребуется)

---

## 📋 Обновление 26.12.2025 - RequestDetailView

### ✅ Реализованы новые функции:

**Requests (Заявки)**
- ✅ RequestDetailView - полный детальный просмотр заявки
- ✅ Система комментариев - добавление и удаление комментариев в реальном времени
- ✅ Изменение статуса - для администраторов
- ✅ Модальное окно для быстрого просмотра деталей

**URL остается неизменным:**
- Frontend: `/requests/{id}/` - работает как через основную страницу, так и через модальное окно
- API: `/api/v1/requests/{id}/` - полная информация о заявке
- API Comments: `/api/v1/requests/{id}/comments/` - список комментариев

---

**Итого найдено проблем:** 2 критичные (✅ исправлены), 1 предупреждение
**Проверено модулей:** 5
**Статус реализации:** ✅ Все URLs корректны, новые разработки интегрированы
**Общий статус:** ✅ **Все критичные проблемы исправлены**
