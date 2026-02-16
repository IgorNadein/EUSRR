# Инструкция по запуску тестов с LDAP

## Подготовка тестового окружения

### 1. Запуск LDAP контейнера

```bash
# Запустить LDAP с профилем
docker-compose --profile ldap up -d ldap

# Проверить что контейнер запущен
docker ps | grep eusrr-ldap

# Просмотр логов
docker-compose logs -f ldap
```

### 2. Настройка переменных окружения для тестов

Скопируйте файл `.env.test` в `.env` или установите переменные:

```bash
cp .env.test .env
```

Ключевые параметры для тестов:
```env
LDAP_ENABLED=true
LDAP_URI=ldap://localhost:389
LDAP_BIND_DN=cn=admin,dc=eusrr,dc=local
LDAP_BIND_PASSWORD=change-me-redacted-secret
LDAP_TLS_REQUIRED=false

# Базовые DN
LDAP_BASE_DN=dc=eusrr,dc=local
LDAP_USERS_BASE=OU=Users,dc=eusrr,dc=local
LDAP_DEPARTMENTS_BASE=OU=Departments,dc=eusrr,dc=local
LDAP_GROUPS_BASE=OU=Groups,dc=eusrr,dc=local
LDAP_POSITIONS_BASE=OU=Positions,dc=eusrr,dc=local
LDAP_DISMISSED_BASE=OU=Dismissed,dc=eusrr,dc=local
```

### 3. Инициализация LDAP структуры

LDAP структура инициализируется автоматически при первом запуске контейнера из файла:
`backend/scripts/ldap/init/01-base-structure.ldif`

Структура включает:
- OU=Users - пользователи
- OU=Departments - отделы
- OU=Groups - группы безопасности
- OU=Positions - должности
- OU=Dismissed - уволенные

### 4. Проверка подключения к LDAP

```bash
# Из контейнера
docker exec -it eusrr-ldap ldapsearch -x -H ldap://localhost -b "dc=eusrr,dc=local" -D "cn=admin,dc=eusrr,dc=local" -w change-me-redacted-secret

# Или через phpLDAPadmin
docker-compose --profile ldap up -d ldap-admin
# Открыть http://localhost:8080
# Login DN: cn=admin,dc=eusrr,dc=local
# Password: change-me-redacted-secret
```

## Запуск тестов

### Все тесты employees API

```bash
cd backend
../.venv/Scripts/python -m pytest tests/api/v1/employees/ -v
```

### Только LDAP тесты

```bash
# Тесты требующие LDAP
../.venv/Scripts/python -m pytest tests/api/v1/employees/ -v -m ldap_required

# Тесты опциональные (работают с LDAP и без)
../.venv/Scripts/python -m pytest tests/api/v1/employees/ -v -m ldap_optional
```

### Тесты без LDAP

```bash
# Отключить LDAP для тестов
LDAP_ENABLED=false ../.venv/Scripts/python -m pytest tests/api/v1/employees/ -v
```

### Параметризованные тесты (с LDAP и без)

Многие тесты теперь параметризованы для проверки обоих режимов:

```python
@pytest.mark.ldap_optional
@pytest.mark.parametrize("ldap_enabled", [True, False])
def test_create_employee(ldap_enabled, settings):
    settings.LDAP_ENABLED = ldap_enabled
    # тест работает в обоих режимах
```

## Отладка

### Просмотр LDAP логов в реальном времени

```bash
docker-compose logs -f ldap
```

### Очистка LDAP данных

```bash
# Остановить и удалить контейнер с данными
docker-compose --profile ldap down -v

# Запустить заново
docker-compose --profile ldap up -d ldap
```

### Проверка LDAP операций из Django shell

```bash
../.venv/Scripts/python manage.py shell
```

```python
from employees.ldap.infrastructure.connections import _ldap
from employees.ldap.directory_service import DirectoryService

# Проверка подключения
with _ldap() as conn:
    print(conn.bind())  # должно быть True

# Проверка создания пользователя
ds = DirectoryService()
# ... тесты операций
```

## Структура тестов

### Новые фикстуры (tests/ldap_fixtures.py):

- `ldap_available` - проверяет доступность LDAP
- `ldap_config` - конфигурация LDAP для тестов
- `ensure_ldap_enabled` - принудительно включает LDAP для теста
- `ensure_ldap_disabled` - принудительно выключает LDAP для теста
- `ldap_cleanup` - автоматическая очистка после теста

### Централизованные helpers (tests/api/v1/employees/test_helpers.py):

- `make_user()` - создание пользователя
- `grant_permission()` - выдача разрешений
- `make_department()` - создание отдела
- `make_position()` - создание должности
- `extract_results()` - извлечение из пагинации

## Маркеры pytest

- `@pytest.mark.ldap_required` - тест требует LDAP (автоматически скипается если недоступен)
- `@pytest.mark.ldap_optional` - тест может работать с LDAP и без

## Примеры тестов

### Тест только с LDAP:

```python
@pytest.mark.ldap_required
def test_ldap_sync(api_client, ldap_cleanup):
    # Тест пропускается если LDAP недоступен
    user = make_user(email="test@example.com")
    ldap_cleanup.add_for_deletion(user.ldap_dn)
    # ...
```

### Параметризованный тест:

```python
@pytest.mark.ldap_optional
@pytest.mark.parametrize("with_ldap", [True, False])
def test_employee_creation(api_client, with_ldap, settings):
    if with_ldap:
        settings.LDAP_ENABLED = True
    else:
        settings.LDAP_ENABLED = False

    # Тест проверяет оба сценария
    # ...
```

## Troubleshooting

### Ошибка: "LDAP server is unavailable"

1. Проверьте что контейнер запущен: `docker ps | grep ldap`
2. Проверьте логи: `docker-compose logs ldap`
3. Проверьте порты: `netstat -an | grep 389`
4. Перезапустите контейнер: `docker-compose restart ldap`

### Ошибка: "LDAP_POSITIONS_BASE is not configured"

Добавьте в `.env`:
```env
LDAP_POSITIONS_BASE=OU=Positions,dc=eusrr,dc=local
```

### Тесты падают с "AttributeError: 'module' object has no attribute '_is_ldap_enabled'"

После рефакторинга views разделены на модули. Обновите патчи:
```python
# Старый путь
@patch('api.v1.employees.views._is_ldap_enabled')

# Новый путь
@patch('api.v1.employees.views._helpers._is_ldap_enabled')
```

## CI/CD Integration

### GitHub Actions пример:

```yaml
services:
  ldap:
    image: osixia/openldap:1.5.0
    env:
      LDAP_DOMAIN: eusrr.local
      LDAP_ADMIN_PASSWORD: change-me-redacted-secret
    ports:
      - 389:389

steps:
  - name: Run tests with LDAP
    env:
      LDAP_ENABLED: true
      LDAP_URI: ldap://localhost:389
    run: pytest tests/api/v1/employees/ -m ldap_required

  - name: Run tests without LDAP
    env:
      LDAP_ENABLED: false
    run: pytest tests/api/v1/employees/ -m "not ldap_required"
```
