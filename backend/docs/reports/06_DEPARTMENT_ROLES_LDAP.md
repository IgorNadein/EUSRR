# Отчет: LDAP интеграция системы ролей

**Дата**: 30.12.2025  
**Анализ**: DirectoryService, синхронизация ролей с LDAP-группами, OU=Roles

---

## 1. Обзор LDAP-интеграции

### Архитектура LDAP для ролей

```
OU=Departments,DC=example,DC=com
    │
    ├── OU=IT Department
    │   ├── OU=Roles                    ← Контейнер ролей отдела
    │   │   ├── CN=Tech Lead            ← LDAP-группа роли
    │   │   ├── CN=Senior Developer
    │   │   └── CN=Junior Developer
    │   ├── CN=IT Department (group)    ← Общая группа отдела
    │   ├── CN=User1                     ← Сотрудники
    │   └── CN=User2
    │
    └── OU=HR Department
        ├── OU=Roles
        │   └── CN=HR Manager
        └── ...
```

### Ключевые сущности

1. **OU=Departments**: Корневой контейнер для всех отделов
2. **OU=<Department>**: Organizational Unit отдела
3. **OU=Roles**: Подконтейнер внутри отдела для групп ролей
4. **CN=<Role>**: LDAP-группы, соответствующие ролям

---

## 2. DirectoryService — Главный сервис

### Расположение
`backend/employees/ldap/directory_service.py`

### Структура

```python
class DirectoryService:
    def __init__(self):
        from .services.department_service import DepartmentService
        from .services.user_service import UserService
        from .services.group_service import GroupService
        
        self._user_service = UserService()
        self._group_service = GroupService(directory_service=self)
        self._department_service = DepartmentService(
            group_service=self._group_service,
            user_service=self._user_service
        )
```

### Делегирование

`DirectoryService` делегирует работу специализированным сервисам:
- **UserService**: Управление пользователями
- **GroupService**: Управление группами
- **DepartmentService**: Управление отделами и ролями
- **PositionService**: Управление должностями

---

## 3. set_member_role() — Назначение роли

### 3.1 Публичный метод DirectoryService

**Расположение**: `backend/employees/ldap/directory_service.py` (строки 166-170)

```python
def set_member_role(
    self, dept: Department, employee: Employee, role: Optional[DepartmentRole]
) -> None:
    """Меняет роль участника с синхронизацией LDAP-групп Roles."""
    return self._department_service.set_member_role(dept, employee, role)
```

**Делегирование**: Передаёт вызов в `DepartmentService`.

---

### 3.2 Реализация в DepartmentService

**Расположение**: `backend/employees/ldap/services/department_service.py` (строки 531-577)

```python
def set_member_role(
    self, dept: Department, employee: Employee, role
) -> None:
    """Меняет роль участника отдела с синхронизацией LDAP-групп Roles.
    
    Args:
        dept: Отдел.
        employee: Сотрудник.
        role: Новая роль или None.
        
    Raises:
        DirectoryDbError: Ошибка при обновлении БД.
        DirectoryLdapError: Ошибка при синхронизации групп.
    """
    # 1. Обновление БД
    try:
        with transaction.atomic():
            link = EmployeeDepartment.objects.get(
                employee_id=employee.id, department_id=dept.id
            )
            link.role = role
            link.save(update_fields=["role"])
    except EmployeeDepartment.DoesNotExist as e:
        raise DirectoryDbError(
            "Employee is not a member of this department"
        ) from e
    except Exception as e:
        raise DirectoryDbError(str(e)) from e
    
    # 2. Синхронизация LDAP
    try:
        if role:
            user_dn = self._user_service._get_employee_dn(employee)
            dept_dn = self._get_department_dn(dept)
            roles_base = f"OU=Roles,{dept_dn}"
            with _ldap() as conn:
                sync_user_groups_by_cns(
                    conn,
                    user_dn,
                    {role.name},  # Синхронизировать только с группой role.name
                    extra_bases=[roles_base],
                    do_write=True,
                )
    except DirectoryServiceError:
        pass  # Игнорируем ошибки сервиса
    except Exception as e:
        raise DirectoryLdapError(
            f"LDAP role sync failed: {e}"
        ) from e
```

### Порядок операций

```
1. DB Transaction (atomic)
   ↓
   EmployeeDepartment.objects.get(...)
   ↓
   link.role = role
   ↓
   link.save()
   ↓
   Commit
   
2. LDAP Sync (best effort)
   ↓
   Получить user_dn (DN сотрудника)
   ↓
   Получить dept_dn (DN отдела)
   ↓
   roles_base = "OU=Roles,<dept_dn>"
   ↓
   sync_user_groups_by_cns(conn, user_dn, {role.name}, extra_bases=[roles_base])
   ↓
   Если ошибка → логировать, но не падать
```

### Ключевая особенность: Best Effort LDAP

```python
try:
    # ... LDAP синхронизация ...
except DirectoryServiceError:
    pass  # Игнорируем
except Exception as e:
    raise DirectoryLdapError(...)
```

**Значение**:
- БД обновляется всегда (transaction atomic)
- LDAP — best effort (ошибки не прерывают операцию)
- При падении LDAP роль назначена в БД, но не синхронизирована

---

## 4. sync_user_groups_by_cns() — Синхронизация групп

### Назначение
Синхронизирует членство пользователя в LDAP-группах по списку CN (Common Names).

### Логика

```python
def sync_user_groups_by_cns(
    conn: Connection,
    user_dn: str,
    target_cns: Set[str],
    extra_bases: List[str],
    do_write: bool
):
    """
    Приводит членство пользователя в LDAP-группах к целевому набору CN.
    
    Args:
        conn: LDAP соединение
        user_dn: DN пользователя
        target_cns: Набор CN групп, в которых пользователь должен быть
        extra_bases: Дополнительные DN для поиска групп (например, OU=Roles)
        do_write: Выполнять ли реальные изменения
    """
```

### Операции

```
1. Найти все группы в extra_bases (OU=Roles,OU=Dept)
   ↓
2. Текущие группы пользователя: current_cns = {...}
   ↓
3. Вычислить разницу:
   - to_add = target_cns - current_cns  (нужно добавить)
   - to_remove = current_cns - target_cns  (нужно удалить)
   ↓
4. Если do_write:
   - Для каждой группы в to_add:
       conn.modify(group_dn, {'member': [(MODIFY_ADD, [user_dn])]})
   - Для каждой группы в to_remove:
       conn.modify(group_dn, {'member': [(MODIFY_DELETE, [user_dn])]})
```

### Пример

**До синхронизации**:
- Сотрудник в группах: `["Tech Lead", "Senior Developer"]`

**Назначена роль**: `role.name = "Junior Developer"`

**После синхронизации**:
- Удалён из: `["Tech Lead", "Senior Developer"]`
- Добавлен в: `["Junior Developer"]`

---

## 5. Интеграция с API

### 5.1 В Department.set_member_role()

**Расположение**: `backend/api/v1/employees/views.py` (строки 956-1030)

```python
@action(detail=True, methods=["post"])
@transaction.atomic
def set_member_role(self, request, pk=None):
    dept = self.get_object()
    # ... валидация ...
    
    svc = DirectoryService() if _is_ldap_enabled() else None
    
    if svc:
        # Режим с LDAP: синхронизируем роли
        try:
            svc.set_member_role(dept, employee, role)
            link = EmployeeDepartment.objects.get(...)
        except (DirectoryLdapError, DirectoryDbError, DirectoryServiceError) as e:
            return Response({"detail": str(e)}, status=...)
    else:
        # Режим без LDAP: просто обновляем роль в линке
        link = EmployeeDepartment.objects.get(...)
        link.role = role
        link.save(update_fields=["role"])
    
    return Response({...}, status=200)
```

### Две ветки выполнения

**1. LDAP включён (`_is_ldap_enabled() = True`)**:
```
API call → DirectoryService.set_member_role()
    ↓
1. DB: EmployeeDepartment.role = new_role
2. LDAP: sync groups in OU=Roles
    ↓
Response
```

**2. LDAP выключен**:
```
API call → Прямое обновление БД
    ↓
EmployeeDepartment.role = new_role
    ↓
Response
```

---

### 5.2 Проверка _is_ldap_enabled()

**Расположение**: Предположительно в `employees/ldap/__init__.py` или `settings.py`

```python
def _is_ldap_enabled() -> bool:
    return getattr(settings, 'LDAP_ENABLED', False) and \
           getattr(settings, 'LDAP_SERVER_URI', None) is not None
```

**Конфигурация** (`settings.py`):
```python
LDAP_ENABLED = True
LDAP_SERVER_URI = 'ldap://dc.example.com'
LDAP_BIND_DN = 'CN=Admin,DC=example,DC=com'
LDAP_BIND_PASSWORD = '...'
LDAP_DEPARTMENTS_BASE = 'OU=Departments,DC=example,DC=com'
```

---

## 6. Хранение DN в моделях

### 6.1 DepartmentRole.ldap_group_dn

```python
class DepartmentRole(models.Model):
    # ...
    ldap_group_dn = models.CharField(max_length=500, blank=True, default='')
```

**Назначение**: Хранит DN LDAP-группы роли.

**Пример значения**:
```
CN=Tech Lead,OU=Roles,OU=IT Department,OU=Departments,DC=example,DC=com
```

**Использование**:
- Прямой доступ к группе роли в LDAP
- Быстрый поиск без построения DN

---

### 6.2 LdapSyncState

```python
class LdapSyncState(models.Model):
    model = models.CharField(max_length=50, db_index=True)  # 'employee', 'department', ...
    object_pk = models.CharField(max_length=50, db_index=True)
    ldap_dn = models.CharField(max_length=500, blank=True, default='')
    last_sync = models.DateTimeField(auto_now=True)
    sync_status = models.CharField(max_length=20, default='synced')
```

**Назначение**: Mapping между объектами Django и LDAP DN.

**Примеры**:
```python
LdapSyncState(model='employee', object_pk='42', 
              ldap_dn='CN=Ivanov,OU=IT,OU=Departments,...')

LdapSyncState(model='department', object_pk='5',
              ldap_dn='OU=IT Department,OU=Departments,...')
```

**Использование**:
- `_get_employee_dn()` → запрос к LdapSyncState
- `_get_department_dn()` → запрос к LdapSyncState

---

## 7. Создание роли в LDAP

### Порядок операций при создании DepartmentRole

```
1. API: POST /api/v1/department-roles/
   {"department": 5, "name": "Tech Lead"}
   ↓
2. DepartmentRoleSerializer.create()
   ↓
   DepartmentRole.objects.create(...)
   ↓
3. (НЕТ автоматической LDAP-синхронизации)
   ↓
4. LDAP-группа создаётся при первом назначении роли сотруднику
```

**Ключевая особенность**: Группа роли в LDAP создаётся **лениво** (lazy), при первом назначении.

### Альтернативный подход (если реализован)

```python
# При create роли:
if _is_ldap_enabled():
    dept_dn = _get_department_dn(dept)
    roles_ou = f"OU=Roles,{dept_dn}"
    group_dn = f"CN={role.name},{roles_ou}"
    
    # Создать группу
    conn.add(group_dn, object_class=['group'], attributes={
        'sAMAccountName': role.name,
        'description': f'Role group for {dept.name}'
    })
    
    # Сохранить DN
    role.ldap_group_dn = group_dn
    role.save()
```

---

## 8. Удаление роли из LDAP

### Текущая реализация

**Проблема**: При `DepartmentRole.delete()` LDAP-группа **НЕ удаляется**.

**Последствие**:
- Orphaned groups остаются в LDAP
- Необходима ручная очистка

### Рекомендация

```python
# В DepartmentRole.delete():
def delete(self, *args, **kwargs):
    if self.ldap_group_dn and _is_ldap_enabled():
        try:
            with _ldap() as conn:
                conn.delete(self.ldap_group_dn)
        except Exception as e:
            logger.warning(f"Failed to delete LDAP group: {e}")
    
    super().delete(*args, **kwargs)
```

---

## 9. Проблемные места

### 9.1 Двухфазная логика (if _is_ldap_enabled)

**Проблема**: Во всех API endpoints дублируется логика:

```python
if _is_ldap_enabled():
    # Ветка с LDAP
else:
    # Ветка без LDAP
```

**Следствие**:
- Усложнение кода
- Две кодовые ветки для тестирования
- Риск рассинхронизации логики

**Решение**: Паттерн Strategy

```python
class RoleBackend(ABC):
    @abstractmethod
    def set_member_role(self, dept, employee, role): ...

class LdapRoleBackend(RoleBackend):
    def set_member_role(self, dept, employee, role):
        # ... LDAP логика ...

class DbOnlyRoleBackend(RoleBackend):
    def set_member_role(self, dept, employee, role):
        # ... DB-only логика ...

# В settings:
if LDAP_ENABLED:
    ROLE_BACKEND = LdapRoleBackend()
else:
    ROLE_BACKEND = DbOnlyRoleBackend()
```

---

### 9.2 Best Effort LDAP без компенсации

**Проблема**:
```python
try:
    # DB update
    link.role = role
    link.save()
except:
    raise  # Rollback

try:
    # LDAP sync
    sync_user_groups_by_cns(...)
except DirectoryServiceError:
    pass  # Игнорируем!
```

**Последствие**: Несогласованное состояние (роль в БД ≠ группа в LDAP).

**Решение**: Очередь задач для повторных попыток

```python
# После успешного DB update:
if ldap_sync_failed:
    schedule_ldap_sync_task.delay(employee_id, role_id)
```

---

### 9.3 Нет валидации существования OU=Roles

**Проблема**: Код предполагает, что `OU=Roles,<dept_dn>` существует.

**Риск**: При создании нового отдела без создания `OU=Roles` синхронизация падает.

**Решение**: Проверка/создание OU при создании отдела

```python
def create_department(dto):
    # ...
    dept_ou = create_ou(dept.name, DEPARTMENTS_BASE)
    roles_ou = create_ou('Roles', dept_ou)  # ← гарантировать наличие
    # ...
```

---

### 9.4 Отсутствие транзакционности LDAP

**Проблема**: LDAP операции не атомарны.

**Сценарий**:
```python
# Назначение роли:
1. Удалить из группы "Tech Lead" → ✅
2. Добавить в группу "Senior Dev" → ❌ (сбой)

Результат: Сотрудник без ролей в LDAP
```

**Решение**: Two-Phase Commit или Saga pattern

```python
# 1. Prepare phase
old_groups = get_current_groups(user_dn)
new_groups = {role.name}

# 2. Commit phase
try:
    for group in old_groups - new_groups:
        remove_from_group(user_dn, group)
    for group in new_groups - old_groups:
        add_to_group(user_dn, group)
except:
    # Rollback
    for group in old_groups:
        add_to_group(user_dn, group)
    raise
```

---

### 9.5 Производительность синхронизации

**Проблема**: `sync_user_groups_by_cns()` делает:
1. Поиск всех групп в OU=Roles
2. Проверка членства для каждой группы
3. Modify для каждой изменённой группы

**При назначении роли 100 сотрудникам**: 100 × (search + N×modify) запросов.

**Решение**: Batch operations

```python
def sync_multiple_users_roles(users_roles: List[Tuple[Employee, Role]]):
    with _ldap() as conn:
        for user, role in users_roles:
            # ... подготовка операций ...
        
        # Выполнить все за раз
        conn.batch_modify(operations)
```

---

## 10. Итоговая схема LDAP-интеграции

```
┌──────────────────────────────────────────────┐
│ API: POST /departments/{id}/set_member_role/ │
└──────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│ _is_ldap_enabled()?                          │
│   No → DB-only branch                        │
│   Yes → LDAP branch                          │
└──────────────────────────────────────────────┘
                    ↓ Yes
┌──────────────────────────────────────────────┐
│ DirectoryService.set_member_role()           │
└──────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│ DepartmentService.set_member_role()          │
│   1. DB: EmployeeDepartment.role = new_role  │
│   2. LDAP: sync_user_groups_by_cns()         │
└──────────────────────────────────────────────┘
                    ↓
┌──────────────────────────────────────────────┐
│ LDAP Operations:                             │
│   - Get user_dn from LdapSyncState           │
│   - Get dept_dn from LdapSyncState           │
│   - roles_base = "OU=Roles,<dept_dn>"        │
│   - Find all groups in roles_base            │
│   - Remove from old role groups              │
│   - Add to new role group                    │
└──────────────────────────────────────────────┘
```

---

**Следующий отчет**: [07_DEPARTMENT_ROLES_TESTS.md](./07_DEPARTMENT_ROLES_TESTS.md) — Покрытие тестами
