# Исправление прав доступа к подпискам календаря

**Дата**: 12 февраля 2026
**Проблема**: 403 Forbidden при попытке переключения видимости календаря
**Статус**: ✅ Исправлено и протестировано

## Описание проблемы

Пользователи получали ошибку `403 Forbidden` при попытке изменить видимость календаря в интерфейсе:

```
PATCH http://localhost:9000/api/v1/calendar/subscriptions/7/ 403 (Forbidden)
Ошибка: "Только владелец календаря может изменять права подписки."
```

### Причина

Метод `perform_update()` в `CalendarSubscriptionViewSet` требовал права владельца календаря для **любых** изменений подписки, включая личные настройки (видимость, цвет).

## Решение

### 1. Разделение типов полей

Разделили поля подписки на две категории:

- **Права доступа** (`can_edit`, `can_manage`) - только владелец календаря
- **Личные настройки** (`is_visible`, `color_override`) - владелец подписки или владелец календаря

### 2. Изменения в `CalendarSubscriptionViewSet.perform_update()`

**Файл**: `backend/api/v1/calendar/views.py`

```python
def perform_update(self, serializer):
    subscription = self.get_object()
    user = self.request.user
    validated_data = serializer.validated_data

    permission_fields = {'can_edit', 'can_manage'}
    personal_fields = {'is_visible', 'color_override'}

    changing_permissions = any(
        field in validated_data for field in permission_fields
    )
    changing_personal = any(
        field in validated_data for field in personal_fields
    )

    # Права - только владелец календаря
    if changing_permissions and not subscription.calendar.is_owner(user):
        raise PermissionDenied(
            "Только владелец календаря может изменять права подписки."
        )

    # Личные настройки - владелец подписки или календаря
    is_subscription_owner = subscription.user == user
    is_calendar_owner = subscription.calendar.is_owner(user)

    if changing_personal and not is_subscription_owner:
        if not is_calendar_owner:
            raise PermissionDenied(
                "Вы можете изменять только свои личные настройки."
            )

    updated = serializer.save()
    invalidate_subscription_cache(user_id=updated.user_id)
```

### 3. Расширение `get_queryset()`

Владельцы календарей теперь видят подписки других пользователей на свои календари:

```python
def get_queryset(self):
    """Подписки пользователя + подписки на его календари."""
    from django.db.models import Q

    user = self.request.user

    if user.is_superuser or user.is_staff:
        return CalendarSubscription.objects.all()

    # Обычные пользователи видят:
    # 1. Свои подписки (user=user)
    # 2. Подписки других пользователей на календари, где они владельцы
    return CalendarSubscription.objects.filter(
        Q(user=user) |  # Свои подписки
        Q(calendar__owner_user=user)  # Владелец календаря
    ).distinct()
```

## Тестирование

### Созданы тесты

**Файл**: `backend/tests/api/v1/calendar_app/test_subscription_permissions.py`

7 новых тестов:

1. ✅ `test_owner_can_change_permissions` - владелец меняет права
2. ✅ `test_subscriber_can_change_personal_settings` - подписчик меняет видимость/цвет
3. ✅ `test_subscriber_cannot_change_permissions` - подписчик НЕ может менять права (403)
4. ✅ `test_other_user_cannot_change_subscription` - посторонний не видит подписку (404)
5. ✅ `test_owner_can_change_subscriber_personal_settings` - владелец меняет настройки подписчика
6. ✅ `test_combined_changes_by_owner` - владелец меняет всё одновременно
7. ✅ `test_subscriber_can_only_change_own_settings` - смешанное изменение запрещено (403)

### Результаты

```bash
# Тесты прав доступа
7 passed

# Все тесты календаря (регрессия)
96 passed
```

## Матрица прав доступа

| Действие | Владелец календаря | Владелец подписки | Другой пользователь |
|----------|-------------------|------------------|-------------------|
| Изменить `can_edit` / `can_manage` | ✅ | ❌ 403 | ❌ 404 |
| Изменить `is_visible` / `color_override` | ✅ | ✅ | ❌ 404 |
| Изменить оба типа полей | ✅ | ❌ 403 | ❌ 404 |

## Проверка в production

1. Войти как обычный пользователь
2. Открыть календарь, на который есть подписка
3. Переключить видимость календаря через UI
4. **Ожидаемый результат**: Видимость меняется без ошибок 403

## Связанные файлы

- `backend/api/v1/calendar/views.py` - основная логика
- `backend/tests/api/v1/calendar_app/test_subscription_permissions.py` - тесты
- `backend/static/js/calendar/calendarManager.js` - frontend (без изменений)

## Безопасность

- ✅ Посторонние пользователи получают 404 (не раскрываем существование ресурса)
- ✅ Подписчики не могут повышать свои права через API
- ✅ Владельцы календарей имеют полный контроль над подписками
- ✅ Личные настройки изолированы между пользователями
