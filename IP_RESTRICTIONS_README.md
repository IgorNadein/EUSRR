# 🔒 IP-ограничения для регистрации - Краткая инструкция

## ✅ Что сделано

Добавлен **middleware** для ограничения доступа к регистрации по IP-адресу.

## 📁 Изменённые файлы

1. **`backend/eusrr_backend/middleware.py`** - добавлен `RegistrationIPRestrictionMiddleware`
2. **`backend/eusrr_backend/settings.py`** - middleware включен в `MIDDLEWARE`
3. **`backend/common/ip_restrictions.py`** - утилиты для проверки IP

## ⚙️ Настройка

В `backend/eusrr_backend/settings.py` найдите:

```python
# IP ОГРАНИЧЕНИЯ ДЛЯ РЕГИСТРАЦИИ
REGISTRATION_ALLOWED_IPS = None  # По умолчанию только локальные IP
```

### Варианты настройки:

```python
# 1. Только локальные IP (по умолчанию)
REGISTRATION_ALLOWED_IPS = None

# 2. Разрешить все IP (для разработки)
REGISTRATION_ALLOWED_IPS = ['*']

# 3. Разрешить конкретные сети
REGISTRATION_ALLOWED_IPS = [
    '192.168.1.0/24',  # Локальная сеть офиса
    '10.0.0.0/8',      # Корпоративная сеть
]

# 4. Разрешить конкретные IP
REGISTRATION_ALLOWED_IPS = ['192.168.1.100', '203.0.113.42']
```

## 🎯 Как работает

**По умолчанию (None):**
- ✅ Разрешены: `127.0.0.1`, `192.168.x.x`, `10.x.x.x`, `172.16-31.x.x`
- ❌ Заблокированы: все внешние IP

**Блокируемые URL:**
- `/auth/register/` (веб-форма)
- `/api/v1/auth/register/` (API)

**Ответ при блокировке:**
- API: `{"detail": "Регистрация доступна только из локальной сети.", "client_ip": "..."}`
- Веб: Красивая страница 403 с информацией об IP

## 🔧 Отключение

### Временно (для разработки):
```python
REGISTRATION_ALLOWED_IPS = ['*']
```

### Полностью:
В `settings.py` закомментируйте строку в `MIDDLEWARE`:
```python
# "eusrr_backend.middleware.RegistrationIPRestrictionMiddleware",
```

## 🧪 Тестирование

```bash
# Из локальной сети - работает
curl http://localhost:9000/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com",...}'

# С внешнего IP - блокируется
curl http://localhost:9000/api/v1/auth/register/ \
  -H "X-Forwarded-For: 203.0.113.50" \
  -d '{"email":"test@example.com",...}'
```

## 🌐 Работа за прокси

Middleware автоматически определяет реальный IP через заголовки `X-Forwarded-For` и `X-Real-IP`.

Настройте Nginx:
```nginx
location / {
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;
}
```

## 📚 Полная документация

См. `IP_REGISTRATION_RESTRICTIONS.md`
