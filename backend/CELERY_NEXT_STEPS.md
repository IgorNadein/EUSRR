# Celery Integration - Следующие шаги

## ✅ Что уже сделано

1. ✅ Добавлены зависимости в `requirements.txt`:
   - `celery==5.5.3`
   - `redis==5.2.1`
   - `django-celery-beat==2.7.0`
   - `django-celery-results==2.5.1`
   - `flower==2.0.1`

2. ✅ Создан файл конфигурации `eusrr_backend/celery.py`
   - Настроена автоматическая регистрация задач
   - Добавлен debug task для тестирования

3. ✅ Обновлен `eusrr_backend/__init__.py`
   - Автоматический импорт celery_app при запуске Django

4. ✅ Добавлены настройки Celery в `settings.py`:
   - `CELERY_BROKER_URL` - Redis как брокер сообщений
   - `CELERY_RESULT_BACKEND` - Redis для хранения результатов
   - Настройка роутинга задач по очередям
   - Таймауты и лимиты для workers

5. ✅ Добавлены приложения в `INSTALLED_APPS`:
   - `django_celery_beat` - для периодических задач
   - `django_celery_results` - для хранения результатов

6. ✅ Созданы Celery задачи в `notifications/tasks.py`:
   - `send_notification_task` - отправка одного уведомления
   - `send_bulk_notifications_task` - массовая отправка
   - `cleanup_old_notifications_task` - очистка старых уведомлений
   - `send_digest_email_task` - email-дайджесты

## 🔄 Следующие шаги (выполнить вручную)

### Шаг 1: Установка зависимостей

Запустите задачу в VS Code:
- **Pip: install requirements**

Или вручную:
```bash
cd backend
..\.venv\Scripts\pip install -r requirements.txt
```

### Шаг 2: Установка и запуск Redis

#### Вариант 1: Windows (рекомендуется Memurai)
1. Скачайте Memurai (Redis для Windows): https://www.memurai.com/
2. Установите и запустите как службу Windows
3. Redis будет доступен на `localhost:6379`

#### Вариант 2: Docker
```bash
docker run -d -p 6379:6379 --name redis redis:7-alpine
```

#### Проверка Redis:
```bash
redis-cli ping
# Должно вернуть: PONG
```

### Шаг 3: Применение миграций

Запустите:
```bash
cd backend
migrate_celery.bat
```

Или вручную:
```bash
..\.venv\Scripts\python manage.py migrate django_celery_beat
..\.venv\Scripts\python manage.py migrate django_celery_results
```

### Шаг 4: Тестирование Celery Worker

В отдельном терминале запустите worker:
```bash
cd backend
..\.venv\Scripts\celery -A eusrr_backend worker -l info --pool=solo
```

**Примечание**: На Windows используйте `--pool=solo` или `--pool=gevent`

### Шаг 5: Тестирование отправки задачи

В Django shell:
```python
..\.venv\Scripts\python manage.py shell

from celery import current_app
current_app.send_task('eusrr_backend.debug_task')
```

Вы должны увидеть выполнение задачи в логах worker.

### Шаг 6: Интеграция с NotificationService

Обновите `notifications/services.py`:
```python
from notifications.tasks import send_notification_task, send_bulk_notifications_task

class NotificationService:
    @staticmethod
    def create_notification(...):
        # Вместо синхронного создания
        send_notification_task.delay(
            notification_type=notification_type,
            user_id=user.id,
            title=title,
            message=message,
            link=link,
            sender_id=sender.id if sender else None,
            metadata=metadata,
        )
```

### Шаг 7: Запуск Flower (мониторинг)

```bash
cd backend
..\.venv\Scripts\celery -A eusrr_backend flower
```

Откройте http://localhost:5555 для просмотра статистики задач.

### Шаг 8: Настройка периодических задач

В Django Admin:
1. Перейдите в "Periodic Tasks"
2. Добавьте задачу для `notifications.cleanup_old_notifications`
3. Настройте интервал (например, раз в день)

Или программно в `eusrr_backend/celery.py`:
```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    'cleanup-old-notifications': {
        'task': 'notifications.cleanup_old_notifications',
        'schedule': crontab(hour=3, minute=0),  # Каждый день в 3:00
        'args': (90,)  # Удалять уведомления старше 90 дней
    },
}
```

Запустите beat scheduler:
```bash
..\.venv\Scripts\celery -A eusrr_backend beat -l info
```

## 📊 Ожидаемый результат

**До внедрения Celery:**
- Отправка сообщения в группу с 8 участниками: ~500ms
- Блокировка API response до отправки всех уведомлений

**После внедрения Celery:**
- Отправка сообщения: <50ms (только создание задачи)
- Уведомления обрабатываются асинхронно
- API мгновенно отвечает пользователю

## 🔍 Отладка

### Проверка статуса Celery
```bash
..\.venv\Scripts\celery -A eusrr_backend inspect active
..\.venv\Scripts\celery -A eusrr_backend inspect stats
```

### Проверка задач в очереди
```bash
..\.venv\Scripts\celery -A eusrr_backend inspect reserved
```

### Логи
- Worker логи: консоль где запущен worker
- Flower: http://localhost:5555
- Django логи: стандартные логи приложения

## 📚 Документация

- Подробная документация: `docs/guides/CELERY_SETUP.md`
- План внедрения (5 дней): `docs/in-progress/CELERY_INTEGRATION_PLAN.md`
- Celery docs: https://docs.celeryq.dev/

## ⚠️ Production Deployment

Для production:
1. Используйте Redis Cluster или Redis Sentinel
2. Запускайте несколько workers с supervisord/systemd
3. Настройте мониторинг (Flower + Prometheus)
4. Добавьте retry policies и dead letter queue
5. Настройте автоматический перезапуск workers

См. `docs/in-progress/CELERY_INTEGRATION_PLAN.md` для деталей.
