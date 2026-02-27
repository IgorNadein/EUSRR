# Диагностика WebSocket 1006 - Сводка

## 📚 Созданные документы

### 1. **WEBSOCKET_1006_QUICK_GUIDE.md** ⚡ (НАЧНИТЕ ЗДЕСЬ!)
**Для:** Быстрой диагностики (5 минут)
**Содержит:**
- Экспресс-скрипт для проверки всех компонентов
- Расшифровку результатов
- Быстрые фиксы
- Команды для мониторинга в реальном времени
- Краткий FAQ

### 2. **WEBSOCKET_1006_PRIORITY_CHECK.md**
**Для:** Детальной диагностики с приоритетами
**Содержит:**
- 5 наиболее вероятных причин (с процентами)
- Детальные инструкции для каждой причины
- Решения и обходные пути
- Чек-лист после исправления

### 3. **WEBSOCKET_1006_DIAGNOSTIC_PLAN.md**
**Для:** Полной методологии диагностики
**Содержит:**
- 8 этапов диагностики от простого к сложному
- Все возможные сценарии проблем
- Примеры конфигураций
- Скрипты для мониторинга
- Эталонная конфигурация Nginx

---

## 🎯 Быстрый старт

### Шаг 1: Экспресс-диагностика (5 минут)

Подключитесь к серверу и выполните:

```bash
ssh igor@172.11.0.11

# Скопируйте и выполните весь блок:
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

### Шаг 2: Интерпретация результатов

**Результат 2 (JWT/Auth):**
- Если видите `Authentication failed`, `code=4401`, `Invalid token` → **Проблема в JWT!**
- Переходите к разделу "Проверка JWT" в WEBSOCKET_1006_QUICK_GUIDE.md

**Результат 3 (Redis):**
- Если НЕ `PONG` → перезапустите Redis: `sudo systemctl restart redis`

**Результат 4 (Nginx errors):**
- Если видите `502` или `504` → проблема с Gunicorn
- Если видите `upstream prematurely closed` → проверьте Django логи

**Результат 6 (Test):**
- `403` - нормально (нет токена)
- `502/504` - проблема с backend

### Шаг 3: Быстрые фиксы (если нужно)

**Фикс 1: Перезапустить всё**
```bash
sudo systemctl restart redis
sudo systemctl restart eusrr
sudo systemctl reload nginx
```

**Фикс 2: Увеличить время жизни токена JWT**
```bash
cd /home/igor/EUSRR/backend
nano eusrr_backend/settings.py
# Найдите SIMPLE_JWT и увеличьте ACCESS_TOKEN_LIFETIME
sudo systemctl restart eusrr
```

**Фикс 3: Включить расширенное логирование**
См. раздел в WEBSOCKET_1006_QUICK_GUIDE.md

---

## 📊 Вероятные причины (ваш случай)

Поскольку ваша конфигурация Nginx **уже правильная** (отдельный блок /ws/, таймауты 7 дней, все заголовки):

### 1. JWT аутентификация (60% вероятность) 🔥
**Проверьте:**
- Логи Django на ошибки auth
- Срок действия токенов
- Передается ли токен в URL правильно

**Где смотреть:**
- `WEBSOCKET_1006_PRIORITY_CHECK.md` → раздел 1
- `WEBSOCKET_1006_QUICK_GUIDE.md` → "Проверка JWT"

### 2. CORS/Origin заголовки (25% вероятность)
**Проверьте:**
- Работает ли с разных доменов (corp.robotail.local vs 172.11.0.11)
- Нужны ли дополнительные CORS заголовки

**Где смотреть:**
- `WEBSOCKET_1006_PRIORITY_CHECK.md` → раздел 2

### 3. Проблемы на стороне клиента (10% вероятность)
**Проверьте:**
- Firewall/антивирус
- Браузерные расширения
- Режим инкогнито

**Где смотреть:**
- `WEBSOCKET_1006_PRIORITY_CHECK.md` → раздел 3
- `WEBSOCKET_1006_QUICK_GUIDE.md` → "Проверка на стороне клиента"

### 4. Redis/Gunicorn (5% вероятность)
**Проверьте:**
- Redis доступен и работает
- Gunicorn workers живы

**Где смотреть:**
- `WEBSOCKET_1006_PRIORITY_CHECK.md` → разделы 4-5

---

## 🛠️ Инструменты для мониторинга

### Мониторинг логов Django:
```bash
ssh igor@172.11.0.11
sudo journalctl -u eusrr -f | grep -i "websocket\|connect\|4401"
```

### Мониторинг активных соединений:
```bash
ssh igor@172.11.0.11
watch -n 2 'sudo netstat -an | grep :9000 | grep ESTABLISHED | wc -l'
```

### Проверка в браузере пользователя:
1. F12 → Network → WS
2. Найти `/ws/` соединение
3. Проверить Status (должен быть 101)
4. Проверить Messages (должны быть ping каждые 20 секунд)

---

## 📞 Если ничего не помогло

### Соберите полный дамп:

```bash
ssh igor@172.11.0.11
cd /tmp

{
  echo "=== SERVICES ==="
  sudo systemctl status nginx eusrr redis --no-pager
  echo -e "\n=== DJANGO LOGS ==="
  sudo journalctl -u eusrr --since "1 hour ago" --no-pager
  echo -e "\n=== NGINX ERRORS ==="
  sudo tail -100 /var/log/nginx/error.log
  echo -e "\n=== NGINX CONFIG ==="
  sudo cat /etc/nginx/sites-enabled/eusrr
  echo -e "\n=== REDIS INFO ==="
  redis-cli INFO
} > ws_debug_$(date +%Y%m%d_%H%M%S).txt

ls -lh ws_debug_*.txt
```

Скачайте файл на локальную машину:
```bash
scp igor@172.11.0.11:/tmp/ws_debug_*.txt .
```

---

## ✅ Контрольный список

Перед тем как просить помощь, убедитесь:

- [ ] Выполнили экспресс-диагностику из Шага 1
- [ ] Проверили JWT логи (это самая частая причина!)
- [ ] Redis отвечает `PONG`
- [ ] Нет ошибок в Nginx error.log
- [ ] Попробовали в режиме инкогнито
- [ ] Проверили на другом устройстве/сети
- [ ] Перезапустили сервисы (redis, eusrr, nginx)
- [ ] Проверили время жизни JWT токена

---

## 📖 Какой документ читать?

### У вас 5 минут?
→ **WEBSOCKET_1006_QUICK_GUIDE.md** ⚡

### Нужно разобраться детально?
→ **WEBSOCKET_1006_PRIORITY_CHECK.md**

### Хотите полную методологию?
→ **WEBSOCKET_1006_DIAGNOSTIC_PLAN.md**

### Проблемы с keepalive/ping?
→ **WEBSOCKET_KEEPALIVE_FIX.md**

---

## 🎓 Полезная информация

### Код ошибки 1006 означает:
"Abnormal Closure" - соединение закрылось без отправки Close frame.

### Это НЕ означает:
- Проблема в коде JavaScript (код правильный)
- Проблема в Nginx конфигурации (конфигурация правильная)

### Это ОБЫЧНО означает:
- Проблема с аутентификацией (JWT токен)
- Проблема на уровне сети/firewall
- Backend отклонил соединение
- Таймауты (но у вас 7 дней, маловероятно)

---

## 🚀 Следующие шаги

1. **Начните с экспресс-диагностики** (Шаг 1 выше)
2. **Проверьте JWT логи** (это самое важное!)
3. **Если не помогло** - читайте WEBSOCKET_1006_PRIORITY_CHECK.md
4. **Включите расширенное логирование** для детального анализа
5. **Соберите дамп** если ничего не помогло

Удачи в диагностике! 🔍
