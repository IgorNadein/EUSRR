"""
Тесты для DepartmentViewSet с опциональной LDAP интеграцией (упрощённые).

Покрытие:
- D1: Список отделов
- D2: Получение конкретного отдела

Примечание: Полные CRUD тесты отделов требуют сложной настройки permissions
и будут добавлены в отдельном файле.
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from employees.models import Department

Employee = get_user_model()


@pytest.fixture
def department(db):
    """Создаёт тестовый отдел"""
    return Department.objects.create(
        name="IT Department",
        description="Information Technology",
    )


@pytest.fixture
def test_employee(db):
    """Создаёт тестового сотрудника"""
    user = Employee.objects.create(
        email="employee@example.com",
        first_name="Test",
        last_name="Employee",
        phone_number="+79990003333",
        is_active=True,
        email_verified=True,
    )
    user.set_password("TestPass123!")
    user.save()
    return user


@pytest.fixture
def authenticated_client(api_client, test_employee):
    """API клиент с аутентификацией"""
    api_client.force_authenticate(user=test_employee)
    return api_client


# ---------- Тесты чтения (доступны без специальных permissions) ----------


@pytest.mark.django_db
def test_department_list_accessible_without_ldap(authenticated_client, settings):
    """D1: Список отделов доступен без LDAP"""
    settings.LDAP_ENABLED = False

    url = reverse("api:v1:departments-list")
    response = authenticated_client.get(url)

    # Список может быть пустым или содержать отделы
    assert response.status_code == status.HTTP_200_OK
    assert isinstance(response.data, (list, dict))


@pytest.mark.django_db
def test_retrieve_department_without_ldap(
    authenticated_client, department, settings
):
    """D2: Получение конкретного отдела без LDAP"""
    settings.LDAP_ENABLED = False

    url = reverse("api:v1:departments-detail", kwargs={"pk": department.id})
    response = authenticated_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == department.id
    assert response.data["name"] == department.name
