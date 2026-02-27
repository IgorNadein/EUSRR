# План рефакторинга модуля Procurement для pip-публикации

**Цель:** Сделать модуль `procurement` независимым и готовым к публикации на PyPI.

**Статус:** 🚧 В разработке  
**Дата начала:** 27 февраля 2026  
**Оценка времени:** 2-3 недели  
**Риск:** ⚠️ Средний (модуль не в проде, но есть тесты)

---

## 📊 Анализ текущего состояния

### Проблемы tight coupling:

**19 жестких связей:**
```python
# ❌ Текущее состояние
from employees.models import Department  # Жесткая зависимость
User = get_user_model()                  # Предполагает employees.Employee

ProcurementRequest:
  - department: ForeignKey(Department)           # 1
  - requestor: ForeignKey(User)                  # 2
  - executor: ForeignKey(User)                   # 3
  
ProcurementItem:
  - request: ForeignKey(ProcurementRequest)      # OK (внутренняя)
  
Approval:
  - request: ForeignKey(ProcurementRequest)      # OK
  - approver: ForeignKey(User)                   # 4
  
EquipmentCategory:
  - parent: ForeignKey('self')                   # OK
  
Equipment:
  - category: ForeignKey(EquipmentCategory)      # OK
  - department: ForeignKey(Department)           # 5
  - responsible_person: ForeignKey(User)         # 6
  - procurement_request: ForeignKey(...)         # OK
  
MaintenanceRecord:
  - equipment: ForeignKey(Equipment)             # OK
  - performed_by: ForeignKey(User)               # 7
  
EquipmentTransfer:
  - equipment: ForeignKey(Equipment)             # OK
  - from_department: ForeignKey(Department)      # 8
  - to_department: ForeignKey(Department)        # 9
  - from_person: ForeignKey(User)                # 10
  - to_person: ForeignKey(User)                  # 11
  - created_by: ForeignKey(User)                 # 12
  
Budget:
  - department: ForeignKey(Department)           # 13
```

**Итого:** 
- 13 зависимостей от внешних моделей
- 9 ссылок на User (Employee)
- 4 ссылки на Department

---

## 🎯 Целевая архитектура

### Принципы pip-ready модуля:

1. **Swappable models** - модели настраиваются через settings
2. **Abstract базы** - переиспользуемая логика
3. **Минимальные зависимости** - только Django core
4. **Type hints** - полная типизация
5. **Документация** - docstrings everywhere

### Целевая структура:

```python
# procurement/settings.py (новый файл)
from django.conf import settings

PROCUREMENT_USER_MODEL = getattr(
    settings, 
    'PROCUREMENT_USER_MODEL', 
    settings.AUTH_USER_MODEL
)

PROCUREMENT_DEPARTMENT_MODEL = getattr(
    settings,
    'PROCUREMENT_DEPARTMENT_MODEL',
    'employees.Department'  # default для EUSRR
)

# procurement/models.py
from django.contrib.auth import get_user_model
from .conf import PROCUREMENT_USER_MODEL, PROCUREMENT_DEPARTMENT_MODEL

class ProcurementRequest(models.Model):
    # ✅ Настраиваемые модели
    department = models.ForeignKey(
        PROCUREMENT_DEPARTMENT_MODEL,
        on_delete=models.PROTECT,
        ...
    )
    requestor = models.ForeignKey(
        PROCUREMENT_USER_MODEL,
        on_delete=models.PROTECT,
        ...
    )
```

---

## 📋 План рефакторинга (10 шагов)

### **Этап 1: Подготовка (1 день)**

#### ✅ Шаг 1.1: Создать бэкап
```bash
# Бэкап БД
python manage.py dumpdata procurement > backup_procurement_$(date +%Y%m%d).json

# Бэкап кода
git checkout -b refactor/procurement-pip-ready
git commit -am "Checkpoint: Before procurement refactoring"
```

#### ✅ Шаг 1.2: Запустить существующие тесты
```bash
pytest backend/tests/api/v1/procurement/ -v --tb=short
# Записать результаты как baseline
```

#### ✅ Шаг 1.3: Создать файлы конфигурации
```
procurement/
  conf.py          # Настройки модуля (новый)
  setup.py         # pip package metadata (новый)
  pyproject.toml   # Modern Python packaging (новый)
  MANIFEST.in      # Файлы для включения в пакет (новый)
```

---

### **Этап 2: Создание конфигурации (2 дня)**

#### ✅ Шаг 2.1: Создать procurement/conf.py
```python
"""
Настройки модуля procurement.

Можно переопределить в settings.py проекта:

PROCUREMENT_USER_MODEL = 'auth.User'
PROCUREMENT_DEPARTMENT_MODEL = 'myapp.Department'
"""
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

# User model (usually Employee or auth.User)
PROCUREMENT_USER_MODEL = getattr(
    settings,
    'PROCUREMENT_USER_MODEL',
    settings.AUTH_USER_MODEL
)

# Department model (must have: name, head, active_employees)
PROCUREMENT_DEPARTMENT_MODEL = getattr(
    settings,
    'PROCUREMENT_DEPARTMENT_MODEL',
    'employees.Department'
)

# Approval thresholds (₽)
APPROVAL_THRESHOLD_LOW = getattr(
    settings,
    'PROCUREMENT_APPROVAL_THRESHOLD_LOW',
    10000
)

APPROVAL_THRESHOLD_HIGH = getattr(
    settings,
    'PROCUREMENT_APPROVAL_THRESHOLD_HIGH',
    100000
)

# Validation функция
def validate_department_model():
    """Проверяет что DEPARTMENT_MODEL имеет нужные поля"""
    from django.apps import apps
    
    try:
        model = apps.get_model(PROCUREMENT_DEPARTMENT_MODEL)
    except LookupError:
        raise ImproperlyConfigured(
            f"PROCUREMENT_DEPARTMENT_MODEL '{PROCUREMENT_DEPARTMENT_MODEL}' "
            f"not found. Make sure the app is in INSTALLED_APPS."
        )
    
    # Проверяем обязательные поля
    required_fields = ['name']
    for field in required_fields:
        if not hasattr(model, field):
            raise ImproperlyConfigured(
                f"PROCUREMENT_DEPARTMENT_MODEL must have '{field}' field"
            )
    
    return model
```

#### ✅ Шаг 2.2: Обновить procurement/apps.py
```python
from django.apps import AppConfig

class ProcurementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'procurement'
    verbose_name = 'Закупки и инвентарь'
    
    def ready(self):
        # Импорт signals
        from . import signals
        
        # Валидация настроек
        from .conf import validate_department_model
        validate_department_model()
```

---

### **Этап 3: Рефакторинг моделей (3 дня)**

#### ✅ Шаг 3.1: Обновить imports в models.py
```python
# ❌ Старое
from employees.models import Department
User = get_user_model()

# ✅ Новое
from django.apps import apps
from .conf import PROCUREMENT_USER_MODEL, PROCUREMENT_DEPARTMENT_MODEL

def get_user_model():
    return apps.get_model(PROCUREMENT_USER_MODEL)

def get_department_model():
    return apps.get_model(PROCUREMENT_DEPARTMENT_MODEL)
```

#### ✅ Шаг 3.2: Изменить ForeignKey на строковые ссылки
```python
# ❌ Старое
department = models.ForeignKey(
    Department,
    on_delete=models.PROTECT,
    ...
)

# ✅ Новое
department = models.ForeignKey(
    PROCUREMENT_DEPARTMENT_MODEL,  # Строка!
    on_delete=models.PROTECT,
    ...
)

# ❌ Старое
requestor = models.ForeignKey(
    User,
    on_delete=models.PROTECT,
    ...
)

# ✅ Новое
requestor = models.ForeignKey(
    PROCUREMENT_USER_MODEL,  # Строка!
    on_delete=models.PROTECT,
    ...
)
```

#### ✅ Шаг 3.3: Добавить type hints
```python
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from django.db.models import Model
    
    UserModel = AbstractUser
    DepartmentModel = Model
else:
    UserModel = None
    DepartmentModel = None

class ProcurementRequest(models.Model):
    # Type hints для IDE
    requestor: UserModel
    department: DepartmentModel
    
    def approve(self, by_user: UserModel) -> None:
        """Одобрить заявку"""
        ...
```

---

### **Этап 4: Миграции (1 день)**

#### ✅ Шаг 4.1: Создать новую миграцию
```bash
python manage.py makemigrations procurement
```

**Важно:** Миграция должна использовать `swappable_dependency`:
```python
# migrations/XXXX_refactor_swappable.py
from django.conf import settings
from django.db import migrations, models
import procurement.conf

class Migration(migrations.Migration):
    
    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        migrations.swappable_dependency(procurement.conf.PROCUREMENT_DEPARTMENT_MODEL),
        ('procurement', '0001_initial'),
    ]
    
    operations = [
        # Django автоматически создаст AlterField для ForeignKey
        ...
    ]
```

#### ✅ Шаг 4.2: Применить миграции
```bash
python manage.py migrate procurement
```

#### ✅ Шаг 4.3: Проверить БД
```bash
python manage.py dbshell
\d+ procurement_procurementrequest
# Проверить что FK ссылаются на правильные таблицы
```

---

### **Этап 5: Обновление кода (2 дня)**

#### ✅ Шаг 5.1: Обновить методы моделей
```python
# Везде где используется User/Department, заменить на get_*_model()

class ProcurementRequest(models.Model):
    def check_budget_available(self):
        Department = get_department_model()  # ← Добавить
        
        try:
            budget = Budget.objects.get(
                department=self.department,
                ...
            )
```

#### ✅ Шаг 5.2: Обновить permissions.py
```python
# api/v1/procurement/permissions.py

from procurement.conf import get_department_model

class IsDepartmentHead(permissions.BasePermission):
    def has_permission(self, request, view):
        Department = get_department_model()  # ← Добавить
        
        # Проверяем через свойство head
        # Предполагается что у Department есть поле head
        return Department.objects.filter(head=request.user).exists()
```

#### ✅ Шаг 5.3: Обновить serializers.py
```python
# api/v1/procurement/serializers.py

from procurement.conf import PROCUREMENT_USER_MODEL

class ProcurementRequestSerializer(serializers.ModelSerializer):
    requestor = serializers.PrimaryKeyRelatedField(
        queryset=get_user_model().objects.all()  # ← Использовать get_user_model()
    )
```

---

### **Этап 6: Обновление тестов (2 дня)**

#### ✅ Шаг 6.1: Обновить conftest.py
```python
# tests/api/v1/procurement/conftest.py

from django.apps import apps
from procurement.conf import PROCUREMENT_USER_MODEL, PROCUREMENT_DEPARTMENT_MODEL

@pytest.fixture
def user_factory(db):
    """Фабрика пользователей - работает с любой моделью"""
    User = apps.get_model(PROCUREMENT_USER_MODEL)
    
    def _create(**kwargs):
        return User.objects.create_user(**kwargs)
    
    return _create

@pytest.fixture
def department_factory(db):
    """Фабрика отделов - работает с любой моделью"""
    Department = apps.get_model(PROCUREMENT_DEPARTMENT_MODEL)
    
    def _create(**kwargs):
        defaults = {'name': 'Test Department'}
        defaults.update(kwargs)
        return Department.objects.create(**defaults)
    
    return _create
```

#### ✅ Шаг 6.2: Запустить тесты
```bash
pytest backend/tests/api/v1/procurement/ -v
# Все 69 тестов должны пройти!
```

---

### **Этап 7: Создание pip пакета (1 день)**

#### ✅ Шаг 7.1: Создать setup.py
```python
# procurement/setup.py
from setuptools import setup, find_packages

setup(
    name='django-procurement',
    version='0.1.0',
    description='Django app for procurement and inventory management',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Your Name',
    author_email='your@email.com',
    url='https://github.com/yourorg/django-procurement',
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'Django>=4.2',
        'djangorestframework>=3.14',
        'Pillow>=10.0',  # Для QR кодов
    ],
    extras_require={
        'dev': [
            'pytest>=7.0',
            'pytest-django>=4.5',
            'black>=23.0',
            'isort>=5.12',
        ]
    },
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Framework :: Django',
        'Framework :: Django :: 4.2',
        'Framework :: Django :: 5.0',
        'Intended Audience :: Developers',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.10',
        'Programming Language :: Python :: 3.11',
        'Programming Language :: Python :: 3.12',
    ],
    python_requires='>=3.10',
)
```

#### ✅ Шаг 7.2: Создать pyproject.toml
```toml
# procurement/pyproject.toml
[build-system]
requires = ["setuptools>=61.0", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "django-procurement"
version = "0.1.0"
description = "Django app for procurement and inventory management"
readme = "README.md"
requires-python = ">=3.10"
license = {text = "MIT"}
authors = [
    {name = "Your Name", email = "your@email.com"}
]
keywords = ["django", "procurement", "inventory", "equipment"]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Framework :: Django",
    "Programming Language :: Python :: 3",
]
dependencies = [
    "Django>=4.2",
    "djangorestframework>=3.14",
    "Pillow>=10.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "pytest-django>=4.5",
    "black>=23.0",
    "isort>=5.12",
]

[project.urls]
Homepage = "https://github.com/yourorg/django-procurement"
Documentation = "https://django-procurement.readthedocs.io"
Repository = "https://github.com/yourorg/django-procurement"
```

#### ✅ Шаг 7.3: Создать MANIFEST.in
```
# procurement/MANIFEST.in
include LICENSE
include README.md
include pyproject.toml
recursive-include procurement/templates *
recursive-include procurement/static *
recursive-include procurement/migrations *.py
recursive-exclude * __pycache__
recursive-exclude * *.pyc
recursive-exclude * *.pyo
```

---

### **Этап 8: Документация (2 дня)**

#### ✅ Шаг 8.1: Создать README.md
```markdown
# Django Procurement

Django приложение для управления закупками и инвентарем.

## Особенности

- ✅ Swappable User/Department models
- ✅ Workflow для заявок на закупку
- ✅ Управление оборудованием
- ✅ Система согласований
- ✅ REST API (DRF)
- ✅ Полные type hints
- ✅ 80%+ test coverage

## Установка

```bash
pip install django-procurement
```

## Быстрый старт

1. Добавьте в INSTALLED_APPS:
```python
INSTALLED_APPS = [
    ...
    'rest_framework',
    'procurement',
]
```

2. Настройте модели (опционально):
```python
# settings.py
PROCUREMENT_USER_MODEL = 'auth.User'  # default: AUTH_USER_MODEL
PROCUREMENT_DEPARTMENT_MODEL = 'myapp.Department'  # default: 'employees.Department'

# Пороги согласования (₽)
PROCUREMENT_APPROVAL_THRESHOLD_LOW = 10000
PROCUREMENT_APPROVAL_THRESHOLD_HIGH = 100000
```

3. Примените миграции:
```bash
python manage.py migrate procurement
```

4. Подключите URLs:
```python
urlpatterns = [
    path('api/v1/procurement/', include('procurement.api.urls')),
]
```

## Требования к Department model

Если используется кастомная модель отдела, она должна иметь:
- `name` (CharField) - название отдела
- `head` (ForeignKey to User, optional) - руководитель

Пример:
```python
class Department(models.Model):
    name = models.CharField(max_length=255)
    head = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )
```

## API

### Endpoints

- `GET /api/v1/procurement/requests/` - список заявок
- `POST /api/v1/procurement/requests/` - создать заявку
- `GET /api/v1/procurement/equipment/` - список оборудования
- ... (see docs/)

## Тестирование

```bash
pytest tests/
```

## Лицензия

MIT License
```

#### ✅ Шаг 8.2: Обновить docstrings
Добавить полные docstrings во все классы и методы с примерами использования.

---

### **Этап 9: Интеграция в EUSRR (1 день)**

#### ✅ Шаг 9.1: Обновить settings.py проекта
```python
# backend/eusrr_backend/settings.py

# Настройки procurement модуля
PROCUREMENT_USER_MODEL = 'employees.Employee'  # Явно указываем
PROCUREMENT_DEPARTMENT_MODEL = 'employees.Department'
PROCUREMENT_APPROVAL_THRESHOLD_LOW = 10000
PROCUREMENT_APPROVAL_THRESHOLD_HIGH = 100000
```

#### ✅ Шаг 9.2: Проверить работу
```bash
# Запустить сервер
python manage.py runserver

# Проверить API
curl http://localhost:9000/api/v1/procurement/requests/

# Проверить админку
# Зайти в /admin/procurement/
```

---

### **Этап 10: Финализация (1 день)**

#### ✅ Шаг 10.1: Запустить полный тест-suite
```bash
# Все тесты procurement
pytest backend/tests/api/v1/procurement/ -v --cov=procurement

# Интеграционные тесты
pytest backend/tests/integration/ -k procurement

# Проверить покрытие
pytest --cov=procurement --cov-report=html
# Цель: 80%+
```

#### ✅ Шаг 10.2: Code quality checks
```bash
# Форматирование
black backend/procurement/
isort backend/procurement/

# Линтинг
flake8 backend/procurement/
mypy backend/procurement/

# Проверка безопасности
bandit -r backend/procurement/
```

#### ✅ Шаг 10.3: Создать git tag
```bash
git add .
git commit -m "refactor: Make procurement module pip-ready

- Add swappable USER/DEPARTMENT models
- Add comprehensive type hints
- Extract configuration to conf.py
- Add setup.py for pip distribution
- Update tests to work with any models
- 100% backward compatible with EUSRR

BREAKING CHANGES: None (backward compatible)
"

git tag -a v0.1.0 -m "Release 0.1.0: pip-ready procurement module"
git push origin refactor/procurement-pip-ready
git push --tags
```

---

## 🧪 Тестирование в изоляции

### Создать тестовый Django проект:

```bash
# Создать чистый проект для проверки
mkdir test-procurement
cd test-procurement
python -m venv venv
source venv/bin/activate

# Установить procurement как pip пакет
pip install -e ../EUSRR/backend/procurement/

# Создать minimal Django проект
django-admin startproject testproject
cd testproject

# Добавить в INSTALLED_APPS
# settings.py
INSTALLED_APPS = [
    ...
    'procurement',
]

# Использовать стандартный auth.User
PROCUREMENT_USER_MODEL = 'auth.User'

# Создать минимальную Department модель
# testproject/models.py
class Department(models.Model):
    name = models.CharField(max_length=255)
    head = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True
    )

PROCUREMENT_DEPARTMENT_MODEL = 'testproject.Department'

# Запустить миграции
python manage.py migrate

# Проверить что всё работает!
python manage.py shell
>>> from procurement.models import ProcurementRequest
>>> ProcurementRequest.objects.create(...)
```

---

## ✅ Критерии успеха

### Функциональные:
- [ ] Все 69 тестов проходят
- [ ] Модуль работает с `auth.User` вместо `employees.Employee`
- [ ] Модуль работает с custom Department моделью
- [ ] API endpoints работают
- [ ] Админка работает
- [ ] Миграции применяются без ошибок

### Код quality:
- [ ] 80%+ test coverage
- [ ] Type hints везде
- [ ] Docstrings для всех public API
- [ ] Black + isort пройдены
- [ ] Flake8 без ошибок
- [ ] Mypy пройден

### Packaging:
- [ ] `pip install -e .` работает
- [ ] setup.py корректен
- [ ] pyproject.toml корректен
- [ ] MANIFEST.in включает все нужные файлы
- [ ] README.md полный

### Backward compatibility:
- [ ] EUSRR проект работает БЕЗ изменений (кроме settings)
- [ ] Существующие данные в БД не затронуты
- [ ] Frontend не требует изменений

---

## 📊 Метрики прогресса

### До рефакторинга:
```
Зависимости: 19 жестких связей (13 внешних)
Покрытие тестами: 81% (56/69 passed)
Документация: Minimal
Type hints: Частичные
pip-ready: ❌
```

### После рефакторинга:
```
Зависимости: 0 жестких связей (все swappable)
Покрытие тестами: 80%+ (все проходят)
Документация: Полная (README, docstrings)
Type hints: 100%
pip-ready: ✅
```

---

## 🚨 Риски и митигация

### Риск 1: Миграции сломают БД
**Митигация:**
- Полный бэкап перед началом
- Тестировать на копии БД
- Rollback plan готов

### Риск 2: Тесты не проходят
**Митигация:**
- Запустить baseline до изменений
- Фиксить по одному тесту
- Не коммитить если есть failed tests

### Риск 3: Breaking changes для EUSRR
**Митигация:**
- Backward compatible подход
- Только добавление, не удаление
- Settings опциональные

### Риск 4: Performance деградация
**Митигация:**
- Бенчмарки до/после
- EXPLAIN ANALYZE запросов
- Индексы на месте

---

## 📝 Чеклист перед коммитом

- [ ] Бэкап БД создан
- [ ] Все тесты проходят
- [ ] Black + isort применены
- [ ] Type hints добавлены
- [ ] Docstrings обновлены
- [ ] README.md актуален
- [ ] Миграции протестированы
- [ ] EUSRR проект работает
- [ ] Coverage 80%+
- [ ] Нет TODO/FIXME в коде

---

## 🎉 После завершения

### Опубликовать на TestPyPI:
```bash
cd backend/procurement
python -m build
twine upload --repository testpypi dist/*
```

### Опубликовать на PyPI (когда готово):
```bash
twine upload dist/*
```

### Документация:
- Создать docs/ сайт (MkDocs/Sphinx)
- Опубликовать на ReadTheDocs

---

**Время начала:** 27.02.2026  
**Ожидаемое завершение:** 15.03.2026 (2-3 недели)  
**Ответственный:** [Ваше имя]  
**Статус:** 📝 План готов, ожидает утверждения
