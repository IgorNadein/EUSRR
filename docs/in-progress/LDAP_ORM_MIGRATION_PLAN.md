# План миграции на LDAP ORM

**Создан:** 19 марта 2026 г.  
**Статус:** 🔄 В работе  
**Цель:** Полный переход от низкоуровневого ldap3 к django-ldapdb ORM + миксины

---

## Обзор текущего состояния

### ✅ Готово
- [x] ModifyDnMixin — поддержка перемещения объектов
- [x] LdapSyncStateMixin — автоматическое управление LdapSyncState
- [x] Миксины интегрированы в модели (LdapUser, LdapGroup, LdapOrganizationalUnit)
- [x] Протестирована работа CREATE и MOVE через ORM
- [x] Документация по миксинам

### ❌ LEGACY код требует замены

#### 1. CREATE операции (conn.add)
- `employees/ldap/services/user_service.py`
  - `_try_create_with_cns()` — создание пользователей
  - `_create_user_in_ldap()` — основной метод создания

- `employees/ldap/services/department_service.py`
  - Создание групп ролей (4 места)
  - Создание OU отделов (1 место)

- `employees/ldap/services/group_service.py`
  - `create_group()` — создание групп

- `employees/ldap/services/position_service.py`
  - Создание групп позиций

#### 2. MOVE операции (conn.modify_dn)
- `employees/ldap/services/user_service.py`
  - `_move_user_to_base()` — перемещение пользователей
  
- `employees/ldap/utils/dn_utils.py`
  - `_move_to_department()` — универсальная функция перемещения

- `employees/ldap/services/department_service.py`
  - Коррекция DN при изменении названия отдела
  - Коррекция DN групп ролей

#### 3. RENAME операции (conn.modify_dn)
- `employees/ldap/services/user_service.py`
  - Изменение CN при смене ФИО

- `employees/ldap/services/group_service.py`
  - `rename_group()` — переименование групп

- `employees/ldap/services/department_service.py`
  - Переименование OU отделов
  - Переименование групп ролей

---

## Стратегия миграции

### Принципы
1. **Постепенная замена** — по одному сервису за раз
2. **Обратная совместимость** — старый код продолжает работать
3. **100% покрытие тестами** — каждое изменение тестируется
4. **Rollback plan** — возможность откатиться назад

### Приоритеты
- 🟢 **P0 (критично)**: UserService — основная функциональность
- 🟡 **P1 (важно)**: DepartmentService, GroupService
- 🟠 **P2 (среднее)**: PositionService
- 🔵 **P3 (низкое)**: Утилиты, вспомогательные функции

---

## Этапы миграции

### ФАЗА 1: UserService (P0) — 3-4 дня

#### 1.1. CREATE пользователей
**Цель:** Заменить `conn.add()` на `LdapUser.objects.create()`

**Файлы:**
- `employees/ldap/services/user_service.py`

**Изменения:**
```python
# Было (LEGACY):
def _try_create_with_cns(self, conn, dto, sam, upn, base_dn, object_classes, cns):
    for cn_txt in cns:
        dn_try = f"CN={cn_txt},{base_dn}"
        attrs = self._build_user_attrs(dto, sam, upn, cn_txt)
        if conn.add(dn_try, object_classes, attrs):
            return dn_try
    return None

# Станет (ORM):
def _try_create_with_cns_orm(self, dto, sam, upn, base_dn, cns):
    """Создание через ORM с обработкой коллизий."""
    from ldap import ALREADY_EXISTS
    from employees.ldap.orm_models import LdapUser
    
    for cn_txt in cns:
        try:
            user = LdapUser.objects.create(
                dn=f"CN={cn_txt},{base_dn}",
                cn=cn_txt,
                sam_account_name=sam,
                user_principal_name=upn,
                given_name=dto.first_name,
                sn=dto.last_name or ".",
                display_name=f"{dto.first_name} {dto.last_name or ''}".strip(),
                mail=dto.email,
                user_account_control=512,  # Normal account
                employee_number=str(dto.employee_id) if dto.employee_id else "",
                # ... остальные поля из dto
            )
            return user.dn
        except ALREADY_EXISTS:
            continue
    return None
```

**Преимущества:**
- Убираем `UserMapperService._build_user_attrs()` — атрибуты задаются напрямую
- Автоматическая валидация полей
- LdapSyncStateMixin создаст LdapSyncState автоматически
- Меньше кода (~40% сокращение)

**Тестирование:**
- [ ] Unit тесты для `_try_create_with_cns_orm()`
- [ ] Integration тесты: создание пользователя с коллизиями CN
- [ ] Проверка LdapSyncState после создания

**Риски:**
- 🟡 Другие поля могут быть не учтены
- 🟢 Rollback: оставить старый метод как `_try_create_with_cns_legacy()`

---

#### 1.2. MOVE пользователей (увольнение, перевод)
**Цель:** Заменить `conn.modify_dn()` на `user.base_dn = ...; user.save()`

**Файлы:**
- `employees/ldap/services/user_service.py`
- `employees/ldap/utils/dn_utils.py`

**Изменения:**
```python
# Было (LEGACY):
def _move_user_to_base(self, conn, user_dn, base_dn):
    rdn = user_dn.split(",", 1)[0]
    ok = conn.modify_dn(user_dn, rdn, new_superior=base_dn)
    if not ok:
        raise RuntimeError(f"LDAP move failed: {conn.result}")
    return f"{rdn},{base_dn}"

# Станет (ORM):
def _move_user_to_base_orm(self, user_dn, base_dn):
    """Перемещение через ModifyDnMixin."""
    from employees.ldap.orm_models import LdapUser
    
    user = LdapUser.objects.get(dn=user_dn)
    user.base_dn = base_dn
    user.save()  # ModifyDnMixin автоматически вызовет modify_dn
    
    return user.dn  # Обновлённый DN
```

**Преимущества:**
- ModifyDnMixin автоматически обновляет LdapSyncState.dn
- Логирование операций из коробки
- Меньше ошибок (нет ручного формирования DN)

**Тестирование:**
- [ ] Unit тесты для `_move_user_to_base_orm()`
- [ ] Integration тесты: перемещение в Dismissed, в отдел
- [ ] Проверка обновления LdapSyncState.dn

**Риски:**
- 🟢 Низкий — миксин уже протестирован

---

#### 1.3. RENAME пользователей (смена ФИО)
**Цель:** Сохранить `conn.modify_dn()` для изменения RDN (cn)

**Обоснование:**
- Изменение RDN (cn=...) != перемещение (newsuperior)
- ModifyDnMixin работает только с `base_dn`
- Для RDN нужен отдельный подход

**Решение:**
```python
# Оставляем LEGACY для изменения CN:
def _update_cn_if_needed(self, conn, dn, new_cn):
    """Изменение CN через modify_dn (без newsuperior)."""
    current_rdn = dn.split(",", 1)[0]
    new_rdn = f"CN={new_cn}"
    
    if current_rdn != new_rdn:
        ok = conn.modify_dn(dn, new_rdn)
        if not ok:
            raise RuntimeError(f"Failed to rename: {conn.result}")
        
        # Обновляем LdapSyncState вручную
        base = dn.split(",", 1)[1]
        new_dn = f"{new_rdn},{base}"
        self._update_sync_state_dn(old_dn=dn, new_dn=new_dn)
        
        return new_dn
    return dn
```

**Альтернатива (будущее):**
- Создать `RenameRdnMixin` для изменения RDN
- Но это P3 приоритет

**Тестирование:**
- [ ] Unit тесты сохранения старой логики
- [ ] Проверка обновления LdapSyncState

---

### ФАЗА 2: DepartmentService (P1) — 2-3 дня

#### 2.1. CREATE OU отделов
**Цель:** `conn.add()` → `LdapOrganizationalUnit.objects.create()`

**Изменения:**
```python
# Было:
ok = conn.add(dn, ["top", "organizationalUnit"])

# Станет:
from employees.ldap.orm_models import LdapOrganizationalUnit

ou = LdapOrganizationalUnit.objects.create(
    dn=dn,
    ou=dept_name,
    description=f"Отдел {dept_name}",
    managed_by=manager_dn if manager_dn else "",
)
```

**Тестирование:**
- [ ] Создание OU через ORM
- [ ] Проверка атрибутов (description, managedBy)

---

#### 2.2. CREATE групп ролей
**Цель:** `conn.add()` → `LdapGroup.objects.create()`

**Изменения:**
```python
# Было:
attrs = {
    "sAMAccountName": sam,
    "description": desc,
    "member": members,
}
ok = conn.add(group_dn, ["top", "group"], attrs)

# Станет:
from employees.ldap.orm_models import LdapGroup

group = LdapGroup.objects.create(
    dn=group_dn,
    cn=cn,
    sam_account_name=sam,
    description=desc,
    member=members if members else [],
)
```

**Тестирование:**
- [ ] Создание групп ролей через ORM
- [ ] Проверка членства (member list)

---

#### 2.3. RENAME OU при изменении названия отдела
**Цель:** `conn.modify_dn()` → `ou.base_dn = ...; ou.save()` (для MOVE)

**ВАЖНО:** Для изменения самого OU (не перемещения) нужен `modify_dn(new_rdn=...)`

**Решение:**
- Оставить `conn.modify_dn()` для изменения RDN OU
- Использовать ModifyDnMixin только если планируется перемещение OU (редко)

**Тестирование:**
- [ ] Переименование OU (IT → Engineering)
- [ ] Проверка обновления всех вложенных DN

---

### ФАЗА 3: GroupService (P1) — 1-2 дня

#### 3.1. CREATE глобальных групп
**Цель:** `conn.add()` → `LdapGroup.objects.create()`

**Аналогично DepartmentService 2.2**

---

#### 3.2. RENAME групп
**Цель:** Оставить `conn.modify_dn()` для изменения CN

**Аналогично UserService 1.3**

---

### ФАЗА 4: PositionService (P2) — 1 день

#### 4.1. CREATE групп позиций
**Цель:** `conn.add()` → `LdapGroup.objects.create()`

**Аналогично DepartmentService 2.2**

---

### ФАЗА 5: Утилиты и рефакторинг (P3) — 2-3 дня

#### 5.1. Создать RenameRdnMixin
**Цель:** Унифицировать изменение RDN через миксин

```python
class RenameRdnMixin:
    """Миксин для изменения RDN (cn=..., ou=...) без перемещения."""
    
    def rename_rdn(self, new_rdn_value):
        """Изменяет RDN без перемещения между контейнерами.
        
        Example:
            user.rename_rdn("Ivanov I 2")  # cn=Ivanov I → cn=Ivanov I 2
        """
        from .infrastructure.connections import _ldap
        
        old_dn = self.dn
        rdn_attr = self.build_rdn().split("=")[0]  # "cn" или "ou"
        new_rdn = f"{rdn_attr}={new_rdn_value}"
        
        with _ldap() as conn:
            success = conn.modify_dn(old_dn, new_rdn)
            if not success:
                raise RuntimeError(f"Failed to rename: {conn.result}")
        
        # Обновляем self.dn
        base = old_dn.split(",", 1)[1]
        self.dn = f"{new_rdn},{base}"
```

**Интеграция:**
```python
class LdapUser(ModifyDnMixin, RenameRdnMixin, LdapSyncStateMixin, LdapModel):
    ...

# Использование:
user = LdapUser.objects.get(dn=...)
user.rename_rdn("Petrov P")  # Изменение CN
user.save()  # Обновление остальных атрибутов
```

---

#### 5.2. Удалить LEGACY код
**Цель:** Удалить старые методы после полной миграции

**Удалить:**
- `UserMapperService._build_user_attrs()` — заменено на прямое создание через ORM
- `dn_utils._move_to_department()` — заменено на ModifyDnMixin
- Все методы с `_legacy` суффиксом

**Проверить зависимости:**
```bash
# Найти все использования LEGACY методов
grep -r "_build_user_attrs" backend/
grep -r "_move_to_department" backend/
```

---

#### 5.3. Обновить документацию
**Цель:** Убрать упоминания о LEGACY, обновить примеры

**Файлы:**
- `employees/ldap/orm_models.py` — убрать секцию LEGACY
- `docs/guides/ldap-orm-mixins-usage.md` — добавить RenameRdnMixin
- `docs/completed/ldap-orm-create-support.md` — пометить как завершённое

---

## Тестирование

### Unit тесты
- [ ] Создание объектов через ORM (все модели)
- [ ] Перемещение через ModifyDnMixin
- [ ] Обработка коллизий CN
- [ ] Обновление LdapSyncState автоматически

### Integration тесты
- [ ] Полный цикл: создание → перемещение → обновление → удаление
- [ ] Создание пользователя → перевод в отдел → увольнение
- [ ] Создание отдела → назначение менеджера → переименование
- [ ] Создание группы → добавление членов → переименование

### Regression тесты
- [ ] Существующие тесты проходят без изменений
- [ ] Функциональность не сломана

### Performance тесты
- [ ] ORM не медленнее ldap3 (допустимо +10%)
- [ ] Batch операции работают эффективно

---

## Риски и митигация

### 🔴 Высокие риски
1. **Потеря данных при ошибке в миграции**
   - Митигация: резервное копирование LDAP перед каждой фазой
   - Rollback: восстановление из бэкапа

2. **Несовместимость с существующими интеграциями**
   - Митигация: тестирование на staging
   - Rollback: feature flag для переключения ORM/LEGACY

### 🟡 Средние риски
1. **Производительность ORM ниже ldap3**
   - Митигация: профилирование и оптимизация
   - Альтернатива: batch операции через bulk_create

2. **Неучтённые edge cases**
   - Митигация: расширенное тестирование
   - Rollback: постепенная миграция (по одному сервису)

### 🟢 Низкие риски
1. **Изменение поведения при обработке ошибок**
   - Митигация: обработка тех же exception (ALREADY_EXISTS, etc.)

---

## Чеклист выполнения

### Подготовка
- [ ] Создать feature branch `feature/ldap-orm-migration`
- [ ] Настроить CI/CD для автоматического тестирования
- [ ] Создать резервную копию LDAP

### ФАЗА 1: UserService
- [ ] Реализовать `_try_create_with_cns_orm()`
- [ ] Написать unit тесты CREATE
- [ ] Реализовать `_move_user_to_base_orm()`
- [ ] Написать unit тесты MOVE
- [ ] Integration тесты UserService
- [ ] Code review
- [ ] Merge в develop

### ФАЗА 2: DepartmentService
- [ ] Реализовать CREATE OU через ORM
- [ ] Реализовать CREATE групп через ORM
- [ ] Unit тесты
- [ ] Integration тесты
- [ ] Code review
- [ ] Merge в develop

### ФАЗА 3: GroupService
- [ ] Реализовать CREATE через ORM
- [ ] Unit тесты
- [ ] Integration тесты
- [ ] Code review
- [ ] Merge в develop

### ФАЗА 4: PositionService
- [ ] Реализовать CREATE через ORM
- [ ] Unit тесты
- [ ] Code review
- [ ] Merge в develop

### ФАЗА 5: Финализация
- [ ] Создать RenameRdnMixin (опционально)
- [ ] Удалить LEGACY код
- [ ] Обновить документацию
- [ ] Final regression тесты
- [ ] Production deployment

---

## Оценка времени

| Фаза | Описание | Оценка | Зависимости |
|------|----------|--------|-------------|
| 1 | UserService (CREATE + MOVE) | 3-4 дня | - |
| 2 | DepartmentService | 2-3 дня | Фаза 1 |
| 3 | GroupService | 1-2 дня | Фаза 1 |
| 4 | PositionService | 1 день | Фаза 1 |
| 5 | Рефакторинг + документация | 2-3 дня | Фазы 1-4 |
| **ИТОГО** | **Полная миграция** | **9-13 дней** | - |

**С учётом тестирования и ревью:** ~15-20 рабочих дней (3-4 недели)

---

## Success Criteria

### Функциональные
- ✅ Все операции CREATE выполняются через ORM
- ✅ Все операции MOVE выполняются через ModifyDnMixin
- ✅ LdapSyncState обновляется автоматически
- ✅ Обработка коллизий CN работает корректно

### Технические
- ✅ 100% покрытие unit тестами новых методов
- ✅ Integration тесты проходят успешно
- ✅ Regression тесты не выявляют проблем
- ✅ Performance не деградировала (±10%)

### Качество кода
- ✅ Код соответствует PEP 8
- ✅ Все методы задокументированы (docstrings)
- ✅ Нет дублирования кода
- ✅ Code review пройден

### Документация
- ✅ Обновлена документация ORM моделей
- ✅ Обновлены гайды по миксинам
- ✅ Создана migration guide для команды

---

## Следующие шаги

1. **Обсудить план с командой** — получить feedback
2. **Установить приоритеты** — согласовать порядок фаз
3. **Начать ФАЗУ 1** — UserService как самый критичный компонент
4. **Еженедельные ревью** — отслеживать прогресс

---

## Контакты и ответственные

- **Tech Lead:** @username
- **Backend разработчик (LDAP):** @username
- **QA Engineer:** @username
- **DevOps (backup/rollback):** @username

---

**Статус обновлён:** 19 марта 2026 г.  
**Следующий ревью:** TBD
