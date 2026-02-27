# Исправление прав доступа для глобальных календарей

**Дата:** 23 февраля 2026 г.
**Статус:** ✅ Выполнено

## Проблема

Обычные пользователи не могли создавать события в глобальных календарях (новая архитектура), даже если у них были соответствующие права через подписку (`can_edit=True`) или если календарь имел `default_can_edit=True`.

### Причина

Метод `get_permissions()` в `CalendarEventsViewSet` проверял права только для **legacy логики** (department/employee), но **не учитывал новую архитектуру** с `calendar_id`:

```python
# Старая логика (ОШИБКА):
def get_permissions(self):
    emp = self._employee_id(required=False)
    dep = self._dept_id(required=False)

    # Календарь компании — только администраторы
    if dep is None:  # ❌ Срабатывало для глобальных календарей!
        return [IsAdminUser()]
```

Когда пользователь создавал событие в глобальном календаре:
1. `calendar_id` передавался в теле запроса
2. `get_permissions()` НЕ видел `calendar_id` (смотрел только URL/query параметры)
3. Видел `dep = None`, `emp = None`
4. Считал это legacy календарём компании
5. Блокировал всех, кроме администраторов

## Решение

Переписан метод `get_permissions()` с поддержкой новой архитектуры календарей:

### Новая логика проверки прав

1. **Приоритет новой архитектуры:** Сначала проверяется наличие `calendar_id`
2. **Проверка через модель Calendar:** Используется метод `calendar.can_user_edit(user)`
3. **Fallback на legacy:** Если `calendar_id` не указан, используется старая логика

### Класс CalendarEditPermission

```python
class CalendarEditPermission(BasePermission):
    """Проверка прав редактирования через календари."""

    def has_permission(self, request, view):
        # Ищем calendar_id в:
        # 1. Теле запроса (create)
        # 2. Query параметрах
        # 3. Объекте события (update/delete)

        if calendar_id is not None:
            calendar = Calendar.objects.get(id=int(calendar_id))
            return calendar.can_user_edit(request.user)

        return None  # Переход к legacy логике
```

### Метод calendar.can_user_edit()

Проверяет права в следующем порядке:
1. Админы/staff → ✅ Всегда могут
2. Владелец календаря → ✅ Всегда может
3. Подписка с `can_edit=True` → ✅ Может
4. Иначе → ❌ Не может

## Изменённые файлы

- `backend/api/v1/calendar/views.py`
  - Метод `CalendarEventsViewSet.get_permissions()` — добавлена проверка новой архитектуры
  - Класс `CalendarEditPermission` — новый permission для календарей

## Как это работает теперь

### Сценарий 1: Глобальный календарь с default_can_edit=True

```python
# Создание календаря админом
calendar = Calendar.objects.create(
    title="Общие мероприятия",
    visibility=CalendarVisibility.PUBLIC,
    default_can_edit=True  # ✅ Все могут редактировать
)

# Обычный пользователь создаёт событие
POST /api/v1/calendar/events/
{
    "calendar_id": 1,
    "title": "Корпоратив",
    "start_date": "2026-03-01",
    "all_day": true
}
# ✅ Успех! Проверка через calendar.can_user_edit()
```

### Сценарий 2: Глобальный календарь с подпиской

```python
# Админ приглашает пользователя
calendar.subscriptions.create(
    user=user,
    can_edit=True  # ✅ Даём право редактировать
)

# Пользователь создаёт событие
POST /api/v1/calendar/events/
{
    "calendar_id": 1,
    "title": "Важная встреча",
    "start_date": "2026-03-05",
    "all_day": true
}
# ✅ Успех! can_edit=True в подписке
```

### Сценарий 3: Legacy календарь компании

```python
# Без calendar_id — старая логика
POST /api/v1/calendar/events/
{
    "title": "Собрание компании",
    "start_date": "2026-03-10",
    "all_day": true
}
# ❌ Требуется IsAdminUser (как и раньше)
```

## Обратная совместимость

✅ **Полностью сохранена:**
- Legacy календари (без `calendar_id`) работают по-прежнему
- Календари отделов требуют `MANAGE_CALENDAR` permission
- Личные календари доступны только владельцу

## Тестирование

### Рекомендуемые тесты:

1. **Глобальный календарь + default_can_edit=True:**
   - Обычный пользователь создаёт событие → ✅ Успех

2. **Глобальный календарь + подписка с can_edit=True:**
   - Подписанный пользователь создаёт событие → ✅ Успех
   - Неподписанный пользователь → ❌ Отказ

3. **Глобальный календарь + подписка с can_edit=False:**
   - Подписанный пользователь создаёт событие → ❌ Отказ

4. **Legacy календарь компании:**
   - Обычный пользователь → ❌ Отказ
   - Админ → ✅ Успех

5. **Update/Delete:**
   - Проверка прав через `event.calendar.can_user_edit()`

## Дополнительные улучшения

### Возможные расширения:

1. **Кеширование проверок прав** (если календарей много)
2. **Логирование отказов** для аудита
3. **Rate limiting** для создания событий
4. **Webhook уведомления** о создании событий

## Связанные файлы

- `backend/calendar_app/models.py` — модели `Calendar`, `CalendarSubscription`
- `backend/api/v1/calendar/serializers.py` — сериализаторы календарей
- `backend/api/v1/calendar/views.py` — ViewSet для событий и календарей

## Примечания

- Проверка прав происходит **до** валидации сериализатора
- Для update/delete используется тот же механизм через `get_object()`
- Админы и staff **всегда** имеют полный доступ

---

**Автор:** GitHub Copilot
**Проверено:** Требуется тестирование
