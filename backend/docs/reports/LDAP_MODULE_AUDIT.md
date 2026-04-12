# Аудит модуля employees/ldap

**Дата:** 10 апреля 2026 г.  
**Контекст:** Аудит после выравнивания Department LDAP sync и retry-очереди

## Обновление 10 апреля 2026

### Каноническая модель Department sync

- Источник истины для `Department`, `EmployeeDepartment.is_active` и ролей отдела теперь находится в Django DB.
- `employees/signals/ldap/department.py` и `employees/tasks.py` больше не содержат отдельную handwritten LDAP-логику для отдела.
- Оба пути делегируют в `DepartmentService`:
  - `sync_department_state()`
  - `sync_department_delete()`
  - `sync_member_state()`
- Retry-очередь больше не вызывает устаревшие private-методы вроде `_move_user_to_department` и `_move_user_to_base_ou`.
- Diff для `Department` формируется до `save()` через временные атрибуты `_ldap_changes` и `_ldap_sync_head`; post-save больше не пытается вычислять изменения повторным чтением уже сохранённой строки.

### Остаточные замечания

- `DepartmentService` по-прежнему содержит legacy CRUD API, которое мутирует DB (`add_member`, `remove_member`, `set_member_role`), но live sync и retry используют только sync-oriented методы.
- `UserService` и часть legacy service-слоя всё ещё требуют отдельной консолидации.

## Текущее использование

### ✅ Активно используется

#### DirectoryService (employees/ldap/directory_service.py)
Используется в:
- `api/v1/employees/views/auth.py` - RegisterAPIView
- `employees/signals/ldap/employee.py` - синхронизация Employee
- `employees/signals/ldap/group.py` - синхронизация Group
- `common/ldap_password_mixin.py` - смена пароля

**Используемые методы:**
- `create_user()` - auth.py (регистрация новых пользователей)
- `update_user()` - signals_ldap.py, ldap_password_mixin.py
- `delete_user()` - signals_ldap.py
- `group_create()` - signals_group.py
- `group_delete()` - signals_group.py
- `group_rename()` - signals_group.py
- `group_set_description()` - signals_group.py
- `group_add_members()` - signals_group.py
- `group_remove_members()` - signals_group.py
- `group_replace_members()` - signals_group.py

#### Services (employees/ldap/services/*)
Используются в сигналах через ленивый импорт:
- `DepartmentService` - `employees/signals/ldap/department.py`, `employees/tasks.py`
- `GroupService` - через `DepartmentService`, `employees/signals/ldap/group.py`
- `UserService` - через `DepartmentService`, `employees/signals/ldap/employee.py`
- `SyncService` - management/commands/sync_directory.py

#### ORM Models (employees/ldap/orm_models.py)
- `LdapUser` - signals_ldap.py, management commands
- `LdapGroup` - через services
- `LdapOrganizationalUnit` - через services

#### Errors (employees/ldap/errors.py)
- `DirectoryLdapError` - используется везде
- `DirectoryDbError` - используется везде
- `DirectoryServiceError` - используется везде

#### Utils
- `utils/text_utils.py` (`esc_filter`) - auth_backends.py
- Остальные utils используются внутри services

---

## ⚠️ НЕ используется (кандидаты на удаление)

### DirectoryService - методы БЕЗ использования в production

**Удалены из ViewSets, больше не вызываются:**

1. **Departments (частично):**
   - `create_department()` - Department создается в БД, сигнал создает OU через update
   - `add_member()` - не используется
   - `remove_member()` - не используется  
   - `set_head()` - не используется
   - `set_member_role()` - не используется

2. **Positions (полностью):**
   - `reconcile_position()` - удалено из PositionViewSet
   - `assign_position()` - не используется
   - `unassign_position()` - не используется
   - `delete_position_group()` - удалено из PositionViewSet

3. **Groups (старые методы, дублируют group_*):**
   - `create_group()` - дублирует `group_create()`
   - `delete_group()` - дублирует `group_delete()`
   - `rename_group()` - дублирует `group_rename()`
   - `set_group_description()` - дублирует `group_set_description()`
   - `add_group_members()` - дублирует `group_add_members()`
   - `remove_group_members()` - дублирует `group_remove_members()`
   - `replace_group_members()` - дублирует `group_replace_members()`
   - `list_group_members()` - дублирует `group_list_members()`
   - `find_group_dn()` - дублирует `group_find_dn()`
   - `sync_groups_catalog()` - удалено из GroupViewSet

4. **Helper методы (удалены вызовы):**
   - `employee_ids_to_dns()` - использовался в GroupViewSet
   - `dns_to_employee_ids()` - использовался в GroupViewSet
   - `employees_brief_by_dns()` - использовался в GroupViewSet

5. **Internal методы департаментов:**
   - `_ensure_department_ou()`
   - `_rename_department_ou()`
   - `_set_ou_managed_by()`
   - `_set_ou_description()`
   - `_delete_department_ou()`
   - `_evict_all_users_from_department_ou()`
   - `_groups_with_member()`
   - `_modify_group_members()`

   **Примечание:** Эти методы могут использоваться внутри services

### Services - потенциально избыточные

**Не используются напрямую, только через DirectoryService:**
- `PositionService` - весь класс (для Positions больше нет сигналов)
- `RoleService` - весь класс (для Roles больше нет сигналов) 

### Репозитории
Все используются через services - оставить.

### Domain/DTOs
- `DirectoryUserDTO` - используется
- `DirectoryDepartmentDTO` - используется
- Остальные DTOs - проверить использование

---

## 📊 Статистика файлов

```
employees/ldap/
├── directory_service.py      ~ 420 строк (можно сократить удалением дублей)
├── services/
│   ├── user_service.py        ✅ используется
│   ├── department_service.py  ✅ используется
│   ├── group_service.py       ✅ используется
│   ├── position_service.py    ❌ НЕ используется (нет сигналов для Position)
│   ├── sync_service.py        ✅ используется (management commands)
├── orm_models.py              ✅ используется
├── orm_services.py            ? проверить
├── errors.py                  ✅ используется
├── config.py                  ✅ используется (sync_service)
├── utils/
│   ├── text_utils.py          ✅ используется (esc_filter)
│   ├── group_utils_orm.py     ✅ используется (services)
│   ├── group_utils.py         ? проверить 
│   ├── ldap_utils.py          ? проверить
│   ├── dn_utils.py            ? проверить
│   ├── image_utils.py         ? проверить
├── repositories/              ✅ используются (через services)
├── infrastructure/            ✅ используется (connections)
├── domain/                    ✅ используется (DTOs)
└── tests/                     ✅ оставить
```

---

## 🎯 Рекомендации

### Этап 1: Очистка DirectoryService

1. **Удалить дублирующие методы групп:** create_group, delete_group, rename_group и т.д. (использовать только group_* версии)

2. **Удалить неиспользуемые методы позиций:** reconcile_position, assign_position, unassign_position, delete_position_group

3. **Удалить неиспользуемые helper методы:** employee_ids_to_dns, dns_to_employee_ids, employees_brief_by_dns

4. **Удалить sync_groups_catalog** - больше не вызывается

5. **Проверить internal методы** - если используются только в services, перенести туда

**Потенциальное сокращение:** ~150-200 строк из directory_service.py

### Этап 2: Удалить неиспользуемые сервисы

1. **PositionService** - полностью удалить (позиции больше не синхронизируются)
2. **RoleService** - проверить и возможно удалить

**Потенциальное сокращение:** ~300-500 строк

### Этап 3: Проверить utils

Проверить какие utils реально используются в оставшихся services.

### Этап 4: Создать сигналы для Position/Role (опционально)

Если нужна синхронизация позиций и ролей - создать сигналы, иначе удалить соответствующие сервисы.

---

## ✅ НЕ трогать

- **orm_models.py** - основа всей LDAP интеграции
- **services/user_service.py** - активно используется
- **services/department_service.py** - активно используется  
- **services/group_service.py** - активно используется
- **services/sync_service.py** - используется в management commands
- **errors.py** - используется везде
- **repositories/** - используются через services
- **infrastructure/** - базовая инфраструктура
- **domain/dtos.py** - используется для передачи данных
- **tests/** - тестовое покрытие

---

## 🔍 Следующие шаги

1. Запустить покрытие тестами для определения мертвого кода
2. Использовать vulture или аналог для поиска неиспользуемого кода
3. Проверить импорты во всех файлах модуля
4. Создать план удаления в несколько этапов с тестированием между этапами
