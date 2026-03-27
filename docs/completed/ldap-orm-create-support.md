# Поддержка CREATE в django-ldapdb ORM

**Дата:** 19 марта 2026 г.  
**Статус:** ✅ Подтверждено тестами

## Проблема

В документации и кодовой базе утверждалось, что `django-ldapdb` ORM **НЕ поддерживает** CREATE операции для пользователей LDAP, и поэтому используется низкоуровневый подход через `ldap3.Connection.add()`.

## Исследование

### Тестирование CREATE через ORM

```python
# Создание пользователя через ORM
user = LdapUser.objects.create(
    dn="CN=Test User,OU=Users,OU=company,DC=robotail,DC=local",
    cn="Test User",
    sam_account_name="testuser",
    user_principal_name="testuser@robotail.local",
    given_name="Test",
    sn="User",
    display_name="Test User",
    mail="testuser@robotail.local",
    user_account_control=512,
)

# ✅ УСПЕХ! Пользователь создан в LDAP
```

### Тестирование обработки коллизий CN

```python
# Попытка создать пользователя с занятым CN
for cn in ["Иванов И", "Иванов И 2", "Иванов И 3"]:
    try:
        user = LdapUser.objects.create(
            dn=f"CN={cn},OU=Users,...",
            cn=cn,
            ...
        )
        break  # ✅ Успех
    except ldap.ALREADY_EXISTS:
        continue  # Пробуем следующий вариант

# ✅ РАБОТАЕТ! Обработка коллизий возможна
```

## Выводы

### ✅ Что ORM МОЖЕТ:

1. **CREATE** — создание пользователей через `.objects.create()`
   - Динамический DN (можно создавать в любых OU)
   - Обработка коллизий CN через try-except
   - Полная поддержка всех атрибутов

2. **UPDATE** — изменение атрибутов через `.save()`

3. **DELETE** — удаление через `.delete()`

4. **READ** — поиск через `.get()` / `.filter()`

### ❌ Что ORM НЕ МОЖЕТ:

1. **ModifyDN** — перемещение/переименование между OU
   - Остаётся через `ldap3.Connection.modify_dn()`
   - Единственное ограничение ORM
   
**Почему не работает изменение DN:**
```python
# ❌ Не работает:
user = LdapUser.objects.get(dn=old_dn)
user.dn = new_dn  # Локальное изменение
user.save()       # ORM пытается modify по НОВОМУ DN → "No such object"

# ✅ Работает (через ldap3):
conn.modify_dn(old_dn, new_rdn, new_superior=new_ou)
```

ORM не отслеживает изменение DN и не вызывает LDAP операцию `modifyDN`.

## Изменения в кодовой базе

### Обновлена документация:

1. `backend/employees/ldap/orm_models.py`
   - ✅ Исправлены docstrings LdapUser, LdapGroup, LdapOrganizationalUnit
   - ✅ Обновлена общая документация в начале файла
   - ✅ Добавлены примеры CREATE через ORM

2. `backend/employees/ldap/services/user_service.py`
   - ✅ Обновлены TODO комментарии
   - ✅ Помечены LEGACY подходы через ldap3.Connection.add()

### Текущий код (LEGACY):

```python
# services/user_service.py
def _create_user_in_ldap(self, conn, dto):
    # LEGACY: использует ldap3.Connection.add()
    for cn in cn_candidates(pretty_cn, safe_cn):
        if conn.add(f"CN={cn},{base_dn}", object_classes, attrs):
            return dn
```

### Рекомендуемый подход (ORM):

```python
def _create_user_in_ldap_orm(self, dto):
    """Создание через ORM (рекомендуется для нового кода)."""
    base_dn = "OU=Users,OU=company,DC=robotail,DC=local"
    
    for cn in cn_candidates(pretty_cn, safe_cn):
        try:
            user = LdapUser.objects.create(
                dn=f"CN={cn},{base_dn}",
                cn=cn,
                sam_account_name=sam,
                user_principal_name=upn,
                given_name=dto.first_name,
                sn=dto.last_name,
                display_name=f"{dto.first_name} {dto.last_name}",
                mail=dto.email,
                user_account_control=512,
            )
            return user.dn
        except ldap.ALREADY_EXISTS:
            continue
    
    raise RuntimeError("Не удалось создать пользователя")
```

## Преимущества ORM подхода

1. **Единообразие** — весь CRUD через ORM
2. **Меньше кода** — не нужен UserMapperService для формирования атрибутов
3. **Типизация** — IDE поддержка и автодополнение
4. **Валидация** — Django автоматически проверяет поля
5. **Идиоматично** — Django way

## Рекомендации

### Для нового кода:
- ✅ Использовать `LdapUser.objects.create()` для CREATE
- ✅ Использовать `.save()` для UPDATE
- ✅ Использовать `.delete()` для DELETE
- ❌ Использовать `ldap3.modify_dn()` для MOVE/RENAME (единственный случай)

### Для существующего кода:
- 📝 LEGACY код через `ldap3.Connection.add()` работает корректно
- 📝 Рефакторинг на ORM — опционально (для единообразия)
- 📝 При рефакторинге — покрыть тестами

## Тестовые результаты

```bash
# Тест 1: Создание пользователя
✅ Пользователь создан: CN=Test User,OU=Users,...

# Тест 2: Поиск созданного пользователя
✅ Найден в LDAP

# Тест 3: Удаление
✅ Удалён успешно

# Тест 4: Коллизия CN
Попытка 1: CN=Test → ✅ Создан
Попытка 1: CN=Test → ❌ ALREADY_EXISTS
Попытка 2: CN=Test 2 → ✅ Создан
```

## Заключение

**django-ldapdb ORM ПОЛНОСТЬЮ ПОДДЕРЖИВАЕТ CREATE операции.**

Утверждение об ограничениях было **ошибочным**. Единственное реальное ограничение — отсутствие поддержки ModifyDN (rename/move).

Рекомендуется использовать ORM для всех операций CREATE/UPDATE/DELETE в новом коде.

---

## UPDATE: Решение для ModifyDN через ModifyDnMixin

**Дата:** 19 марта 2026 г.  
**Статус:** ✅ Реализовано и протестировано

### Проблема

django-ldapdb не поддерживает перемещение объектов между OU, потому что метод `connection.rename_s()` не передаёт параметр `newsuperior`.

### Решение

Создан миксин `ModifyDnMixin` (см. `backend/employees/ldap/mixins.py`), который:

1. Отслеживает изменение `base_dn` атрибута
2. Автоматически вызывает `conn.modify_dn(newsuperior=...)` при `save()`
3. Обновляет `dn` объекта после перемещения

### Использование

```python
from employees.ldap.orm_models import LdapUser

# Создаём пользователя в OU=Users
user = LdapUser.objects.create(
    dn="CN=Test,OU=Users,OU=company,DC=robotail,DC=local",
    cn="Test",
    # ... остальные атрибуты
)

# Перемещаем в OU=Dismissed
user.base_dn = "OU=Dismissed,OU=company,DC=robotail,DC=local"
user.save()  # Автоматически выполнит modify_dn!

# Проверяем
new_user = LdapUser.objects.get(
    dn="CN=Test,OU=Dismissed,OU=company,DC=robotail,DC=local"
)
print(new_user.dn)  # CN=Test,OU=Dismissed,...
```

### Тестовые результаты

```bash
=== Создаём пользователя через ORM ===
Создан: cn=ModifyDnTest,OU=Users,OU=company,DC=robotail,DC=local
Найден в LDAP: CN=ModifyDnTest,OU=Users,...

=== Перемещаем в OU=Dismissed ===
[INFO] ModifyDnMixin: Successfully moved 
  cn=ModifyDnTest,OU=Users,... → cn=ModifyDnTest,OU=Dismissed,...
После save(): dn=cn=ModifyDnTest,OU=Dismissed,...
✅ Не найден в старом месте
✅ Найден в новом месте
```

### Итог

**django-ldapdb ORM теперь поддерживает ВСЕ операции CRUD + MOVE:**

- ✅ **CREATE** — `LdapUser.objects.create(dn=..., ...)`
- ✅ **READ** — `LdapUser.objects.get()` / `.filter()`
- ✅ **UPDATE** — `user.display_name = "New"; user.save()`
- ✅ **DELETE** — `user.delete()`
- ✅ **MOVE** — `user.base_dn = "OU=Dismissed,..."; user.save()` *(через ModifyDnMixin)*

Необходимость в низкоуровневых `ldap3` операциях теперь **полностью устранена** для всех базовых операций!

### Дополнительные миксины

- **LdapSyncStateMixin** — автоматическое управление `LdapSyncState` при операциях с LDAP
- Автоматически обновляет `dn` и метаданные синхронизации
- См. документацию в `backend/employees/ldap/mixins.py`
