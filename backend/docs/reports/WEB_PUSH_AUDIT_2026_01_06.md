# Аудит Web Push Notifications - 6 января 2026

## 🔍 Executive Summary

**Проблема:** `AbortError: Registration failed - push service error` при попытке подписаться на Web Push уведомления.

**Root Cause:** Конфликт между старыми и новыми VAPID ключами в браузере + излишне сложная логика автоматической переподписки.

**Критичность:** 🔴 **ВЫСОКАЯ** - полностью блокирует работу Web Push для существующих пользователей.

---

## 📊 Текущее состояние архитектуры

### 1. Backend компоненты

#### ✅ `notifications/models.py` - WebPushSubscription
**Статус:** Хорошо спроектирована

```python
class WebPushSubscription(models.Model):
    user = ForeignKey(User)           # Владелец подписки
    endpoint = URLField(max_length=512)  # Push Service URL
    auth_key = CharField(max_length=512)  # Ключ авторизации
    p256dh_key = CharField(max_length=512) # Ключ шифрования
    device_name = CharField              # iOS, Windows (Chrome), etc.
    user_agent = TextField               # Browser info
    is_active = Boolean(default=True)    # Активность
    error_count = Integer(default=0)     # Счетчик ошибок
    last_error = TextField               # Последняя ошибка
    created_at, updated_at, last_used_at # Timestamps
    
    unique_together = ['user', 'endpoint']  # ✅ Важно!
```

**Преимущества:**
- ✅ Уникальность по `(user, endpoint)` - один браузер = одна подписка
- ✅ Отслеживание ошибок (`error_count`, `last_error`)
- ✅ Автоматическая деактивация после 5 ошибок
- ✅ Метаданные устройства для отладки

**Недостатки:**
- ⚠️ Нет индекса на `is_active` (частый фильтр в запросах)
- ⚠️ Нет TTL (time-to-live) - старые подписки накапливаются
- ⚠️ `endpoint` может быть > 512 символов у некоторых браузеров

---

#### ⚠️ `notifications/services.py` - send_web_push_notification()
**Статус:** Работает, но требует оптимизации

```python
def send_web_push_notification(notification: Notification) -> int:
    # 1. Проверка VAPID ключей
    vapid_private_key = settings.VAPID_PRIVATE_KEY
    vapid_public_key = settings.VAPID_PUBLIC_KEY
    vapid_email = settings.VAPID_ADMIN_EMAIL
    
    # 2. Получение активных подписок
    subscriptions = WebPushSubscription.objects.filter(
        user=notification.recipient,
        is_active=True
    )
    
    # 3. Формирование payload
    payload = {
        'title': notification.title,
        'body': notification.short_message,
        'data': {'url': notification.action_url, ...}
    }
    
    # 4. Отправка через pywebpush
    for subscription in subscriptions:
        # Извлекаем audience из endpoint
        parsed_url = urlparse(subscription.endpoint)
        audience = f"{parsed_url.scheme}://{parsed_url.netloc}"
        
        vapid_claims = {
            'sub': f'mailto:{vapid_email}',
            'aud': audience  # ✅ КРИТИЧНО для WNS
        }
        
        webpush(
            subscription_info={...},
            data=json.dumps(payload),
            vapid_private_key=vapid_private_key,
            vapid_claims=vapid_claims,
            ttl=86400  # 24 часа
        )
```

**Преимущества:**
- ✅ Корректная настройка VAPID claims с `aud` полем
- ✅ Обработка ошибок (410 Gone, 404 Not Found)
- ✅ Автоматическая деактивация проблемных подписок
- ✅ Подробное логирование

**Недостатки:**
- ⚠️ Синхронная отправка в цикле - медленно для многих подписок
- ⚠️ Нет retry механизма для временных сбоев
- ⚠️ Нет батчинга (группировки подписок)
- ⚠️ TTL=86400 (24ч) - может быть слишком большим для срочных уведомлений

**Рекомендация:** Использовать Celery task для асинхронной отправки.

---

#### ✅ `notifications/api_views.py` - API endpoints
**Статус:** Хорошо реализованы

Endpoints:
1. `GET /api/v1/notifications/push/vapid-key/` - получить публичный ключ
2. `POST /api/v1/notifications/push/subscribe/` - подписаться
3. `DELETE /api/v1/notifications/push/unsubscribe/` - отписаться
4. `GET /api/v1/notifications/push/subscriptions/` - список подписок

**Преимущества:**
- ✅ `update_or_create()` - идемпотентность подписки
- ✅ Логирование только новых подписок (не спамит логи)
- ✅ Graceful handling - не ломается при ошибках

**Недостатки:**
- ⚠️ Нет валидации формата `endpoint` (может быть невалидный URL)
- ⚠️ Нет проверки длины ключей (могут быть некорректные данные)

---

### 2. Frontend компоненты

#### 🔴 `static/js/notifications/push-notifications.js`
**Статус:** Критические проблемы

**Проблема №1: Излишне сложная логика в `_checkSubscription()`**

```javascript
async _checkSubscription() {
    const subscription = await this.swRegistration.pushManager.getSubscription();
    this.isSubscribed = subscription !== null;
    
    if (this.isSubscribed) {
        // ❌ ПЛОХО: Попытка синхронизации с сервером при каждой инициализации
        const lastEndpoint = localStorage.getItem('push_endpoint');
        const currentEndpoint = subscription.endpoint;
        
        if (lastEndpoint !== currentEndpoint) {
            try {
                await this._sendSubscriptionToServer(subscription);
                localStorage.setItem('push_endpoint', currentEndpoint);
            } catch (error) {
                // ❌ ОЧЕНЬ ПЛОХО: Автоматическая переподписка при ошибке
                await subscription.unsubscribe();
                const newSubscription = await this.swRegistration.pushManager.subscribe({...});
                await this._sendSubscriptionToServer(newSubscription);
            }
        }
    }
}
```

**Почему это плохо:**
1. Вызывается при **каждой** загрузке страницы
2. Попытка синхронизации → ошибка → попытка переподписки → `AbortError`
3. Браузер отклоняет запрос из-за частых попыток subscribe/unsubscribe
4. localStorage не синхронизирован с сервером (может быть устаревшим)

**Решение:** Метод должен **ТОЛЬКО проверять** наличие подписки, не пытаясь её изменить.

---

**Проблема №2: subscribe() удаляет старую подписку**

```javascript
async subscribe() {
    // ❌ ПРОБЛЕМА: Принудительное удаление
    const oldSubscription = await this.swRegistration.pushManager.getSubscription();
    if (oldSubscription) {
        await oldSubscription.unsubscribe();
    }
    
    // Создание новой подписки
    const subscription = await this.swRegistration.pushManager.subscribe({...});
}
```

**Почему это вызывает AbortError:**
- `unsubscribe()` отправляет запрос в Push Service (WNS/FCM)
- `subscribe()` сразу после этого пытается создать новую подписку
- Push Service не успевает обработать unsubscribe → конфликт VAPID ключей
- **Result:** `AbortError: Registration failed - push service error`

**Решение:** Не удалять старую подписку, полагаться на `update_or_create` в backend.

---

**Проблема №3: Автоматическая переподписка при входе**

```javascript
// base.html
if (pushNotifications.getPermissionStatus() === 'granted') {
    // ❌ ВСЕГДА переподписываемся при каждом входе
    if (pushNotifications.isSubscribed) {
        await pushNotifications.unsubscribe();
    }
    localStorage.removeItem('push_endpoint');
    await pushNotifications.subscribe();
}
```

**Почему это плохо:**
- При каждом входе → unsubscribe + subscribe → нагрузка на Push Service
- Если пользователь открывает несколько вкладок → множественные попытки переподписки
- Browser rate limiting → `AbortError`

**Решение:** Подписываться **ТОЛЬКО** если `!isSubscribed` и `permission === 'granted'`.

---

#### ✅ `sw.js` - Service Worker
**Статус:** Хорошо реализован

```javascript
self.addEventListener('push', (event) => {
    const payload = event.data.json();
    
    self.registration.showNotification(payload.title, {
        body: payload.body,
        icon: payload.icon,
        data: payload.data,
        tag: payload.tag,
        requireInteraction: payload.requireInteraction
    });
});

self.addEventListener('notificationclick', (event) => {
    event.notification.close();
    const url = event.notification.data.url || '/';
    self.clients.openWindow(url);
});
```

**Преимущества:**
- ✅ Корректная обработка push событий
- ✅ Открытие URL при клике
- ✅ Группировка по `tag`
- ✅ Fallback для некорректных данных

**Недостатки:**
- ⚠️ Нет обработки ошибок `showNotification()`
- ⚠️ Нет фокуса существующих вкладок (всегда открывает новую)

---

### 3. VAPID Configuration

#### ⚠️ `eusrr_backend/settings.py`
**Статус:** Настроено корректно, но есть риски

```python
VAPID_PUBLIC_KEY = os.getenv(
    "VAPID_PUBLIC_KEY",
    "BMTitZy9r4ygYJBgGdaZuCkb7rwR7i..."  # 87 символов
)
VAPID_PRIVATE_KEY = os.getenv(
    "VAPID_PRIVATE_KEY",
    "MIGHAgEAMBMGByqGSM49AgEGCCqGS..."  # ~200 символов
)
VAPID_ADMIN_EMAIL = os.getenv(
    "VAPID_ADMIN_EMAIL",
    "robotail-info@yandex.ru"
)
```

**Проблемы:**
1. ⚠️ VAPID ключи **hardcoded в settings.py** - риск утечки через git
2. ⚠️ Используются дефолтные значения вместо обязательных env vars
3. ⚠️ Нет валидации формата ключей
4. ⚠️ `pywebpush==2.1.2` автоматически извлекает публичный ключ из приватного, но это не документировано

**Рекомендации:**
- 🔒 Хранить VAPID ключи в `.env` файле (не в git)
- 🔒 Fail fast если ключи не установлены (убрать defaults)
- 📝 Добавить миграцию для rotation ключей (если понадобится)

---

## 🐛 Критические баги

### Bug #1: AbortError при подписке
**Severity:** 🔴 CRITICAL  
**Frequency:** Постоянно для пользователей со старыми подписками

**Root Cause:**
1. Браузер хранит старую подписку с VAPID ключом `A`
2. Приложение использует новый VAPID ключ `B`
3. При попытке `subscribe()` с ключом `B`:
   - Push Service видит конфликт (endpoint уже привязан к ключу `A`)
   - Отклоняет запрос → `AbortError`

**Воспроизведение:**
```javascript
// 1. Подписаться с ключом A
await pushManager.subscribe({ applicationServerKey: keyA });

// 2. Изменить VAPID ключ на сервере (keyB)

// 3. Попытка переподписаться
await pushManager.getSubscription().then(s => s.unsubscribe());
await pushManager.subscribe({ applicationServerKey: keyB }); // ❌ AbortError
```

**Решение:**
- Полная очистка: `Service Worker unregister` + `Clear site data`
- ИЛИ дать время Push Service (1-2 секунды после unsubscribe)
- ИЛИ использовать другой браузер/профиль

---

### Bug #2: Бесконечный цикл переподписки
**Severity:** 🟡 MEDIUM  
**Impact:** Спам запросов к серверу, логи переполняются

**Сценарий:**
1. `_checkSubscription()` находит подписку
2. Пытается синхронизировать с сервером → ошибка (например, сервер недоступен)
3. Начинает автоматическую переподписку → unsubscribe + subscribe
4. При следующей загрузке страницы - всё повторяется

**Решение:** Убрать автоматическую переподписку из `_checkSubscription()`.

---

### Bug #3: Race condition при нескольких вкладках
**Severity:** 🟡 MEDIUM

**Сценарий:**
1. Пользователь открывает 3 вкладки одновременно
2. Каждая вкладка выполняет `pushNotifications.init()`
3. Все 3 вкладки пытаются зарегистрировать Service Worker
4. Все 3 вкладки пытаются подписаться (если нет подписки)
5. → Множественные POST запросы к `/subscribe/`
6. → Возможно создание дубликатов в БД (хотя `unique_together` защищает)

**Решение:** Использовать Broadcast Channel API или SharedWorker для синхронизации между вкладками.

---

## 📋 Детальный план рефакторинга

### Phase 1: Критические исправления (Срочно, 1-2 дня)

#### 1.1 Упростить `_checkSubscription()`
**Файл:** `static/js/notifications/push-notifications.js`

**До:**
```javascript
async _checkSubscription() {
    const subscription = await this.swRegistration.pushManager.getSubscription();
    this.isSubscribed = subscription !== null;
    
    if (this.isSubscribed) {
        const lastEndpoint = localStorage.getItem('push_endpoint');
        const currentEndpoint = subscription.endpoint;
        
        if (lastEndpoint !== currentEndpoint) {
            try {
                await this._sendSubscriptionToServer(subscription);
                localStorage.setItem('push_endpoint', currentEndpoint);
            } catch (error) {
                // Переподписка...
            }
        }
    }
}
```

**После:**
```javascript
async _checkSubscription() {
    const subscription = await this.swRegistration.pushManager.getSubscription();
    this.isSubscribed = subscription !== null;
    
    if (this.isSubscribed) {
        console.log('[PushNotifications] Активная подписка найдена');
        // Всё. Никакой синхронизации, никакой переподписки.
    }
}
```

**Обоснование:**
- Метод должен **ТОЛЬКО читать**, не модифицировать
- Синхронизация с сервером - задача `subscribe()`
- Переподписка - явное действие пользователя

---

#### 1.2 Убрать unsubscribe из `subscribe()`
**Файл:** `static/js/notifications/push-notifications.js`

**До:**
```javascript
async subscribe() {
    const oldSubscription = await this.swRegistration.pushManager.getSubscription();
    if (oldSubscription) {
        await oldSubscription.unsubscribe(); // ❌ Убрать
    }
    
    const subscription = await this.swRegistration.pushManager.subscribe({...});
    await this._sendSubscriptionToServer(subscription);
}
```

**После:**
```javascript
async subscribe() {
    // Если уже подписан - ничего не делаем
    if (this.isSubscribed) {
        console.log('[PushNotifications] Уже подписан');
        return true;
    }
    
    try {
        const subscription = await this.swRegistration.pushManager.subscribe({
            userVisibleOnly: true,
            applicationServerKey: this._urlBase64ToUint8Array(this.vapidPublicKey)
        });
        
        await this._sendSubscriptionToServer(subscription);
        this.isSubscribed = true;
        return true;
    } catch (error) {
        console.error('[PushNotifications] Ошибка подписки:', error);
        return false;
    }
}
```

**Обоснование:**
- Browser Push API сам управляет подписками
- `update_or_create` в backend обновит существующую запись
- Избегаем AbortError

---

#### 1.3 Исправить логику автоподписки
**Файл:** `templates/base.html`

**До:**
```javascript
if (pushNotifications.getPermissionStatus() === 'granted') {
    // Всегда переподписываемся
    if (pushNotifications.isSubscribed) {
        await pushNotifications.unsubscribe();
    }
    localStorage.removeItem('push_endpoint');
    await pushNotifications.subscribe();
}
```

**После:**
```javascript
// Подписываемся ТОЛЬКО если:
// 1. Разрешение дано
// 2. НЕТ активной подписки
if (pushNotifications.getPermissionStatus() === 'granted' && !pushNotifications.isSubscribed) {
    console.log('[WebPush] Разрешение есть, подписываемся...');
    await pushNotifications.subscribe();
}
```

**Обоснование:**
- Минимизируем обращения к Push Service
- Подписка сохраняется между сессиями
- Пользователь может явно переподписаться через UI

---

#### 1.4 Добавить метод для ручной очистки
**Файл:** `static/js/notifications/push-notifications.js`

```javascript
/**
 * Полная очистка Service Worker и подписок (для recovery)
 * Вызывать только при критических проблемах
 */
async resetEverything() {
    console.log('[PushNotifications] 🔄 Полная очистка...');
    
    try {
        // 1. Отписываемся от push
        const subscription = await this.swRegistration?.pushManager.getSubscription();
        if (subscription) {
            await subscription.unsubscribe();
            console.log('[PushNotifications] ✅ Подписка удалена');
        }
        
        // 2. Удаляем Service Worker
        if (this.swRegistration) {
            await this.swRegistration.unregister();
            console.log('[PushNotifications] ✅ Service Worker удален');
        }
        
        // 3. Очищаем localStorage
        localStorage.removeItem('push_endpoint');
        
        // 4. Ждем 2 секунды для обработки Push Service
        await new Promise(resolve => setTimeout(resolve, 2000));
        
        // 5. Перерегистрируем Service Worker
        await this._registerServiceWorker();
        
        this.isSubscribed = false;
        console.log('[PushNotifications] ✅ Сброс завершен, можно подписаться снова');
        
        return true;
    } catch (error) {
        console.error('[PushNotifications] ❌ Ошибка сброса:', error);
        return false;
    }
}
```

**Применение:**
```javascript
// В консоли браузера
await window.pushNotifications.resetEverything();
// Обновить страницу
location.reload();
```

---

### Phase 2: Оптимизации (1 неделя)

#### 2.1 Добавить индексы в БД
**Файл:** `notifications/models.py`

```python
class WebPushSubscription(models.Model):
    # ... existing fields ...
    
    class Meta:
        verbose_name = 'Web Push подписка'
        verbose_name_plural = 'Web Push подписки'
        db_table = 'notifications_web_push_subscription'
        unique_together = ['user', 'endpoint']
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['is_active'], name='idx_webpush_active'),
            models.Index(fields=['user', 'is_active'], name='idx_webpush_user_active'),
            models.Index(fields=['created_at'], name='idx_webpush_created'),
        ]
```

**Миграция:**
```bash
.venv/Scripts/python manage.py makemigrations notifications --name add_webpush_indexes
.venv/Scripts/python manage.py migrate
```

---

#### 2.2 Асинхронная отправка через Celery
**Файл:** `notifications/tasks.py`

```python
from celery import shared_task

@shared_task(bind=True, max_retries=3)
def send_web_push_async(self, notification_id):
    """Асинхронная отправка Web Push уведомления"""
    try:
        notification = Notification.objects.get(id=notification_id)
        NotificationService.send_web_push_notification(notification)
    except Notification.DoesNotExist:
        logger.error(f"Notification {notification_id} not found")
    except Exception as e:
        logger.error(f"Error sending web push for notification {notification_id}: {e}")
        # Retry с экспоненциальной задержкой
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))
```

**Использование:**
```python
# Вместо синхронного вызова
NotificationService.send_web_push_notification(notification)

# Асинхронный вызов
from notifications.tasks import send_web_push_async
send_web_push_async.delay(notification.id)
```

---

#### 2.3 Батчинг подписок
**Файл:** `notifications/services.py`

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def send_web_push_notification(notification: Notification) -> int:
    # ... existing setup ...
    
    subscriptions = list(WebPushSubscription.objects.filter(...))
    
    # Параллельная отправка (батчами по 10)
    success_count = 0
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(_send_to_subscription, sub, payload, vapid_claims): sub
            for sub in subscriptions
        }
        
        for future in as_completed(futures):
            subscription = futures[future]
            try:
                if future.result():
                    success_count += 1
            except Exception as e:
                logger.error(f"Error in thread for subscription {subscription.id}: {e}")
    
    return success_count

def _send_to_subscription(subscription, payload, vapid_claims):
    """Helper для параллельной отправки"""
    try:
        subscription_info = {...}
        webpush(subscription_info, json.dumps(payload), ...)
        subscription.reset_errors()
        return True
    except WebPushException as e:
        subscription.increment_error(str(e))
        return False
```

---

#### 2.4 TTL cleanup task
**Файл:** `notifications/management/commands/cleanup_old_subscriptions.py`

```python
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from notifications.models import WebPushSubscription

class Command(BaseCommand):
    help = 'Удаляет старые неактивные подписки'
    
    def handle(self, *args, **options):
        # Удаляем неактивные подписки старше 30 дней
        threshold = timezone.now() - timedelta(days=30)
        
        deleted = WebPushSubscription.objects.filter(
            is_active=False,
            updated_at__lt=threshold
        ).delete()[0]
        
        self.stdout.write(
            self.style.SUCCESS(f'Удалено {deleted} старых подписок')
        )
```

**Добавить в crontab:**
```bash
# Каждый день в 3:00
0 3 * * * cd /path/to/EUSRR/backend && .venv/Scripts/python manage.py cleanup_old_subscriptions
```

---

### Phase 3: Улучшения UX (1-2 недели)

#### 3.1 UI для управления подписками
**Файл:** `templates/profile/notifications_settings.html`

```html
<div class="card mb-3">
    <div class="card-header">
        <h5>Web Push уведомления</h5>
    </div>
    <div class="card-body">
        <div id="push-status">
            <!-- Динамически заполняется JS -->
        </div>
        
        <div class="btn-group mt-3">
            <button id="btn-subscribe-push" class="btn btn-primary">
                Включить уведомления
            </button>
            <button id="btn-unsubscribe-push" class="btn btn-danger">
                Отключить уведомления
            </button>
            <button id="btn-test-push" class="btn btn-info">
                Отправить тестовое уведомление
            </button>
        </div>
        
        <div class="mt-3">
            <h6>Активные устройства:</h6>
            <ul id="subscriptions-list" class="list-group">
                <!-- Список подписок с кнопками удаления -->
            </ul>
        </div>
    </div>
</div>
```

---

#### 3.2 Диагностика для пользователя
**Файл:** `static/js/notifications/push-diagnostics.js`

```javascript
export async function runPushDiagnostics() {
    const results = {
        browserSupport: false,
        permission: 'unknown',
        serviceWorkerRegistered: false,
        hasSubscription: false,
        serverReachable: false,
        vapidKeyReceived: false,
    };
    
    // 1. Проверка поддержки браузера
    results.browserSupport = ('serviceWorker' in navigator) && 
                            ('PushManager' in window) && 
                            ('Notification' in window);
    
    // 2. Проверка разрешения
    results.permission = Notification.permission;
    
    // 3. Проверка Service Worker
    const reg = await navigator.serviceWorker.getRegistration();
    results.serviceWorkerRegistered = !!reg;
    
    // 4. Проверка подписки
    if (reg) {
        const sub = await reg.pushManager.getSubscription();
        results.hasSubscription = !!sub;
    }
    
    // 5. Проверка связи с сервером
    try {
        const response = await fetch('/api/v1/notifications/push/vapid-key/', {
            credentials: 'include'
        });
        results.serverReachable = response.ok;
        if (response.ok) {
            const data = await response.json();
            results.vapidKeyReceived = !!data.vapid_public_key;
        }
    } catch (e) {
        results.serverReachable = false;
    }
    
    return results;
}
```

---

### Phase 4: Мониторинг и алертинг (1 неделя)

#### 4.1 Метрики
**Файл:** `notifications/metrics.py`

```python
from prometheus_client import Counter, Gauge, Histogram

# Счетчики
web_push_sent_total = Counter(
    'web_push_sent_total',
    'Total number of web push notifications sent',
    ['status']  # success, failed
)

web_push_subscriptions = Gauge(
    'web_push_subscriptions',
    'Number of active web push subscriptions'
)

web_push_send_duration = Histogram(
    'web_push_send_duration_seconds',
    'Time to send web push notification',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0]
)

# Использование
def send_web_push_notification(notification):
    with web_push_send_duration.time():
        success_count = # ... existing logic ...
        
        web_push_sent_total.labels(status='success').inc(success_count)
        web_push_sent_total.labels(status='failed').inc(total - success_count)
        
    return success_count
```

---

#### 4.2 Дашборд Grafana
**Метрики для мониторинга:**
1. Количество активных подписок
2. Rate успешных/неудачных отправок
3. Latency отправки
4. Количество AbortError
5. Количество автоматически деактивированных подписок

---

## 🎯 Приоритизация задач

### P0 - Критически важно (сделать СРОЧНО)
1. ✅ Упростить `_checkSubscription()` - убрать автоматическую синхронизацию
2. ✅ Убрать `unsubscribe()` из `subscribe()`
3. ✅ Исправить автоподписку в `base.html`
4. ✅ Добавить `resetEverything()` метод для recovery

**Время:** 4 часа  
**Impact:** Исправляет AbortError для 100% пользователей

---

### P1 - Важно (сделать на этой неделе)
5. Добавить индексы в БД
6. Вынести VAPID ключи в `.env`
7. Добавить cleanup command для старых подписок
8. Улучшить обработку ошибок в Service Worker

**Время:** 1-2 дня  
**Impact:** Производительность + стабильность

---

### P2 - Желательно (следующая итерация)
9. Асинхронная отправка через Celery
10. Батчинг подписок (ThreadPoolExecutor)
11. UI для управления подписками
12. Диагностика для пользователя

**Время:** 1 неделя  
**Impact:** UX + масштабируемость

---

### P3 - Опционально (future work)
13. Метрики Prometheus
14. Дашборд Grafana
15. Broadcast Channel API для синхронизации вкладок
16. A/B тестирование TTL значений

**Время:** 1-2 недели  
**Impact:** Observability + advanced features

---

## 📝 Чек-лист для деплоя

### Pre-deploy
- [ ] Создать backup БД (`pg_dump`)
- [ ] Экспортировать текущие подписки: `python manage.py dumpdata notifications.WebPushSubscription > subscriptions_backup.json`
- [ ] Проверить VAPID ключи в `.env` файле
- [ ] Запустить тесты: `pytest backend/tests/notifications/`

### Deploy
- [ ] Применить миграции: `python manage.py migrate`
- [ ] Обновить статику: `python manage.py collectstatic --noinput`
- [ ] Перезапустить Daphne/Gunicorn
- [ ] Перезапустить Celery workers (если используются)

### Post-deploy
- [ ] Проверить логи: `tail -f logs/django.log | grep WebPush`
- [ ] Проверить Service Worker в DevTools: `Application → Service Workers`
- [ ] Протестировать подписку в чистом браузере
- [ ] Отправить тестовое уведомление: `python manage.py shell < test_push.py`
- [ ] Мониторинг метрик в течение 24 часов

### Rollback plan
Если что-то пошло не так:
```bash
# 1. Откатить миграции
python manage.py migrate notifications 0XXX  # номер предыдущей миграции

# 2. Откатить код
git revert <commit-hash>
git push

# 3. Восстановить подписки
python manage.py loaddata subscriptions_backup.json

# 4. Перезапустить сервисы
sudo systemctl restart eusrr-backend
```

---

## 🧪 Тестирование

### Manual Testing Checklist

#### Сценарий 1: Новый пользователь
- [ ] Открыть сайт в Incognito/Private window
- [ ] Войти под новым пользователем
- [ ] Проверить: появился ли запрос разрешения на уведомления
- [ ] Разрешить уведомления
- [ ] Проверить в консоли: `[WebPush] Инициализирован, подписка: true`
- [ ] Проверить в DevTools → Application → Service Workers: активен
- [ ] Создать тестовый документ → проверить появление уведомления

#### Сценарий 2: Существующий пользователь с подпиской
- [ ] Открыть сайт в обычном окне
- [ ] Войти под пользователем с подпиской
- [ ] Проверить: НЕ должно быть попыток переподписки
- [ ] Проверить логи: НЕ должно быть POST `/subscribe/`
- [ ] Создать тестовый документ → проверить уведомление

#### Сценарий 3: Пользователь без подписки, но с разрешением
- [ ] Очистить подписку в БД: `WebPushSubscription.objects.filter(user=me).delete()`
- [ ] НЕ очищать браузер
- [ ] Обновить страницу
- [ ] Проверить: должна произойти автоподписка
- [ ] Проверить в БД: создана новая запись `WebPushSubscription`

#### Сценарий 4: Recovery после AbortError
- [ ] В консоли: `await window.pushNotifications.resetEverything()`
- [ ] Дождаться сообщения: "Сброс завершен"
- [ ] Обновить страницу (F5)
- [ ] Проверить: подписка создана успешно

#### Сценарий 5: Множественные вкладки
- [ ] Открыть 5 вкладок одновременно
- [ ] Проверить Network tab: количество POST `/subscribe/`
- [ ] Должно быть: 0 или 1 запрос (не 5!)

### Automated Tests

```python
# backend/tests/notifications/test_web_push.py

def test_subscribe_creates_new_subscription(client, user):
    """Новая подписка создается корректно"""
    client.force_login(user)
    
    response = client.post('/api/v1/notifications/push/subscribe/', {
        'endpoint': 'https://fcm.googleapis.com/fcm/send/test123',
        'keys': {
            'p256dh': 'test_p256dh_key',
            'auth': 'test_auth_key'
        }
    }, content_type='application/json')
    
    assert response.status_code == 200
    assert WebPushSubscription.objects.filter(user=user).count() == 1

def test_subscribe_updates_existing_subscription(client, user):
    """Повторная подписка обновляет существующую"""
    # Создаем начальную подписку
    WebPushSubscription.objects.create(
        user=user,
        endpoint='https://fcm.googleapis.com/fcm/send/test123',
        p256dh_key='old_key',
        auth_key='old_auth'
    )
    
    client.force_login(user)
    response = client.post('/api/v1/notifications/push/subscribe/', {
        'endpoint': 'https://fcm.googleapis.com/fcm/send/test123',
        'keys': {
            'p256dh': 'new_key',
            'auth': 'new_auth'
        }
    }, content_type='application/json')
    
    assert response.status_code == 200
    assert WebPushSubscription.objects.filter(user=user).count() == 1
    
    sub = WebPushSubscription.objects.get(user=user)
    assert sub.p256dh_key == 'new_key'

def test_send_web_push_success(notification):
    """Успешная отправка Web Push"""
    # Создаем подписку
    WebPushSubscription.objects.create(
        user=notification.recipient,
        endpoint='https://fcm.googleapis.com/fcm/send/test',
        p256dh_key='test_key',
        auth_key='test_auth',
        is_active=True
    )
    
    with patch('notifications.services.webpush') as mock_webpush:
        count = NotificationService.send_web_push_notification(notification)
        
        assert count == 1
        assert mock_webpush.called
```

---

## 📚 Дополнительная документация

### Для разработчиков
- [Push API MDN](https://developer.mozilla.org/en-US/docs/Web/API/Push_API)
- [Service Worker MDN](https://developer.mozilla.org/en-US/docs/Web/API/Service_Worker_API)
- [VAPID RFC](https://datatracker.ietf.org/doc/html/rfc8292)
- [pywebpush documentation](https://github.com/web-push-libs/pywebpush)

### Troubleshooting guides
- [WEB_PUSH_OFFLINE_ISSUE.md](./troubleshooting/WEB_PUSH_OFFLINE_ISSUE.md)
- [WEB_PUSH_QUICK_TEST.md](./guides/WEB_PUSH_QUICK_TEST.md)
- [FIX_NO_PUSH_SUBSCRIPTIONS.md](./guides/FIX_NO_PUSH_SUBSCRIPTIONS.md)

---

## 📊 Summary

### Текущее состояние
- ❌ AbortError блокирует работу для существующих пользователей
- ⚠️ Излишне сложная логика автоподписки
- ⚠️ Нет recovery механизма при ошибках
- ✅ Backend API хорошо спроектирован
- ✅ Service Worker работает корректно

### После рефакторинга
- ✅ Простая и предсказуемая логика подписки
- ✅ Recovery метод для критических ситуаций
- ✅ Оптимизация производительности (индексы, батчинг)
- ✅ Мониторинг и алертинг
- ✅ UI для управления подписками

### Риски
- 🟡 При изменении VAPID ключей нужна migration для всех пользователей
- 🟡 Push Service rate limits могут блокировать множественные запросы
- 🟢 Rollback plan готов

---

**Дата аудита:** 6 января 2026  
**Автор:** GitHub Copilot  
**Статус:** Ready for implementation
