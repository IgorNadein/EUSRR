# Проблема: Web Push уведомления не приходят при закрытом браузере

**Дата:** 5 января 2026 г.  
**Статус:** ✅ Решено  
**Приоритет:** Критический

## Описание проблемы

Пользователи сообщили, что уведомления не приходят, когда браузер закрыт. Уведомления начинают приходить только после открытия браузера и перехода на сайт.

## Анализ проблемы

### Ожидаемое поведение
Web Push API должен отправлять уведомления **независимо** от того, открыт браузер или нет. Service Worker может получать и показывать уведомления даже когда все вкладки с сайтом закрыты.

### Фактическое поведение
Уведомления отправлялись только через WebSocket, который работает только когда пользователь онлайн на сайте.

### Причина

В файле `backend/notifications/services.py`, метод `send_notification()` (строки ~170-230):

**Проблемный код:**
```python
# Отправить на веб (WebSocket)
if settings.send_web:
    NotificationService.send_web_notification(notification)
    notification.sent_web = True
```

Внутри метода `send_web_notification()` (строка ~391):
```python
# Также отправляем Web Push для offline уведомлений
NotificationService.send_web_push_notification(notification)
```

**Проблема:** 
- `send_web_push_notification()` вызывался **ВНУТРИ** `send_web_notification()`
- Если пользователь офлайн → WebSocket не отправляет → `send_web_notification()` не выполняется полностью
- Следовательно → `send_web_push_notification()` **НЕ вызывается**

## Решение

### Изменения в архитектуре

Разделили отправку на два независимых канала:

1. **WebSocket** (`send_web_socket`) - для онлайн пользователей
2. **Web Push API** (`send_web_push_notification`) - для offline пользователей

### Изменения в коде

#### 1. Метод `send_notification()` - разделение каналов

**До:**
```python
# Отправить на веб (WebSocket)
if settings.send_web:
    NotificationService.send_web_notification(notification)
    notification.sent_web = True
```

**После:**
```python
# Отправить на веб (WebSocket) - для онлайн пользователей
if settings.send_web:
    NotificationService.send_web_socket(notification)
    notification.sent_web = True

# Отправить Web Push (для offline пользователей)
# ВАЖНО: отправляем независимо от WebSocket
if settings.send_web:
    push_count = NotificationService.send_web_push_notification(notification)
    if push_count > 0:
        logger.info(f"Web Push: отправлено на {push_count} устройств")
```

#### 2. Переименование метода для ясности

`send_web_notification()` → `send_web_socket()`

Убрали вызов `send_web_push_notification()` изнутри этого метода.

## Технические детали

### Архитектура Web Push

```
┌─────────────────────────────────────────────────────────────┐
│                      Django Backend                         │
│                                                             │
│  ┌────────────────────────────────────────────────────┐   │
│  │  NotificationService.send_notification()           │   │
│  │                                                     │   │
│  │  1. WebSocket (онлайн)    2. Web Push (offline)   │   │
│  │     ↓                          ↓                    │   │
│  │  send_web_socket()      send_web_push_notification│   │
│  │     ↓                          ↓                    │   │
│  │  Django Channels         pywebpush library         │   │
│  └────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
                ↓                            ↓
    ┌───────────────────┐      ┌───────────────────────────┐
    │  User Online      │      │  Push Service Provider    │
    │  (WebSocket conn) │      │  (FCM, Safari, Mozilla)   │
    └───────────────────┘      └───────────────────────────┘
                                             ↓
                              ┌───────────────────────────┐
                              │  Service Worker          │
                              │  (браузер закрыт/открыт) │
                              │                          │
                              │  sw.js:                  │
                              │  - push event handler    │
                              │  - показ уведомления     │
                              └───────────────────────────┘
```

### Компоненты системы

#### 1. Service Worker (`backend/sw.js`)
- Регистрируется при загрузке сайта
- Работает в фоне даже когда все вкладки закрыты
- Обрабатывает `push` события от браузера
- Показывает нативные уведомления ОС

#### 2. Push Subscription (`WebPushSubscription` модель)
- Хранит endpoint от браузера
- Ключи шифрования (p256dh, auth)
- Информация об устройстве

#### 3. VAPID ключи (настройки)
```python
# backend/eusrr_backend/settings.py
VAPID_PUBLIC_KEY = "BG3WGJZH3bCPtZ1yRjXywfGsHoRT4MZ7npk25twmBireG_Di5-1FBn1ChblWCDicienEr07y4k7R7_A5IjbfjRA="
VAPID_PRIVATE_KEY = "MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQ..."
VAPID_ADMIN_EMAIL = "admin@example.com"
```

#### 4. Frontend модуль (`static/js/notifications/push-notifications.js`)
```javascript
class PushNotificationsManager {
    async init() {
        await this._fetchVapidKey();        // Получить публичный ключ
        await this._registerServiceWorker(); // Зарегистрировать SW
        await this._checkSubscription();     // Проверить подписку
    }
}
```

## Проверка решения

### 1. Проверить наличие подписок
```bash
.venv/Scripts/python manage.py shell
```

```python
from notifications.models import WebPushSubscription
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(email='ваш-email@example.com')

# Проверить активные подписки
subs = WebPushSubscription.objects.filter(user=user, is_active=True)
print(f"Активных подписок: {subs.count()}")
for sub in subs:
    print(f"- Устройство: {sub.device_name}, Создана: {sub.created_at}")
```

### 2. Тестовая отправка через Django shell

```python
from notifications.services import NotificationService
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(email='ваш-email@example.com')

# Создать тестовое уведомление
notification = NotificationService.create_notification(
    recipient=user,
    notification_type_code='test_notification',  # или любой существующий тип
    title='Тест Web Push',
    message='Это тестовое уведомление для проверки Web Push API',
    action_url='/notifications/',
    send_immediately=True
)

print(f"Уведомление создано: {notification.id}")
```

### 3. Проверка в логах

После отправки проверьте логи:
```bash
tail -f backend/logs/django.log | grep "send_web_push"
```

Должны увидеть:
```
[NotificationService.send_notification] 📲 Отправка Web Push (offline)...
[NotificationService.send_web_push_notification] НАЧАЛО: notification_id=123
[NotificationService.send_web_push_notification] Найдено подписок: 1
[NotificationService.send_web_push_notification] ✅ Завершено: 1/1 успешно
```

### 4. Проверка в браузере

#### A. Проверить регистрацию Service Worker
```javascript
// В консоли браузера (F12)
navigator.serviceWorker.getRegistrations().then(regs => {
    console.log('Service Workers:', regs);
    regs.forEach(reg => console.log('- Scope:', reg.scope));
});
```

#### B. Проверить подписку на Push
```javascript
navigator.serviceWorker.ready.then(reg => {
    return reg.pushManager.getSubscription();
}).then(sub => {
    if (sub) {
        console.log('✅ Есть активная подписка:', sub.endpoint);
    } else {
        console.log('❌ Нет активной подписки');
    }
});
```

#### C. Проверить разрешения
```javascript
console.log('Notification permission:', Notification.permission);
// Должно быть: "granted"
```

### 5. Тест с закрытым браузером

1. Откройте сайт, подпишитесь на уведомления (если еще не подписаны)
2. **Закройте браузер полностью**
3. Из Django shell отправьте тестовое уведомление (см. п.2)
4. Должно появиться нативное уведомление ОС (даже с закрытым браузером!)

## Возможные проблемы и решения

### Проблема 1: "pywebpush не установлен"
```bash
cd backend
../.venv/Scripts/pip install pywebpush==2.1.2
```

### Проблема 2: VAPID ключи не настроены
```bash
# Сгенерировать новые ключи
.venv/Scripts/python -c "from py_vapid import Vapid; v = Vapid(); v.generate_keys(); print('Public:', v.public_key.decode()); print('Private:', v.private_key.decode())"
```

Добавить в `.env` или `settings.py`.

### Проблема 3: Service Worker не регистрируется
- Проверить, что `sw.js` доступен по URL `/sw.js`
- Проверить консоль браузера на ошибки
- HTTPS обязателен (кроме localhost)

### Проблема 4: Подписка создается, но уведомления не приходят
- Проверить endpoint в БД - должен начинаться с `https://`
- Проверить счетчик ошибок: если `error_count >= 5`, подписка деактивируется
- Проверить логи Django на ошибки `WebPushException`

### Проблема 5: Уведомления приходят дважды
Это нормально для онлайн пользователей:
- Один раз через WebSocket (мгновенно)
- Второй раз через Web Push (с небольшой задержкой)

Браузер обычно дедуплицирует уведомления с одинаковым `tag`.

## Настройки пользователей

Пользователи могут управлять подписками в настройках уведомлений:
- **Канал "Web"** - включает и WebSocket и Web Push
- Отключение канала → не будут приходить уведомления в браузере

API endpoints:
- `GET /api/v1/notifications/push/vapid-key/` - получить публичный ключ
- `POST /api/v1/notifications/push/subscribe/` - подписаться
- `DELETE /api/v1/notifications/push/unsubscribe/` - отписаться
- `GET /api/v1/notifications/push/subscriptions/` - список устройств

## Мониторинг

### Команда для очистки неактивных подписок
```bash
.venv/Scripts/python manage.py cleanup_push_subscriptions
```

Удаляет:
- Неактивные подписки старше 90 дней
- Подписки с 5+ ошибками
- Подписки от несуществующих пользователей

### Статистика
```python
from notifications.models import WebPushSubscription

# Всего подписок
total = WebPushSubscription.objects.count()
active = WebPushSubscription.objects.filter(is_active=True).count()
with_errors = WebPushSubscription.objects.filter(error_count__gt=0).count()

print(f"Всего: {total}, Активных: {active}, С ошибками: {with_errors}")
```

## Заключение

Проблема решена разделением логики отправки WebSocket и Web Push уведомлений. Теперь:

✅ Web Push отправляются **независимо** от статуса WebSocket  
✅ Уведомления приходят даже с **закрытым браузером**  
✅ Service Worker обрабатывает push-события в фоне  
✅ Поддержка offline режима работает корректно  

## Связанные файлы

- `backend/notifications/services.py` - основная логика отправки
- `backend/notifications/models.py` - модель `WebPushSubscription`
- `backend/notifications/api_views.py` - API для управления подписками
- `backend/sw.js` - Service Worker для обработки push-событий
- `backend/static/js/notifications/push-notifications.js` - frontend модуль
- `backend/eusrr_backend/settings.py` - VAPID настройки

## Дальнейшие улучшения

- [ ] Добавить аналитику доставки уведомлений
- [ ] Настройка расписания тихих часов (не беспокоить ночью)
- [ ] Группировка уведомлений по категориям
- [ ] Rich notifications с изображениями и действиями
- [ ] Звуковые уведомления (custom sounds)
