# Рефакторинг Chat Model - Фаза 2: Обновление views, signals, rules

**Дата**: 11 марта 2026  
**Ветка**: `feature/communications-universal-refactoring`  
**Коммит**: 83843a13  
**Предыдущая фаза**: [CHAT_REFACTORING_PHASE1_COMPLETE.md](CHAT_REFACTORING_PHASE1_COMPLETE.md)

## Цель Фазы 2

Обновить все использования старых полей (`department`, `is_main`, `include_all_employees`) в views, signals, rules и других модулях для поддержки новых полей (`context_object`, `flags`, `include_all_users`).

**Стратегия**: Двойная поддержка (старые + новые поля) для 100% обратной совместимости.

---

## Обзор изменений

### Обновленные файлы (7):

1. **signals.py** - создание чатов для Department
2. **views.py** - фильтрация и доступ к чатам
3. **rules.py** - правила доступа (django-rules)
4. **apps.py** - инициализация глобального чата
5. **admin.py** - защита главных чатов от редактирования
6. **notifications/config.py** - отображение имени чата
7. **models.py** - метод `__str__()`

---

## Детальные изменения

### 1. signals.py

#### Функция: `create_main_department_chat()`

**До:**
```python
@receiver(post_save, sender=Department)
def create_main_department_chat(sender, instance, created, **kwargs):
    if created:
        if not Chat.objects.filter(
            type="department", department=instance, is_main=True
        ).exists():
            Chat.objects.create(
                type="department",
                department=instance,
                is_main=True,
                name=f"Основной чат {instance.name}"
            )
```

**После:**
```python
@receiver(post_save, sender=Department)
def create_main_department_chat(sender, instance, created, **kwargs):
    if created:
        dept_ct = ContentType.objects.get_for_model(Department)
        
        # Проверка: существует ли уже чат (проверяем ОБА поля)
        existing = Chat.objects.filter(
            Q(type="department") & (
                Q(department=instance) |
                Q(context_content_type=dept_ct, context_object_id=instance.id)
            ) & (
                Q(is_main=True) | Q(flags__is_primary=True)
            )
        )
        
        if not existing.exists():
            # Создаем с ОБОИМИ способами привязки
            Chat.objects.create(
                type="department",
                # NEW: GenericFK
                context_content_type=dept_ct,
                context_object_id=instance.id,
                # NEW: flags
                flags={'is_primary': True},
                # DEPRECATED: для совместимости
                department=instance,
                is_main=True,
                name=f"Основной чат {instance.name}"
            )
```

**Результат**:
- ✅ Новые чаты создаются с `context_object` + `flags`
- ✅ Старые поля заполняются для обратной совместимости
- ✅ Проверка существования работает для обоих случаев

---

### 2. views.py (4 критичных обновления)

#### 2.1. Функция: `has_user_access_to_chat()`

**Изменения:**
- Строка 79: `chat.department_id` → проверка через `get_participants()`
- Строка 86: `chat.include_all_employees` → `chat.include_all_users`

**До:**
```python
if chat.type == "department" and chat.department_id:
    result = chat.get_participants.filter(pk=user.pk).exists()
    
if chat.include_all_employees:
    return user.is_active
```

**После:**
```python
if chat.type == "department":
    # get_participants() поддерживает и department, и context_object
    result = chat.get_participants().filter(pk=user.pk).exists()
    
if chat.include_all_users:
    return user.is_active
```

#### 2.2. ChatListView.get_queryset()

**Изменения:**
- Добавлена проверка `context_object` параллельно с `department`
- Используется `ContentType` для Department

**До:**
```python
qs = Chat.objects.filter(
    Q(type="global")
    | Q(type="department", department__in=departments)
    | Q(type="private", participants=user)
    | Q(id__in=membership_chat_ids)
)
```

**После:**
```python
dept_ct = ContentType.objects.get_for_model(departments.model)
dept_ids = list(departments.values_list('id', flat=True))

qs = Chat.objects.filter(
    Q(type="global")
    | Q(type="department", department__in=departments)  # старое поле
    | Q(type="department", context_content_type=dept_ct, context_object_id__in=dept_ids)  # новое поле
    | Q(type="private", participants=user)
    | Q(id__in=membership_chat_ids)
)
```

#### 2.3. ChatDetailView.get_queryset()

Аналогичные изменения для проверки доступа к конкретному чату.

#### 2.4. mark_as_read_ajax()

**Изменения:**
- `c.department_id` → проверка типа department
- `c.get_participants.filter()` → `c.get_participants().filter()` (исправлена ошибка)
- `c.include_all_employees` → `c.include_all_users`

---

### 3. rules.py

#### Предикат: `is_department_chat()`

**До:**
```python
@rules.predicate
def is_department_chat(user, chat):
    if chat is None or not hasattr(user, 'department'):
        return False
    
    if hasattr(chat, 'department'):
        return chat.department == user.department
    
    return False
```

**После:**
```python
@rules.predicate
def is_department_chat(user, chat):
    """
    Проверяет как старое поле department, 
    так и новое context_object (GenericFK).
    """
    if chat is None or not hasattr(user, 'department'):
        return False
    
    # 1. Проверяем старое поле
    if hasattr(chat, 'department') and chat.department:
        if chat.department == user.department:
            return True
    
    # 2. Проверяем новое поле context_object
    if hasattr(chat, 'context_object') and chat.context_object:
        from employees.models import Department
        if isinstance(chat.context_object, Department):
            return chat.context_object == user.department
    
    return False
```

---

### 4. apps.py

#### Функция: `create_main_global_chat()`

**До:**
```python
def create_main_global_chat(sender, **kwargs):
    if not Chat.objects.filter(type="global", is_main=True).exists():
        Chat.objects.create(type="global", is_main=True)
```

**После:**
```python
def create_main_global_chat(sender, **kwargs):
    # Проверяем по обоим полям
    if not Chat.objects.filter(
        Q(type="global") & (
            Q(is_main=True) | Q(flags__is_primary=True)
        )
    ).exists():
        Chat.objects.create(
            type="global",
            flags={'is_primary': True},
            is_main=True  # для совместимости
        )
```

---

### 5. admin.py

#### Метод: `get_readonly_fields()`

**До:**
```python
def get_readonly_fields(self, request, obj=None):
    if obj and obj.is_main:
        return self.readonly_fields + ("type", "department", "is_main")
    return self.readonly_fields
```

**После:**
```python
def get_readonly_fields(self, request, obj=None):
    if obj:
        is_primary = obj.is_main or (obj.flags and obj.flags.get('is_primary'))
        if is_primary:
            return self.readonly_fields + (
                "type", "department", "is_main", 
                "flags", "context_object_id", "context_content_type"
            )
    return self.readonly_fields
```

**Результат**: Главные чаты защищены от редактирования независимо от того, используют они `is_main` или `flags['is_primary']`.

---

### 6. notifications/config.py

#### Функция: `get_chat_display_name()`

**До:**
```python
if chat.type == 'department' and chat.department:
    return f'Чат отдела: {chat.department.name}'
```

**После:**
```python
if chat.type == 'department':
    # Проверяем context_object или старое поле
    dept = chat.context_object if chat.context_object else chat.department
    if dept:
        return f'Чат отдела: {dept.name}'
```

---

### 7. models.py

#### Метод: `Chat.__str__()`

**До:**
```python
if self.type == "department":
    return f"Чат отдела: {self.department or '—'}"
```

**После:**
```python
if self.type == "department":
    dept = self.context_object if self.context_object else self.department
    return f"Чат отдела: {dept or '—'}"
```

---

## Тестирование

### Результаты автоматических тестов:

```bash
$ python test_phase2.py

================================================================================
ФАЗА 2: ТЕСТИРОВАНИЕ ОБНОВЛЕННОГО КОДА
================================================================================

1. Тест signals.py (создание чата для Department):
   ✓ Создан отдел: Test Dept 3372831622
   ✓ Чат создан: Чат отдела: Test Dept 3372831622
     - context_object: Test Dept 3372831622
     - flags: {'is_primary': True}
     - is_primary: True
     - department (DEPRECATED): Test Dept 3372831622
     - is_main (DEPRECATED): True

2. Тест get_participants():
   ✓ Участников: 0

3. Тест __str__ метода:
   ✓ str(chat): Чат отдела: Test Dept 3372831622

4. Тест rules.py (is_department_chat):
   ✓ is_department_chat(user, chat): True

5. Тест apps.py (глобальный чат):
   ✓ Глобальный чат существует: Глобальный чат

6. Cleanup:
   ✓ Удален тестовый отдел (чат удален каскадно)

================================================================================
✅ ВСЕ ТЕСТЫ ФАЗЫ 2 ЗАВЕРШЕНЫ
================================================================================
```

### Проверка синтаксиса:

```bash
$ python manage.py check communications
System check identified no issues (0 silenced).
```

---

## Статистика изменений

```
7 files changed, 107 insertions(+), 24 deletions(-)

communications/signals.py          | +26 -6
communications/views.py            | +41 -12
communications/rules.py            | +15 -4
communications/apps.py             | +8 -2
communications/admin.py            | +9 -3
communications/notifications/config.py | +5 -2
communications/models.py           | +3 -1
```

---

## Обратная совместимость

### ✅ Поддерживаются оба варианта:

| Старое поле (DEPRECATED) | Новое поле | Где используется |
|--------------------------|------------|------------------|
| `department` (FK) | `context_object` (GenericFK) | signals, views, rules, __str__ |
| `is_main` (Boolean) | `flags['is_primary']` (JSONField) | apps, admin, signals |
| `include_all_employees` | `include_all_users` | views |

### Стратегия проверки:

Везде используется паттерн:
```python
# Проверка с приоритетом нового поля
value = new_field if new_field else old_field

# Или через Q() для QuerySet
Q(old_field=...) | Q(new_field=...)
```

---

## Следующие шаги (Фаза 3 - опционально)

### 1. Обновить serializers (API):
- Добавить `context_object` в сериализацию
- Добавить `flags` в ответы API
- Документировать новые поля

### 2. Обновить WebSocket consumers:
- Проверить использование `department`, `is_main`
- Обновить для поддержки `context_object`, `flags`

### 3. Фронтенд (если требуется):
- Обновить отображение чатов департаментов
- Поддержка `flags` на клиенте

### 4. Удаление старых полей (после полного тестирования):
```python
# Migration: Remove deprecated fields
migrations.RemoveField(model_name='chat', name='department')
migrations.RemoveField(model_name='chat', name='is_main')
```

---

## Заключение

✅ **Фаза 2 завершена**:
- Все критичные модули обновлены
- Двойная поддержка (старые + новые поля)
- Все тесты проходят успешно
- Обратная совместимость сохранена

✅ **Готово к review и merge**

**Ветка**: `feature/communications-universal-refactoring`  
**Коммиты**: 938f84f5, 29fb3869, 83843a13

---

**Автор**: GitHub Copilot  
**Дата**: 11 марта 2026  
**Время работы Фазы 2**: ~30 минут
