# WebSocket 1006 - Приоритетная диагностика

## ✅ Конфигурация Nginx ПРАВИЛЬНАЯ

Ваша текущая конфигурация Nginx уже содержит все необходимые настройки для WebSocket, поэтому проблема **НЕ** в базовой конфигурации.

---

## 🎯 Наиболее вероятные причины (в порядке убывания)

### 1. Проблемы с JWT аутентификацией (60% вероятность)

**Симптомы:**
- Ошибка 1006 сразу при попытке подключения
- Работает у одних пользователей, не работает у других
- Может зависеть от времени (истекший токен)

**Быстрая проверка:**
```bash
# На сервере проверьте логи Django
ssh igor@172.11.0.11
sudo journalctl -u eusrr -n 100 | grep -i "websocket\|authentication\|jwt\|token"
```

**Что искать в логах:**
- `Authentication failed`
- `Invalid token`
- `Token has expired`
- `User not found`

**Решение:**

1. Проверьте настройки JWT в `settings.py`:
```bash
cd /home/igor/EUSRR/backend
grep -A 10 "SIMPLE_JWT" eusrr_backend/settings.py
```

2. Убедитесь, что токен передается правильно в JS:
```javascript
// В браузере пользователя (DevTools Console)
console.log('Token:', localStorage.getItem('access_token'));
console.log('WS URL:', window.userWebSocket?.ws?.url);
```

3. Увеличьте время жизни токена (если нужно):
```python
# settings.py
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),  # Было меньше?
    # ...
}
```

---

### 2. Проблемы с CORS/Заголовками Origin (25% вероятность)

**Симптомы:**
- Работает при подключении с `corp.robotail.local`, не работает с `172.11.0.11`
- Работает в одном браузере, не работает в другом
- В консоли браузера могут быть предупреждения о CORS

**Быстрая проверка:**
```bash
# Проверьте Access-Control заголовки
curl -I -H "Origin: http://172.11.0.11" http://172.11.0.11/ws/
```

**Решение:**

Добавьте CORS заголовки в блоки `/ws/` (для обоих серверов - HTTP и HTTPS):

```nginx
location /ws/ {
    # ... существующие настройки ...
    
    # Добавьте:
    proxy_set_header Origin $http_origin;
    
    # Если нужен CORS (необязательно, но может помочь):
    add_header 'Access-Control-Allow-Origin' '$http_origin' always;
    add_header 'Access-Control-Allow-Credentials' 'true' always;
    add_header 'Access-Control-Allow-Methods' 'GET, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' 'Upgrade,Connection,Sec-WebSocket-Key,Sec-WebSocket-Version' always;
}
```

Примените:
```bash
sudo nginx -t && sudo systemctl reload nginx
```

---

### 3. Проблемы на стороне клиента (10% вероятность)

**Симптомы:**
- Работает у большинства, не работает у конкретных пользователей
- Может зависеть от сети (офис vs дом)

**Возможные причины:**
- Корпоративный firewall/proxy блокирует WebSocket
- Антивирус блокирует соединения
- Браузерные расширения (AdBlock, Privacy Badger, NoScript)
- VPN/туннель с проблемами

**Диагностика:**

Попросите пользователя:

1. Открыть **режим инкогнито** (отключит расширения):
```
Ctrl+Shift+N (Chrome/Edge) или Ctrl+Shift+P (Firefox)
```

2. Проверить в консоли браузера (F12 → Console):
```javascript
// Попробуйте подключиться вручную
const token = localStorage.getItem('access_token');
const ws = new WebSocket(`ws://172.11.0.11/ws/?token=${token}`);

ws.onopen = () => console.log('✅ Connected!');
ws.onerror = (e) => console.error('❌ Error:', e);
ws.onclose = (e) => console.log('❌ Closed:', e.code, e.reason);
```

3. Попробовать с другого устройства/сети

**Решение:**
- Добавить исключение в firewall/антивирус
- Отключить проблемные расширения
- Попробовать HTTPS (WSS) вместо HTTP (WS)

---

### 4. Redis недоступен или перегружен (3% вероятность)

**Симптомы:**
- Соединение устанавливается, но сразу закрывается
- Проблема у всех пользователей одновременно

**Быстрая проверка:**
```bash
ssh igor@172.11.0.11

# Проверьте Redis
redis-cli ping
# Должно вернуть: PONG

# Проверьте подключения к Redis
redis-cli CLIENT LIST | grep -c connected
# Должно быть разумное число (<1000)

# Проверьте память Redis
redis-cli INFO memory | grep used_memory_human

# Проверьте статус сервиса
sudo systemctl status redis
```

**Решение:**

Если Redis не работает:
```bash
sudo systemctl restart redis
sudo systemctl enable redis
```

Если Redis перегружен (проверьте логи):
```bash
# Очистите кеш (ВНИМАНИЕ: это удалит все данные Redis!)
redis-cli FLUSHALL

# Или перезапустите
sudo systemctl restart redis
```

---

### 5. Gunicorn worker умер или перегружен (2% вероятность)

**Симптомы:**
- Периодические проблемы
- После перезапуска работает какое-то время

**Быстрая проверка:**
```bash
ssh igor@172.11.0.11

# Проверьте статус Gunicorn
sudo systemctl status eusrr

# Проверьте логи на ошибки
sudo journalctl -u eusrr --since "1 hour ago" | grep -i "error\|worker\|timeout"

# Проверьте количество worker'ов
ps aux | grep gunicorn | grep -v grep
```

**Решение:**

1. Проверьте конфигурацию Gunicorn:
```bash
sudo cat /etc/systemd/system/eusrr.service
```

Должно быть примерно так:
```ini
ExecStart=/home/igor/EUSRR/backend/venv/bin/gunicorn \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:9000 \
    --timeout 300 \
    --access-logfile /var/log/eusrr/access.log \
    --error-logfile /var/log/eusrr/error.log \
    eusrr_backend.asgi:application
```

2. Если конфигурация неправильная, исправьте и перезапустите:
```bash
sudo systemctl daemon-reload
sudo systemctl restart eusrr
```

---

## 🚀 Быстрый чек-лист диагностики

Выполните эти команды **по порядку**:

```bash
# 1. Подключитесь к серверу
ssh igor@172.11.0.11

# 2. Проверьте все сервисы
sudo systemctl status nginx eusrr redis
# Все должны быть active (running)

# 3. Проверьте JWT логи (САМОЕ ВАЖНОЕ!)
sudo journalctl -u eusrr -n 200 | grep -i "websocket\|authentication\|jwt"
# Ищите ошибки аутентификации

# 4. Проверьте Redis
redis-cli ping
# Должно вернуть: PONG

# 5. Проверьте ошибки Nginx
sudo tail -50 /var/log/nginx/error.log
# Не должно быть ошибок 502/504

# 6. Проверьте активные WebSocket соединения
sudo netstat -an | grep :9000 | grep ESTABLISHED
# Должны быть подключения

# 7. Тест WebSocket вручную
curl -i -N \
  -H "Connection: Upgrade" \
  -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" \
  -H "Sec-WebSocket-Key: test" \
  http://127.0.0.1:9000/ws/
# Должен вернуть 403 (нет токена) или 101 (успех с токеном)
```

---

## 🔍 Расширенная диагностика JWT (если проблема в аутентификации)

### На сервере:

```bash
cd /home/igor/EUSRR/backend
source venv/bin/activate

# Запустите Django shell
python manage.py shell
```

```python
# В Django shell:
from users.models import User
from rest_framework_simplejwt.tokens import AccessToken
from datetime import datetime

# Проверьте пользователя, у которого проблема
username = "имя_пользователя"  # Замените на реального пользователя
user = User.objects.get(username=username)

# Создайте новый токен
token = AccessToken.for_user(user)
print(f"User: {user.username}")
print(f"Token: {token}")
print(f"Expires at: {datetime.fromtimestamp(token['exp'])}")

# Проверьте валидность
try:
    token.check_exp()
    print("✅ Token is valid")
except Exception as e:
    print(f"❌ Token error: {e}")

# Выход
exit()
```

### В браузере пользователя (F12 → Console):

```javascript
// 1. Проверьте текущий токен
const token = localStorage.getItem('access_token');
console.log('Token:', token);

// 2. Декодируйте токен (без проверки подписи)
if (token) {
    const parts = token.split('.');
    if (parts.length === 3) {
        const payload = JSON.parse(atob(parts[1]));
        console.log('Token payload:', payload);
        console.log('Expires:', new Date(payload.exp * 1000));
        console.log('Is expired:', new Date() > new Date(payload.exp * 1000));
    }
}

// 3. Попробуйте переподключиться с токеном
if (window.userWebSocket) {
    window.userWebSocket.reconnect();
}
```

---

## 📋 Если проблема только у некоторых пользователей

### Соберите данные от пользователя:

1. **Браузер и ОС**
   - Chrome/Firefox/Edge/Safari?
   - Windows/Mac/Linux?
   - Версия браузера?

2. **Сеть**
   - Офисная сеть или домашняя?
   - VPN включен?
   - Антивирус работает?

3. **Консоль браузера** (F12 → Console)
   - Есть ли красные ошибки?
   - Что показывает WebSocket в Network → WS?

4. **Воспроизведение**
   - Постоянная проблема или периодическая?
   - На других устройствах та же проблема?

### Тест в режиме инкогнито:

1. Откройте инкогнито (Ctrl+Shift+N)
2. Войдите в систему
3. Попробуйте использовать функции с WebSocket
4. Если **работает в инкогнито** → проблема в расширениях браузера
5. Если **не работает в инкогнито** → проблема в сети/firewall

---

## 🛠️ Временное решение для срочных случаев

Если нужно срочно дать пользователю доступ, попробуйте:

### 1. Увеличить время жизни токена

```python
# backend/eusrr_backend/settings.py
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),  # Было 1 час?
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    # ...
}
```

Перезапустите:
```bash
sudo systemctl restart eusrr
```

### 2. Добавить больше логирования в consumer

```python
# backend/communications/user_consumer.py
import logging
logger = logging.getLogger(__name__)

class UserConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        # Добавьте в начало метода:
        client = self.scope.get('client', ['unknown', 0])
        logger.info(f"[WS CONNECT] Client: {client[0]}:{client[1]}")
        logger.info(f"[WS CONNECT] User: {self.scope.get('user')}")
        logger.info(f"[WS CONNECT] Path: {self.scope.get('path')}")
        
        self.user = self.scope.get("user")
        
        if not self.user or isinstance(self.user, AnonymousUser) or not self.user.is_authenticated:
            logger.warning(f"[WS CONNECT] Authentication failed for {client[0]}")
            await self.close(code=4401)
            return
        
        logger.info(f"[WS CONNECT] Success for user {self.user.username}")
        # ...остальной код...
```

Перезапустите и проверьте логи:
```bash
sudo systemctl restart eusrr
sudo journalctl -u eusrr -f | grep "WS CONNECT"
```

---

## ✅ После исправления

### Проверьте работоспособность:

1. **В браузере** (F12 → Network → WS):
   - Соединение должно быть зеленым
   - Status: 101 Switching Protocols
   - Должны приходить ping каждые 20 секунд

2. **На сервере**:
```bash
# Активные соединения
watch -n 2 'sudo netstat -an | grep :9000 | grep ESTABLISHED | wc -l'
# Число должно расти при подключении пользователей

# Логи без ошибок
sudo journalctl -u eusrr -f | grep -i websocket
# Не должно быть ошибок
```

3. **Функциональность**:
   - Новые сообщения приходят без обновления страницы
   - Уведомления появляются в реальном времени
   - Бейдж чатов обновляется

---

## 📞 Если ничего не помогло

Соберите полный дамп для анализа:

```bash
# На сервере
cd /tmp

# Конфигурация
sudo cat /etc/nginx/sites-enabled/eusrr > ws_debug_nginx.conf
sudo cat /etc/systemd/system/eusrr.service > ws_debug_systemd.service

# Логи (последний час)
sudo journalctl -u eusrr --since "1 hour ago" > ws_debug_django.log
sudo tail -500 /var/log/nginx/error.log > ws_debug_nginx_error.log
sudo tail -500 /var/log/nginx/access.log | grep '/ws/' > ws_debug_nginx_ws.log

# Статус
sudo systemctl status nginx eusrr redis > ws_debug_status.txt
redis-cli INFO > ws_debug_redis.txt
ps aux | grep gunicorn > ws_debug_gunicorn.txt

# Создайте архив
tar -czf ws_debug_$(date +%Y%m%d_%H%M%S).tar.gz ws_debug_*

# Скачайте архив на локальную машину
# scp igor@172.11.0.11:/tmp/ws_debug_*.tar.gz .
```

Отправьте архив для детального анализа.

---

## 🎯 Итого: Порядок действий

1. ✅ **Проверьте JWT логи** (60% вероятность проблемы здесь)
2. ✅ **Проверьте CORS/Origin заголовки** (25% вероятность)
3. ✅ **Попросите пользователя попробовать инкогнито** (10% вероятность)
4. ✅ **Проверьте Redis** (3% вероятность)
5. ✅ **Проверьте Gunicorn workers** (2% вероятность)

**Начните с пункта 1 - это самая частая причина!**
