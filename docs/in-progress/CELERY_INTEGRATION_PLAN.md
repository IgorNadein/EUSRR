# План интеграции Celery в проект EUSRR

## 📋 Текущее состояние

- ✅ Celery 5.5.3 установлен в requirements.txt
- ❌ Нет конфигурации Celery
- ❌ Нет celery.py в проекте
- ❌ Нет workers
- ⚠️ documents/tasks.py - закомментирован код с @shared_task

## 🎯 Цели интеграции

### Основные задачи:
1. **Уведомления** - перенести отправку Email/Telegram/Push в фон
2. **Документы** - отложенная отправка уведомлений для массовых рассылок
3. **Периодические задачи** - напоминания, очистка, синхронизация

### Метрики успеха:
- Скорость отклика API увеличится в 3-5 раз
- Возможность обработки 1000+ уведомлений без блокировки
- Мониторинг выполнения задач

---

## 🏗️ Архитектура решения

### Компоненты:

```
┌─────────────────┐
│  Django API     │ ← HTTP requests
└────────┬────────┘
         │ создает задачи
         ↓
┌─────────────────┐
│  Redis (Broker) │ ← очередь задач
└────────┬────────┘
         │ получает задачи
         ↓
┌─────────────────┐
│  Celery Worker  │ ← выполняет задачи
└────────┬────────┘
         │ результаты
         ↓
┌─────────────────┐
│  Redis (Backend)│ ← хранит результаты
└─────────────────┘
```

### Очереди (Queues):

1. **default** - обычные задачи
2. **notifications** - уведомления (высокий приоритет)
3. **emails** - отправка email (низкий приоритет)
4. **periodic** - периодические задачи (cron)

---

## 📝 План реализации

### Этап 1: Базовая настройка (День 1)

**1.1. Создать структуру Celery**
- [x] `backend/eusrr_backend/celery.py` - конфигурация Celery
- [x] Обновить `backend/eusrr_backend/__init__.py` - автозагрузка
- [x] Добавить Redis в settings.py

**1.2. Настроить Redis**
- [ ] Установить Redis локально или через Docker
- [ ] Настроить CELERY_BROKER_URL
- [ ] Настроить CELERY_RESULT_BACKEND

**1.3. Тестовая задача**
- [ ] Создать простую test_task
- [ ] Запустить worker
- [ ] Проверить выполнение

---

### Этап 2: Уведомления (День 2)

**2.1. Перенести отправку уведомлений**
- [ ] `notifications/tasks.py` - создать задачи
  - [ ] `send_notification_async(notification_id)`
  - [ ] `send_email_notification(notification_id)`
  - [ ] `send_telegram_notification(notification_id)`
  - [ ] `send_push_notification(notification_id)`

**2.2. Обновить NotificationService**
- [ ] Изменить `send_notification()` - использовать Celery
- [ ] Добавить параметр `use_celery=True`
- [ ] Fallback на синхронную отправку при ошибке

**2.3. Тестирование**
- [ ] Проверить отправку уведомлений через Celery
- [ ] Измерить время отклика API (было/стало)

---

### Этап 3: Документы (День 3)

**3.1. Раскомментировать tasks.py**
- [ ] documents/tasks.py - восстановить функционал
- [ ] Адаптировать под новую архитектуру

**3.2. Массовые рассылки**
- [ ] Батчинг: группировать уведомления по N штук
- [ ] Прогресс-бар для админа (сколько отправлено)

---

### Этап 4: Периодические задачи (День 4)

**4.1. Celery Beat**
- [ ] Настроить celery beat
- [ ] Создать schedule в settings.py

**4.2. Задачи**
- [ ] Напоминания о документах (раз в день)
- [ ] Очистка старых уведомлений (раз в неделю)
- [ ] Синхронизация LDAP (если нужно)
- [ ] Backup базы данных (раз в сутки)

---

### Этап 5: Мониторинг (День 5)

**5.1. Flower**
- [ ] Установить Flower
- [ ] Настроить доступ
- [ ] Дашборд для мониторинга

**5.2. Логирование**
- [ ] Structured logging для задач
- [ ] Алерты при сбоях (опционально - Sentry)

**5.3. Метрики**
- [ ] Время выполнения задач
- [ ] Количество успешных/неуспешных
- [ ] Размер очереди

---

## ⚙️ Конфигурация

### Redis settings (в .env):
```env
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

### Celery settings (в settings.py):
```python
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = 'Europe/Moscow'
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 минут
```

### Запуск worker:
```bash
# Development
celery -A eusrr_backend worker -l info -Q default,notifications,emails

# Production (with autoscale)
celery -A eusrr_backend worker -l info --autoscale=10,3
```

### Запуск beat:
```bash
celery -A eusrr_backend beat -l info
```

### Запуск Flower:
```bash
celery -A eusrr_backend flower --port=5555
```

---

## 🚀 Deployment

### Docker Compose (пример):
```yaml
services:
  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data

  celery_worker:
    build: .
    command: celery -A eusrr_backend worker -l info
    volumes:
      - .:/app
    depends_on:
      - redis
      - db
    environment:
      - CELERY_BROKER_URL=redis://redis:6379/0

  celery_beat:
    build: .
    command: celery -A eusrr_backend beat -l info
    volumes:
      - .:/app
    depends_on:
      - redis
      - db

  flower:
    build: .
    command: celery -A eusrr_backend flower --port=5555
    ports:
      - "5555:5555"
    depends_on:
      - redis
      - celery_worker
```

---

## ⚠️ Риски и меры минимизации

### Риск 1: Redis недоступен
**Решение:** Fallback на синхронную обработку

### Риск 2: Worker умер
**Решение:** Supervisor/systemd для автоперезапуска

### Риск 3: Очередь переполнена
**Решение:** Rate limiting + мониторинг через Flower

### Риск 4: Долгие задачи блокируют
**Решение:** Разделение на очереди + task time limit

---

## 📊 Метрики для отслеживания

**До внедрения:**
- Время отправки сообщения в групповой чат: ~500ms
- Время создания документа с 100 получателями: ~10s

**После внедрения (цель):**
- Время отправки сообщения: <50ms
- Время создания документа: <200ms
- Уведомления в фоне: не блокируют API

---

## ✅ Критерии готовности к продакшену

- [ ] Все задачи выполняются стабильно
- [ ] Worker автоматически перезапускается при сбое
- [ ] Flower доступен для мониторинга
- [ ] Логирование настроено
- [ ] Redis backup настроен
- [ ] Тестирование под нагрузкой пройдено
- [ ] Документация для деплоя готова

---

## 🔄 Откат изменений

Если что-то пойдет не так:
1. Вернуться к синхронной отправке в NotificationService
2. Закомментировать Celery задачи
3. Переключиться обратно на ветку master

**Git:** `git checkout master && git branch -D feature/celery-integration`
