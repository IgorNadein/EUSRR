# Решение: Нет активных Web Push подписок

**Проблема:** `[NotificationService.send_web_push_notification] ℹ️ Нет активных push-подписок`

**Причина:** В базе данных нет записей WebPushSubscription для пользователя. Браузер не подписан на уведомления.

## Быстрое решение (3 шага)

### Шаг 1: Откройте сайт и консоль браузера

1. Откройте http://localhost:9000 (или ваш адрес)
2. Нажмите F12 → вкладка Console

### Шаг 2: Проверьте статус

Вставьте в консоль:

```javascript
// Проверка 1: Service Worker
navigator.serviceWorker.getRegistrations().then(regs => {
    console.log('Service Workers:', regs.length);
    if (regs.length === 0) console.error('❌ Service Worker НЕ зарегистрирован!');
});

// Проверка 2: Разрешение
console.log('Permission:', Notification.permission);
// Должно быть: "granted"

// Проверка 3: Подписка
navigator.serviceWorker.ready.then(reg => {
    return reg.pushManager.getSubscription();
}).then(sub => {
    if (sub) {
        console.log('✅ Подписка активна:', sub.endpoint.substr(0, 50) + '...');
    } else {
        console.error('❌ Нет подписки!');
    }
});

// Проверка 4: Наш модуль
if (window.pushNotifications) {
    console.log('✅ pushNotifications загружен, isSubscribed:', window.pushNotifications.isSubscribed);
} else {
    console.error('❌ pushNotifications НЕ загружен!');
}
```

### Шаг 3: Подписаться

Если подписки нет, выполните:

```javascript
// Вариант A: Через наш модуль (если загружен)
if (window.pushNotifications) {
    window.pushNotifications.subscribe().then(success => {
        console.log(success ? '✅ Подписка успешна!' : '❌ Ошибка подписки');
    });
}

// Вариант B: Вручную импортировать и подписаться
else {
    import('/static/js/notifications/push-notifications.js')
        .then(module => {
            window.pushNotifications = new module.PushNotificationsManager();
            return window.pushNotifications.init();
        })
        .then(() => {
            console.log('Инициализирован, подписываемся...');
            return window.pushNotifications.subscribe();
        })
        .then(success => {
            console.log(success ? '✅ Подписка успешна!' : '❌ Ошибка подписки');
        })
        .catch(err => console.error('Ошибка:', err));
}
```

**При первом вызове браузер покажет диалог:**
```
localhost хочет:
☐ Показывать уведомления
     [Блокировать] [Разрешить]
```

**Нажмите "Разрешить"!**

### Шаг 4: Проверьте в БД

После подписки проверьте Django shell:

```python
from notifications.models import WebPushSubscription
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(email='igor_26reg@mail.ru')

subs = WebPushSubscription.objects.filter(user=user, is_active=True)
print(f"Активных подписок: {subs.count()}")
for sub in subs:
    print(f"  - {sub.device_name}: {sub.endpoint[:60]}...")
```

Должно быть >= 1.

### Шаг 5: Отправьте тест

```python
from notifications.services import NotificationService
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(email='igor_26reg@mail.ru')

notification = NotificationService.create_notification(
    recipient=user,
    notification_type_code='system_announcement',
    title='🎉 Web Push работает!',
    message='Вы успешно подписались на push-уведомления. Теперь они будут приходить даже с закрытым браузером!',
    action_url='/notifications/',
    send_immediately=True
)
```

**Закройте браузер полностью** и отправьте еще раз - должно прийти нативное уведомление!

## Возможные проблемы

### ❌ Service Worker не регистрируется

**Проверка:** http://localhost:9000/sw.js - должен открыться JS файл

**Решение:** Убедитесь что файл `backend/sw.js` существует и доступен.

### ❌ Разрешение "denied"

**Причина:** Пользователь нажал "Блокировать" в диалоге браузера

**Решение:**

**Chrome:**
1. Адресная строка → Замок 🔒 → Настройки сайта
2. Уведомления → Разрешить
3. Перезагрузите страницу → выполните подписку

**Firefox:**
1. Адресная строка → 🛈 → Дополнительная информация
2. Разрешения → Показывать уведомления → Разрешить
3. Перезагрузите страницу → выполните подписку

### ❌ pushNotifications не загружается

**Причина:** Не авторизован или ошибка загрузки модуля

**Проверка в консоли:**
```javascript
// Смотрим ошибки загрузки
console.error = console.error;  // Показать все ошибки

// Проверить что пользователь авторизован
fetch('/api/v1/notifications/push/vapid-key/', {credentials: 'include'})
    .then(r => r.json())
    .then(d => console.log('✅ Авторизован, VAPID key:', d.vapid_public_key.substr(0, 20) + '...'))
    .catch(e => console.error('❌ Не авторизован:', e));
```

### ❌ HTTPS требуется

**На production:** Push API требует HTTPS (кроме localhost)

**Решение:** Используйте HTTPS или тестируйте на localhost.

### ❌ Подписка создается, но не сохраняется на сервере

**Лог в консоли:**
```
[PushNotifications] Push-подписка создана: https://...
[PushNotifications] Ошибка: Не удалось сохранить подписку на сервере
```

**Проверка:** Откройте Network tab (F12), отправьте POST на `/api/v1/notifications/push/subscribe/`

**Возможные причины:**
- CSRF токен не найден
- Не авторизован
- Ошибка на сервере

**Решение:**
```javascript
// Проверить CSRF токен
console.log('CSRF token:', 
    document.querySelector('[name=csrfmiddlewaretoken]')?.value 
    || document.cookie.match(/csrftoken=([^;]+)/)?.[1]
);
```

## Автоматическая подписка после входа

Добавьте в `base.html` (уже есть):

```html
<script type="module">
  import { pushNotifications } from "{% static 'js/notifications/push-notifications.js' %}";
  
  document.addEventListener('DOMContentLoaded', async () => {
    const initialized = await pushNotifications.init();
    
    if (initialized) {
      // Если разрешение дано, но нет подписки - подписываем автоматически
      if (pushNotifications.getPermissionStatus() === 'granted' && !pushNotifications.isSubscribed) {
        await pushNotifications.subscribe();
      }
    }
  });
</script>
```

Этот код **уже есть** в вашем `base.html` (строки 142-169), но работает только если:
1. Пользователь авторизован
2. Разрешение уже дано (`Notification.permission === 'granted'`)

Если разрешение не дано - нужно **вручную** попросить через UI (кнопка "Включить уведомления").

## Итог

Чтобы Web Push работал:

1. ✅ **Код исправлен** - Web Push вызывается независимо
2. ⚠️ **Нужно подписаться** - выполните шаги 1-3 выше
3. ✅ **После подписки** - уведомления будут приходить даже с закрытым браузером

Ваш код **работает правильно**. Просто нужно **создать подписку** в браузере!
