# Next.js Frontend - Интеграция уведомлений

## Статус: ✅ Полностью подключено

Дата: 9 марта 2026  
Версия API: v2

---

## Что было исправлено

### 1. Backend - UserConsumer (realtime/consumers.py)

**Проблема:** WebSocketNotificationSender отправлял события с типом `notification_message`, но в UserConsumer не было соответствующего метода.

**Решение:** Добавлен метод `notification_message`:

```python
async def notification_message(self, event):
    """Новое уведомление от WebSocketNotificationSender"""
    await self.send_json({
        "type": "notification",
        "notification": event.get("message", {})
    })
```

### 2. Frontend - useNotifications (hooks/useApi.ts)

**Проблема:** Хук загружал уведомления только один раз при mount, без realtime обновлений.

**Решение:** Добавлен WebSocket внутри хука:

```typescript
useEffect(() => {
  // REST API загрузка
  fetchNotifications();
}, []);

useEffect(() => {
  // WebSocket для realtime
  const ws = new WebSocket(wsUrl);
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data);
    
    if (data.type === 'notification' && data.notification) {
      // Добавляем новое уведомление
      setNotifications(prev => [data.notification, ...prev]);
      if (data.notification.unread) {
        setUnreadCount(prev => prev + 1);
      }
    }
    
    if (data.type === 'unread_count') {
      setUnreadCount(data.count);
    }
  };
}, []);
```

### 3. Frontend - NotificationCenter.tsx

**Проблема:** Использовал старые поля v1 API (`title`, `message`, `is_read`, `created_at`).

**Решение:** Обновлено для v2 API с fallback на v1:

```typescript
// v2 API: unread вместо is_read (инвертированное)
const isUnread = notification.unread ?? !notification.is_read;

// v2 API: timestamp вместо created_at
const timestamp = notification.timestamp || notification.created_at;

// v2 API: verb + description вместо title + message
const title = notification.verb || notification.title;
const message = notification.description || notification.message;
```

### 4. TypeScript типы (types/api.ts)

**Проблема:** Старый интерфейс Notification не соответствовал v2 API.

**Решение:** Обновлен интерфейс с поддержкой v2 и fallback на v1:

```typescript
export interface Notification {
  // v2 fields
  id: number;
  verb: string;
  description: string;
  unread: boolean;
  timestamp: string;
  action_url?: string;
  actor?: { type: string; id: number; str: string; };
  target?: { type: string; id: number; str: string; };
  
  // v1 legacy fields (для обратной совместимости)
  title?: string;
  message?: string;
  is_read?: boolean;
  created_at?: string;
}
```

---

## Архитектура

### Полный поток данных

```
1. Django Action (создание заявки)
   ↓
2. Django Signal (post_save)
   ↓
3. notify.send(sender, recipient, verb, description, ...)
   ↓
4. Notification.save() [~1ms, синхронно]
   ↓
5. post_save → channels.py
   ↓
6. UserChannelPreferences проверка
   ↓
7. Celery .delay():
   - send_websocket_notification.delay()
   - send_email_notification.delay()
   - send_push_notification.delay()
   ↓
8. Celery Worker обрабатывает WebSocketNotificationTask
   ↓
9. WebSocketNotificationSender.send()
   ↓
10. channel_layer.group_send(f"user_{user_id}", {
      type: 'notification_message',
      message: {...}
    })
   ↓
11. UserConsumer.notification_message()
   ↓
12. ws.send({type: 'notification', notification: {...}})
   ↓
13. Next.js Frontend - useNotifications WebSocket
   ↓
14. setNotifications([new, ...prev])
   ↓
15. NotificationCenter обновляет UI
   ↓
16. Пользователь видит уведомление в реальном времени
```

### Компоненты

**Backend:**
- `notifications/signals.py` - notify.send() API
- `notifications/channels.py` - роутер по каналам
- `notifications/tasks/websocket.py` - Celery задача
- `notifications/senders/websocket.py` - отправка через Channels
- `realtime/consumers.py` - UserConsumer (WebSocket)

**Frontend:**
- `hooks/useApi.ts` - useNotifications (REST + WebSocket)
- `components/NotificationCenter.tsx` - UI (desktop + mobile)
- `components/AppShell.tsx` - размещение компонента
- `types/api.ts` - TypeScript типы

---

## API Endpoints

### REST API

**Получить уведомления:**
```http
GET /api/v2/notifications/
Authorization: Bearer {token}

Response:
{
  "notifications": [
    {
      "id": 1,
      "verb": "request_created",
      "description": "Новая заявка от Иванов И.И.",
      "unread": true,
      "timestamp": "2026-03-09T18:00:00Z",
      "action_url": "/requests/123/",
      "actor": {"type": "employee", "id": 5, "str": "Иванов И.И."},
      "target": {"type": "request", "id": 123, "str": "Заявка #123"}
    }
  ],
  "total": 42,
  "unread_count": 5
}
```

**Отметить как прочитанное:**
```http
POST /api/v2/notifications/{id}/mark_read/
Authorization: Bearer {token}

Response: {"status": "ok"}
```

**Отметить все как прочитанные:**
```http
POST /api/v2/notifications/mark_all_read/
Authorization: Bearer {token}

Response: {"status": "ok", "count": 5}
```

### WebSocket

**Подключение:**
```
ws://localhost:9000/ws/?token={access_token}
```

**События от сервера:**

```javascript
// Новое уведомление
{
  "type": "notification",
  "notification": {
    "id": 1,
    "verb": "request_approved",
    "description": "Ваша заявка одобрена",
    "unread": true,
    "timestamp": "2026-03-09T18:00:00Z",
    "action_url": "/requests/123/",
    "silent": false
  }
}

// Обновление счетчика
{
  "type": "unread_count",
  "count": 3
}

// Ping (keepalive)
{
  "type": "ping",
  "timestamp": "2026-03-09T18:00:00Z"
}
```

---

## Использование в коде

### Использование хука useNotifications

```tsx
import { useNotifications } from '@/hooks/useApi';

function MyComponent() {
  const { notifications, unreadCount, markAsRead, markAllAsRead, loading } = useNotifications();
  
  return (
    <div>
      <h1>Уведомления ({unreadCount})</h1>
      {notifications.map(n => (
        <div key={n.id} onClick={() => markAsRead(n.id)}>
          <h3>{n.verb}</h3>
          <p>{n.description}</p>
        </div>
      ))}
    </div>
  );
}
```

### Использование NotificationCenter

```tsx
import { NotificationCenter } from '@/components/NotificationCenter';

function Header() {
  return (
    <header>
      <NotificationCenter /> {/* Desktop version */}
    </header>
  );
}

function MobileNav() {
  const [isOpen, setIsOpen] = useState(false);
  
  return (
    <NotificationCenter 
      variant="mobile"
      isOpen={isOpen}
      onToggle={() => setIsOpen(!isOpen)}
    />
  );
}
```

---

## Тестирование

### 1. Проверка REST API

```bash
# Получить все уведомления
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:9000/api/v2/notifications/

# Отметить как прочитанное
curl -X POST -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:9000/api/v2/notifications/1/mark_read/
```

### 2. Проверка WebSocket

1. Открыть DevTools → Console
2. Должно быть: `[Notifications] WebSocket connected`
3. Создать заявку от другого пользователя
4. Должно прийти: `[Notifications] New notification: {...}`
5. Колокольчик должен обновиться автоматически

### 3. Проверка UI

1. Открыть http://localhost:3000/
2. Кликнуть на колокольчик
3. Увидеть список уведомлений
4. Кликнуть на уведомление - счетчик уменьшается
5. "Прочитать все" - все уведомления помечаются прочитанными

---

## Поддерживаемые возможности

✅ **Realtime уведомления** - через WebSocket  
✅ **REST API fallback** - при отключении WebSocket  
✅ **Автоматический reconnect** - до 5 попыток  
✅ **Обратная совместимость** - v1 и v2 API  
✅ **Desktop и Mobile UI** - адаптивный дизайн  
✅ **Push notifications** - через useWebPush  
✅ **Счетчик непрочитанных** - realtime обновление  
✅ **Отметка прочитанных** - индивидуально и все сразу  
✅ **Навигация по action_url** - переход при клике  
✅ **TypeScript типизация** - полная типобезопасность  

---

## Переменные окружения

```env
# Frontend (.env.local)
NEXT_PUBLIC_API_URL=http://localhost:9000
NEXT_PUBLIC_WS_HOST=localhost:9000

# Backend (.env)
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0
```

---

## Запуск для разработки

### Backend

```bash
cd backend

# 1. Django server (WebSocket через Daphne)
.venv/Scripts/python manage.py runserver 9000

# 2. Celery worker (в отдельном терминале)
.venv/Scripts/celery -A eusrr_backend worker -l info

# 3. Redis (должен быть запущен)
redis-server
```

### Frontend

```bash
cd frontend

# Development server
npm run dev

# Production build
npm run build
npm start
```

---

## Известные проблемы

### Нет проблем! 🎉

Все критические баги исправлены. Frontend полностью интегрирован с backend notifications v2.

---

## Следующие шаги (опционально)

1. **Звуковые уведомления** - добавить аудио при получении
2. **Группировка** - группировать похожие уведомления
3. **Фильтрация** - по типу, дате, прочитанности
4. **Настройки каналов** - UI для UserChannelPreferences
5. **Уведомления в заголовке** - обновление document.title

---

## Полезные ссылки

- Backend документация: `backend/notifications/README.md`
- Тестирование: `backend/requests_app/TESTING_NOTIFICATIONS.md`
- Отчет о рефакторинге: `backend/docs/reports/NOTIFICATION_SIGNALS_REFACTORING.md`
