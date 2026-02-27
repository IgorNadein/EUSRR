# Быстрый тест Web Push уведомлений

## 1. Проверка подписки пользователя

Откройте Django shell:
```bash
cd backend
../.venv/Scripts/python manage.py shell
```

Выполните:
```python
from notifications.models import WebPushSubscription
from django.contrib.auth import get_user_model

User = get_user_model()

# Найдите своего пользователя (замените email)
user = User.objects.get(email='nadein-igor-vladimirovich@05-04-1999.ru')

# Проверьте подписки
subs = WebPushSubscription.objects.filter(user=user, is_active=True)
print(f"\n{'='*60}")
print(f"Пользователь: {user.email}")
print(f"Активных Web Push подписок: {subs.count()}")
print(f"{'='*60}\n")

for sub in subs:
    print(f"Устройство: {sub.device_name or 'Неизвестно'}")
    print(f"Endpoint: {sub.endpoint[:60]}...")
    print(f"Создана: {sub.created_at}")
    print(f"Ошибок: {sub.error_count}")
    print("-" * 60)
```

## 2. Отправка тестового уведомления

### Вариант A: Через NotificationService (рекомендуется)

```python
from notifications.services import NotificationService
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(email='nadein-igor-vladimirovich@05-04-1999.ru')

# Создать и отправить уведомление
notification = NotificationService.create_notification(
    recipient=user,
    notification_type_code='system_announcement',  # Или любой другой существующий тип
    title='🔔 Тест Web Push',
    message='Это тестовое уведомление для проверки работы Web Push API. Если вы видите это уведомление при закрытом браузере - всё работает отлично!',
    action_url='/notifications/',
    action_text='Открыть уведомления',
    send_immediately=True
)

if notification:
    print(f"\n✅ Уведомление создано: ID={notification.id}")
    print(f"Статус отправки:")
    print(f"  - WebSocket: {'✅' if notification.sent_web else '❌'}")
    print(f"  - Email: {'✅' if notification.sent_email else '❌'}")
    print(f"  - Telegram: {'✅' if notification.sent_telegram else '❌'}")
else:
    print("\n❌ Ошибка: уведомление не создано")
```

### Вариант B: Прямой вызов Web Push

```python
from notifications.models import Notification, NotificationType
from notifications.services import NotificationService
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(email='nadein-igor-vladimirovich@05-04-1999.ru')

# Найти тип уведомления
notif_type = NotificationType.objects.get(code='system_announcement')

# Создать уведомление вручную
notification = Notification.objects.create(
    recipient=user,
    notification_type=notif_type,
    title='🧪 Тест Web Push (прямой вызов)',
    message='Проверка работы Web Push через прямой вызов send_web_push_notification()',
    short_message='Проверка Web Push',
    action_url='/notifications/'
)

# Отправить только через Web Push
push_count = NotificationService.send_web_push_notification(notification)
print(f"\n📲 Web Push отправлено на {push_count} устройств")
```

## 3. Тест с закрытым браузером

1. **Откройте сайт в браузере**
   - Перейдите на http://localhost:9000 (или ваш адрес)
   - Авторизуйтесь

2. **Проверьте разрешения** (F12 → Console)
   ```javascript
   console.log('Notification permission:', Notification.permission);
   ```
   Должно быть: `granted`

3. **Проверьте подписку**
   ```javascript
   navigator.serviceWorker.ready.then(reg => {
       return reg.pushManager.getSubscription();
   }).then(sub => {
       if (sub) {
           console.log('✅ Подписка активна');
       } else {
           console.log('❌ Нет подписки, подпишитесь в настройках');
       }
   });
   ```

4. **ЗАКРОЙТЕ браузер полностью**
   - Ctrl+Shift+Q (Chrome) или Alt+F4
   - Убедитесь что все окна закрыты

5. **Отправьте уведомление из Django shell** (см. шаг 2)

6. **Проверьте результат**
   - Должно появиться нативное уведомление Windows/macOS/Linux
   - При клике на уведомление → откроется браузер на нужной странице

## 4. Проверка логов

### Логи Django

```bash
# В отдельном терминале (если сервер запущен)
tail -f backend/logs/django.log | grep -E "send_web_push|WebPush"
```

Должны увидеть:
```
[NotificationService.send_notification] 📲 Отправка Web Push (offline)...
[NotificationService.send_web_push_notification] НАЧАЛО: notification_id=XXX
[NotificationService.send_web_push_notification] Найдено подписок: 1
[NotificationService.send_web_push_notification] ✅ Завершено: 1/1 успешно
```

### Логи браузера (Service Worker)

Откройте: `chrome://serviceworker-internals/` (Chrome) или `about:debugging#/runtime/this-firefox` (Firefox)

Найдите ваш Service Worker (`/sw.js`) и нажмите "Inspect" или "Console".

При получении push-уведомления должно быть:
```
[SW] Push received: PushEvent
[SW] Push payload: {title: "...", body: "...", ...}
```

## 5. Возможные проблемы

### ❌ Нет активных подписок

**Причина:** Пользователь не подписался на уведомления

**Решение:**
1. Откройте сайт
2. Перейдите в Настройки → Уведомления
3. Нажмите "Разрешить уведомления" в браузере
4. Убедитесь что канал "Web" включен

### ❌ VAPID ключи не настроены

**Лог:** `⚠️ VAPID ключи не настроены`

**Решение:**
```bash
.venv/Scripts/python -c "from py_vapid import Vapid; v = Vapid(); v.generate_keys(); print('Public:', v.public_key.decode()); print('Private:', v.private_key.decode())"
```
Добавьте ключи в `.env` или `settings.py`.

### ❌ pywebpush не установлен

**Решение:**
```bash
cd backend
../.venv/Scripts/pip install pywebpush==2.1.2
```

### ❌ Service Worker не регистрируется

**Проблема:** Файл `sw.js` недоступен

**Решение:**
1. Проверьте что файл `backend/sw.js` существует
2. Проверьте URL: http://localhost:9000/sw.js (должен открыться)
3. HTTPS обязателен на production (на localhost работает без HTTPS)

### ❌ Error 410 Gone

**Причина:** Подписка устарела (браузер сбросил)

**Решение:**
```python
# В Django shell
from notifications.models import WebPushSubscription
WebPushSubscription.objects.filter(is_active=False).delete()
```

Затем перезагрузите страницу и подпишитесь заново.

### ❌ Уведомления дублируются

**Это нормально** для онлайн пользователей:
- WebSocket → мгновенное уведомление
- Web Push → отложенное (2-5 секунд)

Браузер должен дедуплицировать по `tag`, но не все браузеры это делают корректно.

## 6. Статистика

```python
from notifications.models import WebPushSubscription, Notification

# Всего подписок
total_subs = WebPushSubscription.objects.count()
active_subs = WebPushSubscription.objects.filter(is_active=True).count()
with_errors = WebPushSubscription.objects.filter(error_count__gt=0).count()

print(f"Web Push подписки:")
print(f"  Всего: {total_subs}")
print(f"  Активных: {active_subs}")
print(f"  С ошибками: {with_errors}")

# Уведомления за сегодня
from django.utils import timezone
today = timezone.now().date()
notifications_today = Notification.objects.filter(
    created_at__date=today
).count()

print(f"\nУведомления за сегодня: {notifications_today}")
```

## 7. Очистка неактивных подписок

```bash
# Удалить старые и с ошибками
.venv/Scripts/python manage.py cleanup_push_subscriptions

# Или вручную:
```

```python
from notifications.models import WebPushSubscription
from django.utils import timezone
from datetime import timedelta

# Удалить неактивные старше 90 дней
old_date = timezone.now() - timedelta(days=90)
inactive = WebPushSubscription.objects.filter(
    is_active=False,
    updated_at__lt=old_date
)
count = inactive.count()
inactive.delete()
print(f"Удалено старых подписок: {count}")

# Удалить с большим количеством ошибок
with_errors = WebPushSubscription.objects.filter(error_count__gte=5)
count = with_errors.count()
with_errors.delete()
print(f"Удалено с ошибками: {count}")
```

## Готово!

Если всё работает, вы увидите:
- ✅ Нативные уведомления даже с **закрытым браузером**
- ✅ Клик по уведомлению открывает нужную страницу
- ✅ В логах: `✅ Завершено: 1/1 успешно`
