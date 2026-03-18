# LDAP ORM Integration

Интеграция django-ldapdb для упрощения работы с Active Directory через Django ORM.

## Концепция

**LDAP модели используются ТОЛЬКО для записи (POST/PUT/DELETE)!**

```
GET запросы    → Employee (PostgreSQL)        - быстро ⚡
POST/PUT/DELETE → LdapUser (django-ldapdb ORM) - просто ✨
```

## Связь моделей

### Архитектура связи

```
┌─────────────────────────┐
│  Employee               │ (PostgreSQL, default database)
│  - pk: 123              │
│  - first_name: "John"   │
│  - last_name: "Doe"     │
│  - email: "jdoe@..."    │
└─────────────────────────┘
           ↓ связь через object_pk
┌─────────────────────────┐
│  LdapSyncState          │ (PostgreSQL, default database)
│  - model: 'employee'    │ ← тип модели
│  - object_pk: '123'     │ ← Employee.pk (строка)
│  - ldap_dn: 'CN=John...'│ ← DN в LDAP
│  - ldap_guid: '{UUID}'  │ ← objectGUID из AD
│  - last_django_modify_ts│ ← метка времени
│  - last_sync_dir        │ ← направление синхронизации
└─────────────────────────┘
           ↓ связь через ldap_dn
┌─────────────────────────┐
│  LdapUser               │ (LDAP server, ldap database)
│  - dn: 'CN=John...'     │ ← Distinguished Name (первичный ключ)
│  - cn: "John Doe"       │
│  - sam_account_name: "jdoe"
│  - employee_number: '123'│ ← Employee.pk (опционально, для быстрого поиска)
│  - given_name: "John"   │
│  - sn: "Doe"            │
│  - mail: "jdoe@..."     │
└─────────────────────────┘
```

### Роли моделей

**Employee** (employees/models.py):
- Основная модель сотрудника в PostgreSQL
- Используется для всех GET запросов (быстро)
- Хранит все данные для отображения в UI

**LdapSyncState** (employees/models.py):
- Промежуточная таблица маппинга
- Связывает Employee.pk ↔ LDAP DN
- Хранит метки времени для синхронизации
- Позволяет отследить изменения

**LdapUser** (employees/ldap/orm_models.py):
- ORM модель для записи в LDAP через django-ldapdb
- Используется ТОЛЬКО для POST/PUT/DELETE операций
- Автоматически записывает изменения в Active Directory

### Методы связи в ORM сервисах

```python
from employees.ldap.orm_services import LdapOrmUserService

svc = LdapOrmUserService()

# 1. Создание: автоматически создает LdapSyncState
user = svc.create_user(
    sam_account_name="jdoe",
    first_name="John",
    last_name="Doe",
    email="jdoe@example.com",
    employee_pk=123,  # ← связь с Employee
)
# Создает LdapSyncState(model='employee', object_pk='123', ldap_dn=user.dn)

# 2. Получение DN по Employee.pk (быстро, без LDAP запроса)
dn = svc.get_user_dn_by_employee_pk(employee_pk=123)
# Читает из LdapSyncState.ldap_dn

# 3. Получение LdapUser по Employee.pk
ldap_user = svc.get_user_by_employee_pk(employee_pk=123)
# Сначала ищет DN через LdapSyncState, затем делает LDAP запрос

# 4. Обновление: автоматически обновляет LdapSyncState
svc.update_user(dn, first_name="Johnny")
# Обновляет LdapSyncState.last_django_modify_ts

# 5. Удаление: автоматически удаляет LdapSyncState (при hard delete)
svc.delete_user(dn, soft=False)
# Удаляет LdapSyncState для этого employee_pk
```

### Почему нет ForeignKey?

**LdapUser** и **Employee** находятся в **разных базах данных**:
- Employee → PostgreSQL (database='default')
- LdapUser → LDAP server (database='ldap')

Django **не поддерживает ForeignKey между разными базами данных**.

Поэтому используется:
- `LdapSyncState.object_pk` (CharField) - хранит str(Employee.pk)
- `LdapUser.employee_number` (CharField) - хранит str(Employee.pk) в LDAP
- Связь **слабая** (через строки), но это **нормально** для multi-database setup

## Компоненты

### 1. LDAP ORM Модели

Файл: `employees/ldap/orm_models.py`

```python
from employees.ldap.orm_models import LdapUser, LdapGroup, LdapOrganizationalUnit

# Создание пользователя через ORM
user = LdapUser()
user.cn = "John Doe"
user.sam_account_name = "jdoe"
user.given_name = "John"
user.sn = "Doe"
user.save()  # → пишет в LDAP!
```

**Модели:**
- `LdapUser` - пользователи AD (objectClass=user)
- `LdapGroup` - группы (objectClass=group)  
- `LdapOrganizationalUnit` - отделы (objectClass=organizationalUnit)

### 2. ORM Сервисы

Файл: `employees/ldap/orm_services.py`

```python
from employees.ldap.orm_services import LdapOrmUserService

svc = LdapOrmUserService()

# Создание
user = svc.create_user(
    sam_account_name="jdoe",
    first_name="John",
    last_name="Doe",
    email="jdoe@example.com",
    employee_pk=123,  # ID из Employee модели
    is_active=True,
)

# Обновление
svc.update_user(
    user_dn="CN=John Doe,OU=Users,DC=example,DC=com",
    first_name="Johnny",
    email="johnny@example.com",
)

# Удаление
svc.delete_user(user_dn, soft=True)  # деактивация
```

**Сервисы:**
- `LdapOrmUserService` - пользователи
- `LdapOrmGroupService` - группы
- `LdapOrmDepartmentService` - отделы

### 3. Database Router

Файл: `eusrr_backend/db_routers.py`

Автоматически направляет:
- LDAP модели → `ldap` database
- Django модели → `default` database (PostgreSQL)

### 4. Settings

```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        # ...
    },
    'ldap': {
        'ENGINE': 'ldapdb.backends.ldap',
        'NAME': 'ldaps://dc.example.com:636',
        'USER': 'CN=admin,DC=example,DC=com',
        'PASSWORD': 'password',
    },
}

DATABASE_ROUTERS = ['eusrr_backend.db_routers.LdapRouter']
```

## Преимущества

✅ **Django ORM вместо ldap3** - чистый код, меньше костылей
✅ **Автоматическая валидация** - через Django fields
✅ **Удобство** - унифицированный CRUD API
✅ **Производительность** - чтение из PostgreSQL (быстро), запись через ORM (удобно)

## Примеры использования

### ViewSet с ORM

```python
from employees.ldap.orm_services import LdapOrmUserService

class EmployeeViewSet(viewsets.ModelViewSet):
    def create(self, request):
        # 1. Создаем в Django
        employee = Employee.objects.create(
            first_name=request.data['first_name'],
            last_name=request.data['last_name'],
            email=request.data['email'],
        )
        
        # 2. Создаем в LDAP через ORM
        svc = LdapOrmUserService()
        ldap_user = svc.create_user(
            sam_account_name=employee.email.split('@')[0],
            first_name=employee.first_name,
            last_name=employee.last_name,
            email=employee.email,
            employee_pk=employee.pk,
        )
        
        return Response(EmployeeSerializer(employee).data)
```

### Работа с группами

```python
from employees.ldap.orm_services import LdapOrmGroupService

svc = LdapOrmGroupService()

# Создание группы
group = svc.create_group(
    cn="Developers",
    description="Development team",
)

# Добавление члена
svc.add_member(
    group_dn=group.dn,
    member_dn="CN=John Doe,OU=Users,DC=example,DC=com",
)
```

## Миграция со старого подхода

### Было (ldap3):

```python
from ldap3 import Connection, MODIFY_REPLACE

with ldap_connection() as conn:
    conn.modify(
        user_dn,
        {"givenName": [(MODIFY_REPLACE, ["John"])]},
    )
```

### Стало (django-ldapdb):

```python
from employees.ldap.orm_services import LdapOrmUserService

svc = LdapOrmUserService()
svc.update_user(user_dn, first_name="John")
```

**Результат:**
- ❌ Было: 15-20 строк низкоуровневого кода
- ✅ Стало: 2 строки чистого ORM

## Установка

```bash
# 1. Системные зависимости (Linux)
sudo apt-get install libldap2-dev libsasl2-dev

# 2. Python пакет
pip install django-ldapdb==1.5.1

# 3. Django check
python manage.py check
```

## Следующие шаги

1. Создать сигналы для автоматической синхронизации Employee ↔ LDAP
2. Интегрировать в существующие ViewSets
3. Постепенно мигрировать старый код с ldap3 на ORM

## Заметки

- LDAP модели не мигрируют (managed=False)
- Для связи используется employeeNumber атрибут (хранит Employee.pk)
- Soft delete по умолчанию (деактивация вместо удаления)
