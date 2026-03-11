# 🔍 Диагностика Celery - уведомления не доходят до пользователей

**Проблема:** При создании уведомления задача не попадает в Celery worker  
**Дата:** 11 марта 2026  
**Архитектура:** Django 5.2 + Celery + Redis + Channels

---

## 📋 Архитектура системы уведомлений

### Схема потока данных:

```
1. notify.send() → создание Notification в БД
2. post_save signal → route_notification_to_channels()
3. transaction.on_commit() → send_to_channels()
4. Celery task → send_websocket_notification.delay(notification.id)
5. Redis queue 'notifications' → Worker забирает задачу
6. Worker выполняет → WebSocketNotificationSender.send()
7. Channels → WebSocket → Frontend
```

---

## 🔧 Ваши настройки (из settings.py)

### Celery
```python
CELERY_BROKER_URL = 'redis://localhost:6379/0'  # или из env
CELERY_RESULT_BACKEND = 'redis://localhost:6379/1'

# Очереди
CELERY_TASK_ROUTES = {
    'notifications.tasks.*': {'queue': 'notifications'},  # !!!
    'documents.tasks.*': {'queue': 'default'},
    'employees.tasks.*': {'queue': 'default'},
}

# Важные опции
CELERY_TASK_ACKS_LATE = True  # Подтверждение после выполнения
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # По 1 задаче
```

### Redis
```python
REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
REDIS_PORT = os.getenv('REDIS_PORT', '6379')

# База 0 - Celery broker
# База 1 - Celery results
# База 2 - Channels
```

### Задача уведомлений
```python
# File: notifications/tasks/websocket.py
task_name = "notifications.send_websocket_notification"

# File: notifications/channels.py (строка 84)
send_websocket_notification.delay(notification.id, silent=False)
```

---

## 🚨 Критичные точки проверки

### 1️⃣ Worker должен слушать очередь 'notifications'

**ПРОБЛЕМА:** По умолчанию worker слушает только 'celery' queue!

```bash
# ❌ НЕПРАВИЛЬНО (пропускает notifications queue):
celery -A eusrr_backend worker -l info

# ✅ ПРАВИЛЬНО (слушает обе очереди):
celery -A eusrr_backend worker -l info -Q notifications,default,celery
```

**Для production (systemd/supervisor):**
```ini
# /etc/systemd/system/celery.service
ExecStart=/path/to/venv/bin/celery -A eusrr_backend worker \
    -Q notifications,default,celery \
    -l info \
    --logfile=/var/log/celery/worker.log
```

### 2️⃣ Redis должен быть доступен

```bash
# На сервере проверь переменные окружения
echo $REDIS_HOST  # должно быть IP или localhost
echo $REDIS_PORT  # должно быть 6379

# Проверка подключения
redis-cli -h $REDIS_HOST -p $REDIS_PORT ping
# Должно вернуть: PONG

# Проверка очередей Celery
redis-cli -h $REDIS_HOST -p $REDIS_PORT
> SELECT 0  # база Celery broker
> KEYS *
> LLEN notifications  # длина очереди notifications
> LRANGE notifications 0 5  # показать первые 5 задач
```

### 3️⃣ transaction.on_commit() требует правильный DB backend

**ВАЖНО:** Если используется autocommit=False или транзакции, `on_commit()` может не сработать!

```python
# В Django shell проверь:
from django.db import connection
print("Autocommit:", connection.get_autocommit())  # должно быть True

# Если False - задачи никогда не отправятся!
```

---

## 📝 Пошаговая диагностика

### ШАГ 1: Проверка Celery Worker

```bash
# SSH на production сервер
ps aux | grep celery

# Должно показать процесс типа:
# celery -A eusrr_backend worker -Q notifications,default,celery

# Проверь логи worker
tail -f /var/log/celery/worker.log

# Проверь через systemd (если используется)
sudo systemctl status celery
sudo journalctl -u celery -n 100 --no-pager
```

**Что искать в логах:**
```
✅ [... INFO/MainProcess] celery@hostname ready.
✅ [... INFO/MainProcess] consumer: Connected to redis://...
✅ [... INFO/Consumer] Restoring 0 unacknowledged message(s).

❌ ConnectionError: Error -2 connecting to redis:6379
❌ [... ERROR/MainProcess] consumer: Cannot connect to redis://...
```

### ШАГ 2: Проверка зарегистрированных задач

```bash
# На сервере
cd /path/to/backend
source /path/to/venv/bin/activate

# Проверь зарегистрированные задачи
celery -A eusrr_backend inspect registered | grep notification

# Должно быть:
# - notifications.send_websocket_notification
# - notifications.send_email_notification  
# - notifications.send_push_notification
```

**Если задач нет:**
```bash
# Проверь импорты в eusrr_backend/__init__.py или celery.py
python manage.py shell

>>> from notifications.tasks import send_websocket_notification
>>> print(send_websocket_notification.name)
# Должно вывести: notifications.send_websocket_notification
```

### ШАГ 3: Тест создания уведомления

```bash
cd /path/to/backend
source /path/to/venv/bin/activate
python manage.py shell
```

```python
# В Django shell:
from notifications.signals import notify
from employees.models import Employee
from django.db import transaction

# Найди двух пользователей
sender = Employee.objects.filter(is_active=True).first()
recipient = Employee.objects.filter(is_active=True).exclude(id=sender.id).first()

if sender and recipient:
    print(f"Sender: {sender.get_full_name()} (ID: {sender.id})")
    print(f"Recipient: {recipient.get_full_name()} (ID: {recipient.id})")
    
    # Проверь autocommit
    from django.db import connection
    print(f"Autocommit: {connection.get_autocommit()}")  # ДОЛЖНО БЫТЬ True
    
    # Создай уведомление
    result = notify.send(
        sender=sender,
        recipient=recipient,
        verb='test_diagnostic',
        description='Тестовое уведомление для диагностики Celery',
        action_url='/test/',
    )
    print(f"✅ Notification created: {result}")
    
    # Проверь что задача ушла в Redis
    import redis
    r = redis.Redis(host='localhost', port=6379, db=0)
    queue_len = r.llen('notifications')
    print(f"📦 Tasks in 'notifications' queue: {queue_len}")
    
    if queue_len > 0:
        print("✅ Задача попала в очередь!")
    else:
        print("❌ Задача НЕ попала в очередь!")
else:
    print("❌ Не найдены пользователи для теста")
```

### ШАГ 4: Проверка логов post_save signal

Добавь временный debug лог:

```python
# File: backend/notifications/channels.py
# Строка 24 (внутри route_notification_to_channels)

@receiver(post_save, sender='notifications.Notification')
def route_notification_to_channels(sender, instance, created, **kwargs):
    if not created:
        return
    
    notification = instance
    user = notification.recipient
    
    # === ДОБАВЬ ЭТИ СТРОКИ ===
    import logging
    logger = logging.getLogger(__name__)
    logger.error(f"[DEBUG] route_notification_to_channels called for notification {notification.id}")
    logger.error(f"[DEBUG] Recipient: {user.id if user else 'None'}, Verb: {notification.verb}")
    # === КОНЕЦ ===
    
    # ... остальной код
```

**Перезапусти Django:**
```bash
# Если в production используется gunicorn/uwsgi
sudo systemctl restart gunicorn
# или
sudo systemctl restart uwsgi

# Если через supervisor
sudo supervisorctl restart django
```

**Проверь логи Django:**
```bash
tail -f /var/log/django/debug.log | grep DEBUG
# или
tail -f /var/log/gunicorn/error.log | grep DEBUG
```

### ШАГ 5: Проверка transaction.on_commit()

```python
# В Django shell
from notifications.signals import notify
from employees.models import Employee
from django.db import transaction

sender = Employee.objects.first()
recipient = Employee.objects.exclude(id=sender.id).first()

# === КРИТИЧНЫЙ ТЕСТ ===
# Если autocommit=False, задачи не отправятся!

print("=== Test 1: Normal (should work) ===")
notify.send(
    sender=sender,
    recipient=recipient,
    verb='test_1',
    description='Test without explicit transaction',
)
print("Check Redis queue now!")

print("\n=== Test 2: Inside transaction (should work) ===")
with transaction.atomic():
    notify.send(
        sender=sender,
        recipient=recipient,
        verb='test_2',
        description='Test inside transaction',
    )
print("Check Redis queue now!")

print("\n=== Test 3: Rollback (should NOT add to queue) ===")
try:
    with transaction.atomic():
        notify.send(
            sender=sender,
            recipient=recipient,
            verb='test_3',
            description='Test with rollback',
        )
        raise Exception("Force rollback")
except:
    pass
print("Queue should NOT have this task!")
```

---

## 🐛 Частые проблемы и решения

### Проблема 1: Worker не слушает 'notifications' queue

**Признак:**
```bash
redis-cli LLEN notifications  # показывает задачи
celery -A eusrr_backend inspect active  # пусто
```

**Решение:**
```bash
# Перезапусти worker с правильными очередями
celery -A eusrr_backend worker -l info -Q notifications,default,celery

# Или в systemd файле:
ExecStart=/venv/bin/celery -A eusrr_backend worker -Q notifications,default,celery -l info
sudo systemctl daemon-reload
sudo systemctl restart celery
```

### Проблема 2: Redis на другом хосте

**Признак:**
```
ConnectionError: Error -2 connecting to redis:6379
```

**Решение:**
```bash
# Проверь переменные окружения на production
cat /etc/systemd/system/celery.service | grep Environment
# или
cat /etc/supervisor/conf.d/celery.conf | grep environment

# Должно быть:
Environment="REDIS_HOST=127.0.0.1"  # или реальный IP
Environment="REDIS_PORT=6379"

# Или в .env файле (если используется)
echo "REDIS_HOST=127.0.0.1" >> /path/to/.env
echo "REDIS_PORT=6379" >> /path/to/.env
```

### Проблема 3: UserChannelPreferences не существует

**Признак в логах:**
```
RelatedObjectDoesNotExist: User has no channel_preferences
```

**Решение:**
```python
# В Django shell создай для всех пользователей:
from employees.models import Employee
from notifications.models import UserChannelPreferences

for user in Employee.objects.filter(is_active=True):
    UserChannelPreferences.objects.get_or_create(user=user)
print("✅ Created channel preferences for all users")
```

### Проблема 4: autocommit=False

**Признак:** Задачи вообще не попадают в очередь

**Проверка:**
```python
from django.db import connection
print(connection.get_autocommit())  # должно быть True
```

**Решение в settings.py:**
```python
DATABASES = {
    'default': {
        # ...
        'ATOMIC_REQUESTS': False,  # Если True - может быть проблема
        'AUTOCOMMIT': True,  # Убедись что True
    }
}
```

### Проблема 5: Celery использует старый код

**Признак:** Изменения в коде не применяются

**Решение:**
```bash
# Перезапусти worker
sudo systemctl restart celery

# Или если через supervisor
sudo supervisorctl restart celery

# Убедись что используется правильный venv
ps aux | grep celery
# Должен быть путь к вашему venv, НЕ системный python
```

---

## 🔬 Скрипт автоматической диагностики

Создай файл `diagnose_notifications.py`:

```python
#!/usr/bin/env python
"""
Полная диагностика системы Celery уведомлений
Использование: python manage.py shell < diagnose_notifications.py
"""
import os
import sys
import django

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.conf import settings
from django.db import connection
from celery import current_app
import redis

print("=" * 70)
print("🔍 ДИАГНОСТИКА СИСТЕМЫ CELERY УВЕДОМЛЕНИЙ")
print("=" * 70)

# 1. Настройки
print("\n📋 1. НАСТРОЙКИ CELERY:")
print(f"   BROKER_URL: {settings.CELERY_BROKER_URL}")
print(f"   RESULT_BACKEND: {settings.CELERY_RESULT_BACKEND}")
print(f"   TASK_ROUTES: {settings.CELERY_TASK_ROUTES}")

# 2. База данных
print("\n💾 2. БАЗА ДАННЫХ:")
print(f"   Autocommit: {connection.get_autocommit()}")
if not connection.get_autocommit():
    print("   ⚠️  WARNING: Autocommit=False может блокировать on_commit()")

# 3. Redis
print("\n🔴 3. REDIS:")
try:
    r = redis.from_url(settings.CELERY_BROKER_URL)
    r.ping()
    print("   ✅ Подключение: OK")
    
    # Проверка очередей
    queues = ['notifications', 'default', 'celery']
    for queue in queues:
        try:
            length = r.llen(queue)
            print(f"   📦 Очередь '{queue}': {length} задач")
        except:
            print(f"   ⚠️  Очередь '{queue}': не найдена")
except Exception as e:
    print(f"   ❌ Ошибка подключения: {e}")

# 4. Celery tasks
print("\n⚙️  4. ЗАРЕГИСТРИРОВАННЫЕ ЗАДАЧИ:")
try:
    tasks = current_app.tasks
    notif_tasks = [t for t in tasks if 'notification' in t.lower()]
    if notif_tasks:
        print("   ✅ Задачи уведомлений найдены:")
        for task in notif_tasks:
            print(f"      • {task}")
    else:
        print("   ❌ Задачи уведомлений НЕ найдены!")
        print("      Проверь что импорты работают:")
        try:
            from notifications.tasks import send_websocket_notification
            print(f"      ✅ Импорт OK: {send_websocket_notification.name}")
        except Exception as e:
            print(f"      ❌ Ошибка импорта: {e}")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# 5. Workers
print("\n👷 5. АКТИВНЫЕ WORKERS:")
try:
    i = current_app.control.inspect()
    active = i.active()
    if active:
        for worker_name, tasks in active.items():
            print(f"   ✅ Worker: {worker_name}")
            print(f"      Активных задач: {len(tasks)}")
    else:
        print("   ❌ Нет активных workers!")
        print("      Запусти: celery -A eusrr_backend worker -Q notifications,default,celery")
        
    # Проверка зарегистрированных очередей
    registered = i.registered()
    if registered:
        for worker_name, tasks in registered.items():
            notif_count = len([t for t in tasks if 'notification' in t.lower()])
            print(f"   📋 {worker_name}: {notif_count} задач уведомлений")
except Exception as e:
    print(f"   ❌ Не удалось проверить workers: {e}")
    print("      Worker может быть не запущен или недоступен")

# 6. Тест создания уведомления
print("\n🧪 6. ТЕСТ СОЗДАНИЯ УВЕДОМЛЕНИЯ:")
try:
    from notifications.signals import notify
    from employees.models import Employee
    
    sender = Employee.objects.filter(is_active=True).first()
    recipient = Employee.objects.filter(is_active=True).exclude(id=sender.id).first()
    
    if sender and recipient:
        print(f"   Отправитель: {sender.get_full_name()} (ID: {sender.id})")
        print(f"   Получатель: {recipient.get_full_name()} (ID: {recipient.id})")
        
        # Создаем уведомление
        result = notify.send(
            sender=sender,
            recipient=recipient,
            verb='diagnostic_test',
            description='Автоматический тест диагностики',
        )
        
        if result:
            notif = result if not isinstance(result, list) else result[0]
            print(f"   ✅ Уведомление создано: ID {notif.id}")
            
            # Проверяем попало ли в очередь
            import time
            time.sleep(0.5)  # небольшая задержка для on_commit()
            
            r = redis.from_url(settings.CELERY_BROKER_URL)
            queue_len = r.llen('notifications')
            print(f"   📦 Задач в очереди 'notifications': {queue_len}")
            
            if queue_len > 0:
                print("   ✅ Задача попала в очередь!")
            else:
                print("   ⚠️  Задача НЕ попала в очередь!")
                print("      Возможные причины:")
                print("      - Worker не слушает очередь 'notifications'")
                print("      - Проблема с transaction.on_commit()")
                print("      - Настройки UserChannelPreferences отключили канал")
    else:
        print("   ⚠️  Недостаточно пользователей для теста")
        
except Exception as e:
    print(f"   ❌ Ошибка теста: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
print("📊 ДИАГНОСТИКА ЗАВЕРШЕНА")
print("=" * 70)
```

**Запуск на production:**
```bash
cd /path/to/backend
source /path/to/venv/bin/activate
python manage.py shell < diagnose_notifications.py > diagnostic_result.log
cat diagnostic_result.log
```

---

## ✅ Чеклист для production

- [ ] Celery worker запущен и работает
- [ ] Worker слушает очередь `-Q notifications,default,celery`
- [ ] Redis доступен на `REDIS_HOST:REDIS_PORT`
- [ ] Очередь 'notifications' существует в Redis (база 0)
- [ ] Задача `notifications.send_websocket_notification` зарегистрирована
- [ ] Autocommit = True в Django
- [ ] UserChannelPreferences созданы для всех пользователей
- [ ] Логи Celery показывают "Task ... received"
- [ ] Переменные окружения REDIS_HOST, REDIS_PORT установлены
- [ ] systemd/supervisor файлы настроены правильно
- [ ] Worker использует правильный venv

---

## 🆘 Если ничего не помогло

1. **Включи debug логи:**
```python
# settings.py
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': '/var/log/django/debug.log',
        },
    },
    'loggers': {
        'notifications': {
            'handlers': ['file'],
            'level': 'DEBUG',
        },
        'celery': {
            'handlers': ['file'],
            'level': 'DEBUG',
        },
    },
}
```

2. **Временно отключи transaction.on_commit():**
```python
# File: backend/notifications/channels.py
# Строка 75-92

# ВРЕМЕННО закомментируй:
# transaction.on_commit(send_to_channels)

# И замени на прямой вызов:
send_to_channels()

# Если после этого задачи доходят - проблема в autocommit!
```

3. **Тестируй задачи напрямую:**
```python
# Django shell
from notifications.tasks import send_websocket_notification
from notifications.models import Notification

notif = Notification.objects.last()
result = send_websocket_notification.delay(notif.id)
print(f"Task ID: {result.id}")
print(f"Status: {result.status}")  # через 1-2 сек должно быть SUCCESS
```

---

**Документ создан:** 11.03.2026  
**Версия:** 1.0  
**Автор:** GitHub Copilot + Диагностика реального проекта
