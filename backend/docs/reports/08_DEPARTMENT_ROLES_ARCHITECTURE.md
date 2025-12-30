# Финальный отчет: Архитектура системы ролей и план рефакторинга

**Дата**: 30.12.2025  
**Итоговый анализ**: Текущее состояние, проблемы, план полной переработки

---

## 1. Executive Summary

### Текущее состояние

Система ролей отделов представляет собой **двухуровневую модель прав**:
- Django model permissions (глобальные)
- Scoped permissions (в рамках отдела)

**Ключевые компоненты**:
- 3 модели данных (DepartmentRole, DepartmentPermission, EmployeeDepartment)
- 10 типов прав (DeptPerm.CHOICES)
- LDAP-интеграция (опциональная)
- REST API с проверкой прав
- ~70% покрытие тестами

### Основные проблемы

🔴 **Критические**:
1. Двойная логика (if LDAP/else) во всём коде
2. Дублирование функций проверки прав
3. Best-effort LDAP без компенсации ошибок
4. Отсутствие транзакций в критических операциях

🟡 **Важные**:
5. Смешение уровней прав (Django + scoped)
6. Автосинхронизация permissions без миграций
7. Backward-compat поля увеличивают размер ответов
8. Нет кеширования проверок прав

---

## 2. Архитектура: Текущая vs Целевая

### 2.1 Текущая архитектура

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer (Views)                    │
│  - DepartmentRoleViewSet                                │
│  - DepartmentViewSet.set_member_role()                  │
│  - Inline: if _is_ldap_enabled() → branch logic         │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│               Permission Checks (Mixed)                  │
│  - AdminOrDeptAllowed (DRF BasePermission)              │
│  - has_dept_perm() — by ID                              │
│  - user_has_dept_perm() — by object                     │
│  - Staff/Head shortcuts                                 │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│              Business Logic (Scattered)                  │
│  - Serializers (create/update with M2M)                 │
│  - Utils (_ensure_permissions, _build_links)            │
│  - DirectoryService (LDAP sync)                         │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│                  Data Layer (Models)                    │
│  - DepartmentRole, DepartmentPermission                 │
│  - EmployeeDepartment (link with role FK)               │
│  - LdapSyncState                                        │
└─────────────────────────────────────────────────────────┘
```

**Проблемы**:
- Нет чёткого разделения слоёв
- Бизнес-логика размазана между Views, Serializers, Utils
- LDAP-логика смешана с основной

---

### 2.2 Целевая архитектура (Clean Architecture)

```
┌─────────────────────────────────────────────────────────┐
│                    API Layer (Thin)                     │
│  - DepartmentRoleViewSet                                │
│  - Маршрутизация → Service Layer                       │
│  - Валидация input (Serializers)                       │
│  - Форматирование output                               │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│              Service Layer (Use Cases)                  │
│  - RoleManagementService                                │
│    • create_role(dept, name, permissions)               │
│    • assign_role_to_member(dept, employee, role)        │
│    • update_role_permissions(role, permissions)         │
│    • delete_role(role)                                  │
│  - Permission checking here                             │
│  - Transaction boundaries                               │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│          Infrastructure Layer (Backends)                │
│  - DepartmentRoleBackend (Interface)                    │
│    ├── LdapRoleBackend (LDAP sync)                      │
│    └── DbOnlyRoleBackend (DB only)                      │
│  - Injected via DI                                      │
└─────────────────────────────────────────────────────────┘
                         ↓
┌─────────────────────────────────────────────────────────┐
│              Domain Layer (Models + Logic)              │
│  - DepartmentRole, DepartmentPermission                 │
│  - EmployeeDepartment                                   │
│  - Domain logic in model methods                        │
└─────────────────────────────────────────────────────────┘
```

**Преимущества**:
- Чёткое разделение ответственности
- Testable (service layer с mock backends)
- Легко добавить новые backends (Redis, External API)
- Транзакции на уровне use cases

---

## 3. Детальный план рефакторинга

### Фаза 1: Подготовка (1-2 дня)

#### 1.1 Унификация проверки прав

**Текущее состояние**: Две функции (`has_dept_perm` и `user_has_dept_perm`) делают одно и то же.

**Действия**:
```python
# Новая унифицированная функция
def check_dept_permission(
    user: User,
    department: Department | int,
    permission_code: str
) -> bool:
    """Unified permission check supporting both object and ID."""
    if isinstance(department, int):
        dept_id = department
    else:
        dept_id = department.id
    
    # Единая логика проверки
    if user.is_staff or user.is_superuser:
        return True
    
    if Department.objects.filter(id=dept_id, head_id=user.id).exists():
        return True
    
    return EmployeeDepartment.objects.filter(
        employee_id=user.id,
        department_id=dept_id,
        is_active=True,
        role__scoped_permissions__code=permission_code
    ).exists()

# Обратная совместимость
has_dept_perm = check_dept_permission
user_has_dept_perm = lambda u, dept, code: check_dept_permission(u, dept, code)
```

---

#### 1.2 Объединение _ensure и _perm_choices_synced

**Действия**:
```python
def ensure_department_permissions() -> list[dict]:
    """Single source for permission sync."""
    # ... логика ...

# Удалить дубликат _perm_choices_synced
# Заменить все вызовы на ensure_department_permissions()
```

---

#### 1.3 Добавить кеширование проверок прав

**Действия**:
```python
from functools import lru_cache

@lru_cache(maxsize=256)
def _check_dept_permission_cached(
    user_id: int,
    dept_id: int,
    permission_code: str
) -> bool:
    # ... логика проверки ...

def check_dept_permission(user, department, permission_code):
    # Validate inputs
    # Call cached version
    return _check_dept_permission_cached(user.id, dept_id, permission_code)
```

---

### Фаза 2: Service Layer (3-5 дней)

#### 2.1 Создать RoleManagementService

```python
# employees/services/role_management.py

class RoleManagementService:
    def __init__(self, backend: RoleBackend):
        self.backend = backend
    
    @transaction.atomic
    def create_role(
        self,
        department: Department,
        name: str,
        permission_codes: list[str],
        requester: User
    ) -> DepartmentRole:
        """Create a new role with permissions."""
        # 1. Check permissions
        if not check_dept_permission(requester, department, DeptPerm.ASSIGN_ROLE):
            raise PermissionDenied("User lacks assign_role permission")
        
        # 2. Validate permissions exist
        perms = DepartmentPermission.objects.filter(code__in=permission_codes)
        if perms.count() != len(set(permission_codes)):
            raise ValidationError("Some permission codes not found")
        
        # 3. Create role
        role = DepartmentRole.objects.create(
            department=department,
            name=name
        )
        role.scoped_permissions.set(perms)
        
        # 4. Sync to backend (LDAP/etc)
        self.backend.on_role_created(role)
        
        return role
    
    @transaction.atomic
    def assign_role(
        self,
        department: Department,
        employee: Employee,
        role: DepartmentRole | None,
        requester: User
    ) -> EmployeeDepartment:
        """Assign or remove role from department member."""
        # 1. Check permissions
        if not check_dept_permission(requester, department, DeptPerm.ASSIGN_ROLE):
            raise PermissionDenied()
        
        # 2. Validate member exists
        link = EmployeeDepartment.objects.filter(
            employee=employee,
            department=department
        ).first()
        if not link:
            raise NotFound("Employee not a member of department")
        
        # 3. Validate role belongs to department
        if role and role.department_id != department.id:
            raise ValidationError("Role does not belong to department")
        
        # 4. Update DB
        old_role = link.role
        link.role = role
        link.save(update_fields=['role'])
        
        # 5. Sync to backend
        try:
            self.backend.on_role_assigned(link, old_role, role)
        except BackendError as e:
            # Schedule retry
            logger.error(f"Backend sync failed: {e}")
            schedule_retry_task.delay(link.id)
        
        return link
```

---

#### 2.2 Создать Backend Interface

```python
# employees/backends/base.py

from abc import ABC, abstractmethod

class RoleBackend(ABC):
    @abstractmethod
    def on_role_created(self, role: DepartmentRole) -> None:
        """Called when a role is created."""
        pass
    
    @abstractmethod
    def on_role_deleted(self, role: DepartmentRole) -> None:
        """Called when a role is deleted."""
        pass
    
    @abstractmethod
    def on_role_assigned(
        self,
        link: EmployeeDepartment,
        old_role: DepartmentRole | None,
        new_role: DepartmentRole | None
    ) -> None:
        """Called when a role is assigned/changed."""
        pass
```

---

#### 2.3 Реализовать LdapRoleBackend

```python
# employees/backends/ldap_backend.py

class LdapRoleBackend(RoleBackend):
    def __init__(self):
        self.directory_service = DirectoryService()
    
    def on_role_created(self, role: DepartmentRole) -> None:
        """Create LDAP group for role in OU=Roles."""
        dept_dn = self._get_dept_dn(role.department)
        roles_ou = f"OU=Roles,{dept_dn}"
        group_dn = f"CN={role.name},{roles_ou}"
        
        with _ldap() as conn:
            conn.add(group_dn, ['group'], {
                'sAMAccountName': role.name,
                'description': f'Role: {role.name}'
            })
        
        role.ldap_group_dn = group_dn
        role.save(update_fields=['ldap_group_dn'])
    
    def on_role_assigned(self, link, old_role, new_role) -> None:
        """Sync user groups in LDAP."""
        user_dn = self._get_user_dn(link.employee)
        dept_dn = self._get_dept_dn(link.department)
        roles_base = f"OU=Roles,{dept_dn}"
        
        target_cns = {new_role.name} if new_role else set()
        
        with _ldap() as conn:
            sync_user_groups_by_cns(
                conn, user_dn, target_cns,
                extra_bases=[roles_base],
                do_write=True
            )
```

---

#### 2.4 Реализовать DbOnlyBackend

```python
# employees/backends/db_backend.py

class DbOnlyRoleBackend(RoleBackend):
    """No-op backend for DB-only mode."""
    
    def on_role_created(self, role: DepartmentRole) -> None:
        pass  # Nothing to do
    
    def on_role_deleted(self, role: DepartmentRole) -> None:
        pass
    
    def on_role_assigned(self, link, old_role, new_role) -> None:
        pass
```

---

#### 2.5 Dependency Injection

```python
# employees/services/__init__.py

def get_role_backend() -> RoleBackend:
    """Factory for role backend based on settings."""
    if getattr(settings, 'LDAP_ENABLED', False):
        from .backends.ldap_backend import LdapRoleBackend
        return LdapRoleBackend()
    else:
        from .backends.db_backend import DbOnlyRoleBackend
        return DbOnlyRoleBackend()

def get_role_service() -> RoleManagementService:
    """Factory for role management service."""
    backend = get_role_backend()
    return RoleManagementService(backend)
```

---

### Фаза 3: Рефакторинг API (2-3 дня)

#### 3.1 Упростить ViewSet

```python
class DepartmentRoleViewSet(viewsets.ModelViewSet):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.service = get_role_service()
    
    def create(self, request):
        dept_id = request.data.get('department')
        dept = get_object_or_404(Department, id=dept_id)
        
        role = self.service.create_role(
            department=dept,
            name=request.data['name'],
            permission_codes=request.data.get('scoped_permission_codes', []),
            requester=request.user
        )
        
        serializer = self.get_serializer(role)
        return Response(serializer.data, status=201)
```

**Преимущества**:
- View становится тонким адаптером
- Вся бизнес-логика в service
- Легко тестировать service отдельно

---

#### 3.2 Упростить Department.set_member_role()

```python
@action(detail=True, methods=["post"])
def set_member_role(self, request, pk=None):
    dept = self.get_object()
    service = get_role_service()
    
    payload = SetMemberRoleInput(data=request.data)
    payload.is_valid(raise_exception=True)
    
    employee = get_object_or_404(Employee, id=payload.validated_data['employee_id'])
    role_id = payload.validated_data.get('role_id')
    role = get_object_or_404(DepartmentRole, id=role_id) if role_id else None
    
    try:
        link = service.assign_role(dept, employee, role, request.user)
        return Response({
            "employee_id": employee.id,
            "role_id": role.id if role else None,
            "is_active": link.is_active
        })
    except (PermissionDenied, NotFound, ValidationError) as e:
        return Response({"detail": str(e)}, status=...)
```

---

### Фаза 4: Миграции и очистка (1-2 дня)

#### 4.1 Data Migration для permissions

```python
# Generated migration file

def forward(apps, schema_editor):
    DepartmentPermission = apps.get_model('employees', 'DepartmentPermission')
    
    # Sync with DeptPerm.CHOICES
    from employees.constants import DeptPerm
    for code, name in DeptPerm.CHOICES:
        DepartmentPermission.objects.get_or_create(
            code=code,
            defaults={'name': name}
        )

def reverse(apps, schema_editor):
    pass  # Don't delete

class Migration(migrations.Migration):
    dependencies = [...]
    operations = [
        migrations.RunPython(forward, reverse),
    ]
```

---

#### 4.2 Удалить Django Model Permissions

```python
# В Department.Meta:
class Meta:
    permissions = []  # Удалить все, оставить только scoped
```

**Миграция данных**:
```python
def migrate_permissions(apps, schema_editor):
    # Найти все Permission с employees.change_department_head и т.д.
    # Создать соответствующие роли с scoped_permissions
    # Назначить роли пользователям, у которых были Django permissions
```

---

#### 4.3 Убрать backward-compat поля (breaking change)

```python
class DepartmentRoleSerializer(serializers.ModelSerializer):
    # Удалить:
    # - permissions (read-only)
    # - permissions_verbose (read-only)
    
    class Meta:
        fields = ("id", "department", "name", "scoped_permissions")
```

**Версионирование API**: Перенести на `/api/v2/` с чистой схемой.

---

### Фаза 5: Тестирование (2-3 дня)

#### 5.1 Юнит-тесты для Service

```python
def test_create_role_without_permission():
    service = RoleManagementService(DbOnlyRoleBackend())
    dept = DepartmentFactory()
    user = UserFactory()  # Без прав
    
    with pytest.raises(PermissionDenied):
        service.create_role(dept, "Manager", ["manage_department"], user)

def test_assign_role_syncs_to_backend():
    mock_backend = Mock(spec=RoleBackend)
    service = RoleManagementService(mock_backend)
    
    link = service.assign_role(dept, employee, role, admin_user)
    
    mock_backend.on_role_assigned.assert_called_once_with(
        link, None, role
    )
```

---

#### 5.2 Интеграционные тесты

```python
def test_full_role_assignment_workflow(api_client):
    # 1. Создать отдел
    dept = create_department(...)
    
    # 2. Добавить сотрудников
    add_members(dept, [emp1, emp2])
    
    # 3. Создать роль
    role = create_role(dept, "Manager", [DeptPerm.MANAGE])
    
    # 4. Назначить роль
    assign_role(dept, emp1, role)
    
    # 5. Проверить права
    assert check_dept_permission(emp1, dept, DeptPerm.MANAGE)
    assert not check_dept_permission(emp2, dept, DeptPerm.MANAGE)
    
    # 6. Изменить права роли
    update_role_permissions(role, [DeptPerm.CHANGE_HEAD])
    
    # 7. Проверить изменения
    assert not check_dept_permission(emp1, dept, DeptPerm.MANAGE)
    assert check_dept_permission(emp1, dept, DeptPerm.CHANGE_HEAD)
```

---

#### 5.3 LDAP-тесты с mock

```python
@patch('employees.backends.ldap_backend._ldap')
def test_ldap_backend_creates_group(mock_ldap):
    backend = LdapRoleBackend()
    role = DepartmentRoleFactory()
    
    backend.on_role_created(role)
    
    mock_ldap.return_value.__enter__.return_value.add.assert_called_once()
    assert role.ldap_group_dn is not None
```

---

## 4. Приоритизация проблем

### Критичность: ВЫСОКАЯ 🔴

| # | Проблема | Риск | Сложность | Приоритет |
|---|----------|------|-----------|-----------|
| 1 | Двойная логика LDAP | Усложнение кода, ошибки | Средняя | **P0** |
| 2 | Best-effort LDAP без retry | Несогласованность данных | Высокая | **P0** |
| 3 | Отсутствие транзакций | Race conditions | Низкая | **P0** |
| 4 | Дублирование функций прав | Техдолг, рассинхронизация | Низкая | **P1** |

### Критичность: СРЕДНЯЯ 🟡

| # | Проблема | Риск | Сложность | Приоритет |
|---|----------|------|-----------|-----------|
| 5 | Смешение уровней прав | Путаница, сложность | Средняя | **P1** |
| 6 | Автосинхронизация permissions | Нет контроля версий | Низкая | **P2** |
| 7 | Backward-compat поля | Большие ответы | Низкая | **P2** |
| 8 | Нет кеширования | Лишние запросы | Низкая | **P2** |

### Критичность: НИЗКАЯ 🟢

| # | Проблема | Риск | Сложность | Приоритет |
|---|----------|------|-----------|-----------|
| 9 | Дублирование helpers в тестах | Техдолг | Низкая | **P3** |
| 10 | Нет LDAP-тестов | Неполное покрытие | Средняя | **P3** |
| 11 | Нет граничных тестов | Скрытые баги | Низкая | **P3** |

---

## 5. Roadmap рефакторинга

### Sprint 1: Фундамент (1-2 недели)

**Цели**:
- Унифицировать проверку прав
- Создать Service Layer
- Реализовать Backend Interface

**Задачи**:
1. ✅ Merge функций has_dept_perm
2. ✅ Создать RoleManagementService
3. ✅ Создать RoleBackend interface
4. ✅ Реализовать LdapRoleBackend и DbOnlyRoleBackend
5. ✅ Добавить DI (get_role_service)
6. ✅ Юнит-тесты для service

**Метрики успеха**:
- Все тесты проходят
- Нет регрессий в функциональности

---

### Sprint 2: Рефакторинг API (1 неделя)

**Цели**:
- Упростить ViewSets
- Убрать if LDAP/else из views
- Добавить транзакции

**Задачи**:
1. ✅ Рефакторинг DepartmentRoleViewSet
2. ✅ Рефакторинг Department.set_member_role
3. ✅ Обновить все endpoints на использование service
4. ✅ Добавить @transaction.atomic
5. ✅ Интеграционные тесты

**Метрики успеха**:
- 0 упоминаний _is_ldap_enabled в views
- Все endpoints работают через service

---

### Sprint 3: Миграции и очистка (1 неделя)

**Цели**:
- Перенести на scoped permissions
- Убрать Django model permissions
- Data migrations

**Задачи**:
1. ✅ Data migration для DepartmentPermission
2. ✅ Миграция пользователей с Django perms на роли
3. ✅ Удалить Department.Meta.permissions
4. ✅ Обновить тесты
5. ✅ Обновить документацию

**Метрики успеха**:
- Все права через scoped permissions
- Миграции проходят без ошибок

---

### Sprint 4: Оптимизация (1 неделя)

**Цели**:
- Добавить кеширование
- Убрать backward-compat
- Улучшить производительность

**Задачи**:
1. ✅ Кеширование check_dept_permission
2. ✅ Версионирование API (v2)
3. ✅ Удалить permissions/permissions_verbose
4. ✅ Batch LDAP operations
5. ✅ Load tests

**Метрики успеха**:
- Скорость проверки прав +50%
- Размер ответов API -30%

---

## 6. Метрики качества

### До рефакторинга

| Метрика | Значение |
|---------|----------|
| Cyclomatic complexity (views.py) | ~15 |
| Lines of code (role logic) | ~2000 |
| Test coverage | ~70% |
| API response size | ~5KB (with backward-compat) |
| Permission check time | ~50ms (without cache) |
| LDAP sync failures | ~5% (no retry) |

### После рефакторинга (цель)

| Метрика | Значение |
|---------|----------|
| Cyclomatic complexity | ~8 |
| Lines of code | ~1500 |
| Test coverage | ~90% |
| API response size | ~3KB (v2 API) |
| Permission check time | ~5ms (with cache) |
| LDAP sync failures | <1% (with retry queue) |

---

## 7. Риски и митигация

### Риск 1: Breaking changes для фронтенда

**Описание**: Удаление backward-compat полей сломает старый фронт.

**Митигация**:
- Версионирование API (v1 → v2)
- Поддержка v1 ещё 6 месяцев
- Постепенная миграция фронта

---

### Риск 2: LDAP-синхронизация упадёт при рефакторинге

**Описание**: Изменение логики может нарушить синхронизацию.

**Митигация**:
- Feature flag для включения нового backend
- Параллельное тестирование old/new
- Rollback plan

---

### Риск 3: Производительность ухудшится

**Описание**: Service layer добавляет overhead.

**Митигация**:
- Benchmarks до/после
- Кеширование на уровне service
- Профилирование (django-silk)

---

## 8. Итоговые рекомендации

### Немедленные действия (P0)

1. **Добавить @transaction.atomic** к всем write операциям
2. **Реализовать retry queue** для LDAP-синхронизации
3. **Унифицировать has_dept_perm** функции

### Краткосрочные (1-2 месяца)

1. Создать Service Layer
2. Реализовать Backend pattern
3. Рефакторить ViewSets

### Долгосрочные (3-6 месяцев)

1. Миграция на scoped permissions
2. Версионирование API (v2)
3. Полная оптимизация

---

## 9. Заключение

Система ролей отделов имеет **solid foundation**, но страдает от **архитектурных проблем**, накопленных со временем. Основные направления улучшения:

1. ✅ **Разделение ответственности** — Service Layer + Backend Pattern
2. ✅ **Упрощение кода** — убрать if LDAP/else
3. ✅ **Улучшение надёжности** — транзакции, retry, компенсации
4. ✅ **Оптимизация** — кеширование, batch operations

При последовательной реализации плана **за 4-6 недель** можно достичь:
- 📉 Снижение сложности кода на 40%
- 📈 Увеличение покрытия тестами до 90%
- ⚡ Ускорение проверки прав в 10 раз
- 🛡️ Повышение надёжности LDAP-синхронизации в 5 раз

**Рекомендация**: Начать с P0 задач (транзакции, retry), затем постепенно внедрять Service Layer без breaking changes для фронтенда.

---

**Все отчеты:**
- [01_DEPARTMENT_ROLES_MODELS.md](./01_DEPARTMENT_ROLES_MODELS.md)
- [02_DEPARTMENT_ROLES_API.md](./02_DEPARTMENT_ROLES_API.md)
- [03_DEPARTMENT_ROLES_SERIALIZERS.md](./03_DEPARTMENT_ROLES_SERIALIZERS.md)
- [04_DEPARTMENT_ROLES_PERMISSIONS.md](./04_DEPARTMENT_ROLES_PERMISSIONS.md)
- [05_DEPARTMENT_ROLES_CONSTANTS_UTILS.md](./05_DEPARTMENT_ROLES_CONSTANTS_UTILS.md)
- [06_DEPARTMENT_ROLES_LDAP.md](./06_DEPARTMENT_ROLES_LDAP.md)
- [07_DEPARTMENT_ROLES_TESTS.md](./07_DEPARTMENT_ROLES_TESTS.md)
- [08_DEPARTMENT_ROLES_ARCHITECTURE.md](./08_DEPARTMENT_ROLES_ARCHITECTURE.md) ← **Вы здесь**
