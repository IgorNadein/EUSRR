# Аудит модуля уведомлений

**Дата:** 5 января 2026  
**Статус:** Модуль работает, но обнаружены проблемы с маршрутизацией API

## Обзор проблем

### 1. ❌ API Routing Issues (ИСПРАВЛЕНО)

**Проблема:** Старые JavaScript файлы использовали устаревшие пути `/api/notifications/` вместо `/api/v1/notifications/`

**Затронутые файлы:**
- `static/js/notifications/notification-list.js`
- `static/js/notifications/notification-manager.js`
- `static/js/notifications/notification-settings.js`

**Симптомы:**
```
[WARNING] Not Found: /api/notifications/
[WARNING] HTTP GET /api/notifications/?page=1&page_size=20 404
```

**Решение:** Обновлены все пути в JS файлах на корректные с префиксом `/v1/`

### 2. ⚠️ Отсутствие тестов

**Проблема:** Модуль notifications не имел unit-тестов, что затрудняет:
- Обнаружение регрессий
- Валидацию изменений
- Документирование поведения

**Состояние до аудита:**
- `tests.py` - пустой файл
- `test_views.py` - только тестовый view для ручного создания уведомлений

**Решение:** Созданы комплексные тесты:
- `tests/test_models.py` - тесты моделей (200+ строк)
- `tests/test_api.py` - тесты API endpoints (270+ строк)
- `tests/test_services.py` - тесты NotificationService (240+ строк)

### 3. ⚠️ Web Push Subscription Management

**Потенциальная проблема:** Накопление неактивных подписок

**Текущая логика:**
```python
# После 5 ошибок подписка деактивируется
if self.error_count >= 5:
    self.is_active = False
```

**Отсутствует:**
- Периодическая очистка устаревших подписок
- Автоматическое удаление подписок старше N дней
- Логирование статистики использования

**Рекомендации:**
1. Создать management команду для очистки:
   ```python
   # management/commands/cleanup_push_subscriptions.py
   from datetime import timedelta
   from django.utils import timezone
   
   # Удалить неактивные старше 30 дней
   WebPushSubscription.objects.filter(
       is_active=False,
       updated_at__lt=timezone.now() - timedelta(days=30)
   ).delete()
   ```

2. Добавить в crontab или Celery beat:
   ```python
   # Каждую неделю
   '0 3 * * 0': 'notifications.tasks.cleanup_old_subscriptions'
   ```

## Архитектура модуля

### Структура файлов

```
notifications/
├── models.py                 # Модели (547 строк)
│   ├── NotificationCategory
│   ├── NotificationType
│   ├── Notification
│   ├── UserNotificationSettings
│   └── WebPushSubscription
├── services.py              # Бизнес-логика (630 строк)
│   └── NotificationService
├── api_views.py             # REST API (576 строк)
│   ├── Notifications CRUD
│   ├── Settings management
│   └── Web Push API
├── api_urls.py              # URL маршруты API
├── views.py                 # Template views
├── urls.py                  # URL маршруты views
├── email_sender.py          # Email канал
├── telegram_sender.py       # Telegram канал
├── signals.py               # Django signals
├── admin.py                 # Django admin
└── tests/                   # Тесты (NEW!)
    ├── test_models.py       # 230 строк
    ├── test_api.py          # 280 строк
    └── test_services.py     # 250 строк
```

### Каналы доставки

1. **WebSocket** (realtime) - через Channels
2. **Web Push** (offline) - через pywebpush
3. **Email** - через SMTP
4. **Telegram** - через Bot API

### Модели

#### Notification
```python
- recipient: FK(User) - получатель
- notification_type: FK(NotificationType) - тип
- title, message, short_message - контент
- is_read, read_at - статус прочтения
- is_archived, archived_at - архивация
- sent_web, sent_email, sent_telegram - каналы
- group_key, grouped_count - группировка
```

#### WebPushSubscription
```python
- user: FK(User)
- endpoint: str - Push endpoint URL
- p256dh_key, auth_key - encryption keys
- device_name - название устройства
- is_active - активность
- error_count - счетчик ошибок
- last_error - последняя ошибка
```

## API Endpoints

### Notifications API

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v1/notifications/` | Список уведомлений с фильтрами |
| GET | `/api/v1/notifications/count/` | Количество непрочитанных |
| POST | `/api/v1/notifications/{id}/read/` | Отметить прочитанным |
| POST | `/api/v1/notifications/read-all/` | Отметить все прочитанными |
| DELETE | `/api/v1/notifications/{id}/` | Удалить (архивировать) |
| GET | `/api/v1/notifications/categories/` | Список категорий |
| GET | `/api/v1/notifications/settings/` | Настройки пользователя |
| PUT | `/api/v1/notifications/settings/update/` | Обновить настройки |

### Web Push API

| Метод | Endpoint | Описание |
|-------|----------|----------|
| GET | `/api/v1/notifications/push/vapid-key/` | VAPID публичный ключ |
| POST | `/api/v1/notifications/push/subscribe/` | Подписаться на push |
| DELETE | `/api/v1/notifications/push/unsubscribe/` | Отписаться |
| GET | `/api/v1/notifications/push/subscriptions/` | Список подписок |

## Покрытие тестами

### test_models.py

**Классы:**
- `NotificationCategoryTest` - тесты категорий
- `NotificationTypeTest` - тесты типов
- `NotificationTest` - тесты уведомлений
  - Создание
  - mark_as_read()
  - archive()
- `UserNotificationSettingsTest` - настройки
- `WebPushSubscriptionTest` - Web Push подписки
  - Создание
  - mark_used()
  - increment_error()
  - Автодеактивация после 5 ошибок
  - reset_errors()
  - Unique constraint

### test_api.py

**Классы:**
- `NotificationAPITest` - тесты REST API
  - GET /notifications/ с пагинацией
  - GET с фильтрами (unread_only, search)
  - POST /read/, /read-all/
  - DELETE архивация
  - Проверка авторизации
- `WebPushAPITest` - Web Push API
  - GET /vapid-key/
  - POST /subscribe/ (создание и обновление)
  - DELETE /unsubscribe/ (одна или все)
  - GET /subscriptions/
  - Валидация полей

### test_services.py

**Классы:**
- `NotificationServiceTest` - основной сервис
  - create_notification()
  - get_user_settings()
  - mark_as_read() с проверкой владельца
  - mark_all_as_read()
  - delete_notification()
  - send_realtime_notification() (mock)
  - send_web_push_notification() (mock)
- `NotificationSettingsServiceTest` - настройки
  - update_user_settings()
  - update_category_settings()

## Запуск тестов

```bash
# Все тесты модуля notifications
pytest backend/notifications/tests/ -v

# Только тесты моделей
pytest backend/notifications/tests/test_models.py -v

# Только API тесты
pytest backend/notifications/tests/test_api.py -v

# Тесты сервисов
pytest backend/notifications/tests/test_services.py -v

# С покрытием
pytest backend/notifications/tests/ --cov=notifications --cov-report=html
```

## Проверка Web Push подписок

### Через Django Shell

```python
from notifications.models import WebPushSubscription

# Статистика
total = WebPushSubscription.objects.count()
active = WebPushSubscription.objects.filter(is_active=True).count()
print(f"Total: {total}, Active: {active}")

# Детали
for sub in WebPushSubscription.objects.all():
    print(f"User: {sub.user.email}")
    print(f"  Device: {sub.device_name or 'Unknown'}")
    print(f"  Active: {sub.is_active}")
    print(f"  Errors: {sub.error_count}")
    print(f"  Last error: {sub.last_error[:50] if sub.last_error else 'None'}")
    print(f"  Created: {sub.created_at}")
```

### Через API

```bash
# Получить подписки текущего пользователя
curl -X GET http://localhost:8000/api/v1/notifications/push/subscriptions/ \
  -H "Authorization: Bearer YOUR_TOKEN"

# Отписаться от всех
curl -X DELETE http://localhost:8000/api/v1/notifications/push/unsubscribe/ \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Рекомендации по улучшению

### 1. Добавить индексы для производительности

```python
# models.py
class WebPushSubscription(models.Model):
    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['error_count', 'is_active']),
            models.Index(fields=['updated_at']),
        ]
```

### 2. Добавить мониторинг

```python
# services.py
import prometheus_client

push_sent_counter = prometheus_client.Counter(
    'notifications_push_sent_total',
    'Total Web Push notifications sent'
)

push_error_counter = prometheus_client.Counter(
    'notifications_push_errors_total',
    'Total Web Push errors'
)
```

### 3. Добавить rate limiting

```python
# api_views.py
from rest_framework.throttling import UserRateThrottle

class PushSubscriptionThrottle(UserRateThrottle):
    rate = '10/hour'  # Максимум 10 подписок в час

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@throttle_classes([PushSubscriptionThrottle])
def subscribe_push(request):
    ...
```

### 4. Логирование статистики

```python
# management/commands/notification_stats.py
from django.core.management.base import BaseCommand
from notifications.models import WebPushSubscription

class Command(BaseCommand):
    def handle(self, *args, **options):
        stats = {
            'total': WebPushSubscription.objects.count(),
            'active': WebPushSubscription.objects.filter(is_active=True).count(),
            'with_errors': WebPushSubscription.objects.filter(error_count__gt=0).count(),
            'devices': WebPushSubscription.objects.values('device_name').distinct().count()
        }
        self.stdout.write(self.style.SUCCESS(f"Stats: {stats}"))
```

### 5. Документация API (OpenAPI)

```python
# api_views.py
from drf_spectacular.utils import extend_schema

@extend_schema(
    summary="Subscribe to Web Push notifications",
    request=WebPushSubscriptionSerializer,
    responses={200: {"status": "success"}}
)
@api_view(['POST'])
def subscribe_push(request):
    ...
```

## Выводы

### ✅ Что работает хорошо:

1. **Архитектура** - чистое разделение на модели, сервисы, API
2. **Каналы доставки** - поддержка WebSocket, Web Push, Email, Telegram
3. **Обработка ошибок** - автодеактивация проблемных подписок
4. **Настройки** - гибкие настройки для каждого типа уведомлений

### ⚠️ Что нуждается в улучшении:

1. **Тесты** - ✅ ИСПРАВЛЕНО (созданы комплексные тесты)
2. **API маршруты** - ✅ ИСПРАВЛЕНО (обновлены пути в JS)
3. **Очистка данных** - нужна периодическая очистка старых подписок
4. **Мониторинг** - отсутствует метрики и алерты
5. **Документация API** - нет OpenAPI схемы

### Приоритеты:

1. **ВЫСОКИЙ:** Запустить тесты и убедиться в покрытии
2. **СРЕДНИЙ:** Добавить команду очистки подписок
3. **СРЕДНИЙ:** Добавить мониторинг (Prometheus/Grafana)
4. **НИЗКИЙ:** Добавить OpenAPI документацию
