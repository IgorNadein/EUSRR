# WebSocket 1006 - Быстрая шпаргалка

## 🚨 Экспресс-диагностика (5 минут)

```bash
# Подключитесь к серверу
ssh igor@172.11.0.11

# Скопируйте и выполните все команды сразу:

echo "=== 1. Статус сервисов ==="
sudo systemctl status nginx eusrr redis --no-pager

echo -e "\n=== 2. JWT/Auth ошибки (САМОЕ ВАЖНОЕ!) ==="
sudo journalctl -u eusrr -n 200 --no-pager | grep -i "websocket\|authentication\|jwt\|token\|4401"

echo -e "\n=== 3. Redis доступен? ==="
redis-cli ping

echo -e "\n=== 4. Ошибки Nginx ==="
sudo tail -20 /var/log/nginx/error.log

echo -e "\n=== 5. Активные WS соединения ==="
sudo netstat -an | grep :9000 | grep ESTABLISHED | wc -l

echo -e "\n=== 6. Тест WS подключения ==="
curl -i -N -H "Connection: Upgrade" -H "Upgrade: websocket" \
  -H "Sec-WebSocket-Version: 13" -H "Sec-WebSocket-Key: test" \
  http://127.0.0.1:9000/ws/ 2>&1 | head -20
```

---

## 🎯 Что проверить по результатам

### Результат 2 (JWT/Auth ошибки):

**Если видите:**
- `Authentication failed` → Проблема с токеном
- `code=4401` → Пользователь не аутентифицирован
- `Invalid token` → Токен истек или неправильный
- `AnonymousUser` → Токен не передается

**➡️ Действие:** Проверьте JWT (см. раздел JWT ниже)

### Результат 3 (Redis):

**Если НЕ вернул `PONG`:**
```bash
sudo systemctl restart redis
redis-cli ping
```

### Результат 4 (Nginx):

**Если видите ошибки:**
- `upstream prematurely closed` → Backend закрыл соединение (проверьте Django логи)
- `upstream timed out` → Таймаут (но у вас уже 7 дней, странно)
- `502/504` → Backend недоступен (проверьте Gunicorn)

### Результат 5 (Соединения):

**Если 0:** Никто не подключен (нормально, если нет пользователей онлайн)
**Если >0:** Есть активные соединения → значит у кого-то работает!

### Результат 6 (Тест):

**Ожидается:**
- `HTTP/1.1 403` (нет токена) или
- `HTTP/1.1 101` (успех, если токен не требуется на этом уровне)

**Если `502` или `504`:** Проблема с Gunicorn

---

## 🔑 Проверка JWT (если проблема в auth)

### На сервере:

```bash
cd /home/igor/EUSRR/backend
source venv/bin/activate
python manage.py shell
```

```python
from users.models import User
from rest_framework_simplejwt.tokens import AccessToken
from datetime import datetime

# Замените на проблемного пользователя
user = User.objects.get(username="USERNAME")
token = AccessToken.for_user(user)
print(f"✅ Token: {token}")
print(f"📅 Expires: {datetime.fromtimestamp(token['exp'])}")
exit()
```

### В браузере пользователя (F12 → Console):

```javascript
// Проверьте токен
const token = localStorage.getItem('access_token');
console.log('Token:', token ? 'Exists' : 'Missing!');

// Декодируйте и проверьте срок
if (token) {
    const payload = JSON.parse(atob(token.split('.')[1]));
    console.log('Expires:', new Date(payload.exp * 1000));
    console.log('Expired?', new Date() > new Date(payload.exp * 1000));
}

// Переподключите WS
window.userWebSocket?.reconnect();
```

---

## 🌐 Проверка на стороне клиента

### Пользователь в браузере (F12):

**1. Network → WS:**
- Ищите `/ws/` соединение
- Status должен быть `101 Switching Protocols`
- Если `(pending)` → не подключается
- Если красное → смотрите код ошибки

**2. Console:**
```javascript
// Ручное подключение для теста
const token = localStorage.getItem('access_token');
const ws = new WebSocket(`ws://172.11.0.11/ws/?token=${token}`);

ws.onopen = () => console.log('✅ OPEN');
ws.onerror = (e) => console.error('❌ ERROR:', e);
ws.onclose = (e) => console.log('❌ CLOSE:', e.code, e.reason);

// Подождите 5 секунд...
// Если не открылось - проблема!
```

**3. Режим инкогнито:**
- Ctrl+Shift+N (Chrome/Edge)
- Войдите в систему
- Если **работает** → проблема в расширениях браузера
- Если **не работает** → проблема на сервере/сети

---

## 🔧 Быстрые фиксы

### Фикс 1: Увеличить время жизни токена

```bash
ssh igor@172.11.0.11
cd /home/igor/EUSRR/backend
nano eusrr_backend/settings.py
```

Найдите и измените:
```python
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(hours=24),  # Было меньше?
    # ...
}
```

```bash
sudo systemctl restart eusrr
```

### Фикс 2: Добавить CORS заголовки (если нужно)

```bash
sudo nano /etc/nginx/sites-enabled/eusrr
```

В оба блока `location /ws/` (HTTP и HTTPS) добавьте:
```nginx
proxy_set_header Origin $http_origin;
```

```bash
sudo nginx -t && sudo systemctl reload nginx
```

### Фикс 3: Перезапустить всё

```bash
sudo systemctl restart redis
sudo systemctl restart eusrr
sudo systemctl reload nginx
```

---

## 📊 Мониторинг в реальном времени

### Логи Django (в отдельном терминале):

```bash
ssh igor@172.11.0.11
sudo journalctl -u eusrr -f | grep -i "websocket\|connect\|disconnect"
```

**Что смотреть:**
- `Consumer connected` → Кто-то подключился ✅
- `Consumer disconnected` → Кто-то отключился
- `code=4401` → Проблема с auth ❌
- Traceback → Ошибка в коде ❌

### Активные соединения (в отдельном терминале):

```bash
ssh igor@172.11.0.11
watch -n 2 'sudo netstat -an | grep :9000 | grep ESTABLISHED | wc -l'
```

Число должно расти/уменьшаться при подключении/отключении пользователей.

---

## 🐛 Включить расширенное логирование

Если не понятно что происходит:

```bash
ssh igor@172.11.0.11
cd /home/igor/EUSRR/backend
nano communications/user_consumer.py
```

В начало класса `UserConsumer` добавьте:
```python
import logging
logger = logging.getLogger(__name__)
```

В метод `connect()` в самое начало:
```python
async def connect(self):
    client = self.scope.get('client', ['unknown', 0])
    logger.info(f"🔌 WS: {client[0]} trying to connect")
    logger.info(f"👤 User: {self.scope.get('user')}")
    
    self.user = self.scope.get("user")
    
    if not self.user or isinstance(self.user, AnonymousUser):
        logger.warning(f"❌ WS: {client[0]} - No auth")
        await self.close(code=4401)
        return
    
    logger.info(f"✅ WS: {self.user.username} connected")
    # ...остальной код...
```

Сохраните и перезапустите:
```bash
sudo systemctl restart eusrr
sudo journalctl -u eusrr -f | grep WS
```

Теперь будете видеть каждую попытку подключения!

---

## ❓ FAQ

### Работает у одних, не работает у других?
→ Проблема в JWT токене или сети/браузере клиента

### Не работает ни у кого?
→ Проблема на сервере (Redis, Gunicorn, Nginx)

### Работало, потом перестало?
→ Проверьте что изменилось (обновление кода, конфигурации)

### Периодически отваливается?
→ Может быть нормально (пинги каждые 20 сек должны держать)

### Ошибка только в определенной сети?
→ Firewall/proxy блокирует WebSocket

### Работает в инкогнито, не работает в обычном режиме?
→ Расширения браузера блокируют (AdBlock, Privacy Badger и т.д.)

---

## 📞 Экстренная помощь

Если совсем всё плохо, соберите дамп:

```bash
ssh igor@172.11.0.11
cd /tmp

# Один файл со всей инфой
{
  echo "=== SERVICES ==="
  sudo systemctl status nginx eusrr redis --no-pager
  echo -e "\n=== DJANGO LOGS ==="
  sudo journalctl -u eusrr --since "1 hour ago" --no-pager
  echo -e "\n=== NGINX ERRORS ==="
  sudo tail -100 /var/log/nginx/error.log
  echo -e "\n=== NGINX CONFIG ==="
  sudo cat /etc/nginx/sites-enabled/eusrr
  echo -e "\n=== GUNICORN PROCESSES ==="
  ps aux | grep gunicorn
  echo -e "\n=== REDIS INFO ==="
  redis-cli INFO
  echo -e "\n=== CONNECTIONS ==="
  sudo netstat -an | grep :9000
} > ws_debug_$(date +%Y%m%d_%H%M%S).txt

# Скачайте файл
ls -lh ws_debug_*.txt
```

Скопируйте на локальную машину:
```bash
scp igor@172.11.0.11:/tmp/ws_debug_*.txt .
```

---

## ✅ Контрольный список

- [ ] Все сервисы running (nginx, eusrr, redis)
- [ ] Redis отвечает на PONG
- [ ] В логах нет ошибок JWT/auth
- [ ] Нет ошибок в Nginx error.log
- [ ] Тест curl возвращает 403 или 101 (не 502/504)
- [ ] Токен существует в localStorage браузера
- [ ] Токен не истек
- [ ] Попробовали в режиме инкогнито
- [ ] Проверили на другом устройстве/сети

**Если все пункты ✅ но не работает** → пришлите дамп для детального анализа.
