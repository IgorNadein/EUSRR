# Отчет: Тестовое покрытие системы ролей

**Дата**: 30.12.2025  
**Анализ**: Тестовые файлы, покрытие функциональности, сценарии

---

## 1. Обзор тестовых файлов

### Основные тестовые файлы

| Файл | Строк | Назначение |
|------|-------|------------|
| **test_department_roles.py** | ~306 | CRUD операций ролей, права, фильтрация |
| **test_department_roles_extra.py** | ~304 | Расширенные сценарии: сортировка, staff override |
| **test_department_membership_separation.py** | ~496 | Разделение add_member vs set_role |
| **test_department_head_rights.py** | ~200 | Права руководителя отдела |

**Общее количество**: ~1300 строк тестового кода для системы ролей.

---

## 2. test_department_roles.py — Основные CRUD

### Расположение
`backend/tests/api/v1/employees/test_department_roles.py`

### Покрываемая функциональность

#### 2.1 Фильтрация по отделу

```python
def test_list_filtered_by_department(api_client: APIClient):
    d1 = Department.objects.create(name="Dept A")
    d2 = Department.objects.create(name="Dept B")
    
    r1 = make_role(d1, "Engineer", [])
    r2 = make_role(d1, "Manager", [])
    r3 = make_role(d2, "Sales", [])
    
    # Без фильтра — все 3
    resp = api_client.get(url)
    assert ids == {r1.id, r2.id, r3.id}
    
    # С фильтром по d1 — только роли d1
    resp = api_client.get(url, {"department": d1.id})
    assert ids == {r1.id, r2.id}
```

**Проверяет**:
- Query param `?department=<id>` работает
- Без фильтра возвращает все роли
- С фильтром только роли указанного отдела

---

#### 2.2 Права на создание роли

```python
def test_create_requires_assign_department_role(api_client: APIClient):
    d = Department.objects.create(name="Dept")
    user = make_user("m@example.com")
    
    # Без прав — 403
    resp = api_client.post(url, {"department": d.id, "name": "Worker"})
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    
    # Выдаём право assign_department_role
    grant_assign_in_dept(user, d)
    
    # Теперь можно создать
    resp = api_client.post(url, {"department": d.id, "name": "Worker"})
    assert resp.status_code == status.HTTP_201_CREATED
```

**Проверяет**:
- `AssignRolePerm()` блокирует без прав
- С правом `assign_department_role` → создание разрешено
- Backward-compat поля присутствуют в ответе

---

#### 2.3 Scope-based права (update/destroy)

```python
def test_update_and_destroy_scope_enforced(api_client: APIClient):
    d1 = Department.objects.create(name="Dept1")
    d2 = Department.objects.create(name="Dept2")
    role_other = make_role(d2, "Other", [])
    
    # Нет прав в d2 → 403
    resp = api_client.patch(url_detail_other, {"name": "X"})
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    
    # Права в d1 — всё ещё 403 для d2
    grant_assign_in_dept(user, d1)
    resp = api_client.patch(url_detail_other, {"name": "X"})
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    
    # Права в d2 — теперь можно
    grant_assign_in_dept(user, d2)
    resp = api_client.patch(url_detail_other, {"name": "X"})
    assert resp.status_code == status.HTTP_200_OK
```

**Проверяет**:
- Права проверяются по **отделу роли**, а не глобально
- Право в отделе A не даёт доступ к ролям отдела B
- Destroy также требует право в отделе роли

---

#### 2.4 Работа с правами через API

```python
def test_perm_choices_and_perms_and_set_perms(api_client: APIClient):
    # 1. perm_choices — справочник
    resp = api_client.get(url_choices)
    codes = {row["code"] for row in resp.json().get("results", [])}
    assert {"manage_department", "assign_department_role"}.issubset(codes)
    
    # 2. set_perms — установка прав по кодам
    role = make_role(d, "Engineer", [])
    resp = api_client.post(
        url_set,
        {"permission_codes": ["manage_department", "assign_department_role"]}
    )
    assert resp.status_code == 200
    
    # 3. Проверка permissions_verbose
    verbose = {p["code"] for p in resp.json().get("permissions_verbose", [])}
    assert verbose == {"manage_department", "assign_department_role"}
```

**Проверяет**:
- `/perm_choices/` возвращает все доступные права
- `/set_perms/` заменяет права роли
- `permission_codes` работает (альтернатива ID)
- `permissions_verbose` содержит полную информацию

---

## 3. test_department_roles_extra.py — Дополнительные сценарии

### 3.1 Неавторизованный доступ

```python
def test_unauth_cannot_list_or_get():
    client = APIClient()  # Без force_authenticate
    assert client.get(url_list).status_code in (401, 403)
```

**Проверяет**: Неавторизованные запросы блокируются.

---

### 3.2 Read-only без прав

```python
def test_read_only_allowed_without_assign(api_client: APIClient):
    r = make_role(d, "Worker", [])
    u = make_user("u@example.com")
    api_client.force_authenticate(user=u)
    
    # list разрешён
    resp = api_client.get(url_list, {"department": d.id})
    assert resp.status_code == 200
    
    # retrieve разрешён
    assert api_client.get(url_detail).status_code == 200
```

**Проверяет**:
- GET операции (list/retrieve) доступны всем аутентифицированным
- Write операции требуют специальных прав

---

### 3.3 Staff override

```python
def test_staff_override_for_write(api_client: APIClient):
    staff = make_user("s@example.com", staff=True)
    api_client.force_authenticate(user=staff)
    
    # create без роли в отделе
    resp = api_client.post(url_list, {"department": d.id, "name": "SRole"})
    assert resp.status_code == 201
    
    # update
    assert api_client.patch(url_detail, {"name": "SRole+"}).status_code == 200
    
    # set_perms
    assert api_client.post(url_set, {"permission_codes": [...]}).status_code == 200
```

**Проверяет**:
- `user.is_staff` обходит проверки прав
- Staff может управлять любыми ролями в любых отделах

---

### 3.4 Стабильная сортировка

```python
def test_ordering_stable_by_name_then_id(api_client: APIClient):
    # Роли с одинаковыми именами в разных отделах
    r1 = make_role(d1, "A", [])
    r2 = make_role(d2, "A", [])  # Одинаковое имя
    r3 = make_role(d1, "B", [])
    
    resp = api_client.get(url, {"ordering": "name"})
    items = resp.json().get("results", [])
    
    # Сортировка: name, затем id (tie-break)
    assert items[0]["name"] == "A" and items[0]["id"] < items[1]["id"]
    assert items[2]["name"] == "B"
```

**Проверяет**:
- При одинаковых `name` порядок детерминирован (по `id`)
- `ordering=name` работает корректно

---

## 4. test_department_membership_separation.py — Разделение операций

### Назначение
Проверяет, что `add_member` и `set_member_role` — **разные операции** с разными правами.

---

### 4.1 add_member не назначает роль

```python
def test_add_member_requires_manage_and_does_not_assign_role(api_client):
    d = Department.objects.create(name="Dept")
    target = make_user("target@example.com")
    
    # 403 с правом assign_department_role (но без manage)
    assigner = make_user("assigner@example.com")
    grant_assign_in_dept(assigner, d)
    resp = api_client.post(url, {"employee_id": target.id})
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    
    # 200 с manage_department
    manager = make_user("manager@example.com")
    grant_manage_in_dept(manager, d)
    resp = api_client.post(url, {"employee_id": target.id})
    assert resp.status_code == status.HTTP_200_OK
    
    # Роль НЕ назначена
    link = EmployeeDepartment.objects.get(employee_id=target.id)
    assert link.role_id is None
```

**Проверяет**:
- `add_member` требует `manage_department`, а не `assign_department_role`
- После добавления `role = None`
- Разделение ответственности операций

---

### 4.2 set_member_role требует assign_role

```python
def test_set_member_role_requires_assign_and_works_only_for_members(api_client):
    d = Department.objects.create(name="Dept")
    target = make_user("target@example.com")
    role = make_role(d, "Worker", [])
    
    # add_member сначала
    manager = make_user("manager@example.com")
    grant_manage_in_dept(manager, d)
    api_client.post(url_add_member, {"employee_id": target.id})
    
    # set_member_role с правом assign
    assigner = make_user("assigner@example.com")
    grant_assign_in_dept(assigner, d)
    resp = api_client.post(url_set_role, {
        "employee_id": target.id,
        "role_id": role.id
    })
    assert resp.status_code == status.HTTP_200_OK
    
    # Роль назначена
    link = EmployeeDepartment.objects.get(employee_id=target.id)
    assert link.role_id == role.id
```

**Проверяет**:
- `set_member_role` требует `assign_department_role`
- Можно назначить роль только **существующему** члену отдела
- Роль действительно устанавливается

---

### 4.3 Нельзя назначить роль несуществующему члену

```python
def test_set_member_role_fails_if_not_member(api_client):
    target = make_user("target@example.com")
    # Не добавляем в отдел!
    
    assigner = make_user("assigner@example.com")
    grant_assign_in_dept(assigner, d)
    
    resp = api_client.post(url_set_role, {
        "employee_id": target.id,
        "role_id": role.id
    })
    assert resp.status_code == status.HTTP_404_NOT_FOUND
    assert "not a member" in resp.json()["detail"].lower()
```

**Проверяет**: 404 если сотрудник не в отделе.

---

### 4.4 Валидация принадлежности роли

```python
def test_set_member_role_fails_if_role_from_different_department(api_client):
    d1 = Department.objects.create(name="Dept1")
    d2 = Department.objects.create(name="Dept2")
    role_d2 = make_role(d2, "Worker", [])
    
    target = make_user("target@example.com")
    # Добавляем в d1
    add_member(target, d1)
    
    # Пытаемся назначить роль из d2
    assigner = make_user("assigner@example.com")
    grant_assign_in_dept(assigner, d1)
    
    resp = api_client.post(url_set_role_d1, {
        "employee_id": target.id,
        "role_id": role_d2.id  # Роль из другого отдела!
    })
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert "does not belong" in resp.json()["role_id"][0].lower()
```

**Проверяет**: Нельзя назначить роль из другого отдела.

---

## 5. test_department_head_rights.py — Права руководителя

### 5.1 Руководитель может обновлять отдел

```python
def test_head_can_update_department_without_explicit_role_perms(api_client):
    head = make_user("head@example.com")
    d = Department.objects.create(name="Dept", head=head)
    
    api_client.force_authenticate(user=head)
    resp = api_client.patch(url, {"description": "new"})
    assert resp.status_code == status.HTTP_200_OK
```

**Проверяет**:
- Руководителю не нужна роль для управления отделом
- `dept.head == user` → все права автоматически

---

### 5.2 Руководитель может назначать роли

```python
def test_head_can_set_member_role_and_non_head_cannot(api_client):
    head = make_user("head@example.com")
    d = Department.objects.create(name="Dept", head=head)
    worker = make_user("worker@example.com")
    add_member(worker, d)
    
    # Руководитель назначает роль
    api_client.force_authenticate(user=head)
    resp = api_client.post(url, {"employee_id": worker.id, "role_id": role.id})
    assert resp.status_code == status.HTTP_200_OK
    
    # Другой пользователь — не может
    stranger = make_user("stranger@example.com")
    api_client.force_authenticate(user=stranger)
    resp = api_client.post(url, {"employee_id": worker.id, "role_id": role.id})
    assert resp.status_code == status.HTTP_403_FORBIDDEN
```

**Проверяет**:
- Руководитель имеет право `assign_department_role` автоматически
- Обычный пользователь без роли — запрещено

---

### 5.3 Руководитель теряет права после смены

```python
def test_head_can_change_head_and_loses_rights_afterwards(api_client):
    old_head = make_user("old@example.com")
    d = Department.objects.create(name="Dept", head=old_head)
    new_head = make_user("new@example.com")
    
    # Старый руководитель меняет руководителя
    api_client.force_authenticate(user=old_head)
    resp = api_client.post(url_set_head, {"head_id": new_head.id})
    assert resp.status_code == status.HTTP_200_OK
    
    # Старый больше не глава — нет прав
    resp = api_client.patch(url_detail, {"description": "after"})
    assert resp.status_code == status.HTTP_403_FORBIDDEN
    
    # У нового руководителя — есть
    api_client.force_authenticate(user=new_head)
    resp = api_client.patch(url_detail, {"description": "ok"})
    assert resp.status_code == status.HTTP_200_OK
```

**Проверяет**:
- Смена руководителя мгновенно лишает старого всех прав
- Новый руководитель сразу получает полный доступ

---

## 6. Вспомогательные функции (Helpers)

### Общие для всех тестов

```python
def make_user(email: str, staff: bool = False) -> User:
    """Создаёт пользователя с уникальным phone_number."""
    return User.objects.create_user(
        email=email,
        password="pwd12345",
        phone_number=_unique_phone(),
        send_activation_email=False,
    )

def make_role(dept: Department, name: str, codes: list[str] | None = None) -> DepartmentRole:
    """Создаёт роль с указанными правами."""
    role = DepartmentRole.objects.create(department=dept, name=name)
    if codes:
        perms = [ensure_dept_perm(c) for c in codes]
        role.scoped_permissions.add(*perms)
    return role

def grant_assign_in_dept(user: User, dept: Department) -> DepartmentRole:
    """Выдаёт пользователю роль с правом assign_department_role."""
    role = make_role(dept, "assigner", ["assign_department_role"])
    EmployeeDepartment.objects.update_or_create(
        employee=user, department=dept,
        defaults={"is_active": True, "role": role},
    )
    return role
```

### Назначение
- **make_user**: Создание тестовых пользователей с уникальными phone
- **make_role**: Быстрое создание ролей с правами
- **grant_assign_in_dept**: Выдача прав для тестирования

---

## 7. Покрытие функциональности

### Что покрыто ✅

| Функциональность | Тесты | Статус |
|------------------|-------|--------|
| **CRUD ролей** | test_department_roles.py | ✅ Полное |
| **Фильтрация по отделу** | test_list_filtered_by_department | ✅ |
| **Проверка прав create/update/destroy** | test_create_requires_assign, test_update_and_destroy_scope_enforced | ✅ |
| **set_perms API** | test_perm_choices_and_perms_and_set_perms | ✅ |
| **Backward compatibility** | Проверка permissions/permissions_verbose | ✅ |
| **Staff override** | test_staff_override_for_write | ✅ |
| **Сортировка** | test_ordering_stable_by_name_then_id | ✅ |
| **Разделение add_member / set_role** | test_department_membership_separation.py | ✅ Полное |
| **Права руководителя** | test_department_head_rights.py | ✅ Полное |
| **Валидация роли отдела** | test_set_member_role_fails_if_role_from_different_department | ✅ |

---

### Что НЕ покрыто ❌

| Функциональность | Причина |
|------------------|---------|
| **LDAP синхронизация** | Требует mock LDAP сервера |
| **Concurrent updates** | Нет тестов на race conditions |
| **Массовое назначение ролей** | Нет bulk operations |
| **Удаление роли при наличии назначений** | Проверка CASCADE/SET_NULL |
| **Лимиты на количество ролей** | Нет ограничений в коде |
| **Производительность с большим числом ролей** | Нет load tests |
| **Миграция прав при изменении DeptPerm.CHOICES** | Ручной процесс |

---

## 8. Проблемные места в тестах

### 8.1 Дублирование helper функций

**Проблема**: В каждом тестовом файле свои `make_user()`, `make_role()`, `_unique_phone()`.

**Следствие**: При изменении логики нужно обновлять 4 файла.

**Решение**: Вынести в `conftest.py`:
```python
# tests/api/v1/employees/conftest.py
@pytest.fixture
def make_user():
    def _make(email, staff=False):
        # ... общая логика ...
    return _make
```

---

### 8.2 Отсутствие интеграционных тестов

**Проблема**: Тесты проверяют API endpoints, но не полный workflow.

**Пример недостающего теста**:
```python
def test_full_role_assignment_workflow():
    # 1. Создать отдел
    # 2. Добавить сотрудников
    # 3. Создать роль с правами
    # 4. Назначить роль сотруднику
    # 5. Проверить, что сотрудник может выполнить действие
    # 6. Изменить права роли
    # 7. Проверить, что изменения применились
    # 8. Удалить роль
    # 9. Проверить, что сотрудник потерял права
```

---

### 8.3 Нет тестов на граничные случаи

**Примеры**:
- Назначение 1000 ролей одному отделу
- Роль с 0 прав (пустой scoped_permissions)
- Роль с дублирующимся именем (после изменения department)
- Одновременное создание ролей с одинаковым именем (race)

---

### 8.4 Отсутствие тестов на ошибки валидации

**Примеры**:
- `{"scoped_permission_codes": ["nonexistent_code"]}`
- `{"scoped_permissions": [9999999]}` (несуществующий ID)
- `{"name": ""}` (пустое имя)
- `{"name": "A" * 200}` (превышение max_length)

---

## 9. Рекомендации по улучшению тестов

### 9.1 Добавить фабрики (Factory Boy)

```python
import factory

class DepartmentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Department
    name = factory.Sequence(lambda n: f"Department {n}")

class DepartmentRoleFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = DepartmentRole
    department = factory.SubFactory(DepartmentFactory)
    name = factory.Sequence(lambda n: f"Role {n}")

# Использование:
dept = DepartmentFactory()
role = DepartmentRoleFactory(department=dept)
```

---

### 9.2 Добавить параметризованные тесты

```python
@pytest.mark.parametrize("method,action", [
    ("post", "create"),
    ("patch", "update"),
    ("delete", "destroy"),
])
def test_requires_assign_role_perm(api_client, method, action):
    # ... общая логика для всех write операций ...
```

---

### 9.3 Добавить тесты на производительность

```python
def test_list_roles_performance_with_many_roles(api_client):
    dept = Department.objects.create(name="Dept")
    
    # Создать 1000 ролей
    for i in range(1000):
        make_role(dept, f"Role{i}", [])
    
    # Замерить время
    import time
    start = time.time()
    resp = api_client.get(url, {"department": dept.id})
    duration = time.time() - start
    
    assert resp.status_code == 200
    assert duration < 1.0  # Должно быть быстрее 1 секунды
```

---

### 9.4 Мокировать LDAP для тестов

```python
from unittest.mock import patch

@patch('employees.ldap.directory_service._is_ldap_enabled', return_value=True)
@patch('employees.ldap.directory_service.DirectoryService.set_member_role')
def test_set_member_role_calls_ldap(mock_set_role, mock_enabled, api_client):
    # Тест проверяет, что при включённом LDAP вызывается синхронизация
    # ...
    assert mock_set_role.called
```

---

## 10. Итоговая оценка покрытия

### Метрики

- **Количество тестовых файлов**: 4
- **Количество тестов**: ~20-25
- **Покрытие функциональности**: ~70%
- **Покрытие кода**: (требуется `pytest --cov`)

### Сильные стороны

✅ Хорошее покрытие основных CRUD операций  
✅ Проверка системы прав (scoped permissions)  
✅ Разделение ответственности (add_member vs set_role)  
✅ Проверка прав руководителя  
✅ Backward compatibility

### Слабые стороны

❌ Нет LDAP-тестов  
❌ Нет интеграционных тестов  
❌ Нет граничных случаев  
❌ Нет load/performance тестов  
❌ Дублирование helpers

---

**Финальный отчет**: [08_DEPARTMENT_ROLES_ARCHITECTURE.md](./08_DEPARTMENT_ROLES_ARCHITECTURE.md) — Архитектура и рекомендации
