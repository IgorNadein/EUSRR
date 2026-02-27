# Интеграция django-scheduler в calendar_app

**Ветка:** `feature/django-scheduler-integration`  
**Дата:** 24 февраля 2026  
**Статус:** В процессе

---

## 🎯 Цель

Постепенная замена самописного календаря на проверенное решение **django-scheduler** с сохранением старого кода для параллельной работы и плавной миграции.

**Принцип:** "Strangler Fig Pattern" — новая система работает параллельно, постепенно замещая старую.

---

## 📦 Что установлено

```bash
pip install django-scheduler==0.12.0  # Основной пакет
pip install icalendar==7.0.1          # RFC 5545 (iCalendar)
pip install pytz                      # Timezone support
pip install python-dateutil           # rrule parsing
```

**В settings.py добавлено:**
```python
INSTALLED_APPS = [
    # ...
    "calendar_app.apps.CalendarAppConfig",  # Старый (работает)
    "schedule",                             # Новый (django-scheduler)
    # ...
]
```

---

## 🗂️ Структура таблиц

### Старая система (calendar_app)

```
calendar_app_calendar               # Calendar модель
calendar_app_calendarevent          # CalendarEvent модель  
calendar_app_calendarsubscription   # CalendarSubscription модель
```

### Новая система (django-scheduler)

```
schedule_calendar                   # Calendar (чистая модель)
schedule_event                      # Event (с timezone + rrule)
schedule_rule                       # Rule (RFC 5545 rrule)
schedule_occurrence                 # Occurrence (материализованные вхождения)
schedule_eventrelation              # EventRelation (участники)
```

**Без конфликтов имён!** Таблицы с разными префиксами.

---

## 🔄 План параллельной работы

### Этап 1: API v2 (новый, чистый)

```python
# backend/api/v2/schedule/
├── __init__.py
├── urls.py              # /api/v2/schedule/
├── views.py             # ViewSets для django-scheduler
├── serializers.py       # DRF serializers
└── permissions.py       # Права (переиспользуем логику)
```

**URL разделение:**
- Старый (работает): `/api/v1/calendars/`, `/api/v1/events/`
- Новый (тестируем): `/api/v2/schedule/calendars/`, `/api/v2/schedule/events/`

### Этап 2: Фронтенд (параллельный)

Создать новый компонент:
```typescript
// frontend/src/components/ScheduleCalendar.tsx
// Использует /api/v2/schedule/
```

Старый компонент остаётся:
```typescript
// frontend/src/app/calendar/ (работает с /api/v1/)
```

### Этап 3: Миграция данных

```python
# management/commands/migrate_to_scheduler.py
# Копирует данные: calendar_app → schedule
```

### Этап 4: Переключение

После тестирования:
1. Переключаем фронтенд на `/api/v2/`
2. Отключаем старые URL
3. Удаляем `calendar_app` (через несколько спринтов)

---

## 📊 Сравнение моделей

| Поле | calendar_app | django-scheduler | Маппинг |
|------|--------------|------------------|---------|
| **Calendar** |
| title | ✅ | name | Прямой |
| description | ✅ | description | Прямой |
| color | ✅ | ❌ | Custom field |
| owner_user | ✅ | ❌ | Custom field |
| owner_department | ✅ | ❌ | Custom field |
| visibility | ✅ | ❌ | django-guardian ACL |
| **Event** |
| title | ✅ | title | Прямой |
| start_date + start_time | ✅ | start (DateTimeField+TZ) | Конвертация |
| end_date + end_time | ✅ | end (DateTimeField+TZ) | Конвертация |
| recurrence | 6 типов | rule (RFC 5545) | Конвертация |
| department | ✅ | ❌ | Custom field |
| employee | ✅ | ❌ | EventRelation |

---

## 🔧 Кастомные расширения

Минимальные расширения для сохранения функциональности:

```python
# calendar_app/scheduler_extensions.py

from django.db import models
from schedule.models import Calendar, Event

class ScheduleCalendarExtension(models.Model):
    """Расширение для Calendar (департамент, цвет, видимость)"""
    calendar = models.OneToOneField(
        'schedule.Calendar',
        on_delete=models.CASCADE,
        related_name='extension'
    )
    color = models.CharField(max_length=7, default='#0d6efd')
    owner_department = models.ForeignKey(
        'employees.Department',
        null=True, blank=True,
        on_delete=models.CASCADE
    )
    visibility = models.CharField(
        max_length=20,
        choices=[
            ('public', 'Публичный'),
            ('department', 'Отдел'),
            ('private', 'Приватный'),
        ],
        default='custom'
    )

class ScheduleEventExtension(models.Model):
    """Расширение для Event (департамент, employee)"""
    event = models.OneToOneField(
        'schedule.Event',
        on_delete=models.CASCADE,
        related_name='extension'
    )
    department = models.ForeignKey(
        'employees.Department',
        null=True, blank=True,
        on_delete=models.CASCADE
    )
```

**Итого:** ~50 строк кода vs 651 в старой models.py

---

## ✅ Преимущества нового подхода

| Аспект | Старое решение | django-scheduler |
|--------|----------------|------------------|
| **Код** | 2000+ строк | ~200 строк (с расширениями) |
| **Timezone** | ❌ Нет | ✅ pytz |
| **iCalendar** | ❌ Нет | ✅ RFC 5545 |
| **Участники** | ❌ Нет | ✅ EventRelation |
| **Документация** | Самописная | ReadTheDocs |
| **Обновления** | Вручную | `pip upgrade` |
| **Community** | Нет | GitHub Issues |
| **Интеграция Celery** | Вручную | django-celery-beat |

---

## 🚀 Следующие шаги

1. ✅ **Установка** — django-scheduler установлен
2. ⏳ **Миграции БД** — создать таблицы schedule_*
3. ⏳ **API v2** — создать viewsets на django-scheduler
4. ⏳ **Скрипт миграции** — копирование данных
5. ⏳ **Фронтенд** — новый компонент календаря
6. ⏳ **Тестирование** — параллельная работа
7. ⏳ **Переключение** — деплой на production
8. ⏳ **Удаление старого** — через 2-3 спринта

---

## 📝 Commit strategy

```bash
# Все изменения в ветке feature/django-scheduler-integration
git checkout feature/django-scheduler-integration

# Коммиты:
# 1. feat: add django-scheduler to INSTALLED_APPS
# 2. feat: create schedule_* tables via migrations
# 3. feat: add API v2 for django-scheduler
# 4. feat: add data migration script
# 5. feat: integrate frontend with API v2
# 6. test: parallel work of old and new calendars
# 7. refactor: switch to new calendar
# 8. chore: remove calendar_app (later)
```

---

## 🎯 Безопасность

- Старая система **НЕ ТРОГАЕТСЯ** (работает как прежде)
- Новая система **ПАРАЛЛЕЛЬНО** тестируется
- Production использует `/api/v1/` (старое)
- Staging/Dev тестирует `/api/v2/` (новое)
- Откат: `git revert` + переключение URL

**Zero downtime migration!**
