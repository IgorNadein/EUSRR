# Использование LDAP ORM Mixins

**Файл:** `backend/employees/ldap/mixins.py`  
**Дата:** 19 марта 2026 г.

## ModifyDnMixin — перемещение объектов между OU

### Назначение

Добавляет поддержку перемещения LDAP объектов через изменение `base_dn` + `.save()`.

**Проблема:** django-ldapdb не передаёт `newsuperior` в `rename_s()`, поэтому объекты нельзя перемещать между OU.

**Решение:** Миксин отслеживает изменения `base_dn` и автоматически вызывает `conn.modify_dn(newsuperior=...)`.

### Использование

```python
from employees.ldap.orm_models import LdapUser

# 1. Загружаем пользователя
user = LdapUser.objects.get(cn="Ivanov")
print(user.dn)  # CN=Ivanov,OU=IT,OU=Departments,...

# 2. Меняем base_dn (увольнение)
user.base_dn = "OU=Dismissed,OU=company,DC=robotail,DC=local"

# 3. Сохраняем — миксин автоматически вызовет modify_dn
user.save()

# 4. Проверяем
print(user.dn)  # CN=Ivanov,OU=Dismissed,OU=company,...
```

### Как работает

1. При загрузке объекта из LDAP (`from_db()`) сохраняется `_original_base_dn`
2. При вызове `save()` миксин сравнивает текущий `base_dn` с `_original_base_dn`
3. Если изменился — вызывается `conn.modify_dn(old_dn, new_rdn, newsuperior=new_base_dn)`
4. После успешного перемещения обновляется `self.dn` и `self._saved_dn`
5. Затем вызывается стандартный `super().save()` для обновления атрибутов

### Логирование

```python
import logging
logging.basicConfig(level=logging.INFO)

user.base_dn = "OU=Dismissed,..."
user.save()

# [INFO] ModifyDnMixin: Moving LDAP object
#   Old DN: cn=User,OU=IT,...
#   New RDN: cn=User
#   New superior: OU=Dismissed,...
#   New DN: cn=User,OU=Dismissed,...
# [INFO] ModifyDnMixin: Successfully moved ...
```

### Модели с ModifyDnMixin

- `LdapUser` — перемещение пользователей (отделы, увольнение)
- `LdapGroup` — перемещение групп
- `LdapOrganizationalUnit` — перемещение OU (редко)

---

## LdapSyncStateMixin — автоматическое управление LdapSyncState

### Назначение

Автоматически обновляет `LdapSyncState` при операциях с LDAP объектами.

**Проблема:** При изменении DN в LDAP нужно вручную обновлять `LdapSyncState.dn`.

**Решение:** Миксин автоматически обновляет/создаёт/удаляет записи `LdapSyncState`.

### Настройка модели

```python
class LdapUser(ModifyDnMixin, LdapSyncStateMixin, LdapModel):
    # Указываем связь с Django моделью
    _sync_model_name = 'employee'  # Для LdapSyncState.model
    _sync_pk_field = 'employee_number'  # Поле LDAP с Django PK
    
    employee_number = CharField(db_column='employeeNumber')
    # ... остальные поля
```

### Автоматические операции

#### 1. CREATE — создаёт LdapSyncState

```python
user = LdapUser.objects.create(
    dn="CN=Ivanov,OU=Users,...",
    employee_number="123",  # Django Employee.pk
    # ... остальные атрибуты
)

# ✅ Автоматически создан LdapSyncState:
# - model='employee'
# - object_id='123'
# - dn='CN=Ivanov,OU=Users,...'
# - last_ldap_modify_ts=now()
```

#### 2. UPDATE (обычный) — обновляет timestamp

```python
user = LdapUser.objects.get(dn=...)
user.display_name = "New Name"
user.save()

# ✅ Обновлён LdapSyncState:
# - last_ldap_modify_ts=now()
```

#### 3. UPDATE (с перемещением) — обновляет DN

```python
user = LdapUser.objects.get(dn=old_dn)
user.base_dn = "OU=Dismissed,..."
user.save()

# ✅ Обновлён LdapSyncState:
# - dn='cn=User,OU=Dismissed,...'  # Новый DN!
# - last_ldap_modify_ts=now()
```

#### 4. DELETE — удаляет LdapSyncState

```python
user.delete()

# ✅ Удалён соответствующий LdapSyncState
```

### Если модель не настроена

Миксин просто не выполняет операции:

```python
class LdapGroup(ModifyDnMixin, LdapSyncStateMixin, LdapModel):
    # Нет _sync_model_name / _sync_pk_field
    pass

group = LdapGroup.objects.create(...)
# [WARNING] LdapSyncStateMixin: No _sync_model_name set, skipping sync state
```

---

## Вместе: полная интеграция

### Пример: увольнение пользователя

```python
from employees.models import Employee
from employees.ldap.orm_models import LdapUser

def dismiss_employee(employee_id: int):
    """Увольняет сотрудника."""
    # 1. Django модель
    employee = Employee.objects.get(pk=employee_id)
    employee.status = 'dismissed'
    employee.save()
    
    # 2. LDAP модель (автоматические обновления!)
    ldap_user = LdapUser.objects.get(employee_number=str(employee_id))
    ldap_user.base_dn = "OU=Dismissed,OU=company,DC=robotail,DC=local"
    ldap_user.save()
    
    # ✅ Произошло автоматически:
    # - ModifyDnMixin: переместил в LDAP (modify_dn)
    # - LdapSyncStateMixin: обновил LdapSyncState.dn
    # - Логирование всех операций
```

### Пример: перевод в другой отдел

```python
def transfer_to_department(employee_id: int, new_dept_name: str):
    """Переводит сотрудника в другой отдел."""
    employee = Employee.objects.get(pk=employee_id)
    new_dept = Department.objects.get(name=new_dept_name)
    
    employee.department = new_dept
    employee.save()
    
    # LDAP перемещение
    ldap_user = LdapUser.objects.get(employee_number=str(employee_id))
    ldap_user.base_dn = f"OU={new_dept_name},OU=Departments,OU=company,DC=robotail,DC=local"
    ldap_user.save()
    
    # ✅ Всё обновлено автоматически!
```

---

## Ограничения и особенности

### ModifyDnMixin

1. **Требует build_rdn()** — модель должна реализовать метод `build_rdn()`
2. **Работает только при изменении base_dn** — изменение RDN компонента не поддерживается автоматически
3. **Требует низкоуровневое соединение** — использует `ldap3.Connection.modify_dn()`

### LdapSyncStateMixin

1. **Опционально** — работает только если установлены `_sync_model_name` и `_sync_pk_field`
2. **Требует импорт Employee** — использует `from employees.models import LdapSyncState`
3. **Warning при отсутствии PK** — если `employee_number` пуст, логирует WARNING и пропускает

---

## Интеграция с существующим кодом

### Постепенный рефакторинг

#### Было (LEGACY):

```python
# services/user_service.py
from employees.ldap.utils.dn_utils import _move_to_department

def update_user(self, employee, dto):
    # ... обновление атрибутов через ldap3
    
    # Перемещение в другой отдел
    _move_to_department(old_dn, new_dept_dn)
    
    # Обновление LdapSyncState вручную
    sync_state.dn = new_dn
    sync_state.save()
```

#### Стало (ORM + Mixins):

```python
def update_user(self, employee, dto):
    ldap_user = LdapUser.objects.get(employee_number=str(employee.pk))
    
    # Обновление атрибутов
    ldap_user.given_name = dto.first_name
    ldap_user.sn = dto.last_name
    # ... остальные поля
    
    # Перемещение в другой отдел (если изменился)
    if employee.department:
        new_base_dn = f"OU={employee.department.name},OU=Departments,..."
        ldap_user.base_dn = new_base_dn
    
    ldap_user.save()
    
    # ✅ Всё! Миксины сделают остальное
```

### Преимущества

- **-50% кода** — нет ручного вызова modify_dn, обновления LdapSyncState
- **Автоматические обновления** — меньше ошибок
- **Логирование** — встроенное отслеживание операций
- **Единообразие** — весь LDAP через ORM

---

## Тестирование

См. примеры в:
- `docs/completed/ldap-orm-create-support.md` — тесты CREATE и MOVE
- `backend/employees/ldap/mixins.py` — docstrings с примерами

```python
# Запуск тестов
.venv/bin/python manage.py shell -c "..."
```

---

## Дополнительные ресурсы

- [django-ldapdb документация](https://github.com/django-ldapdb/django-ldapdb)
- [RFC 4511 — LDAP Protocol](https://www.rfc-editor.org/rfc/rfc4511.html)
- [Active Directory DN структура](https://docs.microsoft.com/en-us/windows/win32/ad/naming-properties)
