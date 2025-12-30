# Редизайн LDAP-архитектуры для ролей отделов

**Дата**: 30.12.2025  
**Статус**: Проектирование  
**Проблема**: OU=Roles не работает с групповыми политиками

---

## 1. Текущая проблема

### 1.1 Структура сейчас

```
DC=company,DC=local
└── OU=Departments
    └── OU=IT Department          ← Сотрудники здесь (CN=John Doe)
        ├── CN=John Doe           ← Пользователь
        ├── CN=Jane Smith         ← Пользователь
        ├── CN=IT Department      ← Группа отдела (все члены)
        └── OU=Roles              ← Подпапка для ролей
            ├── CN=Tech Lead      ← Группа роли
            └── CN=DevOps         ← Группа роли
```

### 1.2 Почему не работает

**Проблема с Group Policy (GPO):**
- GPO применяются к объектам **по их расположению в дереве LDAP**
- Пользователи `CN=John Doe` находятся в `OU=IT Department`
- Группы ролей находятся в `OU=Roles,OU=IT Department`
- **Вложенный OU не влияет на policy применяемые к родительскому OU**

**Иллюстрация:**
```
GPO → OU=IT Department (включает John Doe, Jane Smith)
      └── OU=Roles (НЕ включает пользователей! Только группы)
          └── CN=Tech Lead (группа, без GPO на неё)
              └── member: CN=John Doe (но John в родительском OU)
```

**Результат**: Членство в группе `CN=Tech Lead,OU=Roles,...` не даёт применения GPO, потому что:
1. GPO применяется к OU, а не к группам напрямую
2. Пользователи лежат выше, в `OU=IT Department`, а не в `OU=Roles`

### 1.3 Дополнительная проблема

**Текущая логика**: Роли можно назначить только членам отдела.

**Новое требование**: Роли должны быть доступны **любому сотруднику компании** (не обязательно члену отдела).

---

## 2. Новая архитектура

### 2.1 Убираем OU=Roles

**Новая структура:**
```
DC=company,DC=local
└── OU=Departments
    └── OU=IT Department
        ├── CN=John Doe           ← Пользователь
        ├── CN=Jane Smith         ← Пользователь
        ├── CN=DEP_IT Department  ← Группа отдела (члены)
        ├── CN=ROLE_TechLead      ← Группа роли (прямо в OU отдела)
        └── CN=ROLE_DevOps        ← Группа роли (прямо в OU отдела)
```

### 2.2 Преимущества

1. **GPO работают**: Группы ролей в том же OU, что и пользователи
2. **Проще структура**: Нет вложенных OU
3. **Унификация**: Отдел и роли управляются одинаково
4. **Гибкость**: Можно добавлять пользователей из других отделов

### 2.3 Именование групп — конвенция проекта

**Существующая конвенция:**
- `DEP_<Name>` — группы отделов (например, `DEP_IT`, `DEP_HR`)
- `POS_<Name>` — группы должностей (например, `POS_Developer`, `POS_Manager`)

**Для ролей:**
- `ROLE_<Name>` — группы ролей (например, `ROLE_TechLead`, `ROLE_DevOps`)

**Примеры:**
```
CN=DEP_IT,OU=IT Department,...           ← группа членов отдела
CN=ROLE_TechLead,OU=IT Department,...    ← группа роли
CN=ROLE_DevOps,OU=IT Department,...      ← группа роли
```

**Почему такой формат?**
- Единообразие с DEP_ и POS_ 
- Легко фильтровать: `(cn=ROLE_*)`
- Роли уникальны в рамках отдела (unique_together)
- Группа лежит в OU отдела → контекст понятен из расположения

---

## 3. Изменения в моделях Django

### 3.1 DepartmentRole

**Текущее поле:**
```python
ldap_group_dn = models.CharField(
    "DN агрегаторной группы роли в AD (ROLE_*)",
    max_length=512,
    blank=True,
    default="",
)
```

**Без изменений** — поле уже существует и подходит.

### 3.2 EmployeeDepartment — ослабление связи

**Текущее ограничение:**
```python
class EmployeeDepartment(models.Model):
    employee = models.ForeignKey("Employee", ...)
    department = models.ForeignKey(Department, ...)
    role = models.ForeignKey(DepartmentRole, null=True, blank=True, ...)
    
    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["department_id", "employee_id"],
                name="uniq_employee_per_department",
            ),
        ]
```

**Проблема**: Роль можно назначить только через `EmployeeDepartment`, т.е. сотрудник должен быть членом отдела.

### 3.3 Новая модель: RoleAssignment

**Предлагаемое решение**: Создать отдельную модель для назначений ролей.

```python
class RoleAssignment(models.Model):
    """Назначение роли сотруднику (не обязательно члену отдела)."""
    
    employee = models.ForeignKey(
        "Employee",
        on_delete=models.CASCADE,
        related_name="role_assignments"
    )
    role = models.ForeignKey(
        DepartmentRole,
        on_delete=models.CASCADE,
        related_name="assignments"
    )
    assigned_by = models.ForeignKey(
        "Employee",
        null=True,
        on_delete=models.SET_NULL,
        related_name="assigned_roles"
    )
    assigned_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        verbose_name = "Назначение роли"
        verbose_name_plural = "Назначения ролей"
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "role"],
                name="uniq_employee_role",
            ),
        ]
        indexes = [
            models.Index(fields=["role", "is_active"]),
            models.Index(fields=["employee", "is_active"]),
        ]
    
    def __str__(self):
        return f"{self.employee} → {self.role}"
```

### 3.4 Миграция данных

```python
# Миграция: employees/migrations/XXXX_create_role_assignment.py

def migrate_role_assignments(apps, schema_editor):
    """Перенос role из EmployeeDepartment в RoleAssignment."""
    EmployeeDepartment = apps.get_model('employees', 'EmployeeDepartment')
    RoleAssignment = apps.get_model('employees', 'RoleAssignment')
    
    for link in EmployeeDepartment.objects.filter(role__isnull=False):
        RoleAssignment.objects.get_or_create(
            employee=link.employee,
            role=link.role,
            defaults={
                'is_active': link.is_active,
            }
        )
```

### 3.5 Обратная совместимость

**Переходный период:**
- Оставить `EmployeeDepartment.role` (deprecated)
- Добавить property для чтения из `RoleAssignment`

```python
class EmployeeDepartment(models.Model):
    # Deprecated: использовать RoleAssignment
    role = models.ForeignKey(
        DepartmentRole,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="members_legacy",
        help_text="DEPRECATED: Использовать RoleAssignment",
    )
```

---

## 4. Изменения LDAP-логики

### 4.1 Удалить создание OU=Roles

**Файл**: `employees/ldap/services/department_service.py`

**Текущий код (строки 651-655):**
```python
def _ensure_department_ou(self, conn: Connection, name: str) -> str:
    # ... создание OU отдела ...
    conn.add(f"OU=Roles,{dn}", ["top", "organizationalUnit"])  # УДАЛИТЬ
    return dn
```

**Новый код:**
```python
def _ensure_department_ou(self, conn: Connection, name: str) -> str:
    """Гарантирует наличие OU отдела (без вложенного OU=Roles)."""
    base = getattr(settings, "LDAP_DEPARTMENTS_BASE", None)
    if not base:
        raise RuntimeError("LDAP_DEPARTMENTS_BASE is not configured")
    dn = f"OU={name},{base}"
    ok = conn.search(dn, "(objectClass=organizationalUnit)", search_scope=BASE)
    if ok and conn.entries:
        return dn
    ok = conn.add(dn, ["top", "organizationalUnit"])
    if not ok:
        raise RuntimeError(f"LDAP add OU failed: {conn.result}")
    # Больше не создаём OU=Roles
    return dn
```

### 4.2 Создание группы роли

**Новый метод:**
```python
def create_role_group(self, role: DepartmentRole) -> str:
    """Создаёт группу для роли в OU отдела.
    
    Args:
        role: Роль отдела.
        
    Returns:
        str: DN созданной группы.
        
    Raises:
        DirectoryLdapError: Ошибка создания группы.
    """
    dept = role.department
    dept_dn = self._get_department_dn(dept)
    
    # Формат: ROLE_<RoleName> (аналогично DEP_, POS_)
    role_name = self._sanitize_name(role.name)
    cn = f"ROLE_{role_name}"
    
    group_dn = f"CN={cn},{dept_dn}"
    
    with _ldap() as conn:
        attrs = {
            "sAMAccountName": cn,
            "description": f"Role: {role.name} in {dept.name}",
            "groupType": group_type("global", security_enabled=True),
        }
        ok = conn.add(group_dn, ["top", "group"], attrs)
        if not ok:
            if "entryAlreadyExists" in str(conn.result):
                return group_dn  # Уже существует
            raise DirectoryLdapError(f"LDAP create role group failed: {conn.result}")
    
    # Сохранить DN в модели
    role.ldap_group_dn = group_dn
    role.save(update_fields=["ldap_group_dn"])
    
    return group_dn

def _sanitize_name(self, name: str) -> str:
    """Очищает имя для использования в CN."""
    import re
    # Убираем спецсимволы, заменяем пробелы на _
    clean = re.sub(r'[^\w\s-]', '', name)
    clean = re.sub(r'\s+', '_', clean)
    return clean[:50]  # Ограничение длины
```

### 4.3 Переименование группы роли

```python
def rename_role_group(self, role: DepartmentRole, new_name: str) -> str:
    """Переименовывает группу роли в LDAP.
    
    Args:
        role: Роль с текущим ldap_group_dn.
        new_name: Новое название роли.
        
    Returns:
        str: Новый DN группы.
    """
    if not role.ldap_group_dn:
        # Группы нет — создаём
        return self.create_role_group(role)
    
    # Формат: ROLE_<RoleName>
    new_role_name = self._sanitize_name(new_name)
    new_cn = f"ROLE_{new_role_name}"
    
    with _ldap() as conn:
        new_dn = self._group_service.rename(conn, role.ldap_group_dn, new_cn=new_cn)
    
    role.ldap_group_dn = new_dn
    role.save(update_fields=["ldap_group_dn"])
    
    return new_dn
```

### 4.4 Удаление группы роли

```python
def delete_role_group(self, role: DepartmentRole) -> None:
    """Удаляет группу роли из LDAP.
    
    Args:
        role: Роль для удаления группы.
    """
    if not role.ldap_group_dn:
        return
    
    with _ldap() as conn:
        try:
            self._group_service.delete(conn, role.ldap_group_dn)
        except Exception as e:
            # Best effort — логируем, но не падаем
            logger.warning(f"Failed to delete role group {role.ldap_group_dn}: {e}")
```

### 4.5 Назначение роли сотруднику (новая логика)

**Текущий код** (`set_member_role`, строки 540-575):
```python
def set_member_role(self, dept, employee, role):
    # 1. Обновить EmployeeDepartment.role
    link = EmployeeDepartment.objects.get(employee_id=employee.id, department_id=dept.id)
    link.role = role
    link.save()
    
    # 2. Синхронизировать группы в OU=Roles
    if role:
        roles_base = f"OU=Roles,{dept_dn}"  # ← ПРОБЛЕМА: OU=Roles
        sync_user_groups_by_cns(conn, user_dn, {role.name}, extra_bases=[roles_base])
```

**Новый код:**
```python
def assign_role(
    self,
    employee: Employee,
    role: DepartmentRole,
    assigned_by: Employee | None = None
) -> RoleAssignment:
    """Назначает роль сотруднику (не требует членства в отделе).
    
    Args:
        employee: Сотрудник.
        role: Роль для назначения.
        assigned_by: Кто назначил (опционально).
        
    Returns:
        RoleAssignment: Созданное назначение.
        
    Raises:
        DirectoryDbError: Ошибка БД.
        DirectoryLdapError: Ошибка LDAP.
    """
    # 1. Создать/обновить назначение в БД
    try:
        with transaction.atomic():
            assignment, created = RoleAssignment.objects.update_or_create(
                employee=employee,
                role=role,
                defaults={
                    "is_active": True,
                    "assigned_by": assigned_by,
                }
            )
    except Exception as e:
        raise DirectoryDbError(str(e)) from e
    
    # 2. Добавить в LDAP-группу роли
    try:
        self._sync_role_membership(employee, role, add=True)
    except Exception as e:
        logger.error(f"LDAP role sync failed: {e}")
        # Не откатываем БД — best effort
    
    return assignment

def revoke_role(
    self,
    employee: Employee,
    role: DepartmentRole
) -> None:
    """Отзывает роль у сотрудника.
    
    Args:
        employee: Сотрудник.
        role: Роль для отзыва.
    """
    # 1. Деактивировать/удалить назначение
    RoleAssignment.objects.filter(
        employee=employee,
        role=role
    ).update(is_active=False)
    
    # 2. Удалить из LDAP-группы
    try:
        self._sync_role_membership(employee, role, add=False)
    except Exception as e:
        logger.error(f"LDAP role revoke failed: {e}")

def _sync_role_membership(
    self,
    employee: Employee,
    role: DepartmentRole,
    add: bool = True
) -> None:
    """Синхронизирует членство в группе роли LDAP.
    
    Args:
        employee: Сотрудник.
        role: Роль.
        add: True — добавить, False — удалить.
    """
    if not role.ldap_group_dn:
        # Создаём группу если нет
        self.create_role_group(role)
    
    if not role.ldap_group_dn:
        return  # Не удалось создать
    
    user_dn = self._user_service._get_employee_dn(employee)
    
    with _ldap() as conn:
        if add:
            self._group_service.add_members(conn, role.ldap_group_dn, [user_dn])
        else:
            self._group_service.remove_members(conn, role.ldap_group_dn, [user_dn])
```

### 4.6 Удалить ссылки на OU=Roles

**Файлы для изменения:**

1. `employees/ldap/services/department_service.py`:
   - Удалить `conn.add(f"OU=Roles,{dn}", ...)` (строка 655)
   - Заменить `roles_base = f"OU=Roles,{dept_dn}"` на `role.ldap_group_dn`

2. `employees/ldap/sync_service.py`:
   - Удалить `extra_bases.append(f"OU=Roles,OU={dept_for_roles},{dept_base}")` (строка 305)

3. `employees/ldap/utils/group_utils.py`:
   - Убрать специальную логику для `"OU=Roles," in dn` (строка 127)

---

## 5. Изменения API

### 5.1 Новый endpoint: assign_role

**URL**: `POST /api/v1/department-roles/{role_id}/assign/`

**Payload**:
```json
{
  "employee_id": 42
}
```

**Response** (201):
```json
{
  "id": 1,
  "employee_id": 42,
  "role_id": 15,
  "assigned_at": "2025-12-30T10:00:00Z",
  "is_active": true
}
```

**Permission**: `DeptPerm.ASSIGN_ROLE` в отделе роли.

### 5.2 Новый endpoint: revoke_role

**URL**: `POST /api/v1/department-roles/{role_id}/revoke/`

**Payload**:
```json
{
  "employee_id": 42
}
```

**Response** (204): No Content

### 5.3 Список назначений роли

**URL**: `GET /api/v1/department-roles/{role_id}/assignments/`

**Response**:
```json
{
  "count": 3,
  "results": [
    {
      "id": 1,
      "employee_id": 42,
      "employee_name": "John Doe",
      "assigned_at": "2025-12-30T10:00:00Z",
      "assigned_by": 1,
      "is_active": true
    }
  ]
}
```

### 5.4 Deprecated: set_member_role

**Статус**: Deprecated, но поддерживается для обратной совместимости.

**Изменение**: Внутренне вызывает `assign_role`/`revoke_role`.

```python
@action(detail=True, methods=["post"])
def set_member_role(self, request, pk=None):
    """DEPRECATED: Use /department-roles/{id}/assign/ instead."""
    warnings.warn(
        "set_member_role is deprecated, use /department-roles/{id}/assign/",
        DeprecationWarning
    )
    
    dept = self.get_object()
    payload = SetMemberRoleInput(data=request.data)
    payload.is_valid(raise_exception=True)
    
    employee_id = payload.validated_data["employee_id"]
    role_id = payload.validated_data.get("role_id")
    
    employee = get_object_or_404(Employee, id=employee_id)
    
    if role_id:
        role = get_object_or_404(DepartmentRole, id=role_id, department=dept)
        self.service.assign_role(employee, role, request.user.employee)
    else:
        # Снять все роли в этом отделе
        for assignment in RoleAssignment.objects.filter(
            employee=employee,
            role__department=dept,
            is_active=True
        ):
            self.service.revoke_role(employee, assignment.role)
    
    return Response(...)
```

---

## 6. Миграция существующих данных LDAP

### 6.1 Скрипт миграции

```python
# management/commands/migrate_role_groups.py

from django.core.management.base import BaseCommand
from employees.models import DepartmentRole, Department
from employees.ldap.infrastructure.connections import _ldap

class Command(BaseCommand):
    help = "Migrate role groups from OU=Roles to department OU"
    
    def handle(self, *args, **options):
        with _ldap() as conn:
            for role in DepartmentRole.objects.select_related('department').all():
                old_dn = role.ldap_group_dn
                
                if not old_dn or "OU=Roles" not in old_dn:
                    self.stdout.write(f"Skipping {role}: no OU=Roles in DN")
                    continue
                
                # Получить новый DN (в OU отдела, без OU=Roles)
                dept_dn = self._get_dept_dn(role.department)
                role_name = self._sanitize(role.name)
                new_cn = f"ROLE_{role_name}"  # Формат: ROLE_<RoleName>
                new_dn = f"CN={new_cn},{dept_dn}"
                
                # Переместить группу
                try:
                    if conn.search(old_dn, "(objectClass=group)", search_scope=BASE):
                        # Перемещение в LDAP
                        conn.modify_dn(
                            old_dn,
                            f"CN={new_cn}",
                            new_superior=dept_dn
                        )
                        self.stdout.write(self.style.SUCCESS(
                            f"Moved {old_dn} -> {new_dn}"
                        ))
                    else:
                        # Группы нет — создать новую
                        # ...
                except Exception as e:
                    self.stderr.write(f"Error moving {old_dn}: {e}")
                
                # Обновить модель
                role.ldap_group_dn = new_dn
                role.save(update_fields=["ldap_group_dn"])
```

### 6.2 Удаление пустых OU=Roles

```python
def cleanup_empty_roles_ou(self):
    """Удаляет пустые OU=Roles после миграции."""
    with _ldap() as conn:
        base = settings.LDAP_DEPARTMENTS_BASE
        conn.search(
            base,
            "(objectClass=organizationalUnit)",
            attributes=["distinguishedName"]
        )
        
        for entry in conn.entries:
            dn = entry.entry_dn
            if "OU=Roles" not in dn:
                continue
            
            # Проверить пустой ли
            conn.search(dn, "(objectClass=*)", search_scope=LEVEL)
            if not conn.entries:
                conn.delete(dn)
                print(f"Deleted empty OU: {dn}")
```

---

## 7. Проверка прав — изменения

### 7.1 Текущая логика

```python
def has_dept_perm(user_id: int, dept_id: int, permission_code: str) -> bool:
    """Проверяет наличие права через EmployeeDepartment.role."""
    return EmployeeDepartment.objects.filter(
        employee_id=user_id,
        department_id=dept_id,
        is_active=True,
        role__scoped_permissions__code=permission_code
    ).exists()
```

### 7.2 Новая логика

```python
def has_dept_perm(user_id: int, dept_id: int, permission_code: str) -> bool:
    """Проверяет наличие права через RoleAssignment."""
    # Быстрые проверки
    user = User.objects.filter(id=user_id).first()
    if not user:
        return False
    if user.is_staff or user.is_superuser:
        return True
    
    # Руководитель отдела
    if Department.objects.filter(id=dept_id, head__user_id=user_id).exists():
        return True
    
    # Через назначение роли (новая модель)
    return RoleAssignment.objects.filter(
        employee__user_id=user_id,
        role__department_id=dept_id,
        role__scoped_permissions__code=permission_code,
        is_active=True
    ).exists()
```

---

## 8. План внедрения

### Этап 1: Подготовка (1 день)

1. ✅ Создать модель `RoleAssignment`
2. ✅ Написать миграции
3. ✅ Добавить миграцию данных из `EmployeeDepartment.role`

### Этап 2: LDAP-логика (2 дня)

1. ✅ Добавить методы `create_role_group`, `rename_role_group`, `delete_role_group`
2. ✅ Изменить `_ensure_department_ou` — убрать создание OU=Roles
3. ✅ Реализовать `assign_role`, `revoke_role` с LDAP-синхронизацией
4. ✅ Написать скрипт миграции групп из OU=Roles

### Этап 3: API (1 день)

1. ✅ Добавить endpoints `/assign/`, `/revoke/`, `/assignments/`
2. ✅ Deprecate `set_member_role` с поддержкой обратной совместимости
3. ✅ Обновить сериализаторы

### Этап 4: Permissions (0.5 дня)

1. ✅ Обновить `has_dept_perm` для использования `RoleAssignment`
2. ✅ Обновить `AdminOrDeptAllowed`

### Этап 5: Тестирование (2 дня)

1. ✅ Unit-тесты для новых методов
2. ✅ Integration-тесты LDAP (с mock)
3. ✅ Миграция на тестовом AD

### Этап 6: Продакшн миграция (1 день)

1. ✅ Backup LDAP и БД
2. ✅ Запуск миграции Django
3. ✅ Запуск скрипта миграции LDAP-групп
4. ✅ Cleanup пустых OU=Roles
5. ✅ Мониторинг и откат при проблемах

---

## 9. Риски и митигация

### Риск 1: Конфликт имён групп

**Описание**: Группа `ROLE_IT_TechLead` уже существует (например, создана вручную).

**Митигация**:
- Проверять существование перед созданием
- При конфликте — добавлять суффикс: `ROLE_IT_TechLead_2`

### Риск 2: Ошибки миграции LDAP

**Описание**: Перемещение групп может не сработать (права, блокировки).

**Митигация**:
- Запуск в maintenance window
- Fallback: создать новую группу + скопировать members
- Детальное логирование

### Риск 3: Нарушение обратной совместимости

**Описание**: Старый код использует `EmployeeDepartment.role`.

**Митигация**:
- Оставить поле `role` (deprecated)
- Добавить signal для синхронизации с `RoleAssignment`
- Постепенная миграция кода

---

## 10. Итоговая схема

```
┌────────────────────────────────────────────────────────────┐
│                    Django Models                           │
├────────────────────────────────────────────────────────────┤
│  Department                                                 │
│    └── DepartmentRole (roles)                              │
│          └── RoleAssignment (assignments)  ← НОВОЕ         │
│                └── Employee (любой сотрудник)              │
│                                                             │
│  EmployeeDepartment (членство в отделе, БЕЗ роли)         │
└────────────────────────────────────────────────────────────┘
                         ↓
┌────────────────────────────────────────────────────────────┐
│                     LDAP Structure                          │
├────────────────────────────────────────────────────────────┤
│  OU=Departments                                             │
│    └── OU=IT Department                                     │
│          ├── CN=John Doe (пользователь)                     │
│          ├── CN=DEP_IT Department (группа членов)           │
│          ├── CN=ROLE_TechLead (группа роли)  ← В OU!         │
│          └── CN=ROLE_DevOps (группа роли)                    │
│                                                             │
│  [УДАЛЕНО: OU=Roles]                                        │
└────────────────────────────────────────────────────────────┘
```

**Конвенция именования групп:**
- `DEP_<Name>` — группы отделов
- `POS_<Name>` — группы должностей
- `ROLE_<Name>` — группы ролей ← НОВОЕ

---

**Связанные отчёты:**
- [01_DEPARTMENT_ROLES_MODELS.md](./01_DEPARTMENT_ROLES_MODELS.md)
- [06_DEPARTMENT_ROLES_LDAP.md](./06_DEPARTMENT_ROLES_LDAP.md)
- [08_DEPARTMENT_ROLES_ARCHITECTURE.md](./08_DEPARTMENT_ROLES_ARCHITECTURE.md)
