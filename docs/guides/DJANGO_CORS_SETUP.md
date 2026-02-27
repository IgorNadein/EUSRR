# Настройка Django Backend для работы с React Frontend

## ⚡ Быстрая установка CORS

### 1. Установка пакета

```bash
cd backend
.venv/Scripts/pip install django-cors-headers
```

### 2. Добавить в requirements.txt

```bash
echo django-cors-headers >> requirements.txt
```

### 3. Настройка settings.py

Добавьте изменения в `backend/eusrr_backend/settings.py`:

```python
INSTALLED_APPS = [
    "daphne",
    "channels",
    "corsheaders",  # ← ДОБАВИТЬ ЭТО
    "django.contrib.admin",
    # ... остальное
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",  # ← ДОБАВИТЬ ЭТО (второй строкой!)
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    # ... остальное
]

# В конец файла добавить:
# -----------------------------------------------------------------------------
# CORS SETTINGS (для React frontend)
# -----------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    "http://localhost:5173",  # Vite dev server
    "http://127.0.0.1:5173",
]

# Для продакшена добавить ваш домен:
# CORS_ALLOWED_ORIGINS += ["https://your-domain.com"]

# Разрешить credentials (cookies, auth headers)
CORS_ALLOW_CREDENTIALS = True

# Разрешенные headers
CORS_ALLOW_HEADERS = [
    "accept",
    "accept-encoding",
    "authorization",
    "content-type",
    "dnt",
    "origin",
    "user-agent",
    "x-csrftoken",
    "x-requested-with",
]
```

### 4. Перезапустить Django сервер

```bash
.venv/Scripts/python manage.py runserver 8000
```

## 📡 Проверка работы CORS

### Test 1: Проверка из браузера

Откройте консоль в DevTools и выполните:

```javascript
fetch('http://localhost:8000/api/v1/employees/')
  .then(res => res.json())
  .then(data => console.log('Success:', data))
  .catch(err => console.error('Error:', err));
```

Если нет ошибок CORS - всё работает!

### Test 2: Проверка через curl

```bash
curl -H "Origin: http://localhost:5173" \
     -H "Access-Control-Request-Method: GET" \
     -H "Access-Control-Request-Headers: X-Requested-With" \
     -X OPTIONS \
     --verbose \
     http://localhost:8000/api/v1/employees/ 2>&1 | grep -i "< access-control"
```

Должны увидеть:
```
< access-control-allow-origin: http://localhost:5173
< access-control-allow-credentials: true
```

## 🔐 Настройка JWT авторизации

Ваша текущая настройка JWT уже работает через `PhoneOrEmailTokenObtainPairView`.

Frontend будет использовать:
- **Login**: `POST /api/auth/token/` → получить access + refresh
- **Refresh**: `POST /api/auth/token/refresh/` → обновить токен

Проверьте что endpoint работает:

```bash
curl -X POST http://localhost:8000/api/auth/token/ \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "password": "yourpassword"}'
```

Ответ должен быть:
```json
{
  "access": "eyJ0eXAiOiJKV1QiLCJh...",
  "refresh": "eyJ0eXAiOiJKV1QiLCJh..."
}
```

## 🚀 Запуск обоих серверов

### Terminal 1: Django Backend

```bash
cd backend
.venv/Scripts/python manage.py runserver 8000
```

### Terminal 2: React Frontend

```bash
cd frontend
npm run dev
```

Откройте: http://localhost:5173

## ❗ Возможные проблемы

### Ошибка: "CORS policy: No 'Access-Control-Allow-Origin' header"

**Решение:**
1. Проверьте что `corsheaders` установлен: `.venv/Scripts/pip list | grep cors`
2. Убедитесь что `CorsMiddleware` добавлен **ПЕРЕД** `CommonMiddleware`
3. Проверьте что `http://localhost:5173` в `CORS_ALLOWED_ORIGINS`
4. Перезапустите Django сервер

### Ошибка: "django.core.exceptions.ImproperlyConfigured: 'corsheaders' is not a registered tag library"

**Решение:**
```bash
.venv/Scripts/pip uninstall django-cors-headers
.venv/Scripts/pip install django-cors-headers
```

### Авторизация не работает (401 Unauthorized)

**Проверьте:**
1. Токен правильно сохраняется: `localStorage.getItem('eusrr-auth-token')`
2. Токен отправляется в header: `Authorization: Bearer <token>`
3. Токен не истек (срок жизни настроен в `settings.py`)

## 📝 Дополнительно

### Для production добавьте:

```python
# settings.py
if not DEBUG:
    CORS_ALLOWED_ORIGINS = [
        "https://your-production-domain.com",
    ]
    # Отключить CORS для всех:
    CORS_ALLOW_ALL_ORIGINS = False
```

### Для WebSocket (чаты) добавьте:

```python
# settings.py
CORS_ALLOW_HEADERS += [
    "sec-websocket-key",
    "sec-websocket-version",
    "sec-websocket-extensions",
]
```

## ✅ Готово!

Теперь можно запускать frontend и backend вместе.
