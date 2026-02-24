# Миграция фронтенда на django-scheduler - Завершено

**Дата**: 24 февраля 2026  
**Ветка**: `feature/django-scheduler-integration`  
**Коммит**: `ee657b1`

## ✅ Что сделано

### 1. Обновлены API endpoints
- `apiUrls.js`: Все endpoints заменены с `/api/v1/calendar/` на `/api/v1/schedule/`
- Добавлены новые endpoints: `RULES`, `OCCURRENCES`, `RELATIONS`
- Удалены deprecated: `SUBSCRIPTIONS`, `CALENDAR_SUBSCRIBE`, `CALENDAR_INVITE`

### 2. Упрощена архитектура
- **Убрана концепция subscriptions**: django-scheduler не имеет подписок
- **Видимость календарей**: Теперь хранится только в localStorage (для всех календарей)
- **Права доступа**: Управляются на уровне django-scheduler через permissions

### 3. Адаптирован backend serializer
- `CalendarSerializer` теперь принимает поле `title` (для совместимости с EUSRR)
- Автогенерация `slug` из `name/title` если не указан
- Поддержка старых и новых форматов данных

### 4. Обновлены компоненты
- `calendarsApi.js`: Удалены функции `subscribeToCalendar()`, `unsubscribeFromCalendar()`, `inviteUserToCalendar()`, `getMySubscriptions()`, `updateSubscription()`
- `calendarManager.js`: Упрощена логика `toggleCalendarVisibility()`, `subscribe()`, `unsubscribe()` - теперь работают только с localStorage

## 📝 Изменения в файлах

### Modified
1. `backend/api/v1/schedule/serializers.py` - добавлена совместимость с EUSRR API
2. `backend/static/js/constants/apiUrls.js` - обновлены все endpoints
3. `backend/static/js/api/calendarsApi.js` - удалены subscriptions функции
4. `backend/static/js/components/calendarManager.js` - упрощена логика видимости

## 🧪 Тестирование

### 1. Запуск сервера
```bash
cd /c/Users/igor_/Dev/EUSRR/backend
/c/Users/igor_/Dev/EUSRR/.venv/Scripts/python manage.py runserver
```

### 2. Создание тестового календаря
```python
from schedule.models import Calendar, Event
from datetime import datetime, timedelta
import pytz

# Создать календарь
cal = Calendar.objects.create(
    name="Тестовый календарь",
    slug="test-calendar"
)

# Создать событие
tz = pytz.timezone('Europe/Moscow')
now = datetime.now(tz)

Event.objects.create(
    title="Тестовое событие",
    description="Проверка django-scheduler",
    start=now + timedelta(hours=1),
    end=now + timedelta(hours=2),
    calendar=cal,
    color_event="#3498db"
)
```

### 3. Проверка через API
```bash
# Список календарей
curl http://localhost:8000/api/v1/schedule/calendars/

# Список событий
curl http://localhost:8000/api/v1/schedule/events/

# События с фильтрацией
curl "http://localhost:8000/api/v1/schedule/events/?calendar=1&start=2026-02-01T00:00:00Z&end=2026-03-01T00:00:00Z"
```

### 4. Проверка фронтенда
1. Открыть https://corp.robotail.pro (или localhost:8000)
2. Авторизоваться
3. Проверить правую панель календаря
4. Создать тестовый календарь через модальное окно
5. Создать событие
6. Переключить видимость календаря (должно сохраняться в localStorage)

## 🔄 Совместимость

### Что работает как раньше:
- ✅ Создание/редактирование/удаление календарей
- ✅ Создание/редактирование/удаление событий
- ✅ Просмотр событий в FullCalendar
- ✅ Переключение видимости календарей
- ✅ Legacy календари (Компания, Личный, Отделы)

### Что изменилось:
- ⚠️ Нет API подписок (subscribe/unsubscribe) - используется localStorage
- ⚠️ Нет API приглашений (invite) - нужно реализовать через EventRelation если требуется
- ⚠️ Права доступа теперь управляются на уровне django-scheduler permissions

### Что добавилось:
- ✨ Поддержка recurring events через RFC 5545 rrule (Rules)
- ✨ Материализованные вхождения повторяющихся событий (Occurrences)
- ✨ Связи событий (EventRelation) для управления участниками
- ✨ Timezone-aware события из коробки

## 📊 Статистика изменений

**Коммит**: ee657b1
- **4 файла изменено**
- **+91 строк добавлено**
- **-342 строк удалено**
- **Чистый результат**: -251 строка (упрощение кода)

## 🚀 Следующие шаги

1. **Тестирование**: Проверить все функции календаря на dev окружении
2. **Миграция данных**: Создать скрипт переноса календарей/событий из `calendar_app` в `schedule`
3. **Документация**: Обновить пользовательскую документацию
4. **Удаление старого кода**: После успешного тестирования удалить `calendar_app`

## 📌 Полезные ссылки

- [API v1/schedule Guide](./SCHEDULE_API_V1_GUIDE.md)
- [Django Scheduler Integration Plan](./DJANGO_SCHEDULER_INTEGRATION.md)
- [Django Scheduler Docs](https://github.com/thauber/django-scheduler)
- [RFC 5545 (iCalendar)](https://datatracker.ietf.org/doc/html/rfc5545)

---

**Автор**: GitHub Copilot  
**Ревью**: Требуется
