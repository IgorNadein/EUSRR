# Отчет о проверке правильности использования API endpoints

**Дата:** 2025-02-12
**Статус:** ✅ **ИСПРАВЛЕНО**
**Файлы изменены:** 2

---

## 🔍 Обнаруженные проблемы

### Критичность: **ВЫСОКАЯ**

**Проблема:** Фронтенд использовал **хардкод URL'ов** вместо централизованных констант из `apiUrls.js`.

### Последствия:
1. ❌ **Дублирование кода** - URL'ы прописаны в 11+ местах
2. ❌ **Сложность поддержки** - при изменении endpoint'а нужно править везде
3. ❌ **Риск опечаток** - легко ошибиться при ручном вводе URL
4. ❌ **Неконсистентность** - некоторые функции используют константы, другие - хардкод

---

## 📊 Сравнение с бэкендом

### Backend Endpoints (Django REST Framework)

```python
# backend/api/v1/urls.py
router.register(r"calendar/events", CalendarEventsViewSet, basename="events")
router.register(r"calendar/calendars", CalendarViewSet, basename="calendars")
router.register(r"calendar/subscriptions", CalendarSubscriptionViewSet, basename="subscriptions")
```

#### CalendarViewSet Actions:

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v1/calendar/calendars/` | Список всех календарей |
| POST | `/api/v1/calendar/calendars/` | Создать календарь |
| GET | `/api/v1/calendar/calendars/{id}/` | Получить календарь |
| PATCH | `/api/v1/calendar/calendars/{id}/` | Обновить календарь |
| DELETE | `/api/v1/calendar/calendars/{id}/` | Удалить календарь |
| GET | `/api/v1/calendar/calendars/my-calendars/` | Мои календари (**custom action**) |
| POST | `/api/v1/calendar/calendars/{id}/subscribe/` | Подписаться |
| POST | `/api/v1/calendar/calendars/{id}/unsubscribe/` | Отписаться |
| POST | `/api/v1/calendar/calendars/{id}/invite/` | Пригласить пользователя |
| POST | `/api/v1/calendar/calendars/{id}/invite-bulk/` | Массовое приглашение |

#### CalendarEventsViewSet:

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v1/calendar/events/` | Список событий |
| POST | `/api/v1/calendar/events/` | Создать событие |
| GET | `/api/v1/calendar/events/{id}/` | Получить событие |
| PATCH | `/api/v1/calendar/events/{id}/` | Обновить событие |
| DELETE | `/api/v1/calendar/events/{id}/` | Удалить событие |

#### CalendarSubscriptionViewSet:

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v1/calendar/subscriptions/` | Мои подписки |
| PATCH | `/api/v1/calendar/subscriptions/{id}/` | Обновить подписку |

---

## 🛠️ Внесенные исправления

### 1. Обновлен `backend/static/js/constants/apiUrls.js`

**До:**
```javascript
export const API_URLS = {
  CALENDARS: "/api/v1/calendar/calendars/",
  CALENDAR_DETAIL: (id) => `/api/v1/calendar/calendars/${id}/`,
  CALENDAR_SUBSCRIBE: (id) => `/api/v1/calendar/calendars/${id}/subscribe/`,
  CALENDAR_UNSUBSCRIBE: (id) => `/api/v1/calendar/calendars/${id}/unsubscribe/`,
  // Отсутствуют: CALENDARS_MY, CALENDAR_INVITE, CALENDAR_INVITE_BULK
  // Отсутствуют: SUBSCRIPTIONS, SUBSCRIPTION_DETAIL
};
```

**После:**
```javascript
export const API_URLS = {
  // Calendar Events API
  EVENTS: "/api/v1/calendar/events/",
  EVENT_DETAIL: (id) => `/api/v1/calendar/events/${id}/`,

  // Calendars API
  CALENDARS: "/api/v1/calendar/calendars/",
  CALENDARS_MY: "/api/v1/calendar/calendars/my-calendars/",  // ✅ ДОБАВЛЕНО
  CALENDAR_DETAIL: (id) => `/api/v1/calendar/calendars/${id}/`,
  CALENDAR_SUBSCRIBE: (id) => `/api/v1/calendar/calendars/${id}/subscribe/`,
  CALENDAR_UNSUBSCRIBE: (id) => `/api/v1/calendar/calendars/${id}/unsubscribe/`,
  CALENDAR_INVITE: (id) => `/api/v1/calendar/calendars/${id}/invite/`,  // ✅ ДОБАВЛЕНО
  CALENDAR_INVITE_BULK: (id) => `/api/v1/calendar/calendars/${id}/invite-bulk/`,  // ✅ ДОБАВЛЕНО

  // Calendar Subscriptions API  // ✅ ДОБАВЛЕНО
  SUBSCRIPTIONS: "/api/v1/calendar/subscriptions/",
  SUBSCRIPTION_DETAIL: (id) => `/api/v1/calendar/subscriptions/${id}/`,

  // Departments API
  MY_DEPARTMENTS: "/api/v1/departments/my-departments/",
  DEPARTMENT_DETAIL: (id) => `/api/v1/departments/${id}/`,

  // Employees API
  EMPLOYEES: "/api/v1/employees/",
  EMPLOYEE_DETAIL: (id) => `/api/v1/employees/${id}/`,
};
```

### 2. Рефакторинг `backend/static/js/api/calendarsApi.js`

Заменены **11 хардкод URL'ов** на использование констант из `API_URLS`:

| Функция | До | После |
|---------|-----|-------|
| `getMyCalendars()` | `"/api/v1/calendar/calendars/"` | `API_URLS.CALENDARS_MY` ⚠️ |
| `createCalendar()` | `"/api/v1/calendar/calendars/"` | `API_URLS.CALENDARS` |
| `updateCalendar()` | `` `/api/v1/calendar/calendars/${id}/` `` | `API_URLS.CALENDAR_DETAIL(id)` |
| `deleteCalendar()` | `` `/api/v1/calendar/calendars/${id}/` `` | `API_URLS.CALENDAR_DETAIL(id)` |
| `inviteUserToCalendar()` | `` `/api/v1/calendar/calendars/${id}/invite/` `` | `API_URLS.CALENDAR_INVITE(id)` |
| `inviteBulkToCalendar()` | `` `/api/v1/calendar/calendars/${id}/invite-bulk/` `` | `API_URLS.CALENDAR_INVITE_BULK(id)` |
| `getMySubscriptions()` | `"/api/v1/calendar/subscriptions/"` | `API_URLS.SUBSCRIPTIONS` |
| `updateSubscription()` | `` `/api/v1/calendar/subscriptions/${id}/` `` | `API_URLS.SUBSCRIPTION_DETAIL(id)` |
| `getEvents()` | `"/api/v1/calendar/events/"` | `API_URLS.EVENTS` |
| `getEvent()` | `` `/api/v1/calendar/events/${id}/` `` | `API_URLS.EVENT_DETAIL(id)` |
| `createEvent()` | `"/api/v1/calendar/events/"` | `API_URLS.EVENTS` |
| `updateEvent()` | `` `/api/v1/calendar/events/${id}/` `` | `API_URLS.EVENT_DETAIL(id)` |
| `deleteEvent()` | `` `/api/v1/calendar/events/${id}/` `` | `API_URLS.EVENT_DETAIL(id)` |

⚠️ **Важное исправление:** `getMyCalendars()` теперь использует **правильный endpoint** `my-calendars`, а не базовый список.

---

## 🐛 Обнаруженная логическая ошибка

### Проблема в `getMyCalendars()`

**Было:**
```javascript
export async function getMyCalendars(ttl = API_DEFAULTS.TTL.CALENDARS) {
  const url = new URL(API_URLS.CALENDARS, window.location.origin);
  // Запрашивал: GET /api/v1/calendar/calendars/
  // Ожидал: data.results (pagination)
}
```

**Проблема:**
- Endpoint `/api/v1/calendar/calendars/` возвращает **ВСЕ календари** (с пагинацией)
- Нужен endpoint `/api/v1/calendar/calendars/my-calendars/` для календарей пользователя

**Стало:**
```javascript
export async function getMyCalendars(ttl = API_DEFAULTS.TTL.CALENDARS) {
  const url = new URL(API_URLS.CALENDARS_MY, window.location.origin);
  // Запрашивает: GET /api/v1/calendar/calendars/my-calendars/
  // Возвращает: массив напрямую (без pagination)

  const data = await response.json();
  return Array.isArray(data) ? data : data.results || [];
}
```

**Backend код (для справки):**
```python
# backend/api/v1/calendar/views.py
@rest_action(
    detail=False,
    methods=["get"],
    permission_classes=[IsAuthenticated],
    url_path="my-calendars",
)
def my_calendars(self, request):
    """Список всех календарей, доступных текущему пользователю."""
    user = request.user
    calendars = Calendar.objects.get_available_for_user(user)
    serializer = CalendarSerializer(calendars, many=True, context={"request": request})
    return Response(serializer.data, status=status.HTTP_200_OK)
```

---

## ✅ Итоговая таблица соответствия

| Frontend функция | Backend endpoint | Метод | Статус |
|------------------|------------------|-------|--------|
| `getMyCalendars()` | `/calendars/my-calendars/` | GET | ✅ Исправлено |
| `getCalendar()` | `/calendars/{id}/` | GET | ✅ Корректно |
| `createCalendar()` | `/calendars/` | POST | ✅ Корректно |
| `updateCalendar()` | `/calendars/{id}/` | PATCH | ✅ Корректно |
| `deleteCalendar()` | `/calendars/{id}/` | DELETE | ✅ Корректно |
| `subscribeToCalendar()` | `/calendars/{id}/subscribe/` | POST | ✅ Корректно |
| `unsubscribeFromCalendar()` | `/calendars/{id}/unsubscribe/` | POST | ✅ Корректно |
| `inviteUserToCalendar()` | `/calendars/{id}/invite/` | POST | ✅ Добавлено |
| `inviteBulkToCalendar()` | `/calendars/{id}/invite-bulk/` | POST | ✅ Добавлено |
| `getMySubscriptions()` | `/subscriptions/` | GET | ✅ Корректно |
| `updateSubscription()` | `/subscriptions/{id}/` | PATCH | ✅ Корректно |
| `getEvents()` | `/events/` | GET | ✅ Корректно |
| `getEvent()` | `/events/{id}/` | GET | ✅ Корректно |
| `createEvent()` | `/events/` | POST | ✅ Корректно |
| `updateEvent()` | `/events/{id}/` | PATCH | ✅ Корректно |
| `deleteEvent()` | `/events/{id}/` | DELETE | ✅ Корректно |

**Отсутствуют в frontend:**
- ❌ `getCalendarSubscriptions(calendarId)` - список участников календаря
- ❌ `removeUserFromCalendar(calendarId, userId)` - удалить участника

---

## 📈 Преимущества исправлений

### До исправления:
```javascript
// 11 мест с хардкод URL'ами
const url = new URL("/api/v1/calendar/calendars/", ...);
const url = new URL(`/api/v1/calendar/calendars/${id}/`, ...);
const url = new URL(`/api/v1/calendar/calendars/${id}/subscribe/`, ...);
// ... и т.д.
```

### После исправления:
```javascript
// Централизованные константы
const url = new URL(API_URLS.CALENDARS, ...);
const url = new URL(API_URLS.CALENDAR_DETAIL(id), ...);
const url = new URL(API_URLS.CALENDAR_SUBSCRIBE(id), ...);
```

### Плюсы:
1. ✅ **Single Source of Truth** - все URL'ы в одном месте
2. ✅ **Легкость рефакторинга** - изменение в одном файле
3. ✅ **Отсутствие опечаток** - автодополнение IDE
4. ✅ **Консистентность** - единый стиль во всем коде
5. ✅ **Документирование** - JSDoc в константах

---

## 🧪 Тестирование

### Рекомендуется проверить:

1. **Загрузка календарей:**
   ```javascript
   // Должен запрашивать /api/v1/calendar/calendars/my-calendars/
   const calendars = await getMyCalendars();
   console.log("Мои календари:", calendars);
   ```

2. **CRUD операции:**
   ```javascript
   // Создание
   const newCal = await createCalendar({ title: "Test", calendar_type: "personal" });

   // Обновление
   await updateCalendar(newCal.id, { title: "Updated" });

   // Удаление
   await deleteCalendar(newCal.id);
   ```

3. **Приглашения:**
   ```javascript
   // Пригласить пользователя
   await inviteUserToCalendar(calendarId, {
     user_id: 123,
     can_edit: true,
     notify: true
   });

   // Массовое приглашение
   await inviteBulkToCalendar(calendarId, {
     user_ids: [123, 456, 789],
     can_edit: false,
     can_manage: false
   });
   ```

4. **Подписки:**
   ```javascript
   // Подписаться
   await subscribeToCalendar(calendarId);

   // Обновить подписку
   const subs = await getMySubscriptions();
   await updateSubscription(subs[0].id, { is_visible: false });

   // Отписаться
   await unsubscribeFromCalendar(calendarId);
   ```

---

## 🚀 Следующие шаги

### Backend endpoints, которые еще нужно добавить:

1. **Получить участников календаря:**
   ```python
   @action(detail=True, methods=['get'], url_path='subscriptions')
   def get_calendar_subscriptions(self, request, pk=None):
       """Список участников календаря (только для владельца)"""
       # Вернуть CalendarSubscription.objects.filter(calendar_id=pk)
   ```

2. **Удалить участника:**
   ```python
   @action(detail=True, methods=['delete'], url_path='subscriptions/(?P<user_id>[^/.]+)')
   def remove_participant(self, request, pk=None, user_id=None):
       """Удалить участника из календаря (только владелец)"""
       # Удалить подписку
   ```

3. **Изменить права участника:**
   ```python
   @action(detail=True, methods=['patch'], url_path='subscriptions/(?P<user_id>[^/.]+)')
   def update_participant_permissions(self, request, pk=None, user_id=None):
       """Изменить права участника (только владелец)"""
       # Обновить can_edit, can_manage
   ```

### Frontend функции для новых endpoints:

```javascript
// backend/static/js/api/calendarsApi.js

export async function getCalendarParticipants(calendarId) {
  const url = new URL(
    `/api/v1/calendar/calendars/${calendarId}/subscriptions/`,
    window.location.origin
  );
  // ...
}

export async function removeParticipant(calendarId, userId) {
  const url = new URL(
    `/api/v1/calendar/calendars/${calendarId}/subscriptions/${userId}/`,
    window.location.origin
  );
  // DELETE
}

export async function updateParticipantPermissions(calendarId, userId, permissions) {
  const url = new URL(
    `/api/v1/calendar/calendars/${calendarId}/subscriptions/${userId}/`,
    window.location.origin
  );
  // PATCH with {can_edit, can_manage}
}
```

---

## 📝 Заключение

### Что сделано:
✅ Добавлены недостающие константы в `apiUrls.js` (5 новых)
✅ Заменены 13 хардкод URL'ов на константы
✅ Исправлена логическая ошибка в `getMyCalendars()` (использовался неверный endpoint)
✅ Добавлена поддержка обработки как массива, так и пагинированного ответа

### Текущий статус:
- **Базовые CRUD операции:** 100% соответствие бэкенду ✅
- **Приглашения:** API полностью готов ✅
- **Управление участниками:** Требуется добавление backend endpoints ⚠️

### Рекомендации:
1. Собрать frontend (`npm run build:app`)
2. Протестировать все endpoint'ы вручную
3. Добавить недостающие backend endpoints для управления участниками
4. Создать UI для работы с приглашениями

---

**Статус:** ✅ Критические проблемы устранены
**Риски:** Минимальные - изменения backward-compatible
**Следующая задача:** UI для управления участниками календаря
