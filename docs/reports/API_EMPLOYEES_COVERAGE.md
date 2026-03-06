# Employees API Endpoints Coverage Report

## Текущая ситуация

### ✅ Покрыто тестами:

**EmployeeViewSet** (`/api/v1/employees/`):
- ✅ GET /employees/ - список сотрудников
- ✅ GET /employees/me/ - текущий пользователь
- ✅ GET /employees/{id}/ - конкретный сотрудник
- ✅ PATCH /employees/{id}/ - обновление сотрудника
- ✅ GET /employees/?search=... - поиск

**DepartmentViewSet** (`/api/v1/departments/`):
- ✅ GET /departments/ - список отделов
- ✅ GET /departments/{id}/ - конкретный отдел
- ✅ POST /departments/ - создание отдела

**PositionViewSet** (`/api/v1/positions/`):
- ✅ GET /positions/ - список должностей
- ✅ POST /positions/ - создание должности

**SkillViewSet** (`/api/v1/skills/`):
- ✅ GET /skills/ - список навыков
- ✅ POST /skills/ - создание навыка

**GroupViewSet** (`/api/v1/groups/`):
- ✅ GET /groups/ - список групп
- ✅ GET /groups/{id}/ - конкретная группа
- ✅ POST /groups/ - создание группы

### ❌ НЕ покрыто тестами:

#### EmployeeViewSet дополнительные endpoints:

1. **POST /api/v1/employees/** - создание нового сотрудника
   - Требует staff права
   - Поля: email, password, first_name, last_name, phone_number
   - Может включать LDAP синхронизацию

2. **DELETE /api/v1/employees/{id}/** - удаление сотрудника
   - Требует staff права
   - Синхронизация с LDAP при удалении

3. **POST /api/v1/employees/{id}/add_skill/**
   - Добавление навыка сотруднику
   - Body: `{"skill_id": 3}` или `{"skill_name": "Python"}`
   - Требует permission: `employees.manage_employee_skills`

4. **POST /api/v1/employees/{id}/remove_skill/**
   - Удаление навыка у сотрудника
   - Body: `{"skill_id": 3}` или `{"skill_name": "Python"}`
   - Требует permission: `employees.manage_employee_skills`

5. **GET /api/v1/employees/{id}/ldap-info/**
   - Получение LDAP информации о сотруднике
   - Query params: `?force_refresh=true`
   - Требует permission: `employees.view_ldap_info`
   - Возвращает: dn, groups, department_dn, sync статус

6. **GET /api/v1/employees/export-excel/**
   - Экспорт списка сотрудников в Excel
   - Query params: фильтры, поиск
   - Возвращает: Excel файл

7. **PATCH /api/v1/employees/me/**
   - Обновление собственного профиля
   - Любой аутентифицированный пользователь

#### EmployeeActionViewSet (`/api/v1/employee-actions/`):

1. **GET /api/v1/employee-actions/** - список всех кадровых действий
2. **POST /api/v1/employee-actions/** - создание кадрового действия
3. **GET /api/v1/employee-actions/{id}/** - детали действия
4. **PATCH /api/v1/employee-actions/{id}/** - обновление
5. **DELETE /api/v1/employee-actions/{id}/** - удаление

#### DepartmentRoleViewSet (`/api/v1/department-roles/`):

1. **GET /api/v1/department-roles/** - список ролей в отделах
2. **POST /api/v1/department-roles/** - создание роли
3. **GET /api/v1/department-roles/{id}/** - детали роли
4. **PATCH /api/v1/department-roles/{id}/** - обновление
5. **DELETE /api/v1/department-roles/{id}/** - удаление
6. **GET /api/v1/department-roles/my_roles/** - роли текущего пользователя
7. **GET /api/v1/department-roles/{id}/employees/** - сотрудники с этой ролью
8. **POST /api/v1/department-roles/{id}/assign/** - назначить роль сотрудникам
9. **GET /api/v1/department-roles/{id}/permissions/** - права роли
10. **POST /api/v1/department-roles/{id}/set_permissions/** - установить права

#### SkillViewSet дополнительные endpoints:

1. **PUT /api/v1/skills/{id}/** - полное обновление навыка
2. **DELETE /api/v1/skills/{id}/** - удаление навыка
3. **POST /api/v1/skills/bulk_create/** - массовое создание навыков
   - Body: `{"skills": ["Python", "JavaScript", "Docker"]}`
4. **POST /api/v1/skills/merge/** - объединение навыков
   - Body: `{"source_id": 1, "target_id": 2}`

#### GroupViewSet дополнительные endpoints:

1. **PUT /api/v1/groups/{id}/** - полное обновление группы
2. **DELETE /api/v1/groups/{id}/** - удаление группы
3. **GET /api/v1/groups/{id}/permissions/** - права группы
4. **POST /api/v1/groups/{id}/set-permissions/** - установить права
   - Body: `{"permission_ids": [1, 2, 3]}`
5. **POST /api/v1/groups/{id}/add-permissions/** - добавить права
   - Body: `{"permission_ids": [4, 5]}`
6. **POST /api/v1/groups/{id}/remove-permissions/** - удалить права
   - Body: `{"permission_ids": [1]}`
7. **POST /api/v1/groups/{id}/sync/** - синхронизация с LDAP
8. **POST /api/v1/groups/{id}/set-description/** - установить описание
   - Body: `{"description": "..."}`
9. **GET /api/v1/groups/{id}/employees/** - участники группы
10. **POST /api/v1/groups/{id}/add-members/** - добавить участников
    - Body: `{"employee_ids": [1, 2, 3]}`
11. **POST /api/v1/groups/{id}/remove-members/** - удалить участников
    - Body: `{"employee_ids": [1]}`
12. **POST /api/v1/groups/{id}/replace-members/** - заменить всех участников
    - Body: `{"employee_ids": [1, 2, 3]}`

#### Auth endpoints:

1. **POST /api/v1/auth/register/** - ✅ уже есть (но возвращает 400)
2. **POST /api/v1/auth/resend-email/** - повторная отправка письма верификации
   - Body: `{"email": "user@example.com"}`
3. **POST /api/v1/auth/verify-email/** - подтверждение email
   - Body: `{"code": "123456", "email": "user@example.com"}`

#### DepartmentViewSet дополнительные:

1. **PUT /api/v1/departments/{id}/** - полное обновление
2. **DELETE /api/v1/departments/{id}/** - удаление
3. **PATCH /api/v1/departments/{id}/** - частичное обновление

#### PositionViewSet дополнительные:

1. **GET /api/v1/positions/{id}/** - детали должности
2. **PUT /api/v1/positions/{id}/** - полное обновление
3. **PATCH /api/v1/positions/{id}/** - частичное обновление
4. **DELETE /api/v1/positions/{id}/** - удаление

## Итого:

- **Покрыто**: ~15 endpoints
- **Не покрыто**: ~50+ endpoints
- **Покрытие**: ~23%

## Рекомендации:

1. **Приоритет 1** (критичные базовые операции):
   - POST /employees/ (create)
   - DELETE /employees/{id}/
   - PATCH /employees/me/
   - POST /employees/{id}/add_skill/
   - POST /employees/{id}/remove_skill/

2. **Приоритет 2** (LDAP и расширенные функции):
   - GET /employees/{id}/ldap-info/
   - GET /employees/export-excel/
   - POST /auth/verify-email/
   - POST /auth/resend-email/

3. **Приоритет 3** (управление ролями и группами):
   - DepartmentRoleViewSet все endpoints
   - GroupViewSet custom actions
   - EmployeeActionViewSet

4. **Приоритет 4** (CRUD для вспомогательных сущностей):
   - Skills CRUD
   - Positions CRUD  
   - Departments CRUD
