# Исправление снятия выбора календарей компании

**Дата:** 12 февраля 2026 г.
**Тип:** Исправление бага
**Компонент:** Менеджер календарей (calendarManager.js)

## Проблема

При попытке снять выбор (скрыть) календарь компании возникала ошибка **403 Forbidden**:

```
PATCH http://localhost:9000/api/v1/calendar/subscriptions/8/ 403 (Forbidden)
Error: Только владелец календаря может изменять права подписки.
```

### Причина

Система пыталась обновить подписку (`subscription`) через API для **всех новых календарей**, включая календари компании, к которым пользователь не имеет прав редактирования.

**Логика была:**
- Legacy календари → localStorage ✅
- Новые календари → API (updateSubscription) ❌

**Проблема:** Календари компании (`scope: 'company'`) имеют подписки, но пользователь **не владелец** и не может изменять их через API.

## Решение

Изменена логика определения способа сохранения видимости календаря. Теперь проверяется не только `is_legacy`, но и **права редактирования** (`user_can_edit`):

### До исправления:

```javascript
if (calendar?.is_legacy) {
  // localStorage
} else {
  // API (updateSubscription) - ОШИБКА для календарей компании!
}
```

### После исправления:

```javascript
const canUseAPI = calendar && !calendar.is_legacy && calendar.user_can_edit;

if (!canUseAPI) {
  // localStorage - для legacy ИЛИ без прав редактирования
  localStorage.setItem(`calendar_visible_${calendarId}`, String(isVisible));
} else {
  // API - только для календарей с правами редактирования
  await updateSubscription(subscription.id, { is_visible: isVisible });
}
```

## Изменения в коде

### 1. Функция `toggleCalendarVisibility()`

**Файл:** `backend/static/js/components/calendarManager.js`

**Было:**
```javascript
if (calendar?.is_legacy) {
  // localStorage
} else {
  // API
}
```

**Стало:**
```javascript
const canUseAPI = calendar && !calendar.is_legacy && calendar.user_can_edit;

if (!canUseAPI) {
  // localStorage для legacy ИЛИ календарей без прав редактирования
  localStorage.setItem(`calendar_visible_${calendarId}`, String(isVisible));
} else {
  // API только для календарей с правами редактирования
  await updateSubscription(subscription.id, { is_visible: isVisible });
}
```

### 2. Функция `loadCalendars()` - загрузка видимости

**Было:**
```javascript
if (cal.is_legacy) {
  // Читать из localStorage
} else {
  // Читать из подписок
}
```

**Стало:**
```javascript
if (cal.is_legacy || !cal.user_can_edit) {
  // Читать из localStorage для legacy ИЛИ без прав редактирования
  const stored = localStorage.getItem(`calendar_visible_${cal.id}`);
  isVisible = stored === null ? true : stored === "true";
} else {
  // Читать из подписок для календарей с правами редактирования
  const subscription = subscriptions.find((s) => s.calendar === cal.id);
  isVisible = subscription ? subscription.is_visible : true;
}
```

## Логика работы

### Типы календарей и методы сохранения видимости:

| Тип календаря | `is_legacy` | `user_can_edit` | Метод сохранения |
|---------------|-------------|-----------------|------------------|
| Legacy компания | ✅ true | ❌ false | **localStorage** |
| Legacy личный | ✅ true | ✅ true | **localStorage** |
| Legacy отдел | ✅ true | ❌ false | **localStorage** |
| Новый компании (не владелец) | ❌ false | ❌ false | **localStorage** ✅ |
| Новый компании (владелец) | ❌ false | ✅ true | **API** |
| Новый личный (владелец) | ❌ false | ✅ true | **API** |
| Новый отдела (не владелец) | ❌ false | ❌ false | **localStorage** ✅ |
| Новый отдела (владелец/админ) | ❌ false | ✅ true | **API** |

### Ключевое изменение:

**Раньше:** Все новые календари пытались использовать API
**Теперь:** Только календари с `user_can_edit: true` используют API

## Результат

✅ **Календари компании можно скрывать/показывать** без ошибок
✅ **Видимость сохраняется в localStorage** для календарей без прав редактирования
✅ **API используется только** для календарей, где пользователь имеет права
✅ **Fallback на localStorage** работает при ошибках API

## Технические детали

### Почему нельзя изменять подписки через API?

Backend API `/api/v1/calendar/subscriptions/{id}/` имеет ограничение:

```python
# Только владелец календаря может изменять права подписки
if subscription.calendar.owner_user_id != request.user.id:
    return Response(
        {"detail": "Только владелец календаря может изменять права подписки."},
        status=status.HTTP_403_FORBIDDEN
    )
```

Это правильная логика безопасности - обычные пользователи не должны изменять подписки других пользователей.

### Почему localStorage - правильное решение?

Видимость календаря (`is_visible`) - это **локальная настройка UI** конкретного пользователя:
- Не влияет на других пользователей
- Не требует синхронизации между устройствами
- Не нуждается в серверном хранении для календарей без прав редактирования

Для календарей, где пользователь **владелец**, имеет смысл использовать API, чтобы:
- Синхронизировать настройки между устройствами
- Сохранять как часть профиля пользователя

## Тестирование

После исправления проверьте:

1. ✅ Создайте календарь компании (как админ)
2. ✅ Зайдите как обычный пользователь
3. ✅ Попробуйте скрыть календарь компании
4. ✅ Убедитесь, что нет ошибки 403
5. ✅ Обновите страницу - видимость должна сохраниться
6. ✅ Проверьте, что ваш личный календарь по-прежнему использует API

## Связанные файлы

- `backend/static/js/components/calendarManager.js` - основная логика
- `backend/static/js/api/calendarsApi.js` - API функции
- Backend: `backend/calendar_app/views.py` - API endpoint с проверкой прав
