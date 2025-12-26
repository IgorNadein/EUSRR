# Ограничение доступа к регистрации по IP

## Описание

Реализована система ограничения доступа к регистрации новых пользователей по IP-адресу через middleware. Это позволяет разрешить регистрацию только из локальной сети или конкретных IP-адресов.

## Файлы

### 1. `backend/common/ip_restrictions.py`

Утилиты для проверки IP-адресов:

- **`get_client_ip(request)`** - получает реальный IP клиента (учитывает прокси)
- **`is_local_ip(ip_address)`** - проверяет, является ли IP локальным
- **`is_ip_allowed(ip_address, allowed_networks)`** - проверяет доступ для IP

### 2. `backend/eusrr_backend/middleware.py`

Добавлен класс `RegistrationIPRestrictionMiddleware` для проверки IP при регистрации.

### 3. Настройка в `backend/eusrr_backend/settings.py`

В `MIDDLEWARE` добавлена строка:
```python
"eusrr_backend.middleware.RegistrationIPRestrictionMiddleware",
```

Добавлена настройка `REGISTRATION_ALLOWED_IPS`:
```python
REGISTRATION_ALLOWED_IPS = None  # По умолчанию только локальные IP
```

## Конфигурация

### По умолчанию (только локальные IP)

```python
REGISTRATION_ALLOWED_IPS = None
```

Разрешены только:
- `127.0.0.0/8` (localhost)
- `10.0.0.0/8` (частная сеть класса A)
- `172.16.0.0/12` (частная сеть класса B)
- `192.168.0.0/16` (частная сеть класса C)
- `::1` (IPv6 localhost)
- `fe80::/10` (IPv6 link-local)

### Разрешить все IP

```python
REGISTRATION_ALLOWED_IPS = ['*']
```

### Разрешить конкретные сети (CIDR)

```python
REGISTRATION_ALLOWED_IPS = [
    '192.168.1.0/24',    # Локальная сеть офиса
    '10.0.0.0/8',        # Корпоративная сеть
    '172.16.100.0/24',   # VPN сеть
]
```

### Разрешить конкретные IP-адреса

```python
REGISTRATION_ALLOWED_IPS = [
    '192.168.1.100',
    '192.168.1.101',
    '203.0.113.42',
]
```

### Комбинированный подход

```python
REGISTRATION_ALLOWED_IPS = [
    '192.168.1.0/24',    # Вся локальная сеть
    '203.0.113.42',      # Конкретный внешний IP
    '198.51.100.0/28',   # Диапазон внешних IP
]
```

## Поведение при блокировке

### Для обычных view (HTML)

При попытке доступа с неразрешенного IP пользователь увидит:

```html
<h1>403 Forbidden</h1>
<p>Регистрация доступна только из локальной сети.</p>
<p>Ваш IP: 203.0.113.50</p>
```

### Для API endpoints (JSON)

При попытке доступа с неразрешенного IP API вернет:

```json
{
  "detail": "Регистрация доступна только из локальной сети.",
  "client_ip": "203.0.113.50"
}
```

HTTP статус: `403 Forbidden`

## Работа с прокси

Функция `get_client_ip()` корректно определяет реальный IP клиента даже при использовании прокси-серверов:

1. Проверяет заголовок `X-Forwarded-For`
2. Берет первый IP из списка (клиентский IP)
3. Если заголовка нет, использует `REMOTE_ADDR`

### Настройка для работы за Nginx

Добавьте в конфигурацию Nginx:

```nginx
location / {
    proxy_pass http://127.0.0.1:9000;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header Host $host;
}
```

## Тестирование

### Проверка локального доступа

```bash
curl http://localhost:9000/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"test123",...}'
```

Должно работать с `127.0.0.1`.

### Проверка блокировки (эмуляция внешнего IP)

```bash
curl http://localhost:9000/api/v1/auth/register/ \
  -H "Content-Type: application/json" \
  -H "X-Forwarded-For: 203.0.113.50" \
  -d '{"email":"test@example.com","password":"test123",...}'
```

Должно вернуть `403 Forbidden` если `REGISTRATION_ALLOWED_IPS` не содержит этот IP.

### Тестирование в коде

```python
from common.ip_restrictions import is_local_ip, is_ip_allowed

# Проверка локальных IP
assert is_local_ip('127.0.0.1') == True
assert is_local_ip('192.168.1.100') == True
assert is_local_ip('10.0.0.5') == True
assert is_local_ip('203.0.113.50') == False

# Проверка с настройками
from django.conf import settings
settings.REGISTRATION_ALLOWED_IPS = ['192.168.1.0/24']

assert is_ip_allowed('192.168.1.50') == True
assert is_ip_allowed('192.168.2.50') == False
```

## Безопасность

### Рекомендации

1. **Для production**: используйте конкретные сети, не `['*']`
2. **За прокси**: убедитесь, что прокси правильно передает заголовки
3. **IPv6**: модуль поддерживает IPv6, учтите это в конфигурации
4. **Логирование**: при необходимости добавьте логирование заблокированных попыток

### Обход защиты

Потенциальные проблемы:

1. **Подмена заголовков**: если прокси настроен неправильно, злоумышленник может подменить `X-Forwarded-For`
2. **VPN/Proxy клиента**: пользователь может использовать VPN с локальным IP

### Дополнительная защита

Рекомендуется комбинировать с:
- Rate limiting (throttling в DRF)
- CAPTCHA для регистрации
- Email верификация (уже реализована)
- Логирование попыток регистрации

## Примеры использования в других view

Если нужно ограничить доступ к другим URL по IP, можно создать дополнительные middleware или расширить существующий:

```python
class CustomIPRestrictionMiddleware:
    """Ограничение по IP для произвольных URL"""
    
    RESTRICTED_PATHS = (
        "/admin/",           # Например, админка только из локальной сети
        "/api/v1/sensitive/", # Чувствительные API
    )
    
    def __call__(self, request):
        from common.ip_restrictions import get_client_ip, is_ip_allowed
        
        path = request.path_info
        
        if any(path.startswith(p) for p in self.RESTRICTED_PATHS):
            client_ip = get_client_ip(request)
            if not is_ip_allowed(client_ip):
                # Блокируем доступ
                ...
        
        return self.get_response(request)
```

## Отключение ограничений

### Временное отключение (для разработки)

В `settings.py`:

```python
REGISTRATION_ALLOWED_IPS = ['*']  # Разрешить все IP
```

### Полное отключение

В `settings.py` закомментируйте middleware:

```python
MIDDLEWARE = [
    # ... другие middleware ...
    # "eusrr_backend.middleware.RegistrationIPRestrictionMiddleware",  # Отключено
    "eusrr_backend.middleware.CacheControlMiddleware",
]
```

## Мониторинг

### Добавление логирования

Можно расширить `backend/eusrr_backend/middleware.py`:

```python
def __call__(self, request):
    import logging
    logger = logging.getLogger(__name__)
    
    path = request.path_info
    
    if not any(path.startswith(p) for p in self.RESTRICTED_PATHS):
        return self.get_response(request)
    
    client_ip = get_client_ip(request)
    
    if not is_ip_allowed(client_ip):
        logger.warning(
            f'Registration blocked for IP {client_ip} '
            f'(path: {path}, user-agent: {request.META.get("HTTP_USER_AGENT")})'
        )
        # ... блокировка ...
    
    logger.info(f'Registration allowed for IP {client_ip}')
    return self.get_response(request)
```

### Метрики

Можно отслеживать:
- Количество заблокированных попыток регистрации
- IP-адреса, которые часто блокируются
- Географию заблокированных запросов

## Вопросы и поддержка

При возникновении проблем проверьте:

1. Правильность настройки `REGISTRATION_ALLOWED_IPS` в settings.py
2. Корректность заголовков прокси (если используется)
3. Middleware включен в `MIDDLEWARE` в settings.py
4. Формат IP-адресов в конфигурации (должны быть валидными CIDR или IP)
5. Логи Django на наличие ошибок в модуле `eusrr_backend.middleware`
