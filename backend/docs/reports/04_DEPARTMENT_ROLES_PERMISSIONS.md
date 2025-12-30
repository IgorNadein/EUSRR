# Отчет: Система проверки прав в ролях отделов

**Дата**: 30.12.2025  
**Анализ**: AdminOrDeptAllowed, has_dept_perm, user_has_dept_perm — архитектура permission system

---

## 1. Обзор архитектуры прав

### Уровни проверки прав

```
┌──────────────────────────────────────────────────────┐
│ Level 1: Django Model Permissions                    │
│   - Глобальные права на модель Department            │
│   - Проверка: user.has_perm('employees.manage_...')  │
└──────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│ Level 2: Staff/Superuser Override                    │
│   - user.is_staff or user.is_superuser → ALL ACCESS  │
└──────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│ Level 3: Department Head Rights                      │
│   - dept.head == user → ALL DEPARTMENT RIGHTS        │
└──────────────────────────────────────────────────────┘
                        ↓
┌──────────────────────────────────────────────────────┐
│ Level 4: Scoped Role Permissions                     │
│   - EmployeeDepartment.role.scoped_permissions       │
│   - Права действуют ТОЛЬКО в конкретном отделе      │
└──────────────────────────────────────────────────────┘
```

---

## 2. Функции проверки прав

### 2.1 user_is_staffish() — Проверка admin-доступа

**Расположение**: `backend/api/v1/permissions.py` (строки 26-28)

```python
def user_is_staffish(user) -> bool:
    return bool(user and user.is_authenticated and (user.is_superuser or user.is_staff))
```

**Назначение**: Быстрая проверка админского доступа.

**Использование**:
- В условиях before expensive queries
- Для ранних return в permission classes

---

### 2.2 user_is_dept_head() — Проверка руководителя

**Расположение**: `backend/api/v1/permissions.py` (строки 21-24)

```python
def user_is_dept_head(user, dept: Department) -> bool:
    return bool(
        user and user.is_authenticated and dept.head_id == getattr(user, "id", None)
    )
```

**Назначение**: Проверить, является ли пользователь руководителем отдела.

**Особенности**:
- Принимает объект `Department` (не ID)
- Использует `getattr()` для безопасного доступа к `user.id`

**Использование**:
```python
if user_is_dept_head(request.user, department):
    # Руководитель имеет полный доступ
    return True
```

---

### 2.3 user_has_dept_perm() — Проверка скоуп-права

**Расположение**: `backend/api/v1/permissions.py` (строки 32-74)

```python
def user_has_dept_perm(user, dept: Department, perm_code: str) -> bool:
    """Проверяет, есть ли у пользователя право `perm_code` в указанном отделе.
    
    Правила:
        - Неаутентифицированным → False.
        - staff/superuser → True.
        - Руководитель отдела → True.
        - Иначе: существует активная связь EmployeeDepartment, и у роли есть
          DepartmentPermission с нужным code.
    """
    if not (user and user.is_authenticated):
        return False
    
    # staff/superuser — сразу ок
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    
    if not isinstance(dept, Department) or getattr(dept, "id", None) is None:
        raise ValueError("Argument `dept` must be Department instance with a valid id.")
    
    # руководитель — сразу ок
    if getattr(dept, "head_id", None) == user.id:
        return True
    
    # основная проверка: активная связь + у роли есть нужный DepartmentPermission.code
    return EmployeeDepartment.objects.filter(
        employee_id=user.id,
        department_id=dept.id,
        is_active=True,
        role__scoped_permissions__code=perm_code,
    ).exists()
```

### Логика проверки (порядок)

```
1. Аутентификация ──► Нет ──► False
         │
         Да
         ↓
2. Staff/Superuser ──► Да ──► True
         │
         Нет
         ↓
3. Валидация dept ──► Ошибка ──► ValueError
         │
         OK
         ↓
4. Руководитель отдела ──► Да ──► True
         │
         Нет
         ↓
5. Query EmployeeDepartment:
   - employee_id = user.id
   - department_id = dept.id
   - is_active = True
   - role__scoped_permissions__code = perm_code
         │
         ↓
   Exists? ──► Да ──► True
         │
         Нет
         ↓
        False
```

### Особенности

**1. Принимает объект Department**:
```python
# ✅ Правильно:
user_has_dept_perm(user, department_obj, "manage_department")

# ❌ Неправильно:
user_has_dept_perm(user, 5, "manage_department")  # ValueError
```

**2. Использует M2M join**:
```sql
SELECT 1 FROM employees_employeedepartment
JOIN employees_departmentrole_scoped_permissions 
  ON employees_departmentrole_scoped_permissions.departmentrole_id = employees_employeedepartment.role_id
JOIN employees_departmentpermission 
  ON employees_departmentpermission.id = employees_departmentrole_scoped_permissions.departmentpermission_id
WHERE employee_id = %s 
  AND department_id = %s 
  AND is_active = TRUE 
  AND code = %s
LIMIT 1
```

**3. Проверяет `is_active`**:
- Деактивированные членства игнорируются
- Даже если роль есть, но `is_active=False` → доступ запрещён

---

### 2.4 has_dept_perm() — Проверка по ID отдела

**Расположение**: `backend/api/v1/permissions.py` (строки 76-106)

```python
def has_dept_perm(user: AbstractBaseUser, department_id: int, code: str) -> bool:
    """
    Возвращает True, если пользователь имеет право `code` в рамках отдела `department_id`.
    
    Логика:
      1) staff/superuser → всегда True
      2) пользователь является текущим руководителем отдела → True
      3) пользователь состоит в отделе и его роль содержит `code` → True
      4) иначе False
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    
    # 2) Руководитель отдела имеет все управленческие права в своём отделе
    if Department.objects.filter(id=department_id, head_id=user.id).exists():
        return True
    
    # 3) Проверка роли в отделе
    link = (
        EmployeeDepartment.objects.select_related("role")
        .filter(employee_id=user.id, department_id=department_id, is_active=True)
        .first()
    )
    if not link or not link.role_id:
        return False
    
    # роль хранит «скоуп-права» только для этого отдела
    return link.role.scoped_permissions.filter(code=code).exists()
```

### Отличия от user_has_dept_perm

| Аспект | user_has_dept_perm | has_dept_perm |
|--------|-------------------|---------------|
| Параметр отдела | `dept: Department` (объект) | `department_id: int` (ID) |
| Query руководителя | `dept.head_id == user.id` (в памяти) | `Department.objects.filter(...)` (DB) |
| Query прав | 1 запрос (M2M join) | 2 запроса (select_related + M2M) |
| Использование | Когда объект уже загружен | Когда есть только ID |

### Оптимизация

**has_dept_perm** использует:
```python
link = EmployeeDepartment.objects.select_related("role").filter(...).first()
```

**Цель**: Загрузить роль заранее, чтобы следующий запрос использовал кеш:
```python
return link.role.scoped_permissions.filter(code=code).exists()
```

**Результат**: 2 query вместо 3.

---

## 3. AdminOrDeptAllowed — Базовый permission class

### Расположение
`backend/api/v1/permissions.py` (строки 108-310)

### Назначение
Комбинированный permission class для DRF ViewSets:
- Админы имеют полный доступ
- Остальные проверяются по скоуп-правам в конкретном отделе

---

### 3.1 Структура класса

```python
class AdminOrDeptAllowed(BasePermission):
    required_code: Optional[str] = None
    required_code_map: Dict[str, str] = {}
    allow_safe_without_code: bool = True
```

### Атрибуты класса

| Атрибут | Тип | По умолчанию | Назначение |
|---------|-----|--------------|------------|
| `required_code` | str \| None | None | Единый код права для всех действий |
| `required_code_map` | dict[str, str] | {} | Коды прав по имени action |
| `allow_safe_without_code` | bool | True | Разрешать ли GET без кода |

---

### 3.2 Методы

#### get_required_code()

```python
def get_required_code(self, request, view) -> Optional[str]:
    """Определяет требуемый код права для текущего экшена.
    
    Сначала берёт из required_code_map по имени action (DRF: view.action),
    затем fallback на required_code.
    """
    return (
        self.required_code_map.get(getattr(view, "action", None))
        or self.required_code
    )
```

**Приоритет**:
1. `required_code_map[view.action]`
2. `required_code`
3. `None` (если оба пусты)

**Примеры**:
```python
class MyPerm(AdminOrDeptAllowed):
    required_code = DeptPerm.MANAGE  # Для всех действий
    
class MyPerm2(AdminOrDeptAllowed):
    required_code_map = {
        "create": DeptPerm.MANAGE,
        "update": DeptPerm.MANAGE,
        "destroy": DeptPerm.CHANGE_HEAD,  # Другое право для удаления
    }
```

---

#### _extract_dept_id_from_request()

```python
def _extract_dept_id_from_request(self, request, view) -> Optional[int]:
    """Пытается извлечь department_id из kwargs, body или query-параметров.
    
    Порядок:
        1) view.kwargs: department_pk, department_id
        2) request.data: department, department_id
        3) request.query_params: department, department_id
    """
    for k in ("department_pk", "department_id"):
        v = view.kwargs.get(k)
        if v is not None:
            return v
    for k in ("department", "department_id"):
        v = request.data.get(k)
        if v is not None:
            return v
    for k in ("department", "department_id"):
        v = request.query_params.get(k)
        if v is not None:
            return v
    return None
```

**Порядок приоритета**:
1. **URL kwargs** (`/departments/{id}/...` → `department_pk`)
2. **Request body** (`POST {"department": 5}`)
3. **Query params** (`?department=5`)

**Примеры**:
```python
# Вариант 1: Nested route
POST /api/v1/departments/5/roles/
→ view.kwargs = {"department_pk": 5}

# Вариант 2: Body
POST /api/v1/department-roles/
{"department": 5, "name": "Manager"}
→ request.data = {"department": 5}

# Вариант 3: Query
GET /api/v1/department-roles/?department=5
→ request.query_params = {"department": "5"}
```

---

#### _extract_dept_id_from_obj()

```python
def _extract_dept_id_from_obj(self, obj: Any) -> Optional[int]:
    """Извлекает department_id из объекта.
    
    Порядок:
        1) obj.id (если obj сам Department)
        2) obj.department_id / obj.dept_id
        3) obj.department.id
    """
    # 1) сам объект — Department
    if isinstance(obj, Department):
        return getattr(obj, "id", None)
    
    # 2) прямые FK
    for attr in ("department_id", "dept_id"):
        dept_id = getattr(obj, attr, None)
        if dept_id is not None:
            return dept_id
    
    # 3) related Department
    dept = getattr(obj, "department", None)
    if dept:
        return getattr(dept, "id", None)
    
    return None
```

**Примеры**:
```python
# 1. Объект Department
dept = Department.objects.get(id=5)
→ dept_id = 5

# 2. DepartmentRole
role = DepartmentRole.objects.get(id=12)
→ role.department_id = 5

# 3. Объект с related
class MyModel:
    department = ForeignKey(Department)
obj = MyModel.objects.select_related('department').get(...)
→ obj.department.id = 5
```

---

#### has_permission() — Request-level check

```python
def has_permission(self, request, view):
    """Проверка на уровне запроса (до загрузки объекта).
    
    Используется для:
        - list/create (нет конкретного объекта)
        - Определения dept_id из request
    """
    user = request.user
    
    # 1. Админы всегда проходят
    if user_is_staffish(user):
        return True
    
    # 2. Получить требуемый код
    code = self.get_required_code(request, view)
    
    # 3. Если код не требуется
    if not code:
        # SAFE методы разрешены (GET/HEAD/OPTIONS)
        if request.method in SAFE_METHODS and self.allow_safe_without_code:
            return True
        return False  # Небезопасные без кода → запрет
    
    # 4. Извлечь dept_id
    dept_id = self._extract_dept_id_from_request(request, view)
    if not dept_id:
        return False  # Не можем определить отдел → запрет
    
    # 5. Проверить право в отделе
    return has_dept_perm(user, dept_id, code)
```

**Логика потока**:
```
Request → has_permission()
    ↓
1. Staff? → Yes → Allow
    ↓ No
2. Get code (action-specific or default)
    ↓
3. Code is None?
    ↓ Yes
   SAFE method & allow_safe_without_code? → Allow
    ↓ No → Deny
4. Extract dept_id from request
    ↓
5. has_dept_perm(user, dept_id, code) → Allow/Deny
```

---

#### has_object_permission() — Object-level check

```python
def has_object_permission(self, request, view, obj):
    """Проверка на уровне объекта (после загрузки).
    
    Используется для:
        - retrieve/update/destroy (есть конкретный объект)
        - Определения dept_id из самого объекта
    """
    user = request.user
    
    # 1. Админы всегда проходят
    if user_is_staffish(user):
        return True
    
    # 2. Получить код
    code = self.get_required_code(request, view)
    
    # 3. Если код не требуется
    if not code:
        if request.method in SAFE_METHODS and self.allow_safe_without_code:
            return True
        return False
    
    # 4. Извлечь dept_id из объекта
    dept_id = self._extract_dept_id_from_obj(obj)
    if not dept_id:
        return False
    
    # 5. Проверить право
    return has_dept_perm(request.user, dept_id, code)
```

**Отличие от has_permission**:
- Извлечение `dept_id` из **obj**, а не из request
- Используется после `get_object()` в ViewSet

---

## 4. Наследники AdminOrDeptAllowed

### 4.1 В DepartmentViewSet

```python
class ManagePerm(AdminOrDeptAllowed):
    """Право на управление отделом (add/remove members)."""
    required_code = DeptPerm.MANAGE

class ChangeHeadPerm(AdminOrDeptAllowed):
    """Право на назначение руководителя."""
    required_code = DeptPerm.CHANGE_HEAD

class AssignRolePerm(AdminOrDeptAllowed):
    """Право на назначение ролей участникам отдела."""
    required_code = DeptPerm.ASSIGN_ROLE
```

**Использование**:
```python
def get_permissions(self):
    if self.action == 'set_head':
        return [self.ChangeHeadPerm()]
    if self.action in {'add_member', 'remove_member'}:
        return [self.ManagePerm()]
    if self.action == 'set_member_role':
        return [self.AssignRolePerm()]
    ...
```

---

### 4.2 В DepartmentRoleViewSet

```python
class AssignRolePerm(AdminOrDeptAllowed):
    required_code = DeptPerm.ASSIGN_ROLE

def get_permissions(self):
    if self.action in {"create", "update", "partial_update", "destroy", "set_perms"}:
        return [self.AssignRolePerm()]
    return [IsAuthenticated()]
```

**Логика**:
- Создание/изменение/удаление ролей требует `assign_department_role`
- Чтение ролей доступно всем аутентифицированным

---

### 4.3 В Calendar ViewSet

```python
class ManageCalendarPerm(AdminOrDeptAllowed):
    required_code = DeptPerm.MANAGE_CALENDAR
```

**Использование**: Управление календарём событий отдела.

---

## 5. Проблемные места

### 5.1 Дублирование логики в двух функциях

**Проблема**: `user_has_dept_perm` и `has_dept_perm` делают почти одно и то же, но по-разному.

**Следствие**:
- Две кодовые ветки для поддержки
- Разная производительность (1 vs 2 запроса)
- Риск рассинхронизации логики

**Решение**: Унифицировать в одну функцию:
```python
def has_dept_perm(user, dept: Department | int, code: str) -> bool:
    if isinstance(dept, int):
        dept_id = dept
        # Query Department if needed
    else:
        dept_id = dept.id
    # Unified logic
```

---

### 5.2 Нет кеширования результатов проверки

**Проблема**: При множественных проверках в рамках одного request делаются повторные запросы.

**Пример**:
```python
# В одном request:
has_dept_perm(user, 5, "manage_department")  # Query 1
has_dept_perm(user, 5, "assign_department_role")  # Query 2
has_dept_perm(user, 5, "manage_department")  # Query 3 (дубликат)
```

**Решение**: Использовать `@lru_cache` или request-level кеш:
```python
from functools import lru_cache

@lru_cache(maxsize=128)
def has_dept_perm(user_id: int, dept_id: int, code: str) -> bool:
    # ... логика ...
```

---

### 5.3 Неочевидный приоритет в _extract_dept_id_from_request

**Проблема**: Порядок извлечения может привести к неожиданному поведению.

**Пример**:
```http
POST /api/v1/departments/5/roles/
{"department": 10}  # Другой ID в body

→ Используется view.kwargs["department_pk"] = 5
→ Body игнорируется
```

**Решение**: Добавить валидацию конфликтов:
```python
kwargs_id = view.kwargs.get("department_pk")
body_id = request.data.get("department")
if kwargs_id and body_id and kwargs_id != body_id:
    raise PermissionDenied("Conflicting department IDs in URL and body")
```

---

### 5.4 ValueError при невалидном dept в user_has_dept_perm

**Проблема**:
```python
if not isinstance(dept, Department) or getattr(dept, "id", None) is None:
    raise ValueError("Argument `dept` must be Department instance...")
```

**Следствие**: В production ValueError не обрабатывается DRF, возвращается 500.

**Решение**: Использовать `PermissionDenied`:
```python
from rest_framework.exceptions import PermissionDenied

if not isinstance(dept, Department):
    raise PermissionDenied("Invalid department object")
```

---

## 6. Примеры использования

### 6.1 Проверка прав в кастомном action

```python
@action(detail=True, methods=["post"])
def custom_action(self, request, pk=None):
    dept = self.get_object()
    
    # Проверить конкретное право
    if not user_has_dept_perm(request.user, dept, DeptPerm.MANAGE):
        return Response({"detail": "No permission"}, status=403)
    
    # Бизнес-логика
    ...
```

### 6.2 Условная логика на основе прав

```python
def get_queryset(self):
    qs = super().get_queryset()
    user = self.request.user
    
    if user.is_staff:
        return qs  # Все отделы
    
    # Только отделы, где есть право MANAGE
    dept_ids = EmployeeDepartment.objects.filter(
        employee_id=user.id,
        is_active=True,
        role__scoped_permissions__code=DeptPerm.MANAGE
    ).values_list('department_id', flat=True)
    
    return qs.filter(id__in=dept_ids)
```

### 6.3 Множественные права (OR логика)

```python
def has_any_dept_perm(user, dept_id: int, codes: list[str]) -> bool:
    """Проверить наличие хотя бы одного из прав."""
    if user.is_staff or user.is_superuser:
        return True
    
    if Department.objects.filter(id=dept_id, head_id=user.id).exists():
        return True
    
    return EmployeeDepartment.objects.filter(
        employee_id=user.id,
        department_id=dept_id,
        is_active=True,
        role__scoped_permissions__code__in=codes
    ).exists()
```

---

## 7. Итоговая схема проверки прав

```
┌────────────────────────────────────────────────────┐
│ DRF Request                                        │
└────────────────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────────────────┐
│ ViewSet.check_permissions()                        │
│  → AdminOrDeptAllowed.has_permission(request, view)│
└────────────────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────────────────┐
│ 1. user_is_staffish(user)?                         │
│    Yes → Allow                                     │
└────────────────────────────────────────────────────┘
                    ↓ No
┌────────────────────────────────────────────────────┐
│ 2. get_required_code(request, view)                │
│    → DeptPerm.ASSIGN_ROLE                          │
└────────────────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────────────────┐
│ 3. _extract_dept_id_from_request(request, view)    │
│    → dept_id = 5                                   │
└────────────────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────────────────┐
│ 4. has_dept_perm(user, dept_id, code)              │
└────────────────────────────────────────────────────┘
                    ↓
┌────────────────────────────────────────────────────┐
│ 5a. Department.filter(id=dept_id, head=user)?      │
│     Yes → True                                     │
└────────────────────────────────────────────────────┘
                    ↓ No
┌────────────────────────────────────────────────────┐
│ 5b. EmployeeDepartment.filter(                     │
│       employee=user, department=dept_id,           │
│       is_active=True,                              │
│       role__scoped_permissions__code=code          │
│     ).exists()?                                    │
│     Yes → True, No → False                         │
└────────────────────────────────────────────────────┘
```

---

**Следующий отчет**: [05_DEPARTMENT_ROLES_CONSTANTS_UTILS.md](./05_DEPARTMENT_ROLES_CONSTANTS_UTILS.md) — Константы и утилиты
