# План диагностики ошибки WebSocket 1006

## Описание проблемы
У некоторых пользователей возникает ошибка **1006 (Abnormal Closure)** при попытке установить WebSocket соединение с сервером `172.11.0.11`.

Код 1006 означает аномальное закрытие соединения без отправки Close frame, что обычно указывает на проблемы:
- На уровне прокси-сервера (Nginx)
- Сетевые проблемы
- Проблемы с аутентификацией/авторизацией
- Таймауты или неправильная конфигурация

---

## Этап 1: Сбор информации о проблеме

### 1.1 Определите паттерн
- [ ] **Какие пользователи затронуты?**
  - Все пользователи или только некоторые?
  - Есть ли общие признаки (отдел, роль, браузер, ОС)?
  
- [ ] **Когда происходит ошибка?**
  - При первом подключении к странице?
  - После определенного периода работы?
  - При переходе на определенные страницы (чаты, уведомления)?
  
- [ ] **Воспроизводимость**
  - Постоянная ошибка или периодическая?
  - Можно ли воспроизвести на других устройствах под той же учетной записью?

### 1.2 Проверьте браузер пользователя
Попросите пользователя открыть **DevTools** → **Console/Network** и проверить:

```javascript
// В консоли браузера:
// 1. Проверить URL подключения
console.log('WebSocket URL:', window.userWebSocket?.ws?.url);

// 2. Проверить статус соединения
console.log('WebSocket state:', window.userWebSocket?.ws?.readyState);
// 0 = CONNECTING, 1 = OPEN, 2 = CLOSING, 3 = CLOSED

// 3. Проверить код закрытия
window.userWebSocket?.ws?.addEventListener('close', (event) => {
    console.log('Close Code:', event.code);
    console.log('Close Reason:', event.reason);
    console.log('Was Clean:', event.wasClean);
});
```

**Ожидаемые значения:**
- URL: `ws://172.11.0.11/ws/` или `wss://172.11.0.11/ws/` (для HTTPS)
- State: 1 (OPEN) при успешном подключении
- Code: 1006 при ошибке
- Reason: обычно пустая при 1006
- wasClean: false при 1006

---

## Этап 2: Диагностика на сервере

### 2.1 Проверьте текущую конфигурацию Nginx

```bash
# Подключитесь к серверу
ssh igor@172.11.0.11

# Проверьте конфигурацию Nginx
sudo cat /etc/nginx/sites-enabled/eusrr

# Проверьте на ошибки
sudo nginx -t
```

**✅ ТЕКУЩАЯ КОНФИГУРАЦИЯ ПРАВИЛЬНАЯ!**

Ваша конфигурация уже содержит:
- ✅ Отдельный блок `location /ws/` для WebSocket (и для HTTP:80, и для HTTPS:443)
- ✅ Заголовки `Upgrade` и `Connection "upgrade"`
- ✅ `proxy_http_version 1.1`
- ✅ Большие таймауты (7 дней)
- ✅ `proxy_buffering off` для реалтайм данных

**Это означает, что проблема НЕ в базовой конфигурации Nginx!**

Переходите к следующим этапам диагностики.

### 2.2 Проверьте логи Nginx

```bash
# Логи ошибок Nginx
sudo tail -f /var/log/nginx/error.log

# Логи доступа (фильтр по WebSocket)
sudo tail -f /var/log/nginx/access.log | grep '/ws/'

# Поиск ошибок 1006 или подключений WebSocket
sudo grep -i "websocket\|upgrade\|101\|400\|502\|504" /var/log/nginx/error.log | tail -20
```

**Что искать:**
- `upstream prematurely closed connection` - Gunicorn закрыл соединение
- `upstream timed out` - таймаут от backend
- `no live upstreams` - backend недоступен
- `400 Bad Request` - проблема с заголовками
- `502 Bad Gateway` - backend не отвечает
- `504 Gateway Timeout` - таймаут соединения

### 2.3 Проверьте логи приложения (Gunicorn/Django)

```bash
# Логи приложения EUSRR
sudo journalctl -u eusrr -f

# Фильтр по WebSocket событиям
sudo journalctl -u eusrr -f | grep -i "websocket\|consumer\|connection"

# Последние ошибки
sudo journalctl -u eusrr --since "1 hour ago" | grep -i "error\|exception\|traceback"
```

**Что искать:**
- `Consumer connected` / `Consumer disconnected` - логи подключений
- `Authentication failed` - проблемы с JWT/токеном
- `Exception in consumer` - ошибки в коде consumer
- Трассировки ошибок Python

### 2.4 Проверьте статус сервисов

```bash
# Статус Nginx
sudo systemctl status nginx

# Статус приложения
sudo systemctl status eusrr

# Статус Redis (для channels)
sudo systemctl status redis

# Проверьте подключение к Redis
redis-cli ping
# Ожидается: PONG
```

---

## Этап 3: Тестирование WebSocket подключения

### 3.1 Прямое подключение к Gunicorn (без Nginx)

Временно проверьте, работает ли WebSocket напрямую:

```bash
# На сервере проверьте порт Gunicorn (обычно 9000)
sudo netstat -tlnp | grep 9000

# Попробуйте подключиться через curl
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: test" \
  http://127.0.0.1:9000/ws/
```

**Ожидается:**
- Код ответа `101 Switching Protocols` при успехе
- Код `400` или `403` если есть проблемы с аутентификацией

### 3.2 Тест через Nginx

```bash
# С локальной машины
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: test" \
  http://172.11.0.11/ws/
```

Если ответ `502` или `504` - проблема в Nginx конфигурации.

### 3.3 Тест с аутентификацией

Создайте простой HTML файл для теста:

```html
<!-- test_ws.html -->
<!DOCTYPE html>
<html>
<head>
    <title>WS Test</title>
</head>
<body>
    <h1>WebSocket Test</h1>
    <div id="log"></div>
    <script>
        const log = document.getElementById('log');
        
        // Замените на реальный JWT токен пользователя
        const token = 'YOUR_JWT_TOKEN_HERE';
        
        const ws = new WebSocket(`ws://172.11.0.11/ws/?token=${token}`);
        
        ws.onopen = () => {
            log.innerHTML += '<p style="color:green">✅ Connected!</p>';
            console.log('WebSocket opened');
        };
        
        ws.onmessage = (event) => {
            log.innerHTML += `<p>📩 Message: ${event.data}</p>`;
            console.log('Message:', event.data);
        };
        
        ws.onerror = (error) => {
            log.innerHTML += '<p style="color:orange">⚠️ Error occurred</p>';
            console.error('WebSocket error:', error);
        };
        
        ws.onclose = (event) => {
            log.innerHTML += `<p style="color:red">❌ Closed: Code ${event.code}, Reason: ${event.reason || 'none'}</p>`;
            console.log('Close event:', event);
        };
    </script>
</body>
</html>
```

---

## Этап 4: Исправление типичных проблем

### 4.1 Проблема: Отсутствует отдельный блок для WebSocket

**✅ У ВАС УЖЕ НАСТРОЕНО ПРАВИЛЬНО!**

Ваша конфигурация уже содержит правильный блок `location /ws/` с нужными параметрами.

**Пропустите этот пункт и переходите к 4.2**

### 4.2 Проблема: Короткие таймауты

**Симптомы:**
- Соединение работает, но закрывается через 30-60 секунд
- Код 1006 после периода неактивности

**Решение:**
Увеличьте таймауты в Nginx (см. 4.1) и проверьте Gunicorn:

```bash
# Проверьте настройки Gunicorn
sudo cat /etc/systemd/system/eusrr.service

# Должен быть параметр --timeout
# ExecStart=.../gunicorn ... --timeout 300
```

Если таймаут мал, увеличьте:
```bash
sudo nano /etc/systemd/system/eusrr.service
# Измените --timeout 300 (или добавьте если нет)

sudo systemctl daemon-reload
sudo systemctl restart eusrr
```

### 4.3 Проблема: Ошибки аутентификации JWT

**Симптомы:**
- Код 1006 сразу при подключении
- В логах Django: `Authentication failed` или `Invalid token`

**Проверка:**
```python
# На сервере
cd /home/igor/EUSRR/backend
source venv/bin/activate
python manage.py shell

from rest_framework_simplejwt.tokens import AccessToken
from users.models import User

# Проверьте токен конкретного пользователя
user = User.objects.get(username='имя_пользователя')
token = AccessToken.for_user(user)
print(f"Token: {token}")
print(f"Valid: {token.check_exp(current_time=None)}")
```

**Решение:**
- Убедитесь, что токен передается правильно: `?token=...`
- Проверьте срок действия токена (`ACCESS_TOKEN_LIFETIME` в settings.py)
- Убедитесь, что `JWTAuthMiddleware` правильно настроен в `asgi.py`

### 4.4 Проблема: Проблемы с CORS/Same-Origin Policy

**Симптомы:**
- Ошибка только при подключении с определенных доменов
- В консоли браузера: CORS ошибки

**Решение:**
Добавьте в Nginx заголовки CORS для WebSocket:

```nginx
location /ws/ {
    # ... существующие настройки ...
    
    # CORS для WebSocket (если нужно)
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Credentials' 'true' always;
}
```

### 4.5 Проблема: Redis недоступен

**Симптомы:**
- WebSocket подключается, но не работает channel layer
- В логах: `Connection refused` к Redis

**Проверка:**
```bash
# Проверьте Redis
redis-cli ping

# Проверьте настройки в Django
cd /home/igor/EUSRR/backend
grep -A 10 "CHANNEL_LAYERS" eusrr_backend/settings.py
```

**Решение:**
```bash
# Запустите Redis если не работает
sudo systemctl start redis
sudo systemctl enable redis
```

---

## Этап 5: Специфичные сценарии

### 5.1 Проблема только у некоторых пользователей

**Возможные причины:**
1. **Корпоративный firewall** блокирует WebSocket
2. **Антивирус** блокирует соединения
3. **VPN/прокси** на стороне клиента
4. **Браузерные расширения** (блокировщики рекламы, privacy tools)

**Диагностика:**
- Попросите пользователя попробовать в режиме инкогнито
- Попробуйте с другого устройства в той же сети
- Попробуйте с мобильного интернета (вне корп. сети)
- Отключите временно антивирус/расширения браузера

### 5.2 Проблема только в определенное время

**Возможные причины:**
1. Высокая нагрузка на сервер
2. Сетевые проблемы в определенное время
3. Бэкапы или cron задачи нагружающие сервер

**Диагностика:**
```bash
# Мониторинг нагрузки
htop

# Статистика соединений
sudo netstat -an | grep :9000 | wc -l

# Проверьте cron задачи
crontab -l
sudo crontab -l
```

### 5.3 Проблема после обновления кода

**Проверьте:**
1. Миграции базы данных применены
2. Статика собрана
3. Сервисы перезапущены

```bash
cd /home/igor/EUSRR/backend
source venv/bin/activate

# Миграции
python manage.py migrate

# Статика
python manage.py collectstatic --noinput

# Перезапуск
sudo systemctl restart eusrr
sudo systemctl reload nginx
```

---

## Этап 6: Мониторинг и логирование

### 6.1 Добавьте расширенное логирование

В `user_consumer.py` добавьте детальные логи:

```python
import logging
logger = logging.getLogger(__name__)

class UserConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        logger.info(f"[WS] Connection attempt from {self.scope.get('client')}")
        logger.info(f"[WS] User: {self.scope.get('user')}")
        logger.info(f"[WS] Headers: {dict(self.scope.get('headers', []))}")
        
        # ... existing code ...
        
    async def disconnect(self, code):
        logger.warning(f"[WS] Disconnect: user={self.user.username if self.user else 'unknown'}, code={code}")
        # ... existing code ...
```

### 6.2 Настройте мониторинг WebSocket соединений

```bash
# Скрипт для мониторинга WebSocket
cat > /home/igor/monitor_ws.sh << 'EOF'
#!/bin/bash
while true; do
    echo "=== $(date) ==="
    echo "Active WebSocket connections:"
    sudo netstat -an | grep :9000 | grep ESTABLISHED | wc -l
    echo ""
    sleep 10
done
EOF

chmod +x /home/igor/monitor_ws.sh
```

---

## Этап 7: Чек-лист быстрой проверки

Для быстрой диагностики выполните:

```bash
# 1. Сервисы работают?
sudo systemctl status nginx eusrr redis

# 2. Порты слушают?
sudo netstat -tlnp | grep -E ":(80|9000|6379)"

# 3. Ошибки в логах за последний час?
sudo journalctl -u eusrr --since "1 hour ago" | grep -i error
sudo grep -i error /var/log/nginx/error.log | tail -20

# 4. Конфигурация Nginx правильная?
sudo nginx -t

# 5. Redis работает?
redis-cli ping

# 6. WebSocket блок существует?
sudo grep -A 15 "location /ws/" /etc/nginx/sites-enabled/eusrr
```

---

## Этап 8: Рекомендуемая конфигурация Nginx

**Полная рабочая конфигурация для WebSocket:**

```nginx
server {
    listen 80;
    server_name corp.robotail.local 172.11.0.11 127.0.0.1;

    client_max_body_size 50m;

    # Логирование
    access_log /var/log/nginx/eusrr_access.log;
    error_log /var/log/nginx/eusrr_error.log warn;

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

    # WebSocket - КРИТИЧЕСКИ ВАЖНО: отдельный блок перед location /
    location /ws/ {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket специфичные заголовки
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";

        # Таймауты для долгих соединений (7 дней)
        proxy_connect_timeout 7d;
        proxy_send_timeout 7d;
        proxy_read_timeout 7d;
        
        # Отключаем буферизацию для реалтайм данных
        proxy_buffering off;
        
        # Дополнительные настройки для стабильности
        proxy_redirect off;
        proxy_cache_bypass $http_upgrade;
    }

    # API и основное приложение
    location / {
        proxy_pass http://127.0.0.1:9000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # Обычные таймауты для HTTP запросов
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

**Применение:**
```bash
# Сохраните конфигурацию
sudo nano /etc/nginx/sites-enabled/eusrr
# Вставьте конфигурацию выше

# Проверьте
sudo nginx -t

# Примените
sudo systemctl reload nginx

# Проверьте логи
sudo tail -f /var/log/nginx/eusrr_error.log
```

---

## Итоговый алгоритм диагностики

1. **Собрать информацию** (Этап 1)
   - Кто, когда, при каких условиях сталкивается с ошибкой

2. **Проверить сервер** (Этап 2)
   - Nginx конфигурация
   - Логи Nginx/Gunicorn/Redis
   - Статус сервисов

3. **Протестировать подключение** (Этап 3)
   - Напрямую к Gunicorn
   - Через Nginx
   - С аутентификацией

4. **Применить исправления** (Этап 4)
   - Добавить отдельный блок `/ws/`
   - Увеличить таймауты
   - Проверить JWT аутентификацию

5. **Специфичные случаи** (Этап 5)
   - Сетевые ограничения
   - Высокая нагрузка
   - Проблемы после обновлений

6. **Настроить мониторинг** (Этап 6)
   - Расширенное логирование
   - Скрипты мониторинга

7. **Быстрая проверка** (Этап 7)
   - Чек-лист из 6 команд

8. **Применить эталонную конфигурацию** (Этап 8)
   - Проверенная конфигурация Nginx

---

## Полезные команды для копирования

```bash
# === Быстрая диагностика ===
# Подключение к серверу
ssh igor@172.11.0.11

# Проверка всех сервисов
sudo systemctl status nginx eusrr redis

# Просмотр логов в реальном времени
sudo journalctl -u eusrr -f | grep -i "websocket\|error"

# Проверка конфигурации
sudo nginx -t
sudo cat /etc/nginx/sites-enabled/eusrr | grep -A 20 "location /ws/"

# Перезапуск после изменений
sudo systemctl reload nginx
sudo systemctl restart eusrr

# === Мониторинг ===
# Количество WebSocket соединений
watch -n 2 'sudo netstat -an | grep :9000 | grep ESTABLISHED | wc -l'

# Последние ошибки
sudo journalctl -u eusrr --since "10 minutes ago" | grep -i error

# === Тестирование ===
# Тест WebSocket через curl
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: test" \
  http://172.11.0.11/ws/
```

---

## Ожидаемый результат

После выполнения плана диагностики вы:
1. ✅ Определите точную причину ошибки 1006
2. ✅ Примените соответствующее исправление
3. ✅ Настроите мониторинг для предотвращения проблем
4. ✅ Подтвердите, что WebSocket работает стабильно

**Если проблема не решена после всех этапов:**
- Сделайте полный дамп логов (Nginx + Django + Redis)
- Проверьте сетевую инфраструктуру (firewall, routing)
- Рассмотрите переход на WSS (WebSocket Secure) через HTTPS
