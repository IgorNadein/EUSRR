# Интеграция django-rules: Object-Level Permissions

**Дата:** 28 февраля 2026  
**Статус:** ✅ Базовая интеграция завершена  
**Ветка:** `feature/django-rules`

## Обзор

django-rules — это библиотека для декларативного управления правами доступа на уровне объектов в Django. Она позволяет определять сложную логику permissions через композицию простых предикатов.

### Преимущества

- ✅ **Object-level permissions**: проверка прав на конкретные объекты
- ✅ **Декларативный синтаксис**: правила определяются явно и читаемо
- ✅ **Композиция**: комбинирование предикатов через `&`, `|`, `~`
- ✅ **Интеграция**: работает с Django, DRF, Admin, Templates
- ✅ **Производительность**: легковесная библиотека без overhead
- ✅ **Тестируемость**: правила легко покрываются unit-тестами

### Ссылки

- **GitHub**: https://github.com/dfunckt/django-rules
- **Документация**: https://github.com/dfunckt/django-rules#rules
- **PyPI**: https://pypi.org/project/rules/

---

## Установка и настройка

### 1. Установка пакета

```bash
../.venv/Scripts/pip install rules==3.5
```

Добавлено в `requirements.txt`:
```
rules==3.5
```

### 2. Настройка Django

**settings.py**:

```python
INSTALLED_APPS = [
    # ...
    "rules",  # django-rules для декларативных permissions
    # ...
]

AUTHENTICATION_BACKENDS = [
    "eusrr_backend.auth_backends.LDAP3Backend",
    "eusrr_backend.auth_backends.EmailOrPhoneBackend",
    "eusrr_backend.auth_backends.SuperuserOnlyBackend",
    "eusrr_backend.auth_backends.PositionRoleBackend",
    "rules.permissions.ObjectPermissionBackend",  # ← django-rules backend
    "django.contrib.auth.backends.ModelBackend",
]
```

### 3. Создание файлов правил

Созданы базовые правила для двух приложений:

- **employees/rules.py**: правила доступа к профилям сотрудников
- **documents/rules.py**: правила доступа к документам

---

## Архитектура правил

### Базовая структура

```python
import rules

# 1. ПРЕДИКАТЫ - базовые проверки (возвращают True/False)
@rules.predicate
def is_document_owner(user, document):
    return document.owner == user

# 2. ПРАВИЛА - композиция предикатов
rules.add_rule(
    'documents.view_document',
    is_superuser | is_document_owner | has_document_access
)

# 3. PERMISSIONS (опционально) - регистрация в Django permissions
rules.add_perm('documents.view_document', is_superuser | is_document_owner)
```

### Композиция предикатов

```python
# Логическое И (AND)
rule = predicate1 & predicate2

# Логическое ИЛИ (OR)
rule = predicate1 | predicate2

# Логическое НЕ (NOT)
rule = ~predicate1

# Сложные комбинации
rule = (is_owner | is_admin) & ~is_banned & has_subscription
```

---

## Реализованные правила

### Employees (employees/rules.py)

#### Предикаты:
- `is_superuser` — пользователь является суперюзером
- `is_staff` — пользователь имеет статус персонала
- `is_hr_staff` — HR сотрудник (по должности)
- `is_department_head` — руководитель отдела
- `is_own_profile` — собственный профиль
- `is_same_department` — сотрудники в одном отделе

#### Правила:
- `employees.view_employee` — просмотр профиля
- `employees.change_employee` — изменение профиля
- `employees.delete_employee` — удаление сотрудника
- `employees.view_all_employees` — просмотр списка
- `employees.view_reports` — просмотр отчётов
- `employees.change_position` — изменение должности
- `employees.change_department` — изменение отдела
- `employees.view_contact_info` — просмотр контактов

### Documents (documents/rules.py)

#### Предикаты:
- `is_document_owner` — владелец документа
- `is_document_author` — автор документа
- `has_document_access` — доступ через is_public/department/shared
- `can_approve_documents` — может согласовывать (по должности)
- `is_document_approver` — назначен согласующим
- `is_same_department` — документ отдела пользователя
- `is_document_category_manager` — менеджер категории

#### Правила:
- `documents.view_document` — просмотр документа
- `documents.change_document` — изменение документа
- `documents.delete_document` — удаление документа
- `documents.approve_document` — согласование документа
- `documents.publish_document` — публикация документа
- `documents.download_document` — скачивание документа
- `documents.share_document` — выдача доступа
- `documents.view_document_history` — просмотр истории
- `documents.view_department_documents` — документы отдела

---

## Использование

### 1. В Views

```python
from django.core.exceptions import PermissionDenied
import rules

def document_detail(request, pk):
    document = get_object_or_404(Document, pk=pk)
    
    # Проверка через rules.test_rule
    if not rules.test_rule('documents.view_document', request.user, document):
        raise PermissionDenied
    
    return render(request, 'documents/detail.html', {'document': document})


def document_approve(request, pk):
    document = get_object_or_404(Document, pk=pk)
    
    if not rules.test_rule('documents.approve_document', request.user, document):
        raise PermissionDenied
    
    document.status = 'approved'
    document.approved_by = request.user
    document.save()
    
    return redirect('documents:detail', pk=document.pk)
```

### 2. В Templates

```django
{% load rules %}

{% has_rule 'documents.change_document' user document as can_edit %}
{% if can_edit %}
    <a href="{% url 'documents:edit' document.pk %}" class="btn btn-primary">
        Редактировать
    </a>
{% endif %}

{% has_rule 'documents.approve_document' user document as can_approve %}
{% if can_approve and document.status == 'pending' %}
    <form method="post" action="{% url 'documents:approve' document.pk %}">
        {% csrf_token %}
        <button type="submit" class="btn btn-success">Согласовать</button>
    </form>
{% endif %}
```

### 3. В DRF Permissions

```python
from rest_framework import permissions
import rules

class DocumentPermission(permissions.BasePermission):
    """Object-level permission для Document через django-rules"""
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return rules.test_rule('documents.view_document', request.user, obj)
        elif request.method in ['PUT', 'PATCH']:
            return rules.test_rule('documents.change_document', request.user, obj)
        elif request.method == 'DELETE':
            return rules.test_rule('documents.delete_document', request.user, obj)
        return False


# В ViewSet:
class DocumentViewSet(viewsets.ModelViewSet):
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    permission_classes = [permissions.IsAuthenticated, DocumentPermission]
```

### 4. В Django Admin

```python
from django.contrib import admin
import rules

class DocumentAdmin(admin.ModelAdmin):
    def has_change_permission(self, request, obj=None):
        if obj is None:
            # Проверка на уровне модели (list view)
            return super().has_change_permission(request, obj)
        
        # Проверка на уровне объекта (change view)
        return rules.test_rule('documents.change_document', request.user, obj)
    
    def has_delete_permission(self, request, obj=None):
        if obj is None:
            return super().has_delete_permission(request, obj)
        return rules.test_rule('documents.delete_document', request.user, obj)
```

### 5. Фильтрация QuerySet

```python
from django.db.models import Q

def get_accessible_documents(user):
    """Возвращает документы, к которым пользователь имеет доступ"""
    return Document.objects.filter(
        Q(created_by=user) |  # Созданные пользователем
        Q(owner=user) |  # Принадлежащие пользователю
        Q(is_public=True) |  # Публичные
        Q(department_access=user.department) |  # Для отдела
        Q(shared_with=user)  # Расшаренные
    ).distinct()
```

### 6. Model-level Permissions (опционально)

Если нужно интегрировать с Django permissions (`user.has_perm()`):

```python
# В rules.py:
rules.add_perm('documents.view_document', is_superuser | has_document_access)
rules.add_perm('documents.change_document', is_superuser | is_document_owner)

# Теперь можно использовать стандартный API:
if request.user.has_perm('documents.view_document', document):
    # ...
```

---

## Тестирование

### Unit-тесты для предикатов

```python
import pytest
import rules
from employees.rules import is_own_profile, is_hr_staff

@pytest.mark.django_db
def test_is_own_profile():
    user = Employee.objects.create(username='test')
    other = Employee.objects.create(username='other')
    
    assert is_own_profile(user, user) is True
    assert is_own_profile(user, other) is False


@pytest.mark.django_db
def test_is_hr_staff():
    hr_position = Position.objects.create(name='HR Manager')
    dev_position = Position.objects.create(name='Developer')
    
    hr_user = Employee.objects.create(username='hr', position=hr_position)
    dev_user = Employee.objects.create(username='dev', position=dev_position)
    
    assert is_hr_staff(hr_user) is True
    assert is_hr_staff(dev_user) is False
```

### Интеграционные тесты для правил

```python
import pytest
import rules

@pytest.mark.django_db
def test_view_employee_permission():
    hr = Employee.objects.create(username='hr', position=hr_position)
    employee = Employee.objects.create(username='employee')
    
    # HR может просматривать любого сотрудника
    assert rules.test_rule('employees.view_employee', hr, employee)
    
    # Сотрудник может просматривать свой профиль
    assert rules.test_rule('employees.view_employee', employee, employee)
```

---

## Следующие шаги

### 1. Адаптация под реальные модели

Текущие правила содержат примеры и комментарии. Необходимо:

- ✅ Проверить наличие полей в моделях (`owner`, `is_public`, `shared_with` и т.д.)
- ✅ Адаптировать предикаты под реальную структуру
- ✅ Убрать неиспользуемые предикаты
- ✅ Добавить недостающие правила

### 2. Миграция существующих permissions

Заменить ручные проверки на правила:

```python
# Старый код:
if not (request.user.is_superuser or document.owner == request.user):
    raise PermissionDenied

# Новый код:
if not rules.test_rule('documents.change_document', request.user, document):
    raise PermissionDenied
```

### 3. Покрытие тестами

Создать тесты для всех критичных правил:

- `employees/tests/test_rules.py`
- `documents/tests/test_rules.py`

### 4. Расширение на другие приложения

Создать `rules.py` для:

- `calendar_app` — доступ к календарям и событиям
- `requests_app` — создание и обработка заявок
- `communications` — доступ к чатам и сообщениям
- `finance` — финансовые документы и отчёты

### 5. Performance optimization

Для больших выборок использовать фильтрацию на уровне БД:

```python
# Вместо:
documents = [d for d in Document.objects.all() if rules.test_rule('view', user, d)]

# Использовать:
documents = get_accessible_documents(user)
```

### 6. Документация для команды

- Создать примеры использования для каждого приложения
- Обновить CODE_STYLE.md с правилами написания predicates
- Провести код-ревью существующих permissions

---

## Сравнение с django-guardian

| Аспект | django-rules | django-guardian |
|--------|--------------|-----------------|
| **Хранение** | В коде (декларативно) | В БД (таблицы permissions) |
| **Производительность** | Быстрее (нет запросов в БД) | Медленнее (JOIN с таблицами) |
| **Гибкость** | Высокая (любая логика) | Ограничена (user-object pairs) |
| **Миграции** | Не требуются | Нужна БД миграция |
| **Сложность** | Проще | Сложнее |
| **Масштабирование** | Отлично для ~1K объектов | Лучше для миллионов объектов |

**Вывод**: для EUSRR с умеренным количеством объектов и сложной логикой прав django-rules — оптимальный выбор.

---

## Примеры реальных сценариев

### Сценарий 1: Многоуровневое согласование

```python
@rules.predicate
def can_approve_at_current_stage(user, document):
    """Проверка, что пользователь — текущий согласующий"""
    current_stage = document.approval_chain.filter(status='pending').first()
    if not current_stage:
        return False
    return current_stage.approver == user

rules.add_rule(
    'documents.approve_at_stage',
    is_superuser | can_approve_at_current_stage
)
```

### Сценарий 2: Временные ограничения

```python
from django.utils import timezone
from datetime import timedelta

@rules.predicate
def can_edit_recent_document(user, document):
    """Редактирование только в течение 24 часов после создания"""
    if not is_document_owner(user, document):
        return False
    return timezone.now() - document.created_at < timedelta(hours=24)

rules.add_rule(
    'documents.quick_edit',
    can_edit_recent_document
)
```

### Сценарий 3: Иерархия отделов

```python
@rules.predicate
def is_parent_department_head(user, employee):
    """Руководитель вышестоящего отдела"""
    if not hasattr(employee, 'department') or not hasattr(employee.department, 'parent'):
        return False
    return (
        hasattr(user, 'department') and
        user.department == employee.department.parent and
        is_department_head(user)
    )

rules.add_rule(
    'employees.view_subordinate',
    is_superuser | is_department_head | is_parent_department_head
)
```

---

## Отладка и мониторинг

### Логирование проверок прав

```python
import logging

logger = logging.getLogger(__name__)

@rules.predicate
def is_document_owner(user, document):
    result = document.owner == user
    logger.debug(
        f"Permission check: is_document_owner({user.username}, doc_{document.pk}) = {result}"
    )
    return result
```

### Отладочная view для проверки прав

```python
def debug_permissions(request, document_id):
    """DEBUG view для проверки прав доступа"""
    if not settings.DEBUG:
        raise Http404
    
    document = get_object_or_404(Document, pk=document_id)
    
    checks = {
        'view': rules.test_rule('documents.view_document', request.user, document),
        'change': rules.test_rule('documents.change_document', request.user, document),
        'delete': rules.test_rule('documents.delete_document', request.user, document),
        'approve': rules.test_rule('documents.approve_document', request.user, document),
    }
    
    return JsonResponse(checks)
```

---

## Заключение

Базовая интеграция django-rules завершена:

- ✅ Пакет установлен и настроен
- ✅ Созданы примеры правил для employees и documents
- ✅ Документация и примеры использования готовы

Следующий шаг — адаптация правил под реальную структуру моделей и миграция существующих проверок прав на использование django-rules.

---

**Автор**: GitHub Copilot  
**Дата**: 28 февраля 2026
