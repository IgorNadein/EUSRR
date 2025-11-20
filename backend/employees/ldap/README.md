# Модуль LDAP Синхронизации

## Описание

Модуль для синхронизации данных между Active Directory (LDAP) и Django-приложением. Поддерживает двустороннюю синхронизацию пользователей, отделов и групп безопасности.

## Архитектура

Модуль организован по принципу чистой архитектуры с явным разделением ответственности:

```
ldap/
├── domain/              # Бизнес-логика и DTO
│   ├── dto.py           # Data Transfer Objects
│   └── validators.py    # Валидация данных
│
├── infrastructure/      # Внешние зависимости
│   ├── connections.py   # Управление LDAP-соединениями
│   └── ldap_client.py   # Обёртка над ldap3
│
├── repositories/        # Слой доступа к данным
│   ├── ldap_repository.py       # CRUD операции в LDAP
│   ├── db_repository.py         # CRUD операции в Django ORM
│   └── sync_state_repository.py # Управление состоянием синхронизации
│
├── services/            # Бизнес-сервисы
│   ├── directory_service.py     # Фасад для CRUD операций
│   ├── user_service.py          # Управление пользователями
│   ├── department_service.py    # Управление отделами
│   ├── group_service.py         # Управление группами
│   └── sync/
│       ├── user_sync_service.py       # Синхронизация пользователей
│       ├── department_sync_service.py # Синхронизация отделов
│       └── sync_orchestrator.py       # Координация синхронизации
│
└── utils/               # Утилиты
    ├── dn_utils.py      # Работа с Distinguished Names
    ├── ldap_utils.py    # LDAP-специфичные утилиты
    ├── text_utils.py    # Обработка текста (escape, normalize)
    └── image_utils.py   # Обработка изображений (аватары)
```

## Основные компоненты

### 1. DirectoryService

Главный фасад для операций с LDAP. Предоставляет унифицированный API для создания, обновления и удаления объектов.

```python
from employees.ldap import DirectoryService, DirectoryUserDTO

service = DirectoryService()

# Создание пользователя
dto = DirectoryUserDTO(
    first_name="Иван",
    last_name="Иванов",
    email="ivanov@example.com",
    phone_e164="+79991234567",
    department_dn="OU=IT,OU=Departments,DC=example,DC=com",
    group_cns=["Domain Users", "IT Support"],
    initial_password="SecurePass123!",
    is_active=True
)
employee = service.create_user(dto)

# Обновление пользователя
service.update_user(
    employee,
    phone_e164="+79999999999",
    department_dn="OU=HR,OU=Departments,DC=example,DC=com"
)

# Удаление пользователя
service.delete_user(employee)
```

### 2. Синхронизация

Двусторонняя синхронизация с поддержкой различных режимов и областей.

```python
from employees.ldap import SyncConfig, import_users, export_users

# Импорт из LDAP в Django
config = SyncConfig(
    mode='ldap',           # Направление: 'ldap' → Django
    scope='users',         # Область: 'users', 'departments', 'groups', 'all'
    dry_run=False,         # False = применить изменения
    show_changes=True      # Показывать детали изменений
)
created, updated, deleted = import_users(cfg=config)
print(f"Создано: {created}, Обновлено: {updated}, Удалено: {deleted}")

# Экспорт из Django в LDAP
config = SyncConfig(
    mode='django',         # Направление: Django → 'ldap'
    scope='users',
    dry_run=False
)
created, updated, deleted, groups_sync, avatars = export_users(cfg=config)
```

### 3. Конфигурация

```python
from employees.ldap import SyncConfig

config = SyncConfig(
    mode='ldap',              # 'ldap' | 'django' | 'auto'
    scope='all',              # 'all' | 'users' | 'departments' | 'groups'
    dry_run=True,             # Сухой прогон без изменений
    max_changes=1000,         # Лимит изменений за сессию
    users_base_dn="OU=Users,DC=example,DC=com",
    departments_base_dn="OU=Departments,DC=example,DC=com",
    groups_base_dn="OU=Groups,DC=example,DC=com",
    show_changes=True         # Детальный вывод
)
```

## Настройки Django

Добавьте в `settings.py`:

```python
# LDAP Configuration
LDAP_URI = "ldaps://dc.example.com:636"
LDAP_BASE_DN = "DC=example,DC=com"
LDAP_BIND_DN = "CN=service_account,CN=Users,DC=example,DC=com"
LDAP_BIND_PASSWORD = "secure_password"

# Базовые DN для различных типов объектов
LDAP_USERS_BASE = "OU=Users,DC=example,DC=com"
LDAP_DEPARTMENTS_BASE = "OU=Departments,DC=example,DC=com"
LDAP_GROUPS_BASE = "OU=Groups,DC=example,DC=com"

# CA-сертификат (опционально, для LDAPS)
LDAP_CA_CERTS = "/path/to/ca-cert.pem"

# Домен по умолчанию для генерации email
DEFAULT_EMAIL_DOMAIN = "example.com"
```

## Модель данных

### LdapSyncState

Отслеживает состояние синхронизации объектов:

```python
class LdapSyncState(models.Model):
    model = models.CharField(max_length=50)  # 'employee', 'department'
    object_pk = models.CharField(max_length=50)
    ldap_dn = models.TextField()
    ldap_guid = models.CharField(max_length=100)
    sync_dir = models.CharField(max_length=10)  # 'ldap', 'django'
    synced_at = models.DateTimeField(auto_now=True)
```

## Обработка ошибок

```python
from employees.ldap import (
    DirectoryServiceError,   # Базовая ошибка
    DirectoryLdapError,      # Ошибка LDAP
    DirectoryDbError,        # Ошибка БД
    DirectoryGroupError      # Ошибка работы с группами
)

try:
    service.create_user(dto)
except DirectoryLdapError as e:
    # Обработка ошибок LDAP (недоступен сервер, неверные учётные данные)
    logger.error(f"LDAP error: {e}")
except DirectoryDbError as e:
    # Обработка ошибок БД (нарушение ограничений, блокировки)
    logger.error(f"Database error: {e}")
except DirectoryServiceError as e:
    # Общие ошибки сервиса
    logger.error(f"Service error: {e}")
```

## Примеры использования

### Создание отдела

```python
from employees.ldap import DirectoryService, DirectoryDepartmentDTO

service = DirectoryService()
dto = DirectoryDepartmentDTO(
    name="IT Department",
    description="Information Technology",
    head=None  # можно указать Employee
)
department = service.create_department(dto)
```

### Синхронизация групп пользователя

```python
from employees.ldap.groups import sync_user_groups_by_cns
from employees.ldap.connections import _ldap

with _ldap() as conn:
    added, removed = sync_user_groups_by_cns(
        conn=conn,
        user_dn="CN=John Doe,OU=Users,DC=example,DC=com",
        target_cns=["Domain Users", "IT Support", "Developers"],
        do_write=True
    )
    print(f"Добавлено в группы: {added}, Удалено из групп: {removed}")
```

### Импорт отделов

```python
from employees.ldap import SyncConfig
from employees.ldap.sync_service import import_departments

config = SyncConfig(mode='ldap', scope='departments', dry_run=False)
created, updated, deleted = import_departments(cfg=config)
```


## Тестирование

```bash
# Запуск всех тестов модуля
pytest backend/employees/ldap/tests/

# Запуск конкретного теста
pytest backend/employees/ldap/tests/test_sync_service.py

# С покрытием
pytest --cov=employees.ldap backend/employees/ldap/tests/
```

## Лицензия

Внутренний корпоративный модуль EUSRR.
