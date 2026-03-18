# LDAP ORM Integration

Интеграция django-ldapdb для упрощения работы с Active Directory через Django ORM.

## Концепция

**LDAP модели используются ТОЛЬКО для записи (POST/PUT/DELETE)!**

```
GET запросы    → Employee (PostgreSQL)        - быстро ⚡
POST/PUT/DELETE → LdapUser (django-ldapdb ORM) - просто ✨
```

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
