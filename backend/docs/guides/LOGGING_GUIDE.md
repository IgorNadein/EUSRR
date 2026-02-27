# Руководство по системе логирования EUSRR

## Обзор

Проект использует модернизированную систему логирования Django с расширенными возможностями:
- Множественные обработчики (console + файлы)
- Ротация логов по размеру
- Разделение по уровням и категориям
- Структурированное форматирование
- Автоматическая адаптация к DEBUG режиму

## Структура логов

```
backend/logs/
├── all.log          # Все логи уровня INFO и выше
├── error.log        # Только ошибки (ERROR+)
├── debug.log        # Детальные логи (только в DEBUG режиме)
├── security.log     # События безопасности (авторизация, LDAP)
└── requests.log     # HTTP запросы Django
```

## Параметры ротации

| Файл | Макс. размер | Бэкапов | Итого |
|------|--------------|---------|-------|
| all.log | 10 MB | 5 | ~50 MB |
| error.log | 10 MB | 10 | ~100 MB |
| debug.log | 20 MB | 3 | ~60 MB |
| security.log | 10 MB | 20 | ~200 MB |
| requests.log | 20 MB | 5 | ~100 MB |

## Форматы логов

### Verbose (DEBUG режим)
```
[DEBUG   ] 2026-02-17 15:30:45 | employees.ldap             | sync_employee       : 142 | Синхронизация Employee ID=1
```

### Simple (Production консоль)
```
[INFO    ] 2026-02-17 15:30:45 | employees.ldap | Синхронизация Employee ID=1
```

### JSON-style (для парсинга)
```
2026-02-17 15:30:45 | INFO | employees.ldap | sync_employee:142 | Синхронизация Employee ID=1
```

## Использование в коде

### Базовое логирование

```python
import logging

logger = logging.getLogger(__name__)

# Различные уровни
logger.debug("Детальная отладочная информация")
logger.info("Информационное сообщение")
logger.warning("Предупреждение")
logger.error("Ошибка", exc_info=True)  # с traceback
logger.critical("Критическая ошибка")
```

### Контекстная информация

```python
# С дополнительными данными
logger.info(
    "Пользователь %s создал документ %s",
    user.email,
    document.id,
    extra={
        'user_id': user.id,
        'document_id': document.id,
        'action': 'create'
    }
)
```

### Исключения

```python
try:
    employee.sync_to_ldap()
except Exception as e:
    logger.exception("Ошибка синхронизации с LDAP для Employee ID=%s", employee.id)
    # exception() автоматически добавляет traceback
```

### LDAP операции (security.log)

```python
ldap_logger = logging.getLogger('employees.ldap')

ldap_logger.info(
    "LDAP аутентификация успешна: %s",
    username,
    extra={'username': username, 'ip': request.META.get('REMOTE_ADDR')}
)

ldap_logger.warning(
    "LDAP аутентификация провалилась: %s",
    username,
    extra={'username': username, 'reason': 'invalid_credentials'}
)
```

## Логгеры приложений

| Логгер | Файлы | Уровень DEBUG | Уровень Production |
|--------|-------|---------------|---------------------|
| `employees` | all, debug, error | DEBUG | INFO |
| `employees.ldap` | all, security, error | INFO | INFO |
| `documents` | all, debug, error | DEBUG | INFO |
| `communications` | all, debug, error | DEBUG | INFO |
| `notifications` | all, error | INFO | INFO |
| `bots` | all, debug, error | DEBUG | INFO |
| `django.request` | requests, error, mail | WARNING | WARNING |
| `django.db.backends` | console, debug | DEBUG | - |
| `django.security` | security, mail | WARNING | WARNING |

## SQL запросы (только DEBUG)

В режиме `DEBUG=True` все SQL запросы логируются в консоль и `debug.log`:

```python
# settings.py
if DEBUG:
    LOGGING['loggers']['django.db.backends']['level'] = 'DEBUG'
```

Пример вывода:
```
[DEBUG   ] 2026-02-17 15:30:45 | django.db.backends.utils | execute             :  89 | (0.001) SELECT "employees_employee"."id", ... FROM "employees_employee"
```

## Фильтры

### require_debug_true
Обработчик работает только если `DEBUG=True`:
```python
'file_debug': {
    'filters': ['require_debug_true'],
    # ... работает только в DEBUG режиме
}
```

### require_debug_false
Обработчик работает только если `DEBUG=False`:
```python
'mail_admins': {
    'filters': ['require_debug_false'],
    # ... отправляет email только в production
}
```

## Мониторинг логов

### Просмотр в реальном времени

```bash
# Все логи
tail -f backend/logs/all.log

# Только ошибки
tail -f backend/logs/error.log

# События безопасности
tail -f backend/logs/security.log

# Запросы
tail -f backend/logs/requests.log
```

### Поиск по логам

```bash
# Найти все ошибки за сегодня
grep "2026-02-17" backend/logs/error.log

# LDAP события
grep "LDAP" backend/logs/security.log

# Конкретный пользователь
grep "user_id=123" backend/logs/all.log

# SQL запросы с таблицей employees
grep "employees_employee" backend/logs/debug.log
```

### Анализ с помощью Python

```python
import re
from collections import Counter

# Подсчет ошибок по типу
pattern = r'\| (\w+Error)'
with open('backend/logs/error.log', 'r') as f:
    errors = re.findall(pattern, f.read())
    print(Counter(errors).most_common(10))
```

## Production рекомендации

### 1. Ротация по времени (опционально)

Заменить `RotatingFileHandler` на `TimedRotatingFileHandler`:

```python
'file_all': {
    'class': 'logging.handlers.TimedRotatingFileHandler',
    'filename': LOGS_DIR / 'all.log',
    'when': 'midnight',  # ротация каждую полночь
    'interval': 1,
    'backupCount': 30,  # хранить 30 дней
}
```

### 2. Централизованное логирование

Добавить отправку в Sentry, ELK, Graylog:

```python
# pip install sentry-sdk
import sentry_sdk

sentry_sdk.init(
    dsn="https://...",
    environment="production",
)
```

### 3. Очистка старых логов

Добавить в crontab:

```bash
# Удаление логов старше 30 дней
0 2 * * * find /app/backend/logs -name "*.log.*" -mtime +30 -delete
```

### 4. Мониторинг размера

```bash
# Проверка размера директории логов
du -sh backend/logs/

# Топ-5 самых больших файлов
du -ah backend/logs/ | sort -rh | head -5
```

## Настройка email уведомлений

При ошибках в production админы получают email:

```python
# settings.py
ADMINS = [
    ('Admin Name', 'admin@example.com'),
]

# Логгер отправит email при ERROR+
'mail_admins': {
    'level': 'ERROR',
    'class': 'django.utils.log.AdminEmailHandler',
    'filters': ['require_debug_false'],
}
```

## Troubleshooting

### Логи не создаются

1. Проверьте права доступа:
```bash
ls -la backend/logs/
chmod 755 backend/logs/
```

2. Проверьте путь в settings.py:
```python
print(LOGS_DIR)  # должен существовать
```

### Логи слишком большие

1. Уменьшите `maxBytes` в handlers
2. Уменьшите `backupCount`
3. Повысьте уровень логирования (`INFO` → `WARNING`)

### SQL запросы не логируются

Убедитесь что `DEBUG=True`:
```bash
echo $DEBUG  # должно быть True
```

### Дублирование логов

Установите `propagate=False` для логгера:
```python
'employees': {
    'propagate': False,  # не передавать в root logger
}
```

## Best Practices

1. **Используйте правильные уровни:**
   - `DEBUG` - детали для отладки (переменные, состояния)
   - `INFO` - важные события (создание объектов, успешные операции)
   - `WARNING` - неожиданные ситуации (deprecated, retry)
   - `ERROR` - ошибки с обработкой
   - `CRITICAL` - критические ошибки (нет подключения к БД)

2. **Структурируйте сообщения:**
   ```python
   # Плохо
   logger.info("user logged in")
   
   # Хорошо
   logger.info("User %s logged in from %s", user.email, ip_address)
   ```

3. **Не логируйте чувствительные данные:**
   ```python
   # НИКОГДА
   logger.info("Password: %s", password)
   
   # Правильно
   logger.info("Authentication attempt for user %s", username)
   ```

4. **Используйте exc_info для трассировки:**
   ```python
   try:
       operation()
   except Exception:
       logger.error("Operation failed", exc_info=True)
   ```

5. **Логируйте контекст:**
   ```python
   logger.info(
       "Document processed",
       extra={
           'document_id': doc.id,
           'user_id': user.id,
           'processing_time': elapsed,
       }
   )
   ```

## Интеграция с Docker

Логи автоматически доступны через volumes в docker-compose:

```yaml
volumes:
  - ./backend:/app
  # логи в ./backend/logs/ доступны на хосте
```

Просмотр логов контейнера:
```bash
# Console output
docker-compose logs -f web

# Файловые логи
docker-compose exec web tail -f /app/logs/error.log
```
