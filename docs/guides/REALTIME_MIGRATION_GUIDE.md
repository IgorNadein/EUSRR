# Миграция на архитектуру Realtime

## Что изменилось

Создано новое Django-приложение `realtime`, которое объединяет всю WebSocket логику в одном месте.

### Было (старая архитектура)
```
communications/
├── user_consumer.py    # WebSocket для чатов
└── routing.py          # /ws/

notifications/
├── consumers.py        # WebSocket для уведомлений
└── routing.py          # /ws/notifications/
```

**Проблемы:**
- 2 WebSocket соединения на пользователя
- Дублирование функциональности уведомлений
- WebSocket логика смешана с бизнес-логикой приложений

### Стало (новая архитектура)
```
realtime/
├── consumers.py        # UserConsumer - универсальный
├── routing.py          # /ws/
└── README.md           # Документация

communications/
└── models.py, views.py, signals.py  # Только бизнес-логика

notifications/
└── models.py, views.py, signals.py  # Только бизнес-логика
```

**Преимущества:**
- ✅ Одно WebSocket соединение для всего
- ✅ Чистая архитектура (транспорт отделен от бизнес-логики)
- ✅ Легко расширять новыми real-time фичами
- ✅ Ping interval 20 секунд (было 30)

## Что НЕ меняется

- **URL остается тот же:** `ws://corp.robotail.local/ws/`
- **Frontend код не требует изменений** (API совместимо)
- **Базы данных не затронуты** (нет миграций)
- **Nginx конфигурация не меняется**

## Инструкции для сервера

### 1. Получить обновления

```bash
cd ~/EUSRR
git pull origin master
```

### 2. Проверить изменения

```bash
# Должны появиться новые файлы
ls -la backend/realtime/
# Должен показать: consumers.py, routing.py, README.md и др.

# Проверить settings.py
grep -A 30 "INSTALLED_APPS" backend/eusrr_backend/settings.py | grep realtime
# Должно показать: "realtime.apps.RealtimeConfig",

# Проверить asgi.py
grep "realtime" backend/eusrr_backend/asgi.py
# Должно показать: from realtime.routing import websocket_urlpatterns
```

### 3. Перезапустить приложение

```bash
# Остановить Gunicorn
sudo systemctl stop gunicorn

# Проверить что процессы остановлены
ps aux | grep gunicorn

# Запустить снова
sudo systemctl start gunicorn

# Проверить статус
sudo systemctl status gunicorn

# Проверить логи
sudo journalctl -u gunicorn -n 50 -f
```

### 4. Проверка работы

#### Проверка WebSocket соединений

```bash
# Смотреть логи в реальном времени
sudo tail -f /var/log/nginx/access.log | grep ws

# Должны появляться записи при подключении пользователей:
# "GET /ws/ HTTP/1.1" 101
```

#### Проверка в браузере (DevTools)

1. Открыть страницу с чатом
2. F12 → Network → WS
3. Должно быть **одно** соединение: `ws://corp.robotail.local/ws/`
4. В Messages должны приходить ping каждые 20 секунд:
   ```json
   {"type": "ping", "timestamp": "..."}
   ```

### 5. Откат (если что-то пошло не так)

```bash
# Вернуться к предыдущему коммиту
cd ~/EUSRR
git log --oneline -5  # найти хеш коммита до изменений
git checkout <хеш-предыдущего-коммита>

# Перезапустить
sudo systemctl restart gunicorn
```

## Мониторинг

### Логи для отладки

```bash
# Все логи Gunicorn
sudo journalctl -u gunicorn -n 100

# Только ошибки
sudo journalctl -u gunicorn -p err -n 50

# WebSocket connections
sudo journalctl -u gunicorn | grep "UserWS"

# Пример успешного подключения:
# [UserWS] User 10 connected, subscribed to 7 chats
```

### Метрики успешной миграции

- ✅ WebSocket подключается (статус 101 в Nginx logs)
- ✅ Ping приходит каждые 20 секунд
- ✅ Сообщения в чатах отправляются и получаются
- ✅ Уведомления приходят в real-time
- ✅ Нет ошибок в `journalctl -u gunicorn`

## FAQ

### В чем разница для пользователей?

Никакой! Пользователи не заметят изменений, все работает так же.

### Почему ping стал 20 секунд вместо 30?

Более частые ping повышают стабильность соединения на некоторых сетях/прокси.

### Можно ли удалить старые файлы?

Пока нет! Файлы `communications/user_consumer.py` и `notifications/consumers.py` оставлены для совместимости. Удалим их в следующем релизе после тестирования.

### Где посмотреть новую документацию?

`backend/realtime/README.md` - полная документация по WebSocket API

## Контакты

При проблемах:
1. Проверить логи: `sudo journalctl -u gunicorn -n 100`
2. Проверить Nginx: `sudo nginx -t && sudo systemctl status nginx`
3. Откатиться на предыдущую версию (см. раздел "Откат")
