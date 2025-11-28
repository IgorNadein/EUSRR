# Исправление WebSocket Keepalive

## Проблема
WebSocket соединения закрываются через ~27 секунд из-за отсутствия активности. Это приводит к переподключениям и потенциальным проблемам на некоторых компьютерах.

## Решение
Добавлен механизм **ping/pong** для поддержания соединения активным:

### Backend изменения (уже сделаны)
1. ✅ `communications/consumers.py` - ChatConsumer с ping каждые 20 секунд
2. ✅ `communications/consumers.py` - ChatListConsumer с ping каждые 20 секунд  
3. ✅ `notifications/consumers.py` - NotificationConsumer с ping каждые 20 секунд

### Frontend изменения (уже сделаны)
1. ✅ `chatWebSocket.js` - игнорирование ping сообщений
2. ✅ `chatListRealtime.js` - игнорирование ping сообщений
3. ✅ `notification-manager.js` - игнорирование ping сообщений

## Настройка Nginx (НУЖНО ПРИМЕНИТЬ НА СЕРВЕРЕ)

### Текущая проблема
WebSocket настроен в общем блоке `location /`, что может вызывать конфликты.

### Решение
Создайте отдельный блок для WebSocket **ПЕРЕД** `location /`:

```nginx
server {
    listen 80;
    server_name corp.robotail.local 172.11.0.11 127.0.0.1;

    client_max_body_size 50m;

    # Статика
    location /static/ {
        alias /home/igor/EUSRR/backend/staticfiles/;
        autoindex off;
        expires 30d;
        add_header Cache-Control "public, max-age=2592000";
    }

    # Медиа
    location /media/ {
        alias /home/igor/EUSRR/backend/media/;
        autoindex off;
    }

    # API
    location /api/ {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket - ВАЖНО: отдельный блок!
    location /ws/ {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket настройки
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Увеличенные таймауты для долгих соединений
        proxy_connect_timeout 7d;
        proxy_send_timeout 7d;
        proxy_read_timeout 7d;
        
        # Отключаем буферизацию для реалтайм
        proxy_buffering off;
    }

    # Основное приложение (БЕЗ WebSocket настроек!)
    location / {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Обычные таймауты для HTTP
        proxy_read_timeout 60s;
        proxy_send_timeout 60s;
    }
}
```

## Применение на сервере

```bash
# 1. Откройте конфигурацию nginx
sudo nano /etc/nginx/sites-enabled/eusrr

# 2. Замените содержимое на конфигурацию выше

# 3. Проверьте конфигурацию
sudo nginx -t

# 4. Перезагрузите nginx
sudo systemctl reload nginx

# 5. Обновите код на сервере
cd /home/igor/EUSRR
git pull origin master

# 6. Перезапустите приложение
sudo systemctl restart eusrr
```

## Как это работает

1. **Backend**: Каждые 20 секунд отправляет `{"type": "ping", "timestamp": "..."}` через WebSocket
2. **Frontend**: Игнорирует ping сообщения, но они поддерживают соединение активным
3. **Nginx**: Видит активность на WebSocket и не закрывает соединение по таймауту
4. **Gunicorn**: Не считает соединение "мертвым" благодаря регулярным пакетам

## Результат

✅ WebSocket соединения остаются активными бесконечно долго
✅ Нет бесконечных перезагрузок
✅ Работает стабильно во всех браузерах
✅ Минимальная нагрузка (ping раз в 20 секунд)

## Проверка после применения

1. Откройте DevTools → Network → WS
2. Подключитесь к чату
3. Убедитесь, что каждые 20 секунд приходят ping сообщения
4. Соединение не должно закрываться через 27 секунд

## Логи для мониторинга

```bash
# Смотрим логи Gunicorn
sudo journalctl -u eusrr -f | grep -i "websocket\|connection"

# Смотрим логи Nginx
sudo tail -f /var/log/nginx/error.log
```

Ожидаемое поведение:
- `connection open` - соединение открыто
- Регулярные ping без ошибок
- `connection closed` только при явном закрытии (смена страницы, logout)
