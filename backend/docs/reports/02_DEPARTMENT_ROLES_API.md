# Отчет: API ViewSet для работы с ролями отделов

**Дата**: 30.12.2025  
**Анализ**: DepartmentRoleViewSet — CRUD операции, custom actions, система прав

---

## 1. Обзор ViewSet

### Расположение
`backend/api/v1/employees/views.py` (строки 2567-2660)

### Базовая информация

```python
class DepartmentRoleViewSet(viewsets.ModelViewSet):
    queryset = (
        DepartmentRole.objects.select_related("department")
        .prefetch_related("scoped_permissions")
        .all()
    )
    serializer_class = DepartmentRoleSerializer
    ordering_fields = ("name", "id")
    ordering = ("name", "id")
```

### URL Patterns
**Router registration**:
```python
router.register(r'department-roles', DepartmentRoleViewSet, basename='department-roles')
```

**Generated URLs**:
- `GET /api/v1/department-roles/` — list (с фильтрацией `?department=<id>`)
- `POST /api/v1/department-roles/` — create
- `GET /api/v1/department-roles/{id}/` — retrieve
- `PATCH/PUT /api/v1/department-roles/{id}/` — update/partial_update
- `DELETE /api/v1/department-roles/{id}/` — destroy
- `GET /api/v1/department-roles/perm_choices/` — список всех доступных прав
- `GET /api/v1/department-roles/{id}/perms/` — права конкретной роли
- `POST /api/v1/department-roles/{id}/set_perms/` — установка прав роли

---

## 2. Стандартные CRUD операции

### 2.1 LIST — Получение списка ролей

**Endpoint**: `GET /api/v1/department-roles/`

**Query params**:
- `department` (int) — фильтр по ID отдела
- `ordering` (str) — сортировка: `name`, `-name`, `id`, `-id`

**Permission**: `IsAuthenticated()` — любой авторизованный пользователь

**Логика**:
```python
def get_queryset(self):
    qs = super().get_queryset()
    dept = self.request.query_params.get("department")
    if dept:
        qs = qs.filter(department_id=dept)
    
    # Стабильная сортировка с tie-break по id
    ord_param = self.request.query_params.get("ordering")
    if ord_param in {"name", "-name", "id", "-id"}:
        qs = qs.order_by(
            ord_param, "id" if not ord_param.startswith("-") else "-id"
        )
    else:
        qs = qs.order_by(*self.ordering)  # по умолчанию: name, id
    return qs
```

**Особенности**:
- **Prefetch optimization**: `select_related("department")` + `prefetch_related("scoped_permissions")`
- **Стабильная сортировка**: Всегда добавляется tie-break по `id` для однозначного порядка
- **Без пагинации по умолчанию**: Если не указана в settings

**Пример запроса**:
```bash
GET /api/v1/department-roles/?department=5&ordering=name
```

**Пример ответа**:
```json
{
  "count": 3,
  "results": [
    {
      "id": 12,
      "department": 5,
      "name": "Engineer",
      "scoped_permissions": [1, 3],
      "permissions": [1, 3],
      "permissions_verbose": [
        {"id": 1, "code": "manage_department", "name": "Управлять отделом"},
        {"id": 3, "code": "assign_department_role", "name": "Назначать роли"}
      ]
    }
  ]
}
```

---

### 2.2 RETRIEVE — Получение одной роли

**Endpoint**: `GET /api/v1/department-roles/{id}/`

**Permission**: `IsAuthenticated()`

**Ответ**: Полная информация о роли с backward-compat полями.

---

### 2.3 CREATE — Создание роли

**Endpoint**: `POST /api/v1/department-roles/`

**Permission**: `AssignRolePerm()` — требует `DeptPerm.ASSIGN_ROLE` в целевом отделе

```python
class AssignRolePerm(AdminOrDeptAllowed):
    required_code = DeptPerm.ASSIGN_ROLE

def get_permissions(self):
    if self.action in {"create", "update", "partial_update", "destroy", "set_perms"}:
        return [self.AssignRolePerm()]
    return [IsAuthenticated()]
```

**Body**:
```json
{
  "department": 5,
  "name": "Manager",
  "scoped_permissions": [1, 3]  // или
  "scoped_permission_codes": ["manage_department", "assign_department_role"]
}
```

**Логика проверки прав**:
1. Извлекается `department` из request.data
2. `AdminOrDeptAllowed` проверяет:
   - Пользователь staff/superuser → ✅
   - Пользователь — руководитель отдела → ✅
   - У пользователя есть роль с `assign_department_role` в этом отделе → ✅
   - Иначе → 403

**Response**: `201 Created` + данные созданной роли

**Errors**:
- `400` — валидация (duplicate name в отделе, невалидные коды прав)
- `403` — нет прав

---

### 2.4 UPDATE/PARTIAL_UPDATE — Изменение роли

**Endpoints**: 
- `PUT /api/v1/department-roles/{id}/`
- `PATCH /api/v1/department-roles/{id}/`

**Permission**: `AssignRolePerm()` — требует право в **отделе роли** (не в теле запроса)

**Body** (PATCH):
```json
{
  "name": "Senior Manager",
  "scoped_permission_codes": ["manage_department", "change_department_head"]
}
```

**Особенность**: 
- Права проверяются по `role.department_id` (из БД)
- Нельзя изменить роль отдела A, имея права только в отделе B

**Response**: `200 OK` + обновлённые данные

---

### 2.5 DESTROY — Удаление роли

**Endpoint**: `DELETE /api/v1/department-roles/{id}/`

**Permission**: `AssignRolePerm()` в отделе роли

**Логика**:
1. Проверка прав в отделе роли
2. Каскадное удаление роли
3. `EmployeeDepartment.role` → автоматически `SET_NULL` (on_delete=SET_NULL)
4. LDAP-группа роли остаётся (нет автоматической очистки)

**Response**: `204 No Content` или `200 OK`

**Последствия**:
- Все сотрудники с этой ролью теряют её (`role=None`)
- Членство в отделе сохраняется
- Права автоматически удаляются (M2M cascade)

---

## 3. Custom Actions

### 3.1 perm_choices — Справочник доступных прав

**Endpoint**: `GET /api/v1/department-roles/perm_choices/`

**Permission**: `IsAuthenticated()`

**Назначение**: Возвращает полный список прав, которые можно назначить ролям.

**Логика**:
```python
@action(detail=False, methods=["get"])
def perm_choices(self, request):
    data = _ensure_department_permissions()  # Создаёт/синхронизирует из DeptPerm.CHOICES
    return Response({"count": len(data), "results": data}, status=200)
```

**Response**:
```json
{
  "count": 10,
  "results": [
    {"id": 1, "code": "manage_department", "name": "Управлять отделом"},
    {"id": 2, "code": "change_department_head", "name": "Назначать руководителя"},
    {"id": 3, "code": "assign_department_role", "name": "Назначать роли участникам"},
    ...
  ]
}
```

**Особенность**: Идемпотентно создаёт записи в `DepartmentPermission` из `DeptPerm.CHOICES`.

---

### 3.2 perms — Права конкретной роли

**Endpoint**: `GET /api/v1/department-roles/{id}/perms/`

**Permission**: `IsAuthenticated()`

**Назначение**: Получить список прав, назначенных данной роли.

**Логика**:
```python
@action(detail=True, methods=["get"])
def perms(self, request, pk=None):
    role = self.get_object()
    data = [
        {"id": p.id, "code": p.code, "name": p.name}
        for p in role.scoped_permissions.order_by("code")
    ]
    return Response({"count": len(data), "results": data}, status=200)
```

**Response**:
```json
{
  "count": 2,
  "results": [
    {"id": 3, "code": "assign_department_role", "name": "Назначать роли участникам"},
    {"id": 1, "code": "manage_department", "name": "Управлять отделом"}
  ]
}
```

**Сортировка**: Права отсортированы по `code` (алфавитный порядок).

---

### 3.3 set_perms — Установка прав роли

**Endpoint**: `POST /api/v1/department-roles/{id}/set_perms/`

**Permission**: `AssignRolePerm()` в отделе роли

**Назначение**: Полная замена набора прав у роли.

**Body** (один из вариантов):
```json
{
  "permission_ids": [1, 3, 5]
}
```
или
```json
{
  "permission_codes": ["manage_department", "assign_department_role", "view_request"]
}
```

**Логика**:
```python
@action(detail=True, methods=["post"])
def set_perms(self, request, pk=None):
    role = self.get_object()
    
    ids = request.data.get("permission_ids") or []
    codes = request.data.get("permission_codes") or []
    
    if isinstance(ids, list) and ids:
        ids_int = {int(i) for i in ids if str(i).isdigit()}
        qs = DepartmentPermission.objects.filter(id__in=ids_int)
        if qs.count() != len(ids_int):
            return Response({"detail": "Некоторые permission_ids не найдены."}, status=400)
    elif isinstance(codes, list) and codes:
        codes_set = set(codes)
        qs = DepartmentPermission.objects.filter(code__in=codes_set)
        if qs.count() != len(codes_set):
            return Response({"detail": "Некоторые permission_codes не найдены."}, status=400)
    else:
        qs = DepartmentPermission.objects.none()
    
    role.scoped_permissions.set(list(qs))  # Полная замена
    ser = self.get_serializer(role)
    return Response(ser.data, status=200)
```

**Особенности**:
- **Полная замена**: `role.scoped_permissions.set()` — удаляет старые, добавляет новые
- **Валидация**: Проверяет существование всех указанных ID/кодов
- **Приоритет**: Если указаны оба (`ids` и `codes`), используются `ids`

**Response**: `200 OK` + полные данные роли с новым набором прав

**Errors**:
- `400` — некоторые permission_ids/codes не найдены
- `403` — нет права `assign_department_role` в отделе роли

---

## 4. Система прав ViewSet

### 4.1 Матрица прав по действиям

| Action | Permission Class | Required Right | Scope Check |
|--------|-----------------|----------------|-------------|
| `list` | `IsAuthenticated()` | — | Нет |
| `retrieve` | `IsAuthenticated()` | — | Нет |
| `create` | `AssignRolePerm()` | `assign_department_role` | По `request.data['department']` |
| `update` | `AssignRolePerm()` | `assign_department_role` | По `role.department_id` |
| `partial_update` | `AssignRolePerm()` | `assign_department_role` | По `role.department_id` |
| `destroy` | `AssignRolePerm()` | `assign_department_role` | По `role.department_id` |
| `perm_choices` | `IsAuthenticated()` | — | Нет |
| `perms` | `IsAuthenticated()` | — | Нет |
| `set_perms` | `AssignRolePerm()` | `assign_department_role` | По `role.department_id` |

### 4.2 Логика AdminOrDeptAllowed

```python
class AssignRolePerm(AdminOrDeptAllowed):
    required_code = DeptPerm.ASSIGN_ROLE  # "assign_department_role"
```

**Проверка прав** (порядок):
1. **Staff/Superuser**: `user.is_staff` или `user.is_superuser` → ✅ всегда
2. **Руководитель отдела**: `Department.objects.filter(id=dept_id, head_id=user.id).exists()` → ✅
3. **Роль с правом**: 
   ```python
   EmployeeDepartment.objects.filter(
       employee_id=user.id,
       department_id=dept_id,
       is_active=True,
       role__scoped_permissions__code="assign_department_role"
   ).exists()
   ```
   → ✅

**Извлечение department_id**:
- **CREATE**: Из `request.data['department']` или `request.data['department_id']`
- **UPDATE/DESTROY**: Из `role.department_id` (объект уже загружен)

---

## 5. Оптимизация запросов

### 5.1 Prefetch в queryset

```python
queryset = (
    DepartmentRole.objects.select_related("department")
    .prefetch_related("scoped_permissions")
    .all()
)
```

**Цель**: Избежать N+1 queries при сериализации списка ролей.

**Результат**:
- 1 запрос для ролей
- 1 запрос для отделов (JOIN)
- 1 запрос для всех M2M связей с permissions

### 5.2 Сортировка

```python
ordering = ("name", "id")  # Tie-break по id для детерминированного порядка
```

**Особенность**: При одинаковых `name` порядок стабилен благодаря добавлению `id`.

---

## 6. Связь с Department endpoints

### 6.1 Department.set_member_role()

**Endpoint**: `POST /api/v1/departments/{id}/set_member_role/`

**Permission**: `AssignRolePerm()` в этом отделе

**Body**:
```json
{
  "employee_id": 42,
  "role_id": 12  // или null для снятия роли
}
```

**Логика**:
1. Проверка существования `EmployeeDepartment` (сотрудник должен быть в отделе)
2. Валидация `role.department_id == dept.id`
3. Обновление `link.role = role`
4. Если LDAP включён: синхронизация через `DirectoryService.set_member_role()`

**Отличие от DepartmentRoleViewSet**:
- `DepartmentRoleViewSet` управляет **определениями ролей** (роли как сущности)
- `Department.set_member_role()` **назначает роли сотрудникам** (привязка)

---

## 7. Проблемные места

### 7.1 Отсутствие atomic транзакций
**Проблема**: CRUD операции не обёрнуты в `@transaction.atomic`.

**Риск**: При падении между удалением старых и добавлением новых прав в `set_perms()` можно получить inconsistent state.

**Рекомендация**: Добавить `@transaction.atomic` на `create`, `update`, `destroy`, `set_perms`.

---

### 7.2 Нет защиты от изменения department
**Проблема**: Через PATCH можно попытаться изменить `department` у существующей роли.

**Последствие**: Роль может стать несогласованной с уже назначенными сотрудниками.

**Текущая защита**: Serializer не включает `department` в `read_only_fields`, но валидация зависит от БД constraint.

**Рекомендация**: Сделать `department` read-only при update:
```python
def get_serializer(self, *args, **kwargs):
    serializer = super().get_serializer(*args, **kwargs)
    if self.action in {'update', 'partial_update'}:
        serializer.fields['department'].read_only = True
    return serializer
```

---

### 7.3 Дублирование логики синхронизации permissions
**Проблема**: `_ensure_department_permissions()` вызывается и в ViewSet, и в `Department.ui_context()`.

**Следствие**: При каждом GET запросе проверяется/создаётся справочник прав.

**Рекомендация**: 
- Перенести синхронизацию в data migration или management команду
- Вызывать только при изменении `DeptPerm.CHOICES`

---

### 7.4 Нет версионирования API
**Проблема**: Backward-compat поля (`permissions`, `permissions_verbose`) добавлены без версионирования.

**Риск**: Накопление legacy полей в будущем.

**Рекомендация**: При следующем breaking change перейти на v2 API с чистой схемой.

---

## 8. Примеры использования

### 8.1 Создание роли с правами (по кодам)

```bash
POST /api/v1/department-roles/
Authorization: Bearer <token>
Content-Type: application/json

{
  "department": 5,
  "name": "Senior Developer",
  "scoped_permission_codes": [
    "manage_department",
    "assign_department_role",
    "view_request"
  ]
}
```

### 8.2 Обновление прав существующей роли

```bash
POST /api/v1/department-roles/12/set_perms/
Authorization: Bearer <token>
Content-Type: application/json

{
  "permission_codes": [
    "manage_department",
    "change_department_head",
    "manage_department_events"
  ]
}
```

### 8.3 Получение ролей отдела

```bash
GET /api/v1/department-roles/?department=5&ordering=name
Authorization: Bearer <token>
```

---

## 9. Итоговая схема взаимодействия

```
┌─────────────────────────────────────────────────────────┐
│ Frontend Request                                        │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ DepartmentRoleViewSet.get_permissions()                 │
│  - list/retrieve: IsAuthenticated()                     │
│  - write ops: AssignRolePerm(AdminOrDeptAllowed)        │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ AdminOrDeptAllowed.has_permission()                     │
│  1. Check: user.is_staff/is_superuser → Allow           │
│  2. Extract dept_id from request.data or obj            │
│  3. Check: user == dept.head → Allow                    │
│  4. Check: has_dept_perm(user, dept_id, "assign_...") │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ has_dept_perm(user, dept_id, code)                      │
│  Query: EmployeeDepartment.filter(                      │
│    employee=user, department=dept_id, is_active=True,   │
│    role__scoped_permissions__code=code                  │
│  )                                                       │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ DepartmentRoleSerializer                                │
│  - Serialize role with scoped_permissions (M2M)         │
│  - Add backward-compat fields (permissions, verbose)    │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│ Response to Frontend                                    │
└─────────────────────────────────────────────────────────┘
```

---

**Следующий отчет**: [03_DEPARTMENT_ROLES_SERIALIZERS.md](./03_DEPARTMENT_ROLES_SERIALIZERS.md) — Сериализаторы и валидация
