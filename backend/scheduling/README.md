# Scheduling App

Приложение для интеграции и расширения **django-scheduler** в EUSRR.

## Содержимое

### 📦 Основные модули

- **`patch.py`** - Исправление бага django-scheduler с `byweekday`
- **`notifications/`** - Система уведомлений для событий календаря
- **`rules.py`** - Правила доступа django-rules для календарей и событий
- **`apps.py`** - Конфигурация приложения (применяет патчи, регистрирует сигналы)

### 🔧 Патчи

**Проблема django-scheduler:**
При создании повторяющегося события с `byweekday=[1, 4]` (вторник и пятница), если событие создается в пятницу, django-scheduler неправильно заменяет весь массив на `[4]`, игнорируя вторник.

**Решение:**
Модуль `patch.py` автоматически применяется при запуске Django и исправляет метод `Event._event_params()`.

### 🔔 Уведомления

Автоматические уведомления для событий calendar через django signals:

- **Создание события** → уведомление всем участникам календаря
- **Изменение события** → уведомление при изменении важных полей (название, время, описание)
- **Удаление события** → уведомление об отмене

**Конфигурация:**
- `notifications/config.py` - шаблоны сообщений, URL-адреса
- `notifications/handlers.py` - бизнес-логика отправки уведомлений
- `notifications/signals.py` - Django signals для автоматической обработки

### 🔐 Права доступа

Интеграция с **django-rules** для объектных прав доступа:

```python
# В коде
if user.has_perm('can_edit_calendar', calendar):
    # Редактирование разрешено
    
# В шаблонах
{% if request.user|has_rule:'can_edit_event' event %}
  <button>Редактировать</button>
{% endif %}
```

**Правила:**
- `can_view_calendar` / `can_view_event` - просмотр
- `can_edit_calendar` / `can_edit_event` - редактирование
- `can_delete_calendar` / `can_delete_event` - удаление

Права проверяются через `CalendarRelation` из django-scheduler.

## Установка

Приложение автоматически активируется при добавлении в `INSTALLED_APPS`:

```python
INSTALLED_APPS = [
    # ...
    'schedule',  # django-scheduler (обязательно перед scheduling)
    'scheduling',  # Интеграция и расширения
    # ...
]
```

## Использование

### Отправка уведомлений вручную

```python
from scheduling.notifications.handlers import (
    notify_event_created,
    notify_event_changed,
    notify_event_cancelled
)
from schedule.models import Event

event = Event.objects.get(id=1)

# Создано
notify_event_created(event, creator=request.user)

# Изменено
notify_event_changed(event, changed_fields=['title', 'start'], modifier=request.user)

# Отменено
notify_event_cancelled(event, canceller=request.user)
```

### Передача контекста для уведомлений в ViewSet

```python
class EventViewSet(viewsets.ModelViewSet):
    def perform_create(self, serializer):
        event = serializer.save()
        # Передаем создателя для уведомлений
        event._creator = self.request.user
        event.save()
```

## Зависимости

- `django-scheduler >= 0.12.0`
- `django-rules` (опционально, для rules.py)
- `django-notifications-hq` (для системы уведомлений)

## История

Это приложение заменило старое `calendar_app`, которое содержало самописный календарь. 
После перехода на django-scheduler, `calendar_app` был переименован в `scheduling` 
и переориентирован на интеграцию, патчи и расширения для django-scheduler.

**Дата миграции:** 10 марта 2026 г.
