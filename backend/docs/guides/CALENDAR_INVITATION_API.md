# API для приглашения пользователей в календарь

**Дата создания**: 12 февраля 2026
**Ветка**: `feature/optional-calendars`
**Автор**: GitHub Copilot

## Обзор

Добавлена функциональность активного приглашения пользователей в календарь владельцем. Теперь владелец календаря может приглашать пользователей и сразу выдавать им права на редактирование и управление.

## Что было добавлено

### 1. Новые сериализаторы

#### `CalendarInviteSerializer`
Сериализатор для приглашения одного пользователя.

**Поля:**
- `user_id` (int, optional) - ID пользователя для приглашения
- `username` (str, optional) - Username пользователя для приглашения
- `can_edit` (bool, default=False) - Право на редактирование событий
- `can_manage` (bool, default=False) - Право на управление календарем
- `notify` (bool, default=True) - Отправить уведомление о приглашении

**Валидация:**
- Должен быть указан либо `user_id`, либо `username` (не оба)

#### `CalendarInviteBulkSerializer`
Сериализатор для массового приглашения пользователей.

**Поля:**
- `user_ids` (list[int], optional) - Список ID пользователей
- `usernames` (list[str], optional) - Список username пользователей
- `can_edit` (bool, default=False) - Право на редактирование событий
- `can_manage` (bool, default=False) - Право на управление календарем
- `notify` (bool, default=True) - Отправить уведомления о приглашении

**Валидация:**
- Должен быть указан либо `user_ids`, либо `usernames` (не оба)
- Списки не могут быть пустыми

---

### 2. Новые API endpoints

#### `POST /api/v1/calendar/{id}/invite/`
Приглашение одного пользователя в календарь.

**Права доступа:** Только владелец календаря

**Request Body:**
```json
{
  "user_id": 123,
  "can_edit": true,
  "can_manage": false,
  "notify": true
}
```

или

```json
{
  "username": "ivanov",
  "can_edit": true,
  "can_manage": false,
  "notify": true
}
```

**Response (201 Created):**
```json
{
  "id": 45,
  "calendar": 12,
  "calendar_title": "Мой календарь",
  "calendar_color": "#3788d8",
  "user": 123,
  "user_name": "Иван Иванов",
  "is_visible": true,
  "color_override": null,
  "can_edit": true,
  "can_manage": false,
  "notify_on_new_event": true,
  "notify_on_event_change": true,
  "subscribed_at": "2026-02-12T10:30:00Z"
}
```

**Возможные ошибки:**
- `403 Forbidden` - Пользователь не является владельцем календаря
- `404 Not Found` - Пользователь с указанным ID/username не найден
- `400 Bad Request` - Пользователь уже подписан на календарь

---

#### `POST /api/v1/calendar/{id}/invite-bulk/`
Массовое приглашение пользователей в календарь.

**Права доступа:** Только владелец календаря

**Request Body:**
```json
{
  "user_ids": [123, 456, 789],
  "can_edit": true,
  "can_manage": false,
  "notify": true
}
```

или

```json
{
  "usernames": ["ivanov", "petrov", "sidorov"],
  "can_edit": true,
  "can_manage": false,
  "notify": true
}
```

**Response (201 Created):**
```json
{
  "created": [
    {
      "id": 45,
      "calendar": 12,
      "user": 123,
      "user_name": "Иван Иванов",
      "can_edit": true,
      "can_manage": false,
      ...
    },
    {
      "id": 46,
      "calendar": 12,
      "user": 456,
      "user_name": "Петр Петров",
      "can_edit": true,
      "can_manage": false,
      ...
    }
  ],
  "already_subscribed": [
    {
      "user_id": 789,
      "username": "sidorov",
      "subscription_id": 40
    }
  ],
  "errors": [],
  "total_created": 2,
  "total_already_subscribed": 1,
  "total_errors": 0
}
```

**Особенности:**
- Владелец автоматически исключается из списка приглашаемых
- Пользователи, которые уже подписаны, пропускаются (не ошибка)
- Если ни один пользователь не найден - `404 Not Found`
- Ошибки отдельных пользователей не блокируют остальные приглашения

---

### 3. Уведомления

При приглашении (если `notify=true`) пользователю отправляется уведомление:

**Тип:** `calendar_invitation`
**Заголовок:** `Приглашение в календарь: {calendar_title}`
**Текст:** `{owner_name} пригласил вас в календарь "{calendar_title}" с правами: {permissions}.`

**Связанный объект:**
- `related_object_type`: `"calendar"`
- `related_object_id`: ID календаря

---

## Архитектура

### Права доступа

1. **Владелец календаря** может:
   - Приглашать любых пользователей
   - Выдавать права `can_edit` и `can_manage`
   - Отменять подписки других пользователей (через `DELETE /api/v1/calendar/subscriptions/{id}/`)
   - Изменять права существующих подписчиков (через `PATCH /api/v1/calendar/subscriptions/{id}/`)

2. **Обычный пользователь** может:
   - Подписаться на публичный календарь (через `/subscribe/`)
   - Отписаться от календаря (через `/unsubscribe/`)
   - Изменить свои настройки отображения (цвет, видимость)
   - НЕ может выдавать себе права `can_edit` и `can_manage`

### Проверки безопасности

- ✅ Проверка владельца календаря перед приглашением
- ✅ Защита от приглашения самого себя
- ✅ Проверка на дублирование подписок
- ✅ Автоматическое исключение владельца из массового приглашения
- ✅ Транзакционная безопасность при массовом приглашении

---

## Примеры использования

### JavaScript (Frontend)

```javascript
// Приглашение одного пользователя
async function inviteUser(calendarId, userId, canEdit = false) {
    const response = await fetch(`/api/v1/calendar/${calendarId}/invite/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
            user_id: userId,
            can_edit: canEdit,
            can_manage: false,
            notify: true
        })
    });

    if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail);
    }

    return await response.json();
}

// Массовое приглашение
async function inviteBulk(calendarId, userIds, canEdit = false) {
    const response = await fetch(`/api/v1/calendar/${calendarId}/invite-bulk/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
            user_ids: userIds,
            can_edit: canEdit,
            can_manage: false,
            notify: true
        })
    });

    const result = await response.json();
    console.log(`Приглашено: ${result.total_created}, уже подписаны: ${result.total_already_subscribed}`);
    return result;
}
```

### Python (тесты/скрипты)

```python
import requests

# Приглашение одного пользователя
response = requests.post(
    'http://localhost:9000/api/v1/calendar/12/invite/',
    json={
        'username': 'ivanov',
        'can_edit': True,
        'can_manage': False,
        'notify': True
    },
    headers={'Authorization': f'Bearer {token}'}
)

if response.status_code == 201:
    subscription = response.json()
    print(f"Пользователь приглашен: {subscription['user_name']}")

# Массовое приглашение
response = requests.post(
    'http://localhost:9000/api/v1/calendar/12/invite-bulk/',
    json={
        'user_ids': [123, 456, 789],
        'can_edit': True,
        'notify': True
    },
    headers={'Authorization': f'Bearer {token}'}
)

result = response.json()
print(f"Создано подписок: {result['total_created']}")
print(f"Уже подписаны: {result['total_already_subscribed']}")
print(f"Ошибки: {result['total_errors']}")
```

---

## Интеграция с существующей системой

### CalendarSubscription модель
Используется существующая модель без изменений:
- `can_edit` - право на редактирование событий
- `can_manage` - право на управление календарем
- `is_visible` - видимость календаря для пользователя

### Notifications система
Интегрируется с существующей системой уведомлений через модель `Notification`:
- Тип: `calendar_invitation`
- Связь с календарем через `related_object_id`

### Cache invalidation
Автоматически инвалидирует кеш подписок через `invalidate_subscription_cache(user_id=...)` после создания подписки.

---

## Следующие шаги

### Рекомендуемые улучшения:

1. **Frontend UI**:
   - Модальное окно для управления участниками календаря
   - Поиск пользователей с автодополнением
   - Список текущих участников с управлением правами
   - Индикация отправленных приглашений

2. **Email уведомления**:
   - Отправка email при приглашении (опционально)
   - Ссылка для быстрого перехода к календарю

3. **Система приглашений с подтверждением**:
   - Создание модели `CalendarInvitation` для отслеживания статуса
   - Возможность принять/отклонить приглашение
   - Срок действия приглашения

4. **Роли участников**:
   - Расширение прав: viewer, editor, admin
   - Более детальная настройка разрешений

5. **Аудит**:
   - Логирование всех приглашений
   - История изменения прав участников

---

## Тестирование

### Ручное тестирование

1. Создать календарь как владелец
2. Пригласить пользователя через API `/invite/`
3. Проверить, что подписка создана с правильными правами
4. Проверить, что уведомление отправлено
5. Попытаться пригласить уже подписанного пользователя (должна быть ошибка 400)
6. Массово пригласить несколько пользователей через `/invite-bulk/`
7. Проверить результат (created, already_subscribed, errors)

### Unit тесты (TODO)

```python
# backend/calendar_app/tests/test_invitation.py

def test_invite_user_as_owner():
    """Владелец может пригласить пользователя."""
    pass

def test_invite_user_not_owner():
    """Не-владелец не может приглашать."""
    pass

def test_invite_already_subscribed():
    """Нельзя пригласить уже подписанного."""
    pass

def test_invite_bulk():
    """Массовое приглашение работает корректно."""
    pass
```

---

## Изменённые файлы

1. **backend/api/v1/calendar/serializers.py**
   - Добавлен `CalendarInviteSerializer`
   - Добавлен `CalendarInviteBulkSerializer`

2. **backend/api/v1/calendar/views.py**
   - Добавлен метод `CalendarViewSet.invite()`
   - Добавлен метод `CalendarViewSet.invite_bulk()`
   - Добавлен вспомогательный метод `_send_invitation_notification()`

3. **backend/docs/guides/CALENDAR_INVITATION_API.md** (этот файл)
   - Документация по новому API

---

## Совместимость

- ✅ Обратная совместимость с существующим API
- ✅ Работает с legacy календарями (department/employee)
- ✅ Работает с новыми календарями (Calendar entity)
- ✅ Не требует миграций БД (используются существующие модели)

---

## Заключение

Функция приглашения пользователей полностью реализована и готова к использованию. Она интегрируется с существующей архитектурой календарей и подписок, обеспечивает безопасность через проверку прав владельца, и включает систему уведомлений.

**Статус**: ✅ Готово к тестированию
**Требуется**: Frontend UI для удобного управления участниками
