"""
Conftest для тестов requests_app - импортирует общие фикстуры.
"""
import pytest
from django.conf import settings


@pytest.fixture
def user_factory():
    """Фабрика для создания пользователей."""
    from employees.models import Employee
    
    def _make(
        email: str = None,
        *,
        first_name: str = "Test",
        last_name: str = "User",
        active: bool = True,
        **extra
    ):
        import uuid
        if not email:
            email = f"test+{uuid.uuid4().hex[:8]}@example.com"
        
        # Генерируем уникальные phone_number и username
        unique_id = uuid.uuid4().hex[:8]
        if 'phone_number' not in extra:
            extra['phone_number'] = f"+7900{unique_id}"
        if 'username' not in extra:
            extra['username'] = f"user_{unique_id}"
        
        user = Employee.objects.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            is_active=active,
            **extra
        )
        return user
    
    return _make
