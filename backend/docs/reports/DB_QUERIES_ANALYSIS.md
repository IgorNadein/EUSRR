# Анализ обращений к БД в backend/api/v1/employees/views

## Обзор

Модуль содержит 8 ViewSet'ов для работы с сотрудниками, отделами, ролями, навыками, группами и действиями. Проведен детальный анализ всех обращений к базе данных, выявлены проблемы N+1 и предложены оптимизации.

---

## 1. EmployeeViewSet (employees.py)

### Основной queryset (get_queryset)

```python
def get_queryset(self):
    last_action_code_sq = Subquery(
        EmployeeAction.objects.filter(employee_id=OuterRef("pk"))
        .order_by("-date")
        .values("action")[:1]
    )
    
    dep_links_prefetch = Prefetch(
        "departments_links",
        queryset=EmployeeDepartment.objects.filter(is_active=True)
            .select_related("department", "role"),
        to_attr="dept_links",
    )

    prefetches = [
        "skills",
        dep_links_prefetch,
        Prefetch("actions", queryset=EmployeeAction.objects.order_by("-date")),
    ]

    qs = (
        Employee.objects.select_related("position")
        .prefetch_related(*prefetches)
        .annotate(last_action_code=last_action_code_sq)
        .order_by(*self.ordering)
    )
```

**Запросы к БД:**
1. ✅ `SELECT ... FROM employees_employee` (основной)
2. ✅ `JOIN employees_position` (select_related)
3. ✅ `SELECT ... FROM employees_skill WHERE id IN (...)` (prefetch skills)
4. ✅ `SELECT ... FROM employees_employeedepartment JOIN employees_department, employees_departmentrole` (prefetch dept_links)
5. ✅ `SELECT ... FROM employees_employeeaction WHERE employee_id IN (...) ORDER BY -date` (prefetch actions)
6. ✅ Subquery для last_action_code (в основном запросе)

**Оценка:** ⭐⭐⭐⭐⭐ (5/5) - Отлично оптимизирован
- Использует select_related для ForeignKey (position)
- Использует prefetch_related с кастомными queryset для ManyToMany (skills)
- Использует Prefetch с select_related для оптимизации вложенных связей
- Применяет Subquery для аннотации вместо дополнительных запросов
- Фильтрация по отделу использует values() для подзапросов

### Фильтрация по department

```python
if dep_id:
    member_ids = EmployeeDepartment.objects.filter(
        department_id=dep_id
    ).values("employee_id")
    
    head_ids = Department.objects.filter(
        id=dep_id
    ).values("head_id")
    
    role_assignment_ids = RoleAssignment.objects.filter(
        role__department_id=dep_id, is_active=True
    ).values("employee_id")

    qs = qs.filter(
        Q(id__in=member_ids) | Q(id__in=head_ids) | Q(id__in=role_assignment_ids)
    ).distinct()
```

**Проблема:** ❌ **N+1 не обнаружена, но 3 ДОПОЛНИТЕЛЬНЫХ ПОДЗАПРОСА**
- 3 отдельных подзапроса для member_ids, head_ids, role_assignment_ids
- Можно заменить на Exists() подзапросы (уже есть аннотации ниже)

**Рекомендация:**
```python
# Использовать только аннотации без материализации подзапросов
qs = qs.filter(
    Q(_is_dept_member=True) | Q(_is_dept_head=True) | Q(_has_role_assignment=True)
)
```

### Action: me() - GET/PATCH профиль

```python
def me(self, request):
    emp = request.user
    
    if request.method == "GET":
        emp = (
            Employee.objects.select_related("position")
            .prefetch_related(
                Prefetch(
                    "departments_links",
                    queryset=EmployeeDepartment.objects.filter(is_active=True)
                        .select_related("department", "role"),
                ),
                Prefetch("actions", queryset=EmployeeAction.objects.order_by("-date")),
                "skills",
                "groups",
                "user_permissions",
            )
            .get(pk=request.user.pk)
        )
```

**Запросы:** 8 запросов
1. ✅ SELECT employee + JOIN position
2. ✅ SELECT departments_links + JOIN department + JOIN role
3. ✅ SELECT actions ORDER BY -date
4. ✅ SELECT skills
5. ✅ SELECT groups
6. ✅ SELECT user_permissions
7. ✅ SELECT groups.permissions (через ManyToMany)
8. ✅ SELECT position.groups (вложенный prefetch)

**Оценка:** ⭐⭐⭐⭐ (4/5) - Хорошо, но можно улучшить
- ❌ groups и user_permissions не используют select_related для ContentType
- ❌ position.groups загружаются дважды (для сотрудника и для должности)

**Рекомендация:**
```python
.prefetch_related(
    Prefetch("groups", queryset=Group.objects.prefetch_related("permissions")),
    Prefetch("user_permissions", queryset=Permission.objects.select_related("content_type")),
)
```

### Action: add_skill / remove_skill

```python
def add_skill(self, request, pk=None):
    sid = request.data.get("skill_id")
    sname = request.data.get("skill_name")

    if sid:
        sk = Skill.objects.filter(pk=sid).first()  # 1 запрос
    elif sname:
        sk = Skill.objects.filter(name__iexact=sname).first()  # 1 запрос
        if not sk:
            sk = Skill.objects.create(name=sname)   # INSERT
```

**Проблема:** ⚠️ **Двойной запрос при создании**
- filter().first() + create() - 2 запроса
- Лучше использовать get_or_create()

**Рекомендация:**
```python
if sname:
    sk, created = Skill.objects.get_or_create(
        name__iexact=sname,
        defaults={"name": sname}
    )
```

### Action: ldap_info

```python
def ldap_info(self, request, pk=None):
    emp = self.get_object()  # 1 запрос (кэшируется)
    
    try:
        ldap_sync = LdapSyncState.objects.get(
            model='employee',
            object_pk=str(emp.pk)
        )  # 2 запрос
```

**Оценка:** ⭐⭐⭐ (3/5) - Можно оптимизировать
- ❌ Отдельный запрос для LdapSyncState
- ✅ Но вызывается только для одного объекта

**Рекомендация:** Добавить prefetch для LdapSyncState в get_queryset при детальном просмотре

### Action: export_excel

```python
def export_excel(self, request):
    queryset = self.filter_queryset(self.get_queryset())
    queryset = (
        queryset.select_related("position")
        .prefetch_related(
            Prefetch(
                "departments_links",
                queryset=EmployeeDepartment.objects.filter(is_active=True)
                    .select_related("department", "role"),
            ),
            "skills",
        )
    )
```

**Оценка:** ⭐⭐⭐⭐⭐ (5/5) - Отлично оптимизирован

---

## 2. EmployeeActionViewSet (actions.py)

### Основной queryset

```python
def get_queryset(self):
    qs = EmployeeAction.objects.select_related(
        "employee",
        "employee__position",
        "created_by",
    ).order_by("-date")
```

**Запросы:** 1 запрос с JOINs
- ✅ SELECT ... JOIN employee JOIN position JOIN created_by

**Оценка:** ⭐⭐⭐⭐⭐ (5/5) - Идеально

### Action: create (fired)

```python
if act_type == "fired":
    # Деактивация связей с отделами
    EmployeeDepartment.objects.filter(employee=emp, is_active=True).update(
        is_active=False
    )  # 1 UPDATE запрос
    
    if LDAP_ENABLED:
        has_ldap_dn = LdapSyncState.objects.filter(
            model="employee",
            object_pk=str(emp.id),
            ldap_dn__isnull=False,
        ).exists()  # 1 SELECT EXISTS
        
        if has_ldap_dn:
            active_departments = EmployeeDepartment.objects.filter(
                employee=emp, is_active=True
            ).select_related("department")  # 1 SELECT + JOIN
```

**Проблема:** ⚠️ **Избыточные запросы**
- Сначала UPDATE всех связей (деактивация)
- Потом SELECT для проверки активных (их уже нет после UPDATE!)

**Рекомендация:** Получить active_departments ДО update()

### Action: create (hired_back)

```python
elif act_type == "hired_back":
    if LDAP_ENABLED:
        has_ldap_dn = LdapSyncState.objects.filter(...)  # SELECT EXISTS
        if has_ldap_dn:
            sync_state = LdapSyncState.objects.get(...)  # SELECT (дубль!)
```

**Проблема:** ❌ **Двойной запрос**
- exists() + get() - 2 запроса для одного объекта

**Рекомендация:**
```python
sync_state = LdapSyncState.objects.filter(...).first()
if sync_state and sync_state.ldap_dn:
    # работаем
```

---

## 3. DepartmentRoleViewSet (roles.py)

### Основной queryset

```python
queryset = (
    DepartmentRole.objects.select_related("department")
    .prefetch_related("scoped_permissions")
    .all()
)
```

**Запросы:** 3 запроса
1. ✅ SELECT roles + JOIN department
2. ✅ SELECT permissions WHERE id IN (...)
3. ✅ SELECT role_permissions через ManyToMany

**Оценка:** ⭐⭐⭐⭐⭐ (5/5) - Отлично

### Action: assignments

```python
def assignments(self, request, pk=None):
    qs = RoleAssignment.objects.filter(role=role).select_related(
        "employee", "assigned_by"
    )  # 1 запрос + 2 JOINs
```

**Оценка:** ⭐⭐⭐⭐⭐ (5/5) - Отлично

### Action: assign

```python
def assign(self, request, pk=None):
    employee = Employee.objects.get(id=employee_id)  # 1 запрос
    # ...
    if ldap_enabled:
        assignment = svc.assign_role(employee, role, assigned_by)
    else:
        assignment, created = RoleAssignment.objects.update_or_create(
            employee=employee, role=role, defaults={...}
        )  # 1 SELECT + 1 INSERT/UPDATE
```

**Оценка:** ⭐⭐⭐⭐ (4/5) - Хорошо
- ⚠️ Employee.objects.get() без select_related

---

## 4. DepartmentViewSet (departments.py)

### Основной queryset

```python
queryset = Department.objects.select_related("head").prefetch_related("roles").all()

def get_queryset(self):
    qs = super().get_queryset()
    
    # Подзапросы для подсчета
    active_links = EmployeeDepartment.objects.filter(
        department_id=OuterRef("pk"),
        is_active=True,
    ).values("department_id").annotate(c=Count("employee_id", distinct=True))
    
    qs = qs.annotate(
        active_members_count=Subquery(
            active_links.values("c")[:1],
            output_field=models.IntegerField(),
        )
    ).annotate(
        inactive_members_count=Coalesce(
            Subquery(...),  # аналогично для неактивных
            0,
            output_field=models.IntegerField(),
        )
    )
```

**Запросы:** 3 запроса
1. ✅ SELECT departments + JOIN head + 2 Subquery в аннотациях
2. ✅ SELECT roles WHERE department_id IN (...)
3. ✅ SELECT department_roles_permissions (ManyToMany)

**Оценка:** ⭐⭐⭐⭐⭐ (5/5) - Отлично
- Использует Subquery вместо отдельных запросов для подсчета
- select_related для head
- prefetch_related для roles

### Action: members

```python
def members(self, request, pk=None):
    active_links = EmployeeDepartment.objects.filter(
        department_id=dept.pk, is_active=True
    ).select_related("employee", "role")  # 1 запрос + 2 JOINs
```

**Проблема:** ⚠️ **Неоптимально для сериализации**
- select_related("employee") но нет prefetch для вложенных связей employee (position, skills)

**Рекомендация:**
```python
.select_related("employee__position", "role")
.prefetch_related("employee__skills")
```

### Action: set_head

```python
def set_head(self, request, pk=None):
    link = EmployeeDepartment.objects.filter(
        employee=emp, department=dept
    ).first()  # 1 запрос
    
    if not link:
        link = EmployeeDepartment(employee=emp, department=dept, is_active=True)
        link.save()  # 1 INSERT
```

**Оценка:** ⭐⭐⭐ (3/5) - Можно улучшить
- filter().first() + save() вместо get_or_create()

**Рекомендация:**
```python
link, created = EmployeeDepartment.objects.get_or_create(
    employee=emp, department=dept,
    defaults={"is_active": True}
)
```

---

## 5. GroupViewSet (groups.py)

### Основной queryset

```python
queryset = Group.objects.all()

def get_queryset(self):
    qs = super().get_queryset()
    
    if self.action == "list":
        qs = qs.annotate(
            members_count=Count("user", distinct=True),
            permissions_count=Count("permissions", distinct=True),
        )
```

**Проблема:** ❌ **N+1 для детального просмотра**
- При retrieve нет prefetch_related для permissions
- При retrieve нет prefetch_related для members (user)

**Рекомендация:**
```python
if self.action == "retrieve":
    qs = qs.prefetch_related("permissions__content_type", "user")
```

### Action: permissions

```python
def permissions(self, request, pk=None):
    perms = grp.permissions.select_related("content_type").distinct()
```

**Оценка:** ⭐⭐⭐⭐⭐ (5/5) - Отлично

### Action: employees

```python
def employees(self, request, pk=None):
    sub = LdapSyncState.objects.filter(
        model="employee",
        object_pk=Cast(OuterRef("pk"), CharField()),
    ).values("ldap_dn")[:1]

    employees = (
        Employee.objects.annotate(ldap_dn=Subquery(sub))
        .filter(groups=grp)
        .select_related("position")
        .order_by("last_name", "first_name")
    )
```

**Проблема:** ⚠️ **Отсутствует prefetch**
- Нет prefetch_related для skills, departments_links

**Оценка:** ⭐⭐⭐⭐ (4/5) - Хорошо, но можно лучше

---

## 6. SkillViewSet (skills.py)

### Основной queryset

```python
queryset = Skill.objects.all().order_by("name")
```

**Проблема:** ⚠️ **Нет оптимизации**
- При list/retrieve может быть N+1 если сериализатор обращается к employee_set

**Оценка:** ⭐⭐⭐ (3/5) - Базовый

### Action: bulk_create

```python
def bulk_create(self, request):
    existing = set(
        Skill.objects.filter(name__in=cleaned).values_list("name", flat=True)
    )  # 1 SELECT с values_list
    
    to_create = [Skill(name=n) for n in cleaned if n not in existing]
    Skill.objects.bulk_create(to_create, ignore_conflicts=True)  # 1 bulk INSERT
    
    created = Skill.objects.filter(
        name__in=[n for n in cleaned if n not in existing]
    ).order_by("name")  # 1 SELECT для возврата
```

**Оценка:** ⭐⭐⭐⭐⭐ (5/5) - Отлично
- Использует bulk_create для массовой вставки
- values_list для минимизации данных

### Action: merge

```python
def merge(self, request):
    source = Skill.objects.get(pk=sid)  # 1 SELECT
    target = Skill.objects.get(pk=tid)  # 2 SELECT
    
    if reassign:
        qs = Employee.objects.filter(skills=source).only("id").distinct()
        for emp in qs:
            emp.skills.add(target)     # N запросов INSERT
            emp.skills.remove(source)  # N запросов DELETE
```

**Проблема:** ❌ **N+1 В ЦИКЛЕ!**
- Для каждого сотрудника: 1 INSERT + 1 DELETE в ManyToMany таблицу

**Рекомендация:**
```python
# Использовать raw SQL для массового обновления
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute("""
        UPDATE employees_employee_skills 
        SET skill_id = %s 
        WHERE skill_id = %s
    """, [target.id, source.id])
```

---

## 7. PositionViewSet (positions.py)

### Основной queryset

```python
queryset = Position.objects.all().prefetch_related("groups")
```

**Оценка:** ⭐⭐⭐⭐ (4/5) - Хорошо
- prefetch_related для groups
- ⚠️ Но нет prefetch для groups.permissions

**Рекомендация:**
```python
queryset = Position.objects.all().prefetch_related(
    Prefetch("groups", queryset=Group.objects.prefetch_related("permissions"))
)
```

### Action: permissions

```python
def permissions(self, request, pk=None):
    perms = (
        Permission.objects.filter(group__positions=pos)
        .select_related("content_type")
        .distinct()
    )
```

**Оценка:** ⭐⭐⭐⭐⭐ (5/5) - Идеально

---

## 8. Auth Views (auth.py)

### RegisterAPIView

```python
# Проверка существующего email
user = Employee.objects.filter(email__iexact=email).first()  # 1 SELECT

# Проверка существующего телефона
existing_phone = Employee.objects.filter(
    phone_number=parsed_phone
).exclude(email__iexact=email).exists()  # 2 SELECT

# Проверка пользователя (дубль!)
user = Employee.objects.filter(email__iexact=email).first()  # 3 SELECT (ДУБЛЬ!)

# Создание
emp = Employee.objects.create(...)  # 4 INSERT

# Проверка Position
if pos_id and Position.objects.filter(pk=pos_id).exists():  # 5 SELECT
    emp.position_id = pos_id

# Установка навыков
emp.skills.set(Skill.objects.filter(pk__in=skills_ids))  # 6 SELECT + N INSERTs
```

**Проблема:** ❌ **МНОЖЕСТВЕННЫЕ ПРОБЛЕМЫ**
1. Двойной запрос для проверки email
2. exists() для Position вместо get()
3. Нет оптимизации для bulk insert навыков

**Рекомендация:**
```python
# Проверить email и телефон за 1 запрос
existing = Employee.objects.filter(
    Q(email__iexact=email) | Q(phone_number=parsed_phone)
).values_list("email", "phone_number")

# Position
try:
    position = Position.objects.get(pk=pos_id)
    emp.position = position
except Position.DoesNotExist:
    pass

# Навыки - уже оптимально через .set()
```

---

## Сводная таблица проблем

| ViewSet | Проблема | Критичность | Решение |
|---------|----------|-------------|---------|
| EmployeeViewSet | Materialize подзапросов в фильтре по department | ⚠️ Средняя | Использовать аннотации напрямую |
| EmployeeViewSet.me | Нет select_related для Permission.content_type | ⚠️ Низкая | Добавить Prefetch с select_related |
| EmployeeViewSet.add_skill | filter().first() + create() | ⚠️ Низкая | get_or_create() |
| EmployeeActionViewSet | Избыточные запросы при fired | ⚠️ Средняя | Получить данные ДО UPDATE |
| EmployeeActionViewSet | Двойной запрос exists() + get() | ⚠️ Средняя | filter().first() |
| DepartmentViewSet.members | Нет prefetch для employee.position | ⚠️ Средняя | select_related("employee__position") |
| DepartmentViewSet.set_head | filter().first() + save() | ⚠️ Низкая | get_or_create() |
| GroupViewSet | Нет prefetch при retrieve | ⚠️ Средняя | Добавить prefetch_related |
| SkillViewSet.merge | N+1 в цикле add/remove | 🔴 Высокая | Raw SQL для массового UPDATE |
| RegisterAPIView | Двойной SELECT для email | ⚠️ Средняя | Объединить проверки |

---

## Рекомендации по оптимизации

### 1. Критичные (требуют немедленного исправления)

**SkillViewSet.merge** - N+1 в цикле
```python
# Было
for emp in qs:
    emp.skills.add(target)
    emp.skills.remove(source)

# Стало
from django.db import connection
with connection.cursor() as cursor:
    # Обновляем skill_id в таблице ManyToMany
    cursor.execute("""
        UPDATE employees_employee_skills 
        SET skill_id = %s 
        WHERE skill_id = %s
    """, [target.id, source.id])
```

### 2. Важные (улучшат производительность)

**EmployeeViewSet - фильтр по department**
```python
# Было: материализация подзапросов
member_ids = EmployeeDepartment.objects.filter(...).values("employee_id")
qs = qs.filter(Q(id__in=member_ids) | ...)

# Стало: использовать Exists()
qs = qs.filter(
    Q(
        Exists(EmployeeDepartment.objects.filter(
            employee_id=OuterRef("pk"),
            department_id=dep_id,
            is_active=True
        ))
    ) | Q(
        Exists(Department.objects.filter(
            id=dep_id,
            head_id=OuterRef("pk")
        ))
    ) | Q(
        Exists(RoleAssignment.objects.filter(
            employee_id=OuterRef("pk"),
            role__department_id=dep_id,
            is_active=True
        ))
    )
)
```

**GroupViewSet - добавить prefetch**
```python
def get_queryset(self):
    qs = super().get_queryset()
    
    if self.action == "list":
        qs = qs.annotate(
            members_count=Count("user", distinct=True),
            permissions_count=Count("permissions", distinct=True),
        )
    elif self.action == "retrieve":
        qs = qs.prefetch_related(
            Prefetch("permissions", queryset=Permission.objects.select_related("content_type")),
            Prefetch("user", queryset=Employee.objects.select_related("position")),
        )
    
    return qs
```

### 3. Улучшения кода (best practices)

**Везде где filter().first() + create()**
```python
# Было
obj = Model.objects.filter(...).first()
if not obj:
    obj = Model.objects.create(...)

# Стало
obj, created = Model.objects.get_or_create(..., defaults={...})
```

**Двойные запросы exists() + get()**
```python
# Было
if Model.objects.filter(...).exists():
    obj = Model.objects.get(...)

# Стало
obj = Model.objects.filter(...).first()
if obj:
    # работаем
```

---

## Метрики производительности

### Текущее состояние

| Endpoint | Запросов к БД | Оценка |
|----------|---------------|---------|
| GET /employees/ | 5-6 | ⭐⭐⭐⭐⭐ Отлично |
| GET /employees/{id}/ | 6-8 | ⭐⭐⭐⭐ Хорошо |
| GET /employees/me/ | 8-10 | ⭐⭐⭐⭐ Хорошо |
| POST /employees/{id}/add_skill/ | 2-3 | ⭐⭐⭐⭐ Хорошо |
| POST /skills/merge/ | **2 + 2N** | 🔴 N+1 |
| GET /departments/ | 3 | ⭐⭐⭐⭐⭐ Отлично |
| GET /departments/{id}/members/ | 1 | ⭐⭐⭐⭐⭐ Отлично |
| GET /groups/{id}/ | **1 + N** | ⚠️ N+1 |
| POST /auth/register/ | 6-8 | ⭐⭐⭐ Норм |

### После оптимизации

| Endpoint | Было | Стало | Улучшение |
|----------|------|-------|-----------|
| POST /skills/merge/ | 2 + 2N | 3 | **-2N запросов** 🎯 |
| GET /groups/{id}/ | 1 + N | 3 | **-N запросов** 🎯 |
| GET /employees/?department=X | 8 | 7 | -1 (убрать materialize) |
| POST /auth/register/ | 6-8 | 5-6 | -1-2 (объединить проверки) |

---

## Инструменты для мониторинга

### Django Debug Toolbar

```python
# settings.py
if DEBUG:
    INSTALLED_APPS += ['debug_toolbar']
    MIDDLEWARE += ['debug_toolbar.middleware.DebugToolbarMiddleware']
    INTERNAL_IPS = ['127.0.0.1']
```

### Django Silk (для production)

```python
INSTALLED_APPS += ['silk']
MIDDLEWARE += ['silk.middleware.SilkyMiddleware']
```

### Custom query counter decorator

```python
from django.db import connection, reset_queries
from functools import wraps

def print_queries(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        reset_queries()
        result = func(*args, **kwargs)
        print(f"{func.__name__}: {len(connection.queries)} queries")
        for q in connection.queries:
            print(f"  {q['time']}s: {q['sql'][:100]}")
        return result
    return wrapper

# Использование
@print_queries
def my_view(request):
    # ...
```

---

## Заключение

### Сильные стороны
✅ Большинство ViewSet'ов хорошо оптимизированы
✅ Активно используется select_related/prefetch_related
✅ Применяются Subquery и аннотации для избежания N+1
✅ Используется bulk_create для массовых операций

### Требуют внимания
⚠️ SkillViewSet.merge - критическая N+1 проблема
⚠️ GroupViewSet - отсутствует prefetch при retrieve
⚠️ Несколько мест с двойными запросами (exists + get)
⚠️ RegisterAPI - можно объединить проверки

### Общая оценка: ⭐⭐⭐⭐ (4/5)

Код написан с пониманием оптимизации БД, но есть несколько критических мест требующих доработки.
