# Запуск backend с поддержкой WebSocket

## Проблема

`python manage.py runserver` **НЕ поддерживает WebSocket**. Для real-time функций нужен ASGI сервер.

## Решение

Используйте **Daphne** (уже установлен в requirements.txt):

### Windows (PowerShell/CMD):

```bash
cd C:/Users/igor_/Dev/EUSRR/backend
c:/Users/igor_/Dev/EUSRR/.venv/Scripts/python -m daphne -b 0.0.0.0 -p 9000 eusrr_backend.asgi:application
```

### Или через активированный venv:

```bash
cd C:/Users/igor_/Dev/EUSRR/backend
..\\.venv\\Scripts\\activate
daphne -b 0.0.0.0 -p 9000 eusrr_backend.asgi:application
```

## Проверка

После запуска должно появиться:
```
2026-02-25 12:00:00 [INFO] Starting server at tcp:port=9000:interface=0.0.0.0
2026-02-25 12:00:00 [INFO] HTTP/2 support enabled
2026-02-25 12:00:00 [INFO] Configuring endpoint tcp:port=9000:interface=0.0.0.0
2026-02-25 12:00:00 [INFO] Listening on TCP address 0.0.0.0:9000
```

## Альтернатива: Uvicorn

Если Daphne не работает:

```bash
pip install uvicorn[standard]
uvicorn eusrr_backend.asgi:application --host 0.0.0.0 --port 9000 --reload
```

## Production

Для production используйте:

```bash
daphne -b 0.0.0.0 -p 9000 eusrr_backend.asgi:application --access-log - --proxy-headers
```

## Автозапуск (опционально)

Создайте скрипт `start_backend.bat`:

```batch
@echo off
cd C:\\Users\\igor_\\Dev\\EUSRR\\backend
c:\\Users\\igor_\\Dev\\EUSRR\\.venv\\Scripts\\python -m daphne -b 0.0.0.0 -p 9000 eusrr_backend.asgi:application
pause
```

Затем просто запускайте `start_backend.bat`.

## Проверка WebSocket

Откройте консоль браузера (F12) и проверьте:

✅ **Успешное подключение:**
```
✅ WebSocket connected to chat 2
```

❌ **Ошибка подключения:**
```
❌ WebSocket error: {}
⚠️  WebSocket не может подключиться. Убедитесь что backend запущен через Daphne
```

## Важно!

- ❌ `python manage.py runserver` - **НЕ работает** с WebSocket
- ✅ `daphne eusrr_backend.asgi:application` - **РАБОТАЕТ** с WebSocket
- ✅ `uvicorn eusrr_backend.asgi:application` - **РАБОТАЕТ** с WebSocket
