# Отчет: Модели данных системы ролей отделов

**Дата**: 30.12.2025  
**Анализ**: Структура моделей DepartmentRole, DepartmentPermission, EmployeeDepartment

---

## 1. DepartmentPermission — Справочник прав отдела

### Расположение
`backend/employees/models.py` (строки ~450-470)

### Структура модели

```python
class DepartmentPermission(models.Model):
    code = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=200)
```

### Назначение
Справочник департаментских прав (scoped permissions), которые могут назначаться ролям внутри отделов.

### Поля

| Поле | Тип | Особенности | Назначение |
|------|-----|-------------|------------|
| `code` | CharField(100) | unique=True, db_index=True | Уникальный код права (например, "manage_department") |
| `name` | CharField(200) | - | Человекочитаемое название права |

### Источник кодов прав
Коды синхронизируются с `employees.constants.DeptPerm.CHOICES`:

```python
class DeptPerm:
    MANAGE = "manage_department"
    CHANGE_HEAD = "change_department_head"
    ASSIGN_ROLE = "assign_department_role"
    MANAGE_CALENDAR = "manage_department_events"
    CREATE_POST = "publish_department_post"
    MANAGE_FEED = "manage_department_feed"
    VIEW_REQUESTCOMMENT = "view_requestcomment"
    ADD_REQUESTCOMMENT = "add_requestcomment"
    VIEW_REQUEST = "view_request"
    CAN_PROCESS_REQUESTS = "can_process_requests"

    CHOICES = (
        (MANAGE, "Управлять отделом"),
        (CHANGE_HEAD, "Назначать руководителя"),
        (ASSIGN_ROLE, "Назначать роли участникам"),
        (MANAGE_CALENDAR, "Управлять календарём отдела"),
        (CREATE_POST, "Публиковать новости на странице отдела"),
        (MANAGE_FEED, "Редактировать публикации отдела"),
        (VIEW_REQUESTCOMMENT, "Просмотр комментариев по заявлениям"),
        (ADD_REQUESTCOMMENT, "Добавление коментариев по заявлениям"),
        (VIEW_REQUEST, "Просмотр заявлений отдела"),
        (CAN_PROCESS_REQUESTS, "Рассмотрение заявлений отдела"),
    )
```

### Идемпотентная синхронизация
Записи создаются/обновляются автоматически через `_ensure_department_permissions()` в `employees/utils.py`.

### Особенности
- **Единственная точка истины**: `DeptPerm.CHOICES` в constants.py
- **Автоматическая синхронизация**: При вызове `/api/v1/department-roles/perm_choices/` или `ui-context/`
- **Нет миграций**: Новые права добавляются через код без миграций БД

---

## 2. DepartmentRole — Роль внутри отдела

### Расположение
`backend/employees/models.py` (строки ~470-500)

### Структура модели

```python
class DepartmentRole(models.Model):
    department = models.ForeignKey(
        'Department',
        on_delete=models.CASCADE,
        related_name='roles'
    )
    name = models.CharField(max_length=100)
    scoped_permissions = models.ManyToManyField(
        DepartmentPermission,
        blank=True,
        related_name='roles'
    )
    ldap_group_dn = models.CharField(max_length=500, blank=True, default='')

    class Meta:
        unique_together = [('department', 'name')]
        verbose_name = 'Роль отдела'
        verbose_name_plural = 'Роли отделов'
```

### Назначение
Роль, определённая в рамках конкретного отдела. Каждая роль имеет набор скоуп-прав (scoped_permissions), действующих только в этом отделе.

### Поля

| Поле | Тип | Связь | Особенности | Назначение |
|------|-----|-------|-------------|------------|
| `department` | ForeignKey | Department | CASCADE, related_name='roles' | Отдел, к которому принадлежит роль |
| `name` | CharField(100) | - | unique_together с department | Название роли (уникально в рамках отдела) |
| `scoped_permissions` | ManyToManyField | DepartmentPermission | blank=True, related_name='roles' | Набор прав роли |
| `ldap_group_dn` | CharField(500) | - | blank=True, default='' | DN группы в LDAP (для синхронизации) |

### Constraints

```python
unique_together = [('department', 'name')]
```

**Значение**: Имя роли уникально только в рамках одного отдела. В разных отделах могут быть роли с одинаковыми именами.

### Связи

```python
Department.roles  # related_name='roles'
# Получить все роли отдела:
department.roles.all()
```

### LDAP Integration
- **OU=Roles внутри OU отдела**: Для каждой роли создаётся LDAP-группа внутри `OU=Roles,OU=<Отдел>,OU=Departments,...`
- **Автоматическая синхронизация**: При назначении роли пользователю (`set_member_role`) происходит добавление в соответствующую LDAP-группу
- **Хранение DN**: Поле `ldap_group_dn` содержит полный DN группы роли

---

## 3. EmployeeDepartment — Связь сотрудника и отдела

### Расположение
`backend/employees/models.py` (строки ~500-540)

### Структура модели

```python
class EmployeeDepartment(models.Model):
    employee = models.ForeignKey(
        'Employee',
        on_delete=models.CASCADE,
        related_name='department_memberships'
    )
    department = models.ForeignKey(
        'Department',
        on_delete=models.CASCADE,
        related_name='employee_links'
    )
    role = models.ForeignKey(
        DepartmentRole,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employee_assignments'
    )
    date_from = models.DateField(blank=True, null=True)
    date_to = models.DateField(blank=True, null=True)
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta:
        unique_together = [('department', 'employee')]
        verbose_name = 'Членство в отделе'
        verbose_name_plural = 'Членство в отделах'
```

### Назначение
Связывает сотрудника с отделом и **опционально** назначает роль. Поддерживает временные рамки членства и флаг активности.

### Поля

| Поле | Тип | Связь | Особенности | Назначение |
|------|-----|-------|-------------|------------|
| `employee` | ForeignKey | Employee | CASCADE, related_name='department_memberships' | Сотрудник |
| `department` | ForeignKey | Department | CASCADE, related_name='employee_links' | Отдел |
| `role` | ForeignKey | DepartmentRole | SET_NULL, null=True, blank=True, related_name='employee_assignments' | Роль в отделе (опционально) |
| `date_from` | DateField | - | null=True, blank=True | Дата начала членства |
| `date_to` | DateField | - | null=True, blank=True | Дата окончания членства |
| `is_active` | BooleanField | - | default=True, db_index=True | Флаг активного членства |

### Constraints

```python
unique_together = [('department', 'employee')]
```

**Значение**: Сотрудник может иметь только одну связь с каждым отделом. Нет дублирования членства.

### Ключевые особенности

#### 1. Роль опциональна
```python
role = models.ForeignKey(..., null=True, blank=True)
```
- Сотрудник может быть членом отдела **без роли**
- Роль назначается отдельно через `set_member_role()`
- Разделение: `add_member` (добавить в отдел) != `set_member_role` (назначить роль)

#### 2. SET_NULL при удалении роли
```python
role = models.ForeignKey(..., on_delete=models.SET_NULL)
```
- При удалении роли у сотрудников автоматически `role = None`
- Членство в отделе сохраняется
- Не требуется вручную очищать связи

#### 3. is_active флаг
- **Indexed**: `db_index=True` для быстрых фильтраций
- **Использование**: Проверка прав в `has_dept_perm()` учитывает только `is_active=True`
- **Soft delete**: Можно деактивировать членство без физического удаления

### Связи

```python
# Получить все отделы сотрудника:
employee.department_memberships.filter(is_active=True)

# Получить всех сотрудников отдела:
department.employee_links.filter(is_active=True).select_related('employee', 'role')

# Получить всех сотрудников с конкретной ролью:
role.employee_assignments.filter(is_active=True)
```

---

## 4. Department.Meta.permissions — Django-уровень

### Расположение
`backend/employees/models.py` — класс Department

### Структура

```python
class Department(models.Model):
    # ... поля ...
    
    class Meta:
        permissions = [
            ("change_department_head", "Может назначать руководителя отдела"),
            ("assign_department_role", "Может назначать роли участникам отдела"),
            ("manage_department", "Может управлять отделом"),
        ]
```

### Назначение
Дополнительные Django permissions на уровне модели Department. Используются в системе прав совместно со scoped permissions.

### Взаимодействие уровней прав

```
┌──────────────────────────────────────┐
│ 1. Django Model Permissions          │
│    - change_department_head          │
│    - assign_department_role          │
│    - manage_department               │
└──────────────────────────────────────┘
              ↓
┌──────────────────────────────────────┐
│ 2. DepartmentPermission (scoped)     │
│    - Записи в БД из DeptPerm.CHOICES │
│    - Привязываются к ролям           │
└──────────────────────────────────────┘
              ↓
┌──────────────────────────────────────┐
│ 3. DepartmentRole.scoped_permissions │
│    - M2M к DepartmentPermission      │
│    - Действует только в своём отделе │
└──────────────────────────────────────┘
              ↓
┌──────────────────────────────────────┐
│ 4. EmployeeDepartment.role           │
│    - Связь сотрудника с ролью        │
│    - Проверка: is_active=True        │
└──────────────────────────────────────┘
```

---

## 5. Критические особенности архитектуры

### 5.1 Двухуровневая система прав

**Уровень 1: Django permissions** (глобальные)
- Привязаны к модели Department
- Проверяются через `user.has_perm('employees.manage_department')`
- **НЕ учитывают** конкретный отдел

**Уровень 2: Scoped permissions** (в рамках отдела)
- Хранятся в `DepartmentPermission`
- Назначаются ролям через `DepartmentRole.scoped_permissions`
- Проверяются через `has_dept_perm(user, dept_id, code)`
- **Учитывают** конкретный отдел

### 5.2 Руководитель отдела имеет все права

```python
# В has_dept_perm():
if Department.objects.filter(id=department_id, head_id=user.id).exists():
    return True  # ✅ Руководитель имеет любое право
```

**Значение**: Руководителю не нужны роли для управления своим отделом.

### 5.3 Разделение операций

**add_member** (`DeptPerm.MANAGE`)
- Добавляет сотрудника в отдел
- **НЕ назначает роль** (`role=None`)
- Требует право `manage_department`

**set_member_role** (`DeptPerm.ASSIGN_ROLE`)
- Назначает/снимает роль у **существующего** члена
- Требует членство в отделе
- Требует право `assign_department_role`

**remove_member** (`DeptPerm.MANAGE`)
- Удаляет из отдела (deactivate или delete)
- Автоматически очищает роль (SET_NULL)

### 5.4 Уникальность и скоуп

```python
# ✅ Правильно: разные отделы, одно имя роли
DepartmentRole(department=dept1, name="Manager")
DepartmentRole(department=dept2, name="Manager")

# ❌ Ошибка: один отдел, одно имя
DepartmentRole(department=dept1, name="Manager")
DepartmentRole(department=dept1, name="Manager")  # IntegrityError
```

---

## 6. Проблемные места и ограничения

### 6.1 Смешение уровней прав
**Проблема**: Django permissions в Department.Meta и scoped permissions в DepartmentPermission имеют частичное пересечение кодов.

**Пример**:
- `Department.Meta.permissions`: `"manage_department"`
- `DeptPerm.MANAGE`: `"manage_department"`

**Следствие**: Неочевидно, какой уровень проверять в каком контексте.

### 6.2 Автоматическая синхронизация permissions
**Проблема**: `_ensure_department_permissions()` создаёт записи при каждом вызове API.

**Риски**:
- Нет контроля версий прав
- Удаление кода из `DeptPerm.CHOICES` не удаляет запись из БД
- Нет миграций для отслеживания изменений

### 6.3 LDAP soft dependency
**Проблема**: Код везде проверяет `if _is_ldap_enabled()` для переключения логики.

**Следствие**: Две разные кодовые ветки, усложнение тестирования.

### 6.4 Нет валидации role.department == link.department
**Проблема**: При назначении роли не проверяется на уровне модели, что роль принадлежит тому же отделу.

**Защита**: Только в API-слое (`set_member_role` в views.py).

---

## 7. Рекомендации по рефакторингу

### 7.1 Унифицировать систему прав
- Удалить Django permissions из `Department.Meta`
- Оставить только scoped permissions через `DepartmentPermission`
- Добавить миграцию для перехода

### 7.2 Добавить валидацию на уровне модели
```python
class EmployeeDepartment(models.Model):
    def clean(self):
        if self.role and self.role.department_id != self.department_id:
            raise ValidationError("Role must belong to the same department")
```

### 7.3 Создать миграции для permissions
- Вместо `_ensure_department_permissions()` использовать data migrations
- Добавить версионирование справочника прав

### 7.4 Абстрагировать LDAP-логику
- Создать адаптер `DepartmentRoleBackend` с двумя реализациями: LDAP и DB-only
- Убрать `if _is_ldap_enabled()` из бизнес-логики

---

## 8. Итоговая схема данных

```
┌──────────────────────────────────┐
│ Department                       │
│ - id                             │
│ - name                           │
│ - head_id (FK → Employee)        │
│ - ldap_group_dn                  │
└──────────────────────────────────┘
           ↑ (department FK)
           │
┌──────────────────────────────────┐         ┌──────────────────────────────┐
│ DepartmentRole                   │ M2M     │ DepartmentPermission         │
│ - id                             │←────────→ - id                          │
│ - department_id (FK ↑)           │         │ - code (unique)              │
│ - name (unique per dept)         │         │ - name                       │
│ - ldap_group_dn                  │         └──────────────────────────────┘
└──────────────────────────────────┘
           ↑ (role FK, nullable)
           │
┌──────────────────────────────────┐
│ EmployeeDepartment               │
│ - id                             │
│ - employee_id (FK → Employee)    │
│ - department_id (FK ↑)           │
│ - role_id (FK ↑, nullable)       │
│ - is_active (indexed)            │
│ - date_from, date_to             │
│ UNIQUE: (department, employee)   │
└──────────────────────────────────┘
```

---

**Следующий отчет**: [02_DEPARTMENT_ROLES_API.md](./02_DEPARTMENT_ROLES_API.md) — API ViewSet и endpoints
