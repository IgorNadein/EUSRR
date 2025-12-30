# Отчет: Константы и утилиты системы ролей

**Дата**: 30.12.2025  
**Анализ**: DeptPerm, _ensure_department_permissions, вспомогательные функции

---

## 1. DeptPerm — Справочник кодов прав

### Расположение
`backend/employees/constants.py` (строки 30-55)

### Структура

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

### Назначение
Единая точка истины для всех кодов прав отделов. Используется:
- В `AdminOrDeptAllowed` классах для указания `required_code`
- В `_ensure_department_permissions()` для синхронизации с БД
- В проверках прав `has_dept_perm(user, dept_id, DeptPerm.MANAGE)`

---

## 2. Категории прав

### 2.1 Управление отделом

| Код | Константа | Описание | Использование |
|-----|-----------|----------|---------------|
| `manage_department` | `DeptPerm.MANAGE` | Добавление/удаление участников | `add_member`, `remove_member` |
| `change_department_head` | `DeptPerm.CHANGE_HEAD` | Назначение руководителя | `set_head` |
| `assign_department_role` | `DeptPerm.ASSIGN_ROLE` | Назначение ролей участникам | `set_member_role`, CRUD ролей |

### 2.2 Контент отдела

| Код | Константа | Описание | Использование |
|-----|-----------|----------|---------------|
| `manage_department_events` | `DeptPerm.MANAGE_CALENDAR` | Управление календарём | CalendarViewSet |
| `publish_department_post` | `DeptPerm.CREATE_POST` | Публикация новостей | FeedViewSet |
| `manage_department_feed` | `DeptPerm.MANAGE_FEED` | Редактирование публикаций | FeedViewSet |

### 2.3 Заявки отдела

| Код | Константа | Описание | Использование |
|-----|-----------|----------|---------------|
| `view_request` | `DeptPerm.VIEW_REQUEST` | Просмотр заявлений | RequestsViewSet |
| `view_requestcomment` | `DeptPerm.VIEW_REQUESTCOMMENT` | Просмотр комментариев | RequestsViewSet |
| `add_requestcomment` | `DeptPerm.ADD_REQUESTCOMMENT` | Добавление комментариев | RequestsViewSet |
| `can_process_requests` | `DeptPerm.CAN_PROCESS_REQUESTS` | Рассмотрение заявлений | RequestsViewSet |

---

## 3. _ensure_department_permissions() — Синхронизация БД

### Расположение
`backend/employees/utils.py` (строки 91-107)

### Назначение
Идемпотентная синхронизация справочника `DepartmentPermission` с `DeptPerm.CHOICES`.

### Код

```python
def _ensure_department_permissions() -> list[dict]:
    """
    Гарантирует наличие записей DepartmentPermission на основе DeptPerm.CHOICES.
    Возвращает список словарей {id, code, name} в порядке CHOICES.
    """
    items: list[dict] = []
    # пробежимся по CHOICES, создадим/обновим имя, соберём выдачу
    for code, label in DeptPerm.CHOICES:
        obj, _ = DepartmentPermission.objects.get_or_create(
            code=code, defaults={"name": label}
        )
        # если имя в БД отстаёт от CHOICES — мягко синхронизируем
        if obj.name != label:
            obj.name = label
            obj.save(update_fields=["name"])
        items.append({"id": obj.id, "code": obj.code, "name": obj.name})
    return items
```

### Логика работы

```
Для каждого (code, label) в DeptPerm.CHOICES:
    ↓
1. get_or_create(code=code, defaults={"name": label})
    ↓
2. Если obj.name != label (имя изменилось в коде):
    ↓
   obj.name = label
   obj.save()
    ↓
3. Добавить {id, code, name} в результат
    ↓
Вернуть list[dict]
```

### Особенности

**Идемпотентность**:
- Можно вызывать многократно без побочных эффектов
- При повторном вызове не создаёт дубликаты

**Автоматическое обновление имён**:
```python
# Было в константах:
(MANAGE, "Управлять отделом")

# Изменили на:
(MANAGE, "Полное управление отделом")

# При следующем вызове _ensure_department_permissions():
obj.name = "Полное управление отделом"  # Автообновление
```

**НЕ удаляет устаревшие**:
- Если код удалён из `DeptPerm.CHOICES`, запись в БД остаётся
- Ручная очистка через admin или migration

---

### Вызовы в коде

**1. DepartmentRoleViewSet.perm_choices()**:
```python
@action(detail=False, methods=["get"])
def perm_choices(self, request):
    data = _ensure_department_permissions()
    return Response({"count": len(data), "results": data}, status=200)
```

**2. Department.ui_context()**:
```python
perm_choices = _perm_choices_synced()  # Вызывает _ensure_department_permissions
```

---

## 4. _perm_choices_synced() — Алиас для синхронизации

### Расположение
`backend/employees/utils.py` (строки 158-171)

### Код

```python
def _perm_choices_synced() -> list[dict]:
    """
    Возвращает справочник прав для ролей отдела, синхронизируя записи с DeptPerm.CHOICES.
    """
    items = []
    for code, label in DeptPerm.CHOICES:
        obj, _ = DepartmentPermission.objects.get_or_create(
            code=code, defaults={"name": label}
        )
        if obj.name != label:
            obj.name = label
            obj.save(update_fields=["name"])
        items.append({"id": obj.id, "code": obj.code, "name": obj.name})
    return items
```

### Назначение
Дубликат `_ensure_department_permissions()` с другим именем. Используется в `Department.ui_context()`.

### Проблема
Две функции делают одно и то же → техдолг.

---

## 5. _head_choices_for_dept() — Кандидаты на руководителя

### Расположение
`backend/employees/utils.py` (строки 110-155)

### Назначение
Возвращает список сотрудников, которые могут быть назначены руководителями отдела.

### Код

```python
def _head_choices_for_dept(dept: Department, serializer) -> list[dict]:
    """
    Вернёт список кандидатов для назначения руководителя отдела.
    
    Формат элемента:
      {
        "id": int,            # ID сотрудника
        "name": str,          # display_name из EmployeeBriefSerializer
        "email": str          # email сотрудника (может быть пустой строкой)
      }
    """
    choices, seen = [], set()
    qs = (
        EmployeeDepartment.objects.filter(department_id=dept.id)
        .select_related("employee")
        .order_by(
            "employee__last_name",
            "employee__first_name",
            "employee__patronymic",
            "employee_id",
        )
    )
    for link in qs:
        data = serializer(link.employee).data
        if data["id"] not in seen:
            choices.append(
                {
                    "id": data["id"],
                    "name": data["display_name"],
                    "email": data.get("email", "") or "",
                }
            )
            seen.add(data["id"])
    
    # Если текущий руководитель не в списке членов → добавить в начало
    if dept.head_id and dept.head_id not in seen:
        head_data = serializer(dept.head).data
        choices.insert(
            0,
            {
                "id": head_data["id"],
                "name": head_data["display_name"],
                "email": head_data.get("email", "") or "",
            },
        )
    
    return choices
```

### Логика

```
1. Получить всех членов отдела (EmployeeDepartment)
   ↓
2. Сортировка: last_name, first_name, patronymic, id
   ↓
3. Для каждого члена:
   - Сериализовать employee
   - Если id уже в seen → пропустить (дедупликация)
   - Добавить {id, name, email} в choices
   ↓
4. Если текущий head не в choices:
   - Сериализовать dept.head
   - Вставить в начало списка
   ↓
5. Вернуть choices
```

### Особенности

**Дедупликация через seen**:
- Защита от дублей при некорректных данных

**Текущий руководитель всегда в списке**:
- Даже если не является членом отдела
- Вставляется в позицию 0 (первый элемент)

**Сортировка по ФИО**:
- Удобный порядок для UI dropdown

---

## 6. _build_links_for_dept() — Список участников отдела

### Расположение
`backend/employees/utils.py` (строки 174-203)

### Назначение
Возвращает полную информацию о членстве сотрудников в отделе (для UI).

### Код (начало)

```python
def _build_links_for_dept(dept: Department, serializer) -> list[dict]:
    """
    Возвращает список линков отдела:
    [{
      "employee": <EmployeeBriefSerializer.data>,
      "role": {"id","name"}|None,
      "is_active": bool
    }, ...]
    """
    links: list[dict] = []
    qs = (
        EmployeeDepartment.objects.filter(department_id=dept.id)
        .select_related("employee", "role")
        .order_by(
            "employee__last_name",
            "employee__first_name",
            "employee__patronymic",
            "employee_id",
        )
    )
    for link in qs:
        emp_data = serializer(link.employee).data
        role_data = None
        if link.role:
            role_data = {"id": link.role.id, "name": link.role.name}
        
        links.append({
            "employee": emp_data,
            "role": role_data,
            "is_active": link.is_active,
        })
    
    return links
```

### Формат ответа

```json
[
  {
    "employee": {
      "id": 42,
      "display_name": "Иванов Иван Иванович",
      "email": "ivanov@example.com",
      "position": "Разработчик"
    },
    "role": {
      "id": 12,
      "name": "Tech Lead"
    },
    "is_active": true
  },
  {
    "employee": {
      "id": 43,
      "display_name": "Петров Пётр",
      "email": "petrov@example.com"
    },
    "role": null,
    "is_active": true
  }
]
```

### Использование

**В Department.members()**:
```python
@action(detail=True, methods=["get"], url_path="members")
def members(self, request, pk=None):
    dept = self.get_object()
    links = _build_links_for_dept(dept, EmployeeBriefSerializer)
    return Response({"count": len(links), "results": links}, status=200)
```

**В Department.ui_context()**:
```python
links = _build_links_for_dept(dept, EmployeeBriefSerializer)
payload = {
    "dept": dept_data,
    "roles": roles_data,
    "links": links,  # ← здесь
    ...
}
```

---

## 7. Проблемные места

### 7.1 Дублирование _ensure и _perm_choices_synced

**Проблема**: Две идентичные функции.

```python
# _ensure_department_permissions()
for code, label in DeptPerm.CHOICES:
    obj, _ = DepartmentPermission.objects.get_or_create(...)
    # ... логика ...

# _perm_choices_synced()
for code, label in DeptPerm.CHOICES:
    obj, _ = DepartmentPermission.objects.get_or_create(...)
    # ... та же логика ...
```

**Решение**: Удалить одну, использовать алиас:
```python
_perm_choices_synced = _ensure_department_permissions
```

---

### 7.2 N+1 запросов в _build_links_for_dept

**Проблема**: Для каждого link вызывается `serializer(link.employee).data`.

**Текущая защита**: `select_related("employee", "role")` — предзагрузка.

**Оптимизация**: Использовать `prefetch_related` для вложенных данных:
```python
qs = (
    EmployeeDepartment.objects.filter(department_id=dept.id)
    .select_related("employee", "role", "employee__position")
    .prefetch_related("employee__skills")
)
```

---

### 7.3 Частые вызовы синхронизации

**Проблема**: `_ensure_department_permissions()` вызывается при каждом GET запросе к `/perm_choices/` и `/ui-context/`.

**Следствие**:
- Множественные `get_or_create` даже когда ничего не изменилось
- Нагрузка на БД

**Решение**: Кешировать результат:
```python
from django.core.cache import cache

def _ensure_department_permissions() -> list[dict]:
    cache_key = "dept_permissions_v1"
    cached = cache.get(cache_key)
    if cached:
        return cached
    
    items = []
    for code, label in DeptPerm.CHOICES:
        obj, _ = DepartmentPermission.objects.get_or_create(...)
        # ...
        items.append(...)
    
    cache.set(cache_key, items, timeout=3600)  # 1 час
    return items
```

**Инвалидация кеша**: При изменении `DeptPerm.CHOICES` (редко).

---

### 7.4 Нет защиты от удалённых кодов

**Проблема**: Если код удалён из `DeptPerm.CHOICES`, запись в БД остаётся.

**Сценарий**:
```python
# Было:
SOME_PERM = "some_permission"
CHOICES = (..., (SOME_PERM, "Какое-то право"), ...)

# Стало (удалили):
CHOICES = (..., (OTHER_PERM, "Другое право"), ...)
```

**Следствие**:
- В БД остаётся `DepartmentPermission(code="some_permission")`
- Роли могут ссылаться на устаревшее право
- Проверки прав будут работать, но семантика нарушена

**Решение**: Data migration при удалении кодов:
```python
def remove_obsolete_permission(apps, schema_editor):
    DepartmentPermission = apps.get_model('employees', 'DepartmentPermission')
    DepartmentPermission.objects.filter(code='some_permission').delete()
```

---

### 7.5 Жёсткая зависимость от serializer в utils

**Проблема**: Функции принимают `serializer` как параметр:
```python
def _build_links_for_dept(dept: Department, serializer) -> list[dict]:
    # ... использует serializer(link.employee).data
```

**Следствие**:
- Функция не может работать без сериализатора
- Сложно тестировать в изоляции

**Решение**: Передавать функцию преобразования или использовать словари:
```python
def _build_links_for_dept(dept: Department, transform_fn=None) -> list[dict]:
    if transform_fn is None:
        transform_fn = lambda emp: {"id": emp.id, "name": emp.get_full_name()}
    # ...
```

---

## 8. Использование констант в коде

### 8.1 В Permission Classes

```python
class ManagePerm(AdminOrDeptAllowed):
    required_code = DeptPerm.MANAGE  # ← использование константы

class AssignRolePerm(AdminOrDeptAllowed):
    required_code = DeptPerm.ASSIGN_ROLE
```

### 8.2 В проверках прав

```python
if has_dept_perm(request.user, dept.id, DeptPerm.MANAGE):
    # Разрешено управление отделом
    ...
```

### 8.3 В тестах

```python
def test_manage_perm_required():
    ensure_dept_perm(DeptPerm.MANAGE, "Управлять отделом")
    role = make_role(dept, "Manager", [DeptPerm.MANAGE])
    # ...
```

---

## 9. Рекомендации по улучшению

### 9.1 Унифицировать функции синхронизации

```python
# Оставить одну функцию
def ensure_department_permissions() -> list[dict]:
    # ... логика ...

# Создать алиас для обратной совместимости
_ensure_department_permissions = ensure_department_permissions
_perm_choices_synced = ensure_department_permissions
```

### 9.2 Добавить management команду

```python
# employees/management/commands/sync_dept_permissions.py
class Command(BaseCommand):
    def handle(self, *args, **options):
        items = _ensure_department_permissions()
        self.stdout.write(f"Synced {len(items)} permissions")
```

**Использование**:
```bash
python manage.py sync_dept_permissions
```

### 9.3 Логировать изменения

```python
def _ensure_department_permissions() -> list[dict]:
    items = []
    for code, label in DeptPerm.CHOICES:
        obj, created = DepartmentPermission.objects.get_or_create(...)
        if created:
            logger.info(f"Created DepartmentPermission: {code}")
        elif obj.name != label:
            logger.info(f"Updated name: {code} '{obj.name}' → '{label}'")
            obj.name = label
            obj.save()
        items.append(...)
    return items
```

### 9.4 Типизация возвращаемых значений

```python
from typing import TypedDict

class PermChoiceDict(TypedDict):
    id: int
    code: str
    name: str

def _ensure_department_permissions() -> list[PermChoiceDict]:
    # ...
```

---

## 10. Итоговая схема взаимодействия

```
┌───────────────────────────────────┐
│ DeptPerm.CHOICES (constants.py)   │
│  - Single source of truth         │
└───────────────────────────────────┘
            ↓
┌───────────────────────────────────┐
│ _ensure_department_permissions()  │
│  - Sync DB with constants         │
│  - Create missing entries         │
│  - Update names                   │
└───────────────────────────────────┘
            ↓
┌───────────────────────────────────┐
│ DepartmentPermission (DB table)   │
│  - Persistent storage             │
│  - Referenced by roles via M2M    │
└───────────────────────────────────┘
            ↓
┌───────────────────────────────────┐
│ DepartmentRole.scoped_permissions │
│  - M2M to DepartmentPermission    │
└───────────────────────────────────┘
            ↓
┌───────────────────────────────────┐
│ EmployeeDepartment.role           │
│  - FK to DepartmentRole           │
└───────────────────────────────────┘
            ↓
┌───────────────────────────────────┐
│ has_dept_perm() checks            │
│  - Query: role__scoped_perm__code │
└───────────────────────────────────┘
```

---

**Следующий отчет**: [06_DEPARTMENT_ROLES_LDAP.md](./06_DEPARTMENT_ROLES_LDAP.md) — LDAP интеграция
