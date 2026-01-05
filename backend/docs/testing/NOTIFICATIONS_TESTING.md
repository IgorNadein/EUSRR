# Тестирование модуля уведомлений

## Быстрый старт

### Запуск всех тестов

```bash
# Из корня backend/
python manage.py test notifications.tests

# Или с pytest
pytest notifications/tests/ -v

# С покрытием кода
pytest notifications/tests/ --cov=notifications --cov-report=html
```

### Запуск конкретных тестов

```bash
# Только тесты моделей
pytest notifications/tests/test_models.py -v

# Только API тесты
pytest notifications/tests/test_api.py -v

# Только сервисы
pytest notifications/tests/test_services.py -v

# Конкретный тест
pytest notifications/tests/test_models.py::WebPushSubscriptionTest::test_auto_deactivate_after_5_errors -v
```

## Покрытие тестами

### Модели (test_models.py)

#### NotificationCategoryTest
- ✅ Создание категории
- ✅ Строковое представление
- ✅ Активность по умолчанию

#### NotificationTypeTest
- ✅ Создание типа
- ✅ Связь с категорией
- ✅ Приоритет и настройки по умолчанию

#### NotificationTest
- ✅ Создание уведомления
- ✅ `mark_as_read()` - отметка как прочитанное
- ✅ `archive()` - архивация

#### UserNotificationSettingsTest
- ✅ Создание настроек
- ✅ Каналы доставки (web, email, telegram)

#### WebPushSubscriptionTest
- ✅ Создание подписки
- ✅ `mark_used()` - обновление времени использования
- ✅ `increment_error()` - инкремент ошибок
- ✅ Автодеактивация после 5 ошибок
- ✅ `reset_errors()` - сброс счетчика
- ✅ Unique constraint (user + endpoint)

### API Endpoints (test_api.py)

#### NotificationAPITest
- ✅ GET `/api/v1/notifications/` - список
- ✅ Пагинация (page, page_size)
- ✅ Фильтр `unread_only=true`
- ✅ GET `/api/v1/notifications/count/` - счетчик
- ✅ POST `/api/v1/notifications/{id}/read/` - прочитать
- ✅ POST `/api/v1/notifications/read-all/` - прочитать все
- ✅ DELETE `/api/v1/notifications/{id}/` - удалить (архивировать)
- ✅ Поиск `?search=...`
- ✅ Проверка авторизации

#### WebPushAPITest
- ✅ GET `/api/v1/notifications/push/vapid-key/` - VAPID ключ
- ✅ POST `/api/v1/notifications/push/subscribe/` - подписка
  - Создание новой
  - Обновление существующей
  - Валидация полей
- ✅ DELETE `/api/v1/notifications/push/unsubscribe/` - отписка
  - Конкретной подписки
  - Всех подписок
- ✅ GET `/api/v1/notifications/push/subscriptions/` - список подписок

### Сервисы (test_services.py)

#### NotificationServiceTest
- ✅ `create_notification()` - создание
- ✅ Обработка несуществующего типа
- ✅ `get_user_settings()` - автосоздание настроек
- ✅ `mark_as_read()` - с проверкой владельца
- ✅ `mark_all_as_read()` - массовая операция
- ✅ `delete_notification()` - архивация
- ✅ `send_realtime_notification()` - WebSocket (mock)
- ✅ `send_web_push_notification()` - Web Push (mock)

#### NotificationSettingsServiceTest
- ✅ `update_user_settings()` - обновление настроек
- ✅ `update_category_settings()` - массовое обновление категории

## Management команды

### Статистика уведомлений

```bash
python manage.py notification_stats
```

**Выводит:**
- 📧 Общая статистика уведомлений
- 📁 Статистика по категориям
- 🔔 Топ-10 типов уведомлений
- 👥 Топ-10 пользователей
- 📱 Статистика Web Push подписок
- 📤 Статистика по каналам доставки

### Очистка устаревших подписок

```bash
# Dry run (показать что будет удалено)
python manage.py cleanup_push_subscriptions --dry-run

# Удалить неактивные старше 30 дней (по умолчанию)
python manage.py cleanup_push_subscriptions

# Удалить старше 60 дней
python manage.py cleanup_push_subscriptions --days=60
```

**Удаляет:**
- ❌ Неактивные подписки старше N дней
- ❌ Подписки с 10+ ошибками старше N дней

## Проверка Web Push подписок

### Через Django Shell

```bash
python manage.py shell
```

```python
from notifications.models import WebPushSubscription

# Статистика
print(f"Total: {WebPushSubscription.objects.count()}")
print(f"Active: {WebPushSubscription.objects.filter(is_active=True).count()}")

# Детали по подпискам
for sub in WebPushSubscription.objects.all():
    print(f"\nUser: {sub.user.email}")
    print(f"  Device: {sub.device_name or 'Unknown'}")
    print(f"  Active: {sub.is_active}")
    print(f"  Errors: {sub.error_count}")
    if sub.last_error:
        print(f"  Last error: {sub.last_error[:100]}")
```

### Проверка конкретной подписки

```python
from notifications.models import WebPushSubscription
from notifications.services import NotificationService
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(email='your@email.com')

# Проверить подписки пользователя
subs = WebPushSubscription.objects.filter(user=user)
print(f"User has {subs.count()} subscriptions")

for sub in subs:
    print(f"  {sub.device_name}: Active={sub.is_active}, Errors={sub.error_count}")
```

### Тестовая отправка уведомления

```python
from notifications.services import NotificationService
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(email='your@email.com')

# Создать и отправить тестовое уведомление
notification = NotificationService.create_notification(
    recipient=user,
    notification_type_code='system_announcement',
    title='🧪 Test Notification',
    message='This is a test push notification',
    action_url='/notifications/',
    send_immediately=True
)

if notification:
    print(f"✅ Notification created: {notification.id}")
    print(f"   sent_web: {notification.sent_web}")
else:
    print("❌ Failed to create notification")
```

## Проверка API через curl

### Получить список уведомлений

```bash
curl -X GET "http://localhost:8000/api/v1/notifications/?page=1&page_size=10" \
  -H "Cookie: sessionid=YOUR_SESSION_ID"
```

### Подписаться на Web Push

```bash
curl -X POST "http://localhost:8000/api/v1/notifications/push/subscribe/" \
  -H "Cookie: sessionid=YOUR_SESSION_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "endpoint": "https://fcm.googleapis.com/fcm/send/test",
    "keys": {
      "p256dh": "test_p256dh_key",
      "auth": "test_auth_key"
    },
    "device_name": "Chrome on Windows"
  }'
```

### Получить VAPID ключ

```bash
curl -X GET "http://localhost:8000/api/v1/notifications/push/vapid-key/" \
  -H "Cookie: sessionid=YOUR_SESSION_ID"
```

## CI/CD интеграция

### GitHub Actions

```yaml
# .github/workflows/tests.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          cd backend
          pip install -r requirements.txt
      
      - name: Run notification tests
        run: |
          cd backend
          pytest notifications/tests/ -v --cov=notifications
      
      - name: Upload coverage
        uses: codecov/codecov-action@v2
```

## Troubleshooting

### Тесты падают с ошибкой "No module named 'notifications'"

**Решение:** Убедитесь что запускаете из папки `backend/`:
```bash
cd backend
pytest notifications/tests/ -v
```

### Ошибка "pywebpush не установлен"

**Решение:** Установите зависимости:
```bash
pip install pywebpush py-vapid
```

### Тесты Web Push падают

**Проблема:** Отсутствуют VAPID ключи в settings

**Решение:** Добавьте в `settings.py`:
```python
VAPID_PUBLIC_KEY = "your_public_key"
VAPID_PRIVATE_KEY = "your_private_key"
VAPID_ADMIN_EMAIL = "admin@example.com"
```

## Метрики покрытия

**Цель:** 80%+ покрытие кода тестами

```bash
# Генерация отчета о покрытии
pytest notifications/tests/ --cov=notifications --cov-report=html

# Открыть отчет
# backend/htmlcov/index.html
```

**Текущее покрытие:**
- ✅ Модели: ~90%
- ✅ API Views: ~85%
- ✅ Services: ~80%
- ⚠️ Signals: ~40% (требуется улучшение)
- ⚠️ Email/Telegram senders: ~30% (требуется улучшение)
