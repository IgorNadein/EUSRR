# Анализ существующего кода для Detail View

**Статус:** 📋 Анализ
**Дата:** 26 декабря 2025 г.
**Задача:** feature/requests-detail-view - Этап 1

---

## 🔍 Анализ RequestsView

### Файл: `backend/requests_app/views_front.py`

```python
class RequestsView(LoginRequiredMixin, TemplateView):
    template_name = 'requests/requests_list.html'
    # ... логика загрузки списка заявок
```

**Выводы:**
- ✅ Используется TemplateView (можем использовать для RequestDetailView)
- ✅ Требует LoginRequiredMixin
- ✅ Загружает данные через API клиента
- ✅ Использует pagination

**Как загружает данные:**
```python
client = get_api_client(request)
# Запрос к /api/v1/requests/
response = client.get('/api/v1/requests/', params={...})
```

---

## 🔍 Анализ request_comments() и request_comment_add()

### Функции в `views_front.py` (строки ~277, ~293)

```python
def request_comments(request: HttpRequest, pk: int) -> JsonResponse:
    """Загружает комментарии к заявке"""
    # Возвращает JSON с комментариями

def request_comment_add(request: HttpRequest, pk: int) -> JsonResponse:
    """Добавляет комментарий к заявке"""
    # POST запрос с текстом комментария
    # Возвращает JSON с результатом
```

**Выводы:**
- ✅ Используют JsonResponse для AJAX
- ✅ Работают через POST/GET
- ✅ Уже адаптированы для фронтенда
- ⚠️ Нужно будет интегрировать в модальное окно

---

## 🔍 Анализ API эндпоинтов

### `/api/v1/requests/{pk}/` - RequestViewSet

**Файл:** `backend/api/v1/requests/views.py`

**Методы:**
- ✅ GET - получить одно заявление
- ✅ PATCH/PUT - обновить заявление (изменить статус)
- ✅ DELETE - удалить (если есть права)

**Структура ответа:**
```json
{
    "id": 1,
    "title": "Название заявки",
    "description": "Описание",
    "status": "new|processed|approved|rejected",
    "employee": {"id": 1, "full_name": "Иван Иванов"},
    "recipients": [...],
    "cc_users": [...],
    "approver": {...},
    "departments": [...],
    "created_at": "2025-12-26T10:00:00Z",
    "updated_at": "2025-12-26T10:00:00Z",
    "decided_at": null,
    "type": "document|info|order",
    // ... другие поля
}
```

**Проверка прав доступа:**
- Пользователь видит заявку если:
  - Он автор
  - Он в списке recipients
  - Он в списке cc_users
  - Он approver
  - Он в числе сотрудников указанных отделов

---

## 🔍 Анализ существующих шаблонов

### `backend/templates/requests/requests_list.html`

**Структура:**
- Header с фильтрами (Мои/Все/Новая)
- Таблица со списком заявок
- Пагинация
- Sidebar с фильтрами (статус, отделы, тип)

**Как открываются детали:**
- Может быть, есть модальное окно? Нужно проверить
- Или просто кликает по ссылке?

---

## 🔍 Анализ модальных окон в проекте

**Где уже используются модали:**
- В communications (открытие чата)
- В documents (просмотр документа)
- В employees (профиль сотрудника)
- Возможно, в других местах

**Как реализованы:**
- Bootstrap modals (5.x)
- Открываются через JavaScript
- Загружают контент через AJAX или встроены в HTML

**Пример структуры:**
```html
<div class="modal fade" id="requestModal" tabindex="-1">
    <div class="modal-dialog modal-lg">
        <div class="modal-content">
            <div class="modal-header">
                <h5 class="modal-title">Заявление #<span id="requestId"></span></h5>
                <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
            </div>
            <div class="modal-body">
                <!-- Содержимое загружается сюда -->
            </div>
            <div class="modal-footer">
                <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Закрыть</button>
                <button type="button" class="btn btn-primary" id="saveBtn">Сохранить</button>
            </div>
        </div>
    </div>
</div>
```

---

## 🔍 Структура JavaScript модулей

**Директория:** `backend/static/js/modules/`

**Существующие модули:**
- `chatModule.js` - работа с чатами
- `documentModule.js` - работа с документами
- Другие...

**Паттерн использования:**
```javascript
// Экспортирование как ES6 модулей
export class RequestDetailManager {
    constructor() { }

    init() { }

    openModal(id) { }
    loadData(id) { }
    // ...
}
```

**Как подключаются:**
```html
<script type="module">
    import { RequestDetailManager } from '/static/js/modules/requestDetail.js';

    const manager = new RequestDetailManager();
    manager.init();
</script>
```

---

## 🔍 Анализ прав доступа

### Где проверяются права:

1. **В API (RequestViewSet):**
   - DRF permission classes
   - Проверяет право просмотра заявки
   - Проверяет право редактирования

2. **Во views_front.py:**
   - `LoginRequiredMixin` - требует аутентификацию
   - Фильтрует заявки по доступным для пользователя

3. **На фронтенде:**
   - Скрывают кнопки действий если нет прав
   - JS проверяет ответы API (403 Forbidden)

**Правила доступа к заявке:**
- ✅ Просмотр: автор, recipients, cc_users, approver, сотрудники отделов
- ✅ Редактирование статуса: approver, сотрудники с правом обработки
- ✅ Комментирование: все, кто видит заявку

---

## 🔍 CSS стили

**Фреймворк:** Bootstrap 5

**Существующие классы для модалей:**
- `.modal`, `.modal-dialog`, `.modal-content`
- `.modal-header`, `.modal-body`, `.modal-footer`
- `.btn`, `.btn-primary`, `.btn-secondary`
- Кастомные классы в `requests.css`

**Нужно создать:**
- Стили для модального окна заявки
- Стили для вкладок (может быть, уже есть)
- Стили для комментариев
- Стили для действий (кнопок)

---

## 📋 Чек-лист для следующих этапов

### Что готово использовать:
- ✅ API эндпоинты работают
- ✅ Функции для комментариев есть
- ✅ Структура views понятна
- ✅ Bootstrap модали используются в проекте

### Что нужно создать:
- ❌ RequestDetailView (новый класс)
- ❌ URL маршрут для detail
- ❌ HTML шаблон модального окна
- ❌ JavaScript модуль для логики
- ❌ CSS стили для модали

### Потенциальные проблемы:
- ⚠️ CSRF токен при AJAX запросах
- ⚠️ Права доступа нужно проверить
- ⚠️ N+1 проблема при загрузке связанных данных
- ⚠️ Кэширование при массивных запросах

---

## 🎯 Рекомендации для реализации

### 1. RequestDetailView

```python
class RequestDetailView(LoginRequiredMixin, TemplateView):
    """
    Отображает детальную страницу заявления.
    Может быть как отдельная страница, так и содержимое модали.
    """
    template_name = 'requests/request_detail.html'

    def get_context_data(self, pk, **kwargs):
        context = super().get_context_data(**kwargs)

        # Загрузить заявление через API
        client = get_api_client(self.request)
        response = client.get(f'/api/v1/requests/{pk}/')

        if response.ok:
            context['request_obj'] = response.json()
        else:
            # Обработать ошибку (404, 403 и т.д.)
            pass

        return context
```

### 2. JavaScript модуль

```javascript
export class RequestDetailModal {
    constructor(containerId = 'requestModal') {
        this.modal = new bootstrap.Modal(document.getElementById(containerId));
        this.container = document.getElementById(containerId);
        this.init();
    }

    init() {
        // Добавить обработчики событий
        // Инициализировать элементы
    }

    open(requestId) {
        this.loadData(requestId)
            .then(() => this.modal.show());
    }

    loadData(requestId) {
        // Загрузить данные через API
        // Обновить содержимое модали
    }
}
```

### 3. Интеграция с список заявок

```javascript
// На странице списка добавить слушатели
document.querySelectorAll('[data-request-id]').forEach(row => {
    row.addEventListener('click', (e) => {
        const requestId = row.dataset.requestId;
        requestDetailModal.open(requestId);
    });
});
```

---

## 📚 Полезные ссылки в проекте

- API документация: `/api/v1/`
- Существующие views: `backend/requests_app/views_front.py`
- Существующие templates: `backend/templates/requests/`
- JS модули: `backend/static/js/modules/`
- CSS: `backend/static/css/`

---

## 🚀 Готово начинать разработку!

**Ключевые файлы для открытия:**
1. `backend/requests_app/views_front.py` - понять структуру
2. `backend/templates/requests/requests_list.html` - понять шаблон
3. `backend/static/js/modules/` - посмотреть примеры JS
4. `backend/api/v1/requests/views.py` - понять API

**Следующий шаг:** Начать Этап 2 - создание RequestDetailView
