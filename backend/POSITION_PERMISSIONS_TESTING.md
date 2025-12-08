# Тестирование Прав Доступа Через Должности (Position Permissions)

## Описание Проблемы

### Исходная Жалоба Пользователя
> "Ты говорил, что пользователь с должностью получает все права которые есть у групп в этой должности, но по факту кнопка создания публикаций не появляется"

**Ожидаемое поведение:**
- Пользователь имеет должность (Position)
- Должность связана с группами (Position.groups)
- Группы имеют права (Group.permissions)
- Пользователь должен получить все права из групп своей должности

**Фактическое поведение:**
- UI кнопки не появляются (например, "Создать публикацию")
- Пользователи с должностями не могут выполнять действия, несмотря на наличие прав в группах

## Архитектура Системы Прав

### Цепочка Наследования
```
Position → Position.groups (ManyToMany) → Group.permissions (ManyToMany) → Permission
                ↓
           Employee.position (ForeignKey)
                ↓
         User (связан через OneToOne)
```

### Реализация Backend

**Файл:** `backend/eusrr_backend/auth_backends.py`

```python
class PositionRoleBackend(BaseBackend):
    """
    Custom authentication backend that grants permissions based on 
    Position.groups relationships.
    """
    
    def get_all_permissions(self, user_obj, obj=None):
        if not user_obj.is_active or user_obj.is_anonymous:
            return set()
        
        # Получаем права из должности
        if hasattr(user_obj, 'employee') and user_obj.employee.position:
            pos = user_obj.employee.position
            return set(
                Permission.objects.filter(
                    group__positions=pos
                ).select_related('content_type').values_list(
                    'content_type__app_label',
                    'codename'
                )
            )
        
        return set()
```

**Конфигурация:** `settings.py` (строка 329)
```python
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'eusrr_backend.auth_backends.LDAPAuthBackend',
    'eusrr_backend.auth_backends.LDAPGroupAuthBackend',
    'eusrr_backend.auth_backends.PositionRoleBackend',  # ← Наш backend
]
```

### Модели

**Файл:** `backend/employees/models.py`

```python
class Position(models.Model):
    """Должность сотрудника"""
    name = models.CharField(max_length=100, unique=True)
    groups = models.ManyToManyField(
        Group,
        related_name='positions',
        blank=True
    )

class Employee(models.Model):
    """Сотрудник"""
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    position = models.ForeignKey(
        Position,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )
```

## Тестовая Стратегия

### Цель Тестов
Определить, является ли проблема:
1. **Логической ошибкой** в `PositionRoleBackend` → Тесты упадут
2. **Проблемой конфигурации** (кэширование, LDAP sync, deployment) → Тесты пройдут

### Структура Тестов

**Файл:** `backend/tests/employees/test_position_permissions.py`

#### Базовые Тесты (TestPositionPermissions)
```python
class TestPositionPermissions:
    """Основная функциональность"""
    
    ✅ test_user_without_position_has_no_permissions
       Проверяет: Пользователь без должности = нет прав
    
    ❌ test_user_with_position_gets_permissions
       Проверяет: Position с Group → User получает права
       
    ❌ test_position_change_updates_permissions
       Проверяет: Смена должности → права обновляются
       
    ❌ test_remove_position_removes_permissions
       Проверяет: Удаление должности → права убираются
       
    ❌ test_multiple_users_same_position
       Проверяет: Несколько user с одной Position → одинаковые права
       
    ❌ test_staff_user_keeps_permissions
       Проверяет: Staff users сохраняют is_staff права
       
    ✅ test_position_group_permissions_are_additive
       Проверяет: Несколько групп → права складываются
       
    ❌ test_get_all_permissions_includes_position_perms
       Проверяет: get_all_permissions() возвращает права должности
```

#### Граничные Случаи (TestPositionPermissionsEdgeCases)
```python
class TestPositionPermissionsEdgeCases:
    """Edge cases и особые ситуации"""
    
    ✅ test_position_without_groups_grants_no_permissions
       Проверяет: Position без groups = нет прав
       
    ❌ test_inactive_user_has_no_permissions
       Проверяет: Неактивный user = нет прав (даже с Position)
       
    ❌ test_direct_user_permissions_and_position_permissions
       Проверяет: Прямые права user + права Position = аддитивны
```

#### Интеграционные Тесты (TestPositionPermissionsIntegration)
```python
class TestPositionPermissionsIntegration:
    """Интеграция с реальными моделями"""
    
    ❌ test_feed_publish_permission_via_position
       Проверяет: Право "feed.publish_company_post" работает
       
    ❌ test_document_add_permission_via_position
       Проверяет: Право "documents.add_document" работает
```

### Текущие Результаты
```
============== test session starts ==============
collected 13 items

✅ PASSED: 3 tests
❌ ERRORS: 10 tests

Passing Tests:
- test_user_without_position_has_no_permissions
- test_position_group_permissions_are_additive  
- test_position_without_groups_grants_no_permissions

Failing Tests:
- All tests with IntegrityError or fixture issues
```

## Обнаруженные Проблемы в Тестах

### Проблема 1: IntegrityError на Permission Creation
**Ошибка:**
```
IntegrityError: UNIQUE constraint failed: auth_permission.content_type_id, auth_permission.codename
```

**Причина:**
Использование `Permission.objects.get_or_create()` в фикстурах приводит к попыткам создать дубликаты.

**Решение:**
Изменить паттерн создания:

```python
# ❌ Старый код
perm, _ = Permission.objects.get_or_create(
    codename='publish_company_post',
    content_type=feed_content_type,
    defaults={'name': 'Can publish company post'}
)

# ✅ Новый код  
perm = Permission.objects.filter(
    codename='publish_company_post',
    content_type=feed_content_type
).first()

if not perm:
    perm = Permission.objects.create(
        codename='publish_company_post',
        content_type=feed_content_type,
        name='Can publish company post'
    )
```

**Статус:** Исправлено в 3 местах:
- ✅ Фикстура `group_with_publish_perm` (строки 44-62)
- ✅ Фикстура `group_with_document_perm` (строки 64-82)
- ✅ Тест `test_position_group_permissions_are_additive` (строки 244-269)

### Проблема 2: Fixture Visibility Between Test Classes
**Ошибка:**
```
fixture 'engineer_position' not found
fixture 'feed_content_type' not found
fixture 'documents_content_type' not found
```

**Причина:**
Фикстуры определены в `TestPositionPermissions` как методы класса, но дочерние классы `TestPositionPermissionsEdgeCases` и `TestPositionPermissionsIntegration` не имеют к ним доступа.

**Возможные решения:**
1. Перенести фикстуры на уровень модуля (вне классов)
2. Использовать `@pytest.fixture(scope="module")`
3. Использовать наследование классов
4. Создать фикстуры в `conftest.py`

**Статус:** ❌ Не исправлено

### Проблема 3: Permission Objects Already Exist in Database
**Ошибка:**
При запуске тестов Django уже имеет базовые права из миграций.

**Решение:**
Использовать `.filter().first()` вместо `.create()` для всех Permission объектов.

**Статус:** ✅ Частично исправлено (нужна проверка всех 13 тестов)

## План Исправления

### Шаг 1: Рефакторинг Фикстур ✅ IN PROGRESS
- [x] Заменить `get_or_create` на `filter().first()` + conditional create
- [x] Применить в `group_with_publish_perm`
- [x] Применить в `group_with_document_perm`
- [x] Применить в `test_position_group_permissions_are_additive`
- [ ] Перенести фикстуры на module level

### Шаг 2: Запуск Тестов
```bash
cd /c/Users/Игорь/Dev/EUSRR/backend
pytest tests/employees/test_position_permissions.py -v --tb=short
```

**Ожидаемый результат после исправлений:**
- Все 13 тестов должны запуститься (не ERROR)
- Проверим, сколько PASS vs FAIL

### Шаг 3: Анализ Результатов

#### Сценарий А: Все тесты PASS ✅
**Вывод:** Логика `PositionRoleBackend` корректна

**Действия:**
1. Проверить production конфигурацию:
   - `AUTHENTICATION_BACKENDS` order
   - Кэширование прав (Django cache)
   - LDAP синхронизация групп
   
2. Проверить данные в БД:
   ```python
   # Django shell
   user = User.objects.get(username='...')
   print(user.employee.position)
   print(user.employee.position.groups.all())
   print(user.get_all_permissions())  # Должны быть права из Position
   ```

3. Проверить middleware и template context

#### Сценарий Б: Некоторые тесты FAIL ❌
**Вывод:** Есть проблема в логике `PositionRoleBackend`

**Действия:**
1. Проанализировать failing assertions
2. Исправить `get_all_permissions()` или `has_perm()`
3. Убедиться что query `Permission.objects.filter(group__positions=pos)` корректен
4. Проверить returns в формате "app_label.codename"

## Проверка UI Visibility

### Текущая Реализация

**Файл:** `backend/templates/feed/feed_list.html` (строка 19)
```html
{% if user.is_staff or perms.feed.publish_company_post or perms.feed.publish_department_post %}
    <button class="btn btn-primary">Создать публикацию</button>
{% endif %}
```

**Файл:** `backend/templates/documents/document_list.html` (строки 17-21)
```html
{% if user.is_staff or perms.documents.add_document %}
    <a href="{% url 'documents:document_create' %}" class="btn btn-primary">
        Добавить документ
    </a>
{% endif %}
```

### Логика Проверки в Templates

Django использует `perms.app_label.codename` в шаблонах:
1. Вызывает `user.has_perm('app_label.codename')`
2. Проходит по всем AUTHENTICATION_BACKENDS
3. Если хотя бы один backend вернёт `True` → permission granted

**Требования:**
- `PositionRoleBackend.has_perm()` должен вернуть `True`
- `PositionRoleBackend.get_all_permissions()` должен включать это право
- Формат: tuple `('app_label', 'codename')` или строка `'app_label.codename'`

## Отладочные Команды

### Django Shell Testing
```python
from django.contrib.auth.models import User, Permission, Group
from django.contrib.contenttypes.models import ContentType
from employees.models import Employee, Position

# Получить пользователя
user = User.objects.get(username='test_user')

# Проверить должность
print(f"Position: {user.employee.position}")
print(f"Position Groups: {user.employee.position.groups.all()}")

# Проверить права через backend
from eusrr_backend.auth_backends import PositionRoleBackend
backend = PositionRoleBackend()
all_perms = backend.get_all_permissions(user)
print(f"All Permissions: {all_perms}")

# Проверить has_perm
has_perm = backend.has_perm(user, 'feed.publish_company_post')
print(f"Has feed.publish_company_post: {has_perm}")

# Проверить через Django API
has_perm_django = user.has_perm('feed.publish_company_post')
print(f"User.has_perm('feed.publish_company_post'): {has_perm_django}")
```

### SQL Query Debugging
```python
from django.db import connection
from django.test.utils import CaptureQueriesContext

with CaptureQueriesContext(connection) as queries:
    perms = backend.get_all_permissions(user)
    
for q in queries:
    print(q['sql'])
```

### LDAP Group Sync Check
```python
from employees.ldap.services import PositionService

pos = Position.objects.get(name='Engineer')
dn = PositionService._ensure_position_group(pos)
print(f"LDAP Group DN: {dn}")
```

## Ожидаемая SQL Query

При вызове `get_all_permissions()` должен выполниться query:

```sql
SELECT DISTINCT 
    django_content_type.app_label,
    auth_permission.codename
FROM auth_permission
INNER JOIN django_content_type 
    ON auth_permission.content_type_id = django_content_type.id
INNER JOIN auth_group_permissions 
    ON auth_permission.id = auth_group_permissions.permission_id
INNER JOIN auth_group 
    ON auth_group_permissions.group_id = auth_group.id
INNER JOIN employees_position_groups 
    ON auth_group.id = employees_position_groups.group_id
WHERE employees_position_groups.position_id = ?
```

## Контрольный Чеклист

### Pre-Test Checklist
- [x] Создан файл `tests/employees/test_position_permissions.py`
- [x] 13 тестов покрывают все сценарии
- [x] Фикстуры используют `.filter().first()` для Permission
- [ ] Фикстуры доступны во всех test классах
- [ ] Тесты запускаются без ERROR

### Post-Test Checklist (если тесты проходят)
- [ ] Проверить `user.get_all_permissions()` в production shell
- [ ] Проверить `user.has_perm('feed.publish_company_post')` в production
- [ ] Проверить что `Position.groups` содержит нужные группы
- [ ] Проверить что `Group.permissions` содержит нужные права
- [ ] Проверить порядок AUTHENTICATION_BACKENDS
- [ ] Очистить Django permission cache
- [ ] Перезапустить сервер

### Post-Test Checklist (если тесты не проходят)
- [ ] Проанализировать failing assertions
- [ ] Исправить логику в `PositionRoleBackend.get_all_permissions()`
- [ ] Исправить логику в `PositionRoleBackend.has_perm()`
- [ ] Убедиться что query возвращает правильный формат
- [ ] Проверить related_name в моделях
- [ ] Перезапустить тесты

## Следующие Шаги

1. **Сейчас:** Исправить fixture visibility (перенести на module level)
2. **Потом:** Запустить pytest с verbose output
3. **Далее:** Проанализировать PASS/FAIL результаты
4. **Финал:** Исправить production или backend в зависимости от результатов

## Дополнительная Информация

### Связанные Файлы
- `backend/eusrr_backend/auth_backends.py` - PositionRoleBackend
- `backend/employees/models.py` - Position, Employee
- `backend/templates/feed/feed_list.html` - UI для публикаций
- `backend/templates/documents/document_list.html` - UI для документов
- `backend/tests/employees/test_position_permissions.py` - Тесты

### Связанные Коммиты
- `769f2ed` - test: add comprehensive position permissions tests

### Известные Ограничения
- Права кэшируются Django (может требовать перезапуска)
- LDAP синхронизация может задерживаться
- Staff users всегда имеют все права (is_staff=True)

---

**Документ создан:** 2025-01-XX  
**Последнее обновление:** После фикса Permission creation pattern  
**Статус:** 🔄 Отладка тестовой инфраструктуры
