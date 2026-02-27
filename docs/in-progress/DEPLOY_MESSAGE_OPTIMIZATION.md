# Деплой оптимизации уведомлений

## Что изменилось

**Проблема:** Сообщение в чате не появляется сразу - нужно ждать пока все уведомления разошлются.

**Решение:** Signal handler теперь запускает одну асинхронную задачу Celery, которая обрабатывает все уведомления в фоне.

## Измененные файлы

- `backend/notifications/tasks.py` - добавлена задача `process_message_notifications_task`
- `backend/communications/notification_signals.py` - signal handler теперь асинхронный
- `docs/guides/MESSAGE_NOTIFICATIONS_OPTIMIZATION.md` - полная документация

## Деплой

### На сервере (172.11.0.11):

```bash
# 1. Обновить код
cd ~/EUSRR
git pull origin master

# 2. Перезапустить Celery worker (для загрузки новой задачи)
sudo systemctl restart celery-eusrr
sudo systemctl status celery-eusrr

# 3. Перезапустить Gunicorn (для загрузки нового кода Django)
sudo systemctl restart gunicorn-eusrr
sudo systemctl status gunicorn-eusrr

# 4. Проверить логи worker'а
sudo tail -f /var/log/celery/worker.log
```

### Проверка

1. Откройте групповой чат с несколькими участниками
2. Отправьте сообщение
3. **Сообщение должно появиться мгновенно** (< 50ms)
4. В логах worker'а через 1-2 секунды появится:
   ```
   [INFO] Processed message 3732: sent 8 notifications
   ```

### Если что-то не работает

```bash
# Проверить статус сервисов
sudo systemctl status celery-eusrr
sudo systemctl status gunicorn-eusrr

# Посмотреть последние ошибки
sudo journalctl -u celery-eusrr -n 50
sudo journalctl -u gunicorn-eusrr -n 50

# Перезапустить все
sudo systemctl restart celery-eusrr celery-beat-eusrr gunicorn-eusrr
```

## Ожидаемый результат

### До:
- API response: ~500ms
- Сообщение появляется с задержкой

### После:
- API response: <50ms ✨
- Сообщение появляется мгновенно
- Уведомления обрабатываются в фоне

## Дата

8 января 2026 г.
