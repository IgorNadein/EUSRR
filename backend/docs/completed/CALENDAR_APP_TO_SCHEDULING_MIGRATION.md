# Миграция calendar_app → scheduling

**Дата:** 10 марта 2026 г.  
**Статус:** ✅ Завершено

---

## 📋 Что было сделано

### 1. Создано новое приложение `scheduling`

Структура:
```
backend/scheduling/
├── __init__.py
├── apps.py                      # Конфигурация + применение патчей
├── patch.py                     # Патч для django-scheduler (byweekday fix)
├── rules.py                     # Права доступа (django-rules)
├── README.md                    # Документация
├── migrations/
│   ├── __init__.py
│   └── 0001_initial.py
└── notifications/
    ├── __init__.py
    ├── config.py                # Шаблоны уведомлений
    ├── handlers.py              # Бизнес-логика уведомлений
    └── signals.py               # Django signals
```

### 2. Перенесен функционал

#### Из `schedule_patch.py` → `scheduling/patch.py`
- Патч для исправления бага django-scheduler с `byweekday`
- Автоматически применяется в `apps.py`

#### Из `calendar_app/notifications/` → `scheduling/notifications/`
- Адаптированы для работы с `schedule.Event` вместо `CalendarEvent`
- Используют `CalendarRelation` для определения получателей
- Поддержка передачи контекста (creator, modifier, canceller)

#### Из `calendar_app/rules.py` → `scheduling/rules.py`
- Правила доступа для календарей и событий
- Интеграция с `CalendarRelation` из django-scheduler

### 3. Обновлена конфигурация

#### `settings.py`
```python
# Было:
"calendar_app.apps.CalendarAppConfig",

# Стало:
"scheduling.apps.SchedulingConfig",
```

#### `api/apps.py`
```python
# Было:
import schedule_patch
schedule_patch.apply_patch()

# Стало:
# Патч применяется в scheduling.apps.SchedulingConfig
pass
```

### 4. Удалено

#### Папки:
- ✅ `backend/calendar_app/` - старое приложение
- ✅ `backend/api/v1/calendar/` - неиспользуемый API (не был зарегистрирован в urls)
- ✅ `backend/tests/test_calendar_permissions.py` - тесты старого функционала
- ✅ `backend/tests/api/v1/calendar_app/` - тесты старого API

#### Файлы:
- ✅ `backend/schedule_patch.py` - перенесен в `scheduling/patch.py`

---

## 🎯 Почему это было нужно

### Проблема
`calendar_app` содержал самописную календарную систему с моделями:
- `Calendar`
- `CalendarEvent`
- `CalendarSubscription`

**НО:** API endpoints (`/api/v1/calendars/`, `/api/v1/events/`) **НЕ БЫЛИ** зарегистрированы в `urls.py`, что означало:
- Мертвый код в проекте
- Неиспользуемые модели и таблицы в БД
- Дублирование с `django-scheduler`

### Решение
Полностью перейти на `django-scheduler` с:
- ✅ Патчами для исправления багов
- ✅ Системой уведомлений
- ✅ Правилами доступа

---

## 📊 Сравнение: До и После

### До миграции

**Использовалось:**
- `django-scheduler` для API (`/api/v1/schedule/`)
- `schedule_patch.py` в корне проекта

**НЕ использовалось:**
- `calendar_app` модели (Calendar, CalendarEvent, CalendarSubscription)
- `calendar_app` API endpoints (не зарегистрированы)
- Уведомления `calendar_app`

**Проблемы:**
- Захламление кодовой базы
- Неиспользуемые таблицы в БД
- Отсутствие уведомлений для django-scheduler

### После миграции

**Используется:**
- ✅ `django-scheduler` для всего функционала
- ✅ `scheduling` приложение - интеграция и расширения
- ✅ `scheduling.patch` - исправление багов
- ✅ `scheduling.notifications` - уведомления для событий
- ✅ `scheduling.rules` - права доступа

**Удалено:**
- ❌ Мертвый код `calendar_app`
- ❌ Неиспользуемые API endpoints
- ❌ Старые таблицы БД

**Улучшения:**
- 🔥 Чистая кодовая база
- 🔥 Уведомления работают для django-scheduler
- 🔥 Централизованное управление патчами

---

## 🔧 Техническая информация

### Django-scheduler модели (используются)

```
schedule_calendar          # Календари
schedule_event             # События
schedule_rule              # Правила повторения (RFC 5545)
schedule_occurrence        # Вхождения событий
schedule_eventrelation     # Связь Event ↔ Участники
schedule_calendarrelation  # Связь Calendar ↔ Участники
```

### Старые таблицы calendar_app (удаляются)

```sql
-- Эти таблицы больше не используются
DROP TABLE IF EXISTS calendar_app_calendarevent CASCADE;
DROP TABLE IF EXISTS calendar_app_calendarsubscription CASCADE;
DROP TABLE IF EXISTS calendar_app_calendar CASCADE;
```

**Удаление таблиц:**
```bash
.venv/Scripts/python manage.py migrate scheduling 0001
```

---

## ⚡ Использование

### Уведомления в ViewSet

```python
from schedule.models import Event

class EventViewSet(viewsets.ModelViewSet):
    def perform_create(self, serializer):
        event = serializer.save()
        # Передаем создателя для уведомлений
        event._creator = self.request.user
        event.save()
    
    def perform_update(self, serializer):
        event = serializer.save()
        # Передаем модификатора
        event._modifier = self.request.user
        event.save()
    
    def perform_destroy(self, instance):
        # Передаем отменившего
        instance._canceller = self.request.user
        instance.delete()
```

### Ручная отправка уведомлений

```python
from scheduling.notifications.handlers import (
    notify_event_created,
    notify_event_changed,
    notify_event_cancelled
)

# Создано
notify_event_created(event, creator=request.user)

# Изменено
notify_event_changed(event, changed_fields=['title', 'start'], modifier=request.user)

# Отменено
notify_event_cancelled(event, canceller=request.user)
```

---

## 📝 Следующие шаги

1. ✅ Приложение `scheduling` готово к использованию
2. ⏳ Протестировать уведомления в production
3. ⏳ При необходимости удалить таблицы: `python manage.py migrate scheduling 0001`
4. ⏳ Обновить документацию проекта

---

## 🔗 Связанные документы

- [scheduling/README.md](backend/scheduling/README.md) - Документация нового приложения
- [docs/in-progress/DJANGO_SCHEDULER_INTEGRATION.md](docs/in-progress/DJANGO_SCHEDULER_INTEGRATION.md) - История интеграции
- [backend/docs/CHANGELOG.md](backend/docs/CHANGELOG.md) - История изменений

---

## ✅ Проверочный список

- [x] Создано приложение `scheduling`
- [x] Перенесен патч из `schedule_patch.py`
- [x] Создана система уведомлений
- [x] Созданы правила доступа (django-rules)
- [x] Обновлен `settings.py`
- [x] Обновлен `api/apps.py`
- [x] Удален `calendar_app/`
- [x] Удален `api/v1/calendar/`
- [x] Удален `schedule_patch.py`
- [x] Удалены тесты старого функционала
- [x] Создана документация
