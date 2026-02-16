"""
Общие helper-функции для тестов API employees.

Используйте эти функции вместо создания собственных в каждом тестовом файле.
"""
import itertools
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from employees.models import Employee, Department, DepartmentRole, Position

from tests.test_config import DEFAULT_PASSWORD, TEST_EMAIL_DOMAIN

User = get_user_model()

# Счетчики для уникальных значений
_email_counter = itertools.count(1)
_phone_counter = itertools.count(1000)


def make_unique_email(prefix: str = "user") -> str:
    """Генерирует уникальный email для тестов."""
    return f"{prefix}{next(_email_counter)}@{TEST_EMAIL_DOMAIN}"


def make_unique_phone() -> str:
    """Генерирует уникальный телефонный номер для тестов."""
    return f"+7999000{next(_phone_counter):04d}"


def make_user(
    email: str = None,
    *,
    staff: bool = False,
    superuser: bool = False,
    verified: bool = True,
    active: bool = True,
    password: str = DEFAULT_PASSWORD,
    **extra
) -> User:
    """
    Создает пользователя для тестов.
    
    Args:
        email: Email пользователя (если None, генерируется автоматически)
        staff: Флаг is_staff
        superuser: Флаг is_superuser
        verified: Флаг email_verified
        active: Флаг is_active
        password: Пароль (по умолчанию DEFAULT_PASSWORD)
        **extra: Дополнительные поля
        
    Returns:
        User: Созданный пользователь
    """
    if email is None:
        email = make_unique_email()
    
    if 'phone_number' not in extra:
        extra['phone_number'] = make_unique_phone()
    
    if 'first_name' not in extra:
        extra['first_name'] = 'Test'
    
    if 'last_name' not in extra:
        extra['last_name'] = 'User'
    
    user = User.objects.create(
        email=email,
        is_staff=staff,
        is_superuser=superuser,
        email_verified=verified,
        is_active=active,
        **extra
    )
    user.set_password(password)
    user.save()
    
    return user


def grant_permission(user: User, permission_codename: str):
    """
    Выдает пользователю указанное разрешение.
    
    Args:
        user: Пользователь
        permission_codename: Codename разрешения в формате 'app_label.codename'
                            или просто 'codename'
    """
    if '.' in permission_codename:
        app_label, codename = permission_codename.split('.', 1)
        perm = Permission.objects.get(
            content_type__app_label=app_label,
            codename=codename
        )
    else:
        # Пытаемся найти по codename
        perm = Permission.objects.get(codename=permission_codename)
    
    user.user_permissions.add(perm)
    user.save()


def make_department(**kwargs) -> Department:
    """
    Создает отдел для тестов.
    
    Args:
        **kwargs: Поля модели Department
        
    Returns:
        Department: Созданный отдел
    """
    if 'name' not in kwargs:
        kwargs['name'] = f"Test Department {Department.objects.count() + 1}"
    
    return Department.objects.create(**kwargs)


def make_position(**kwargs) -> Position:
    """
    Создает должность для тестов.
    
    Args:
        **kwargs: Поля модели Position
        
    Returns:
        Position: Созданная должность
    """
    if 'name' not in kwargs:
        kwargs['name'] = f"Test Position {Position.objects.count() + 1}"
    
    return Position.objects.create(**kwargs)


def make_department_role(department: Department, **kwargs) -> DepartmentRole:
    """
    Создает роль отдела для тестов.
    
    Args:
        department: Отдел
        **kwargs: Дополнительные поля
        
    Returns:
        DepartmentRole: Созданная роль
    """
    if 'name' not in kwargs:
        kwargs['name'] = f"Test Role {DepartmentRole.objects.count() + 1}"
    
    return DepartmentRole.objects.create(
        department=department,
        **kwargs
    )


def extract_results(data):
    """
    Извлекает результаты из пагинированного ответа API.
    
    Args:
        data: Данные ответа (dict или list)
        
    Returns:
        list: Список результатов
    """
    if isinstance(data, dict) and 'results' in data:
        return data['results']
    return data
