# Отчет: Сериализаторы системы ролей отделов

**Дата**: 30.12.2025  
**Анализ**: DepartmentRoleSerializer, SetMemberRoleInput — валидация, backward compatibility

---

## 1. DepartmentRoleSerializer — Основной сериализатор

### Расположение
`backend/api/v1/employees/serializers.py` (строки 589-675)

### Назначение
Сериализация/десериализация объектов `DepartmentRole` с поддержкой:
- Записи прав по ID или кодам
- Backward compatibility для старого API
- Валидации уникальности и принадлежности прав

---

## 2. Структура полей

### 2.1 Основные поля

```python
class DepartmentRoleSerializer(serializers.ModelSerializer):
    scoped_permissions = serializers.PrimaryKeyRelatedField(
        queryset=DepartmentPermission.objects.all(), 
        many=True, 
        required=False
    )
    scoped_permission_codes = serializers.ListField(
        child=serializers.CharField(), 
        required=False, 
        write_only=True
    )
    
    # Backward-compat (read-only)
    permissions = serializers.SerializerMethodField(read_only=True)
    permissions_verbose = serializers.SerializerMethodField(read_only=True)
    
    class Meta:
        model = DepartmentRole
        fields = (
            "id",
            "department",
            "name",
            # новые write-поля
            "scoped_permissions",
            "scoped_permission_codes",
            # совместимость (read-only зеркала)
            "permissions",
            "permissions_verbose",
        )
        read_only_fields = ("id",)
```

### 2.2 Матрица полей

| Поле | Тип | Read/Write | Required | Назначение |
|------|-----|------------|----------|------------|
| `id` | Integer | Read-only | — | PK роли |
| `department` | Integer (FK) | Read/Write | Yes (create) | ID отдела |
| `name` | String | Read/Write | Yes | Название роли |
| `scoped_permissions` | List[Integer] | Read/Write | No | ID прав (новая схема) |
| `scoped_permission_codes` | List[String] | Write-only | No | Коды прав (альтернатива) |
| `permissions` | List[Integer] | Read-only | — | Legacy: ID прав |
| `permissions_verbose` | List[Object] | Read-only | — | Legacy: полная инфо прав |

---

## 3. Логика создания (CREATE)

### 3.1 Метод create()

```python
def create(self, validated_data):
    # Вытаскиваем write-only/внешние поля до super().create()
    codes = validated_data.pop("scoped_permission_codes", None)
    perms = validated_data.pop("scoped_permissions", None)
    
    role = super().create(validated_data)
    
    if perms is not None:
        role.scoped_permissions.set(perms)
    
    if codes is not None:
        qs = DepartmentPermission.objects.filter(code__in=codes)
        if qs.count() != len(set(codes)):
            raise serializers.ValidationError(
                {"scoped_permission_codes": "Некоторые коды не существуют"}
            )
        role.scoped_permissions.set(list(qs))
    
    return role
```

### 3.2 Порядок операций

```
1. validated_data = {department, name, scoped_permissions, scoped_permission_codes}
                                ↓
2. Извлечь codes и perms из validated_data (pop)
                                ↓
3. super().create(validated_data)  # создать role без M2M
                                ↓
4. Если есть perms → role.scoped_permissions.set(perms)
                                ↓
5. Если есть codes → валидация → role.scoped_permissions.set(...)
                                ↓
6. Return role
```

### 3.3 Приоритет

**Если указаны оба поля:**
```python
if perms is not None:
    role.scoped_permissions.set(perms)  # Применяется первым

if codes is not None:
    # ... валидация ...
    role.scoped_permissions.set(list(qs))  # Перезаписывает предыдущее!
```

**Вывод**: `scoped_permission_codes` имеет **больший приоритет** и перезапишет `scoped_permissions`.

---

## 4. Логика обновления (UPDATE)

### 4.1 Метод update()

```python
def update(self, instance, validated_data):
    # Аналогично: вынимаем до super().update()
    codes = validated_data.pop("scoped_permission_codes", None)
    perms = validated_data.pop("scoped_permissions", None)
    
    role = super().update(instance, validated_data)
    
    if perms is not None:
        role.scoped_permissions.set(perms)
    
    if codes is not None:
        qs = DepartmentPermission.objects.filter(code__in=codes)
        if qs.count() != len(set(codes)):
            raise serializers.ValidationError(
                {"scoped_permission_codes": "Некоторые коды не существуют"}
            )
        role.scoped_permissions.set(list(qs))
    
    return role
```

### 4.2 Особенности PATCH

**При PATCH запросе без указания прав:**
```json
PATCH /api/v1/department-roles/12/
{
  "name": "New Name"
}
```

- `perms` и `codes` будут `None`
- Права **не изменятся** (не будут очищены)
- Обновится только `name`

**При явном указании пустого массива:**
```json
{
  "scoped_permissions": []
}
```
- Все права будут **удалены**: `role.scoped_permissions.set([])`

---

## 5. Backward Compatibility

### 5.1 Поле permissions (read-only)

```python
def get_permissions(self, obj: DepartmentRole):
    return list(obj.scoped_permissions.values_list("id", flat=True))
```

**Назначение**: Старый API возвращал список ID прав. Теперь это зеркало `scoped_permissions`.

**Пример ответа**:
```json
{
  "id": 12,
  "scoped_permissions": [1, 3, 5],
  "permissions": [1, 3, 5]  // дубликат для совместимости
}
```

### 5.2 Поле permissions_verbose (read-only)

```python
def get_permissions_verbose(self, obj: DepartmentRole):
    return [
        {"id": p.id, "code": p.code, "name": p.name}
        for p in obj.scoped_permissions.order_by("code").all()
    ]
```

**Назначение**: Полная информация о правах с сортировкой по `code`.

**Пример ответа**:
```json
{
  "permissions_verbose": [
    {"id": 3, "code": "assign_department_role", "name": "Назначать роли участникам"},
    {"id": 1, "code": "manage_department", "name": "Управлять отделом"}
  ]
}
```

**Сортировка**: По коду прав (алфавитный порядок).

---

## 6. Валидация

### 6.1 Валидация кодов прав

```python
if codes is not None:
    qs = DepartmentPermission.objects.filter(code__in=codes)
    if qs.count() != len(set(codes)):
        raise serializers.ValidationError(
            {"scoped_permission_codes": "Некоторые коды не существуют"}
        )
```

**Проверки**:
1. `set(codes)` — устраняет дубликаты в запросе
2. `qs.count()` — количество найденных в БД
3. Если не совпадают → какие-то коды не существуют

**Пример ошибки**:
```json
{
  "scoped_permission_codes": ["Некоторые коды не существуют"]
}
```

### 6.2 Валидация уникальности (department, name)

**Уровень проверки**: Constraint БД `unique_together = [('department', 'name')]`

**Ошибка при дубликате**:
```python
# Django автоматически поднимает IntegrityError
# DRF оборачивает в ValidationError
```

**Пример ответа**:
```json
{
  "non_field_errors": ["The fields department, name must make a unique set."]
}
```

### 6.3 Валидация ID прав (scoped_permissions)

```python
scoped_permissions = serializers.PrimaryKeyRelatedField(
    queryset=DepartmentPermission.objects.all(),
    many=True,
    required=False
)
```

**Автоматическая проверка**:
- Все указанные ID должны существовать в `DepartmentPermission`
- При несуществующем ID → `ValidationError`

---

## 7. SetMemberRoleInput — Назначение роли сотруднику

### Расположение
`backend/api/v1/employees/serializers.py` (строки 712-734)

### Назначение
Валидация payload для `Department.set_member_role()` endpoint.

### Структура

```python
class SetMemberRoleInput(serializers.Serializer):
    # Поддерживаем алиасы: employee / role
    employee_id = serializers.IntegerField(required=False)
    role_id = serializers.IntegerField(allow_null=True, required=False)
    employee = serializers.IntegerField(required=False)
    role = serializers.IntegerField(allow_null=True, required=False)
    is_active = serializers.BooleanField(required=False)  # новый флаг
    
    def validate(self, attrs):
        # Нормализация алиасов
        if "employee" in attrs and "employee_id" not in attrs:
            attrs["employee_id"] = attrs.pop("employee")
        if "role" in attrs and "role_id" not in attrs:
            attrs["role_id"] = attrs.pop("role")
        
        # Проверка обязательного employee_id
        if "employee_id" not in attrs:
            raise serializers.ValidationError(
                {"employee_id": "This field is required."}
            )
        
        return attrs
```

### Поддерживаемые форматы

**Вариант 1: Явные суффиксы**
```json
{
  "employee_id": 42,
  "role_id": 12
}
```

**Вариант 2: Короткие имена**
```json
{
  "employee": 42,
  "role": 12
}
```

**Вариант 3: Снятие роли**
```json
{
  "employee_id": 42,
  "role_id": null  // или просто не указывать поле
}
```

**Вариант 4: С флагом активности (новое)**
```json
{
  "employee_id": 42,
  "role_id": 12,
  "is_active": false  // деактивировать членство
}
```

### Особенности валидации

**employee_id обязателен**:
```python
if "employee_id" not in attrs:
    raise serializers.ValidationError(...)
```

**role_id опционален**:
```python
role_id = serializers.IntegerField(allow_null=True, required=False)
```
- Если `null` или отсутствует → роль снимается
- Если указан → назначается

**is_active опционален**:
- Новое поле (недавно добавлено)
- Позволяет изменять активность членства при назначении роли

---

## 8. Проблемные места

### 8.1 Двойная установка прав при наличии обоих полей

**Проблема**:
```python
if perms is not None:
    role.scoped_permissions.set(perms)  # Шаг 1

if codes is not None:
    # валидация
    role.scoped_permissions.set(list(qs))  # Шаг 2: перезаписывает!
```

**Последствие**: Если клиент отправит оба поля, `scoped_permissions` будет проигнорирован.

**Решение**: Добавить валидацию:
```python
def validate(self, attrs):
    if 'scoped_permissions' in attrs and 'scoped_permission_codes' in attrs:
        raise serializers.ValidationError(
            "Cannot specify both scoped_permissions and scoped_permission_codes"
        )
    return attrs
```

---

### 8.2 Нет валидации принадлежности роли к отделу

**Проблема**: На уровне сериализатора не проверяется, что `role.department_id == validated_data['department']`.

**Где защита**: Только в ViewSet и на уровне БД constraint.

**Риск**: Если сериализатор используется вне ViewSet, можно создать несогласованные данные.

**Решение**: Добавить кастомную валидацию:
```python
def validate(self, attrs):
    role_id = attrs.get('role_id')
    dept_id = attrs.get('department')
    if role_id and dept_id:
        role = DepartmentRole.objects.filter(id=role_id).first()
        if role and role.department_id != dept_id:
            raise serializers.ValidationError({
                'role_id': 'Role must belong to the specified department'
            })
    return attrs
```

---

### 8.3 Дублирование логики валидации кодов

**Проблема**: Одинаковая логика в `create()` и `update()`:
```python
# В обоих методах:
if codes is not None:
    qs = DepartmentPermission.objects.filter(code__in=codes)
    if qs.count() != len(set(codes)):
        raise serializers.ValidationError(...)
    role.scoped_permissions.set(list(qs))
```

**Решение**: Вынести в приватный метод:
```python
def _apply_codes_if_present(self, instance: DepartmentRole, validated_data: dict):
    codes = validated_data.pop("scoped_permission_codes", None)
    if codes is not None:
        qs = DepartmentPermission.objects.filter(code__in=codes)
        if qs.count() != len(set(codes)):
            raise serializers.ValidationError(
                {"scoped_permission_codes": "Некоторые коды не существуют"}
            )
        instance.scoped_permissions.set(list(qs))
```

**Текущий код**: Этот метод уже существует (`_apply_codes_if_present`), но **не используется** в `create()`/`update()`! Дублирование осталось.

---

### 8.4 Backward-compat поля увеличивают размер ответа

**Проблема**:
```json
{
  "scoped_permissions": [1, 3, 5],
  "permissions": [1, 3, 5],  // дубликат
  "permissions_verbose": [
    {"id": 1, "code": "manage_department", "name": "..."},
    {"id": 3, "code": "assign_department_role", "name": "..."},
    {"id": 5, "code": "view_request", "name": "..."}
  ]
}
```

**Последствие**: При списке из 50 ролей размер ответа удваивается из-за дублирования.

**Решение**: 
- Использовать query param для включения legacy полей: `?include_legacy=true`
- Или перейти на v2 API без backward-compat

---

## 9. Использование в коде

### 9.1 В DepartmentRoleViewSet

```python
class DepartmentRoleViewSet(viewsets.ModelViewSet):
    serializer_class = DepartmentRoleSerializer
    
    # Автоматически используется в:
    # - list() → many=True
    # - retrieve() → один объект
    # - create() → validation + создание
    # - update()/partial_update() → validation + обновление
```

### 9.2 В DepartmentViewSet.ui_context()

```python
roles_qs = DepartmentRole.objects.filter(department_id=dept.id)
roles_data = DepartmentRoleSerializer(roles_qs, many=True).data
```

**Цель**: Получить все роли отдела для отображения в UI.

---

## 10. Сравнение с другими сериализаторами

### 10.1 GroupSerializer (Django Groups)

```python
class GroupSerializer(serializers.ModelSerializer):
    permissions = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(), many=True, required=False
    )
    permissions_verbose = serializers.SerializerMethodField(read_only=True)
```

**Отличия**:
- Нет поддержки кодов (только ID)
- Нет backward-compat (новое поле)
- Работает с глобальными Django permissions

**Сходства**:
- M2M к permissions
- Verbose поле для полной информации

---

## 11. Примеры запросов/ответов

### 11.1 CREATE с кодами прав

**Request**:
```http
POST /api/v1/department-roles/
Content-Type: application/json

{
  "department": 5,
  "name": "Tech Lead",
  "scoped_permission_codes": [
    "manage_department",
    "assign_department_role",
    "manage_department_events"
  ]
}
```

**Response** (201):
```json
{
  "id": 15,
  "department": 5,
  "name": "Tech Lead",
  "scoped_permissions": [1, 3, 4],
  "permissions": [1, 3, 4],
  "permissions_verbose": [
    {"id": 3, "code": "assign_department_role", "name": "Назначать роли участникам"},
    {"id": 1, "code": "manage_department", "name": "Управлять отделом"},
    {"id": 4, "code": "manage_department_events", "name": "Управлять календарём отдела"}
  ]
}
```

### 11.2 UPDATE только названия

**Request**:
```http
PATCH /api/v1/department-roles/15/
Content-Type: application/json

{
  "name": "Senior Tech Lead"
}
```

**Response** (200):
```json
{
  "id": 15,
  "department": 5,
  "name": "Senior Tech Lead",
  "scoped_permissions": [1, 3, 4],  // не изменились
  ...
}
```

### 11.3 Ошибка валидации кодов

**Request**:
```http
POST /api/v1/department-roles/
Content-Type: application/json

{
  "department": 5,
  "name": "Invalid Role",
  "scoped_permission_codes": ["manage_department", "nonexistent_code"]
}
```

**Response** (400):
```json
{
  "scoped_permission_codes": ["Некоторые коды не существуют"]
}
```

---

## 12. Рекомендации по улучшению

### 12.1 Использовать метод _apply_codes_if_present

```python
def create(self, validated_data):
    perms = validated_data.pop("scoped_permissions", None)
    role = super().create(validated_data)
    
    if perms is not None:
        role.scoped_permissions.set(perms)
    
    self._apply_codes_if_present(role, validated_data)  # ← использовать
    return role
```

### 12.2 Добавить mutual exclusion валидацию

```python
def validate(self, attrs):
    if 'scoped_permissions' in attrs and 'scoped_permission_codes' in attrs:
        raise serializers.ValidationError(
            "Specify either scoped_permissions or scoped_permission_codes, not both"
        )
    return attrs
```

### 12.3 Сделать department read-only при update

```python
class Meta:
    model = DepartmentRole
    fields = (...)
    extra_kwargs = {
        'department': {'required': True}  # обязательно при create
    }

def __init__(self, *args, **kwargs):
    super().__init__(*args, **kwargs)
    if self.instance is not None:  # update
        self.fields['department'].read_only = True
```

### 12.4 Оптимизировать backward-compat

```python
def __init__(self, *args, **kwargs):
    include_legacy = kwargs.pop('include_legacy', False)
    super().__init__(*args, **kwargs)
    
    if not include_legacy:
        self.fields.pop('permissions', None)
        self.fields.pop('permissions_verbose', None)
```

**Использование**:
```python
serializer = DepartmentRoleSerializer(role, include_legacy=True)
```

---

## 13. Итоговая схема потока данных

```
┌────────────────────────────────────────┐
│ Client Request Body                    │
│ {department, name,                     │
│  scoped_permission_codes: [...]}       │
└────────────────────────────────────────┘
                 ↓
┌────────────────────────────────────────┐
│ DepartmentRoleSerializer.to_internal   │
│  - Validate fields                     │
│  - Convert codes to internal format    │
└────────────────────────────────────────┘
                 ↓
┌────────────────────────────────────────┐
│ create() / update()                    │
│  1. Pop codes and perms from data      │
│  2. super().create/update (basic)      │
│  3. Set M2M: scoped_permissions        │
│  4. Validate codes → query DB          │
│  5. Set M2M with codes if present      │
└────────────────────────────────────────┘
                 ↓
┌────────────────────────────────────────┐
│ DepartmentRoleSerializer.to_represent  │
│  - Add scoped_permissions              │
│  - Add permissions (backward-compat)   │
│  - Add permissions_verbose             │
└────────────────────────────────────────┘
                 ↓
┌────────────────────────────────────────┐
│ Response with all fields               │
└────────────────────────────────────────┘
```

---

**Следующий отчет**: [04_DEPARTMENT_ROLES_PERMISSIONS.md](./04_DEPARTMENT_ROLES_PERMISSIONS.md) — Система проверки прав
