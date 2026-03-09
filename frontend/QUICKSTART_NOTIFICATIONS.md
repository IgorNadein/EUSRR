# 🚀 Quick Start - Уведомления

## Для пользователя

### Проверить работу уведомлений

1. **Запустить backend:**
   ```bash
   cd backend
   .venv/Scripts/python manage.py runserver 9000
   
   # В другом терминале:
   .venv/Scripts/celery -A eusrr_backend worker -l info
   ```

2. **Запустить frontend:**
   ```bash
   cd frontend
   npm run dev
   ```

3. **Открыть в браузере:**
   - http://localhost:3000/
   - Авторизоваться
   - Кликнуть на колокольчик (🔔) в header

4. **Тестовое уведомление:**
   - Создать заявку от другого пользователя
   - Уведомление должно прийти автоматически (без перезагрузки)
   - Счетчик обновится
   - Колокольчик подсветится

---

## Для разработчика

### Создать уведомление программно

```python
# В Django shell или коде
from notifications.signals import notify
from employees.models import Employee

sender = Employee.objects.get(id=1)
recipient = Employee.objects.get(id=2)

notify.send(
    sender=sender,
    recipient=recipient,
    verb='test_notification',
    description='Тестовое уведомление',
    action_url='/test/',
)
```

### Проверить WebSocket в DevTools

1. Открыть Console
2. Должно быть:
   ```
   [Notifications] WebSocket connecting to: ws://localhost:9000/ws/?token=...
   [Notifications] WebSocket connected
   ```
3. Создать уведомление
4. Должно прийти:
   ```
   [Notifications] New notification: {id: 1, verb: 'test', ...}
   ```

### Отладка

**Backend не отправляет:**
```bash
# Проверить Celery tasks
cd backend
.venv/Scripts/celery -A eusrr_backend inspect active

# Проверить Redis
redis-cli ping  # Должно вернуть PONG

# Проверить логи Celery
# В терминале где запущен worker должно быть:
# Task send_websocket_notification[...] received
# Task send_websocket_notification[...] succeeded
```

**Frontend не получает:**
```javascript
// В DevTools → Console
// Должно быть подключение:
[Notifications] WebSocket connected

// Если ошибка подключения:
// Проверить CORS и WebSocket URL
```

---

## Структура файлов

```
frontend/
├── src/
│   ├── hooks/
│   │   ├── useApi.ts                    # ✅ useNotifications (REST + WS)
│   │   ├── useNotificationWebSocket.ts  # ⚙️ Отдельный WS хук (опция)
│   │   └── useWebPush.ts                # 🔔 Push уведомления
│   ├── components/
│   │   ├── NotificationCenter.tsx       # 🎨 UI компонент
│   │   └── AppShell.tsx                 # 📐 Layout с NotificationCenter
│   └── types/
│       └── api.ts                       # 📝 TypeScript типы
└── NOTIFICATIONS_INTEGRATION.md         # 📖 Полная документация

backend/
├── notifications/
│   ├── signals.py                       # 📨 notify.send() API
│   ├── channels.py                      # 🔀 Роутер по каналам
│   ├── tasks/websocket.py               # ⚙️ Celery задача
│   ├── senders/websocket.py             # 📤 WebSocket sender
│   └── models.py                        # 💾 Notification v2
└── realtime/
    └── consumers.py                     # 🔌 UserConsumer (WS)
```

---

## Что изменилось

### ✅ Исправлено (9 марта 2026)

1. **Backend** - добавлен `UserConsumer.notification_message()`
2. **Frontend** - WebSocket интеграция в `useNotifications`
3. **UI** - поддержка v2 API (verb, description, unread, timestamp)
4. **Types** - обновлен интерфейс Notification

### 🎯 Результат

- ✅ Realtime уведомления работают
- ✅ Автоматическое обновление счетчика
- ✅ Совместимость с v1 и v2 API
- ✅ Автоматический reconnect
- ✅ TypeScript типизация

---

## Поддержка

- Полная документация: `frontend/NOTIFICATIONS_INTEGRATION.md`
- Backend тесты: `backend/requests_app/TESTING_NOTIFICATIONS.md`
- Архитектура: `backend/notifications/README.md`
