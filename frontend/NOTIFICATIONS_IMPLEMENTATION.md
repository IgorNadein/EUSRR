# Реализация системы уведомлений на фронтенде

**Дата:** 2026-02-27  
**Технологии:** Next.js 16.1.6, React 19, TypeScript 5, Sonner  
**Статус:** ✅ Завершено

## Обзор

Реализована полноценная система уведомлений для фронтенда с поддержкой:
- 📱 **Web Push** - нативные push уведомления (работают даже когда вкладка закрыта)
- 🔔 **Toast уведомления** - всплывающие уведомления в интерфейсе (Sonner)
- 📋 **Notification Center** - центр уведомлений с badge и историей
- ⚙️ **Настройки** - управление подписками на push уведомления

## Установленные библиотеки

```json
{
  "sonner": "^1.x" // Toast уведомления для Next.js
}
```

**Почему Sonner?**
- ✅ Создан специально для Next.js/React
- ✅ Легковесный (2.5KB gzipped)
- ✅ Красивый дизайн из коробки
- ✅ Поддержка promise/loading состояний
- ✅ Используется в shadcn/ui

## Структура файлов

```
frontend/
├── public/
│   └── sw.js                                      # Service Worker для Web Push
├── src/
│   ├── components/
│   │   ├── NotificationCenter.tsx                 # UI компонент центра уведомлений
│   │   ├── Providers.tsx                          # Добавлен Toaster от Sonner
│   │   └── AppShell.tsx                           # Интегрирован NotificationCenter в header
│   ├── hooks/
│   │   ├── useWebPush.ts                          # React хук для Web Push
│   │   └── useApi.ts                              # Уже был (useNotifications)
│   └── lib/
│       ├── push.ts                                # Утилиты для Web Push
│       └── api.ts                                 # Добавлены методы push подписок
```

## Компоненты и функции

### 1. Service Worker (`public/sw.js`)

**Назначение:** Обрабатывает входящие push события от сервера даже когда вкладка закрыта.

**Функции:**
- `push` event - получение и показ нативных уведомлений
- `notificationclick` event - открытие страницы при клике
- `notificationclose` event - отправка статистики (опционально)

**Формат данных от сервера:**
```javascript
{
  "title": "Новая заявка",
  "body": "Заявка #123 требует вашего внимания",
  "icon": "/logo.png",
  "tag": "notification-123",
  "data": {
    "url": "/requests/123",
    "notification_id": 123,
    "category": "requests"
  },
  "requireInteraction": false
}
```

**Регистрация:** Автоматическая при вызове `useWebPush()`.

### 2. Web Push хук (`hooks/useWebPush.ts`)

**Назначение:** React хук для управления Web Push подписками.

**Использование:**
```tsx
import { useWebPush } from '@/hooks/useWebPush';

function MyComponent() {
  const { 
    isSupported,      // Поддерживается ли Web Push
    isSubscribed,     // Есть ли активная подписка
    permission,       // 'default' | 'granted' | 'denied'
    subscribe,        // Подписаться
    unsubscribe,      // Отписаться
    isLoading         // Загрузка
  } = useWebPush();

  return (
    <button 
      onClick={subscribe} 
      disabled={!isSupported || isLoading}
    >
      {isSubscribed ? 'Отключить' : 'Включить'} уведомления
    </button>
  );
}
```

**API методы:**
- `subscribe()` - запрашивает разрешение и создает подписку
- `unsubscribe()` - удаляет подписку
- `requestPermission()` - явно запрашивает разрешение

**Внутренняя логика:**
1. Проверяет поддержку браузером (`isPushSupported()`)
2. Получает VAPID ключ с сервера
3. Регистрирует Service Worker
4. Создает push подписку (`PushManager.subscribe()`)
5. Отправляет данные подписки на сервер

### 3. NotificationCenter (`components/NotificationCenter.tsx`)

**Назначение:** UI компонент центра уведомлений с иконкой bell.

**Возможности:**
- 🔔 Badge с количеством непрочитанных
- 📋 Список последних 20 уведомлений
- ✅ Отметка как прочитано
- ⚙️ Настройки push подписок
- 📱 Респонсивный дизайн (desktop + mobile)

**Структура:**
```tsx
<NotificationCenter>
  <button> {/* Bell иконка с badge */} </button>
  <dropdown>
    <header> {/* Заголовок + кнопки */} </header>
    <settings> {/* Включить/выключить push */} </settings>
    <list> {/* Список уведомлений */} </list>
    <footer> {/* Ссылка на полный список */} </footer>
  </dropdown>
</NotificationCenter>
```

**Интеграция:**
```tsx
import { NotificationCenter } from '@/components/NotificationCenter';

<header>
  <NotificationCenter />
</header>
```

### 4. Toast уведомления (Sonner)

**Назначение:** Всплывающие уведомления в интерфейсе.

**Провайдер:** Уже добавлен в `Providers.tsx`:
```tsx
import { Toaster } from 'sonner';

<Toaster position="top-right" richColors />
```

**Использование:**
```tsx
import { toast } from 'sonner';

// Простое уведомление
toast('Изменения сохранены');

// С типом
toast.success('Подписка активирована');
toast.error('Не удалось сохранить');
toast.warning('Осталось 5 минут');
toast.info('Новое обновление доступно');

// С действиями
toast('Файл загружен', {
  action: {
    label: 'Открыть',
    onClick: () => window.open('/files/123')
  }
});

// Promise (автоматический loading → success/error)
toast.promise(
  apiClient.saveData(),
  {
    loading: 'Сохранение...',
    success: 'Сохранено!',
    error: 'Ошибка сохранения'
  }
);
```

**Преимущества:**
- Автоматическое управление очередью
- Swipe to dismiss (свайп для закрытия)
- Поддержка action buttons
- Красивые анимации

### 5. API методы (`lib/api.ts`)

**Добавлены методы:**

```typescript
// Получить VAPID ключ для подписки
async getVapidPublicKey(): Promise<{ vapid_public_key: string }>

// Создать push подписку
async subscribePush(data: {
  endpoint: string;
  keys: { p256dh: string; auth: string };
  device_name?: string;
}): Promise<{ status: string; message: string; created: boolean }>

// Удалить push подписку
async unsubscribePush(endpoint?: string): Promise<{ status: string }>

// Получить список подписок
async getPushSubscriptions(): Promise<{ subscriptions: any[] }>
```

**Уже существующие:**
```typescript
// Получить список уведомлений
async getNotifications(): Promise<any>

// Отметить уведомление как прочитанное
async markNotificationAsRead(id: number): Promise<void>

// Отметить все как прочитанные
async markAllNotificationsAsRead(): Promise<void>
```

## Workflow (Как это работает)

### 1. Инициализация при загрузке страницы

```
User opens page
     ↓
useWebPush hook initialized
     ↓
Check browser support (Service Worker + Push API + Notification API)
     ↓
✅ Supported → Continue
     ↓
Fetch VAPID public key from server
     ↓
Register Service Worker (/sw.js)
     ↓
Check current subscription (PushManager.getSubscription())
     ↓
isSubscribed = (subscription !== null)
```

### 2. Подписка на уведомления (User action)

```
User clicks "Включить уведомления"
     ↓
Check permission:
  - 'default' → Request permission (Notification.requestPermission())
  - 'denied' → Show error toast
  - 'granted' → Continue
     ↓
Create push subscription (PushManager.subscribe())
  - userVisibleOnly: true
  - applicationServerKey: VAPID key
     ↓
Serialize subscription (endpoint + keys.p256dh + keys.auth)
     ↓
Send to backend (POST /api/v1/notifications/push/subscribe/)
     ↓
Backend saves to WebPushDevice table
     ↓
✅ Show success toast
```

### 3. Получение push уведомления

```
Backend sends push notification (django-push-notifications)
     ↓
Browser receives push event (даже если вкладка закрыта)
     ↓
Service Worker intercepts 'push' event
     ↓
Parse payload (JSON.parse(event.data.text()))
     ↓
Show native notification (registration.showNotification())
     ↓
User clicks notification
     ↓
Service Worker 'notificationclick' event
     ↓
Focus or open window with notification URL
```

### 4. Обновление списка уведомлений

```
NotificationCenter component mounts
     ↓
useNotifications() hook called
     ↓
Fetch notifications from API (GET /api/v1/notifications/)
     ↓
Display in dropdown with unread badge
     ↓
User clicks notification
     ↓
Mark as read (POST /api/v1/notifications/{id}/mark_read/)
     ↓
Navigate to action_url
```

## Интеграция в существующие компоненты

### AppShell.tsx

**Изменения:**
- Импортирован `NotificationCenter`
- Заменены статичные кнопки Bell на `<NotificationCenter />`
- Добавлено в desktop версию (header)
- Добавлено в mobile версию (нижняя панель)

**До:**
```tsx
<button className="...">
  <Bell size={18} />
</button>
```

**После:**
```tsx
<NotificationCenter />
```

### Providers.tsx

**Изменения:**
- Импортирован `Toaster` из Sonner
- Добавлен `<Toaster />` в провайдеры

```tsx
import { Toaster } from 'sonner';

<Toaster position="top-right" richColors />
```

## Тестирование

### Тестовый сценарий 1: Подписка на уведомления

1. Открыть приложение в браузере
2. Кликнуть на иконку Bell в header
3. Кликнуть на "Настройки" (⚙️)
4. Кликнуть "Включить" в разделе Push уведомления
5. Браузер покажет запрос разрешения → Разрешить
6. Toast: "Подписка на уведомления активирована"
7. В настройках должно быть "Включены" и кнопка "Отключить"

### Тестовый сценарий 2: Получение push уведомления

**Из Django shell:**
```python
from notifications.services import NotificationService
from notifications.models import Notification
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.get(username='testuser')
notification = Notification.objects.filter(recipient=user).first()

# Отправить push
count = NotificationService.send_web_push_notification(notification)
print(f"Отправлено: {count}")
```

**Проверки:**
1. Нативное уведомление должно появиться (даже если вкладка закрыта)
2. При клике должна открыться нужная страница
3. В NotificationCenter должно появиться уведомление
4. Badge должен увеличиться

### Тестовый сценарий 3: Toast уведомления

**В любом компоненте:**
```tsx
import { toast } from 'sonner';

<button onClick={() => toast.success('Тестовое уведомление')}>
  Показать toast
</button>
```

**Проверки:**
1. Toast появляется в правом верхнем углу
2. Автоматически исчезает через 4 секунды
3. Можно закрыть свайпом вправо
4. При наведении пауза на таймере

### Тестовый сценарий 4: NotificationCenter UI

1. Открыть NotificationCenter
2. Должен показаться список уведомлений
3. Непрочитанные - с синим фоном и точкой
4. При клике на уведомление:
   - Отмечается как прочитанное
   - Badge уменьшается
   - Происходит навигация (если есть URL)
5. "Прочитать все" - все уведомления становятся прочитанными

## Браузерная совместимость

### Web Push API

| Браузер | Desktop | Mobile | Примечания |
|---------|---------|--------|------------|
| Chrome | ✅ 50+ | ✅ 50+ | Полная поддержка |
| Firefox | ✅ 44+ | ✅ 48+ | Полная поддержка |
| Safari | ✅ 16+ | ❌ | iOS не поддерживает |
| Edge | ✅ 79+ | ✅ | На базе Chromium |
| Opera | ✅ 37+ | ✅ | На базе Chromium |

**Важно:** iOS Safari НЕ поддерживает Web Push (даже в iOS 16+).
- Для iOS нужно использовать нативное приложение + APNS

### Fallback стратегия

```tsx
const { isSupported, isSubscribed } = useWebPush();

if (!isSupported) {
  // Показываем альтернативу
  return <div>Push уведомления не поддерживаются вашим браузером</div>;
}
```

## Production checklist

- [ ] **HTTPS обязателен** - Service Worker требует HTTPS
- [ ] **VAPID ключи** - проверить что есть в production settings
- [ ] **Service Worker scope** - проверить что sw.js доступен в корне
- [ ] **Тестирование на реальных устройствах**
  - Desktop Chrome/Firefox
  - Android Chrome
  - Desktop Safari (если поддержка добавится)
- [ ] **Мониторинг ошибок** - логировать ошибки Service Worker
- [ ] **Rate limiting** - защита от спама push уведомлений

## Конфигурация

### Environment variables (Backend)

```bash
# В .env или settings.py
VAPID_PUBLIC_KEY=BMTitZy9r4ygYJBgGdaZuCkb7rwR7iHLJv...
VAPID_PRIVATE_KEY=<private_key>
VAPID_ADMIN_EMAIL=admin@example.com
```

### Next.js конфигурация

**`next.config.ts`** - добавить headers для Service Worker (если нужно):
```typescript
async headers() {
  return [
    {
      source: '/sw.js',
      headers: [
        {
          key: 'Service-Worker-Allowed',
          value: '/'
        }
      ]
    }
  ];
}
```

## Troubleshooting

### Проблема: Service Worker не регистрируется

**Возможные причины:**
- Приложение запущено на HTTP (нужен HTTPS или localhost)
- sw.js недоступен (404)
- Браузер не поддерживает Service Worker

**Решение:**
```bash
# Проверить доступность sw.js
curl http://localhost:3000/sw.js

# В консоли браузера
navigator.serviceWorker.getRegistrations().then(console.log)
```

### Проблема: Push подписка не создается

**Возможные причины:**
- Разрешение denied
- VAPID ключ неверный
- PushManager не поддерживается

**Решение:**
```javascript
// В консоли браузера
console.log('Permission:', Notification.permission);
console.log('PushManager supported:', 'PushManager' in window);

// Проверить VAPID ключ
fetch('/api/v1/notifications/push/vapid-key/')
  .then(r => r.json())
  .then(console.log);
```

### Проблема: Уведомления не приходят

**Возможные причины:**
- Подписка истекла (endpoint недействителен)
- Backend не может отправить (VAPID ошибка)
- Service Worker не активен

**Решение:**
```python
# Django shell - проверить активные устройства
from push_notifications.models import WebPushDevice
devices = WebPushDevice.objects.filter(user=user, active=True)
print(devices.count())

# Отправить тестовое уведомление
devices.send_message('{"title": "Test", "body": "Hello"}')
```

## Дальнейшие улучшения

### Функциональность

- [ ] **Фильтры уведомлений** - по категориям (заявки, сообщения, календарь)
- [ ] **Группировка** - по дате или типу
- [ ] **Действия в уведомлении** - прямо из push (approve/reject)
- [ ] **Звук** - настраиваемый звук для разных типов
- [ ] **Badge на иконке приложения** - счетчик непрочитанных

### UX/UI

- [ ] **Skeleton loading** - вместо "Загрузка..."
- [ ] **Infinite scroll** - для списка уведомлений
- [ ] **Поиск** - по уведомлениям
- [ ] **Настройки по типам** - включить/выключить для каждого типа
- [ ] **Темная тема** - поддержка dark mode

### Производительность

- [ ] **WebSocket real-time** - мгновенное обновление списка
- [ ] **Service Worker cache** - кеширование данных уведомлений
- [ ] **Prefetch** - предзагрузка страниц из action_url

### Аналитика

- [ ] **Отслеживание открытий** - сколько push уведомлений открыто
- [ ] **Conversion tracking** - какие уведомления ведут к действиям
- [ ] **A/B тестирование** - разные тексты/форматы

## Заключение

✅ **Система уведомлений полностью реализована:**

**Backend:**
- django-push-notifications 3.1.0
- WebPushDevice модель
- VAPID ключи настроены
- API endpoints готовы

**Frontend:**
- Service Worker для Web Push
- NotificationCenter UI компонент
- useWebPush React хук
- Sonner для toast уведомлений
- Интеграция в AppShell

**Результат:**
- Нативные push уведомления (работают даже когда вкладка закрыта)
- Красивый UI с badge и историей
- Настройки подписок
- Респонсивный дизайн
- TypeScript типизация

**Готово к использованию!** 🎉
