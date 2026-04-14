import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from employees.constants import DeptPerm
from employees.models import (
    Department,
    DepartmentPermission,
    DepartmentRole,
    EmployeeDepartment,
    RoleAssignment,
)
from tests.conftest import _unique_phone
from tests.test_config import DEFAULT_PASSWORD

User = get_user_model()


def _unique_email() -> str:
    return f"user{User.objects.count()}@example.com"


def make_user(*, staff: bool = False, superuser: bool = False) -> User:
    user = User.objects.create_user(
        email=_unique_email(),
        password=DEFAULT_PASSWORD,
        phone_number=_unique_phone(),
        send_activation_email=False,
        first_name="Dept",
        last_name="User",
    )
    user.is_staff = staff
    user.is_superuser = superuser
    user.email_verified = True
    user.is_active = True
    user.save(
        update_fields=["is_staff", "is_superuser", "email_verified", "is_active"]
    )
    return user


@pytest.fixture()
def api_client() -> APIClient:
    return APIClient()


@pytest.mark.django_db
def test_department_user_perms_includes_feed_flags_for_head(api_client: APIClient):
    head = make_user()
    dept = Department.objects.create(name="Бухгалтерия", head=head)

    api_client.force_authenticate(user=head)
    url = reverse("api:v1:departments-user-perms", args=[dept.id])
    resp = api_client.get(url)

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["can_publish_posts"] is True
    assert resp.json()["can_manage_feed"] is True


@pytest.mark.django_db
def test_department_user_perms_resolves_role_based_feed_rights(api_client: APIClient):
    employee = make_user()
    dept = Department.objects.create(name="Закупки")
    role = DepartmentRole.objects.create(department=dept, name="Редактор ленты")
    publish_perm, _ = DepartmentPermission.objects.get_or_create(
        code=DeptPerm.CREATE_POST,
        defaults={"name": "Публиковать новости на странице отдела"},
    )
    role.scoped_permissions.add(publish_perm)
    RoleAssignment.objects.create(employee=employee, role=role, is_active=True)

    api_client.force_authenticate(user=employee)
    url = reverse("api:v1:departments-user-perms", args=[dept.id])
    resp = api_client.get(url)

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["can_publish_posts"] is True
    assert resp.json()["can_manage_feed"] is False


@pytest.mark.django_db
def test_department_user_perms_allows_active_member_to_publish(api_client: APIClient):
    employee = make_user()
    dept = Department.objects.create(name="Склад")
    EmployeeDepartment.objects.create(
        employee=employee,
        department=dept,
        is_active=True,
    )

    api_client.force_authenticate(user=employee)
    url = reverse("api:v1:departments-user-perms", args=[dept.id])
    resp = api_client.get(url)

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["can_publish_posts"] is True
    assert resp.json()["can_manage_feed"] is False


@pytest.mark.django_db
def test_department_user_perms_allows_role_only_to_publish_without_scoped_perm(
    api_client: APIClient,
):
    employee = make_user()
    dept = Department.objects.create(name="Логистика")
    role = DepartmentRole.objects.create(department=dept, name="Наблюдатель")
    RoleAssignment.objects.create(employee=employee, role=role, is_active=True)

    api_client.force_authenticate(user=employee)
    url = reverse("api:v1:departments-user-perms", args=[dept.id])
    resp = api_client.get(url)

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["can_publish_posts"] is True
    assert resp.json()["can_manage_feed"] is False
