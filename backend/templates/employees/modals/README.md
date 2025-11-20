# Модальные окна для работы с сотрудниками

## `_create_employee.html`

Модальное окно для создания нового профиля сотрудника.

### Использование

```django
{# Включить модал в шаблон #}
{% include "employees/modals/_create_employee.html" %}

{# Инициализировать JavaScript (в конце страницы) #}
<script type="module">
  import { initCreateEmployeeModal } from '{% static "js/components/createEmployeeModal.js" %}';
  
  initCreateEmployeeModal({
    submitUrl: '{% url "employees:employee_create_modal" %}'
  });
</script>
```

### Интеграция с page_header компонентом

```django
{% include "includes/components/page_header.html" with 
  icon="bi-people"
  title="Сотрудники"
  create_as_card=True
  create_modal="#createEmployeeModal"
  create_text="Создать профиль"
%}

{# В конце шаблона #}
{% include "employees/modals/_create_employee.html" %}

<script type="module">
  import { initCreateEmployeeModal } from '{% static "js/components/createEmployeeModal.js" %}';
  initCreateEmployeeModal({
    submitUrl: '{% url "employees:employee_create_modal" %}'
  });
</script>
```

### JavaScript API

#### `initCreateEmployeeModal(options)`

Инициализирует обработчик модального окна создания сотрудника.

**Параметры:**
- `options.modalId` (string) - ID модального окна, по умолчанию `'createEmployeeModal'`
- `options.formId` (string) - ID формы, по умолчанию `'createEmployeeForm'`
- `options.errorsId` (string) - ID блока ошибок, по умолчанию `'createEmployeeErrors'`
- `options.submitBtnId` (string) - ID кнопки отправки, по умолчанию `'createEmployeeSubmit'`
- `options.submitUrl` (string) - URL для отправки формы, **обязательный параметр**

**Пример:**
```javascript
initCreateEmployeeModal({
  submitUrl: '/employees/create/modal/',
  modalId: 'myCustomModal'  // опционально
});
```

### Поля формы

**Обязательные:**
- Email
- Телефон

**Опциональные:**
- Фамилия, Имя, Отчество
- Пол (M/F)
- Дата рождения
- Должность (выбор из списка)
- Пароль (генерируется автоматически, если не указан)
- Telegram, WhatsApp, WeChat
- Аватар (изображение)

### Backend

Модал отправляет AJAX запрос на:
```
POST /employees/create/modal/
```

Вьюха: `employees.views_front.employee_create_modal`

Обрабатывает данные формы, обращается к API через `get_api_client()` и возвращает JSON:

**Успех:**
```json
{
  "success": true,
  "message": "Сотрудник успешно создан",
  "employee_id": 123,
  "redirect_url": "/employees/123/"
}
```

**Ошибка:**
```json
{
  "success": false,
  "error": "Описание ошибки"
}
```

### Особенности

1. **Нет прямого обращения к API** - запрос идёт через фронтовую вьюху `employee_create_modal`, которая сама обращается к API
2. **Валидация** - ошибки парсятся из ответа API и показываются в модале
3. **Автозакрытие** - при успехе модал закрывается и происходит редирект на профиль созданного сотрудника
4. **Loading state** - кнопка блокируется и показывает spinner во время отправки

### Зависимости

- Bootstrap 5 Modal
- Django CSRF middleware
- Список должностей в контексте (`positions_list`)
