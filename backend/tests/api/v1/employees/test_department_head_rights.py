# backend/tests/api/v1/employees/test_department_head_rights.py
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from employees.models import Department, DepartmentRole, EmployeeDepartment, Employee
from tests.conftest import _unique_phone
from tests.test_config import DEFAULT_PASSWORD

User = get_user_model()

# =========================
# Helpers
# =========================

def _unique_phone() -> str:
    base = 79000000000  # 79 + 9 нулей
    return str(base + User.objects.count())

@pytest.fixture
def make_user(email: str, staff: bool = False, verified: bool = True) -> User:
    """Fixture для создания пользователей."""

    u = User.objects.create_user(
        email=email,
        password="pwd12345",
        phone_number=_unique_phone(),
        send_activation_email=False,
        email_verified=True,
    )
    # 👇 явная активация для тестов управленческих прав
    if not u.is_active:
        u.is_active = True
        u.save(update_fields=["is_active"])
    return u

def _unique_email() -> str:
    base = "asd@mail.com"
    return str(Employee.objects.count()) + base

def _make_user(staff=False, superuser=False) -> Employee:
    """
    Создаёт активного и 'email_verified' пользователя, чтобы не споткнуться о
    валидацию при назначении руководителя.
    """
    u = Employee.objects.create_user(
        email=_unique_email(),
        password=DEFAULT_PASSWORD,
        phone_number=_unique_phone(),
        send_activation_email=False,
        first_name="T",
        last_name="U",
    )
    u.is_staff = staff
    u.is_superuser = superuser
    u.email_verified = True  # <- критично для твоей нынешней валидации
    u.is_active = True  # <- тоже нужен для твоей ветки is_active
    u.save(update_fields=["is_staff", "is_superuser", "email_verified", "is_active"])
    return u

def make_role(
    dept: Department, name: str, codes: list[str] | None = None
) -> DepartmentRole:
    role = DepartmentRole.objects.create(department=dept, name=name)
    # в этих тестах права роли не нужны (руководитель имеет доступ сам по себе),
    # но фабрика оставлена для удобства
    return role

def add_member(
    user: User,
    dept: Department,
    role: DepartmentRole | None = None,
    is_active: bool = True,
):
    EmployeeDepartment.objects.update_or_create(
        employee=user,
        department=dept,
        defaults={"is_active": is_active, "role": role},
    )

# =========================
# Fixtures
# =========================

@pytest.fixture()
def api_client() -> APIClient:
    return APIClient()

# =========================
# Tests
# =========================

@pytest.mark.django_db
def test_head_can_update_department_without_explicit_role_perms(api_client: APIClient):
    head = make_user("head@example.com")
    d = Department.objects.create(name="Dept", description="old", head=head)

    # руководитель аутентифицируется
    api_client.force_authenticate(user=head)
    url = reverse("api:v1:departments-detail", args=[d.id])

    # PATCH произвольного поля (не head) должен быть разрешён руководителю
    resp = api_client.patch(url, {"description": "new"}, format="json")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["description"] == "new"

@pytest.mark.django_db
def test_head_can_set_member_role_and_non_head_cannot(api_client: APIClient):
    head = make_user("head@example.com")
    d = Department.objects.create(name="Dept", head=head)

    worker = make_user("worker@example.com")
    add_member(worker, d)  # сотрудник состоит в отделе

    role_worker = make_role(d, "Worker")

    # руководитель назначает роль участнику
    api_client.force_authenticate(user=head)
    url = reverse("api:v1:departments-set-member-role", args=[d.id])
    payload = {"employee_id": worker.id, "role_id": role_worker.id, "is_active": True}
    resp = api_client.post(url, payload, format="json")
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["employee_id"] == worker.id
    assert data["role_id"] == role_worker.id
    assert data["is_active"] is True

    # другой пользователь без статуса руководителя — не может
    stranger = make_user("stranger@example.com")
    api_client.force_authenticate(user=stranger)
    resp = api_client.post(url, payload, format="json")
    assert resp.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
def test_head_can_change_head_and_loses_rights_afterwards(api_client: APIClient):
    old_head = make_user("old@example.com")
    d = Department.objects.create(name="Dept", head=old_head)

    new_head = make_user("new@example.com")

    # старый руководитель меняет руководителя на другого
    api_client.force_authenticate(user=old_head)
    url_set_head = reverse("api:v1:departments-set-head", args=[d.id])
    resp = api_client.post(url_set_head, {"head_id": new_head.id}, format="json")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["head"]["id"] == new_head.id

    # теперь старый руководитель больше не глава — у него не должно быть прав управления отделом
    url_detail = reverse("api:v1:departments-detail", args=[d.id])
    resp = api_client.patch(url_detail, {"description": "after"}, format="json")
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # а у нового руководителя — есть
    api_client.force_authenticate(user=new_head)
    resp = api_client.patch(url_detail, {"description": "ok"}, format="json")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["description"] == "ok"
