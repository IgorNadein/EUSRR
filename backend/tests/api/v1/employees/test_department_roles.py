# backend/tests/api/v1/employees/test_department_roles.py
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from django.test import override_settings
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch

from employees.models import (
    Department,
    DepartmentRole,
    DepartmentPermission,
    EmployeeDepartment,  # <-- если у тебя EmployeeDepartmentLink, замени импорт и упоминания ниже
    RoleAssignment,
)
from tests.conftest import _unique_phone

User = get_user_model()

# =========================
# Helpers
# =========================

def make_user(email: str, staff: bool = False, verified: bool = True) -> User:
    extra = {
        "phone_number": _unique_phone(),
        "is_staff": staff,
        "send_activation_email": False,
    }
    try:
        User._meta.get_field("verified")
        extra["verified"] = verified
    except Exception:
        pass
    return User.objects.create_user(
        email=email,
        password="pwd12345",
        **extra,
    )

def ensure_dept_perm(code: str, name: str | None = None) -> DepartmentPermission:
    return DepartmentPermission.objects.get_or_create(
        code=code, defaults={"name": name or code}
    )[0]

def make_role(dept: Department, name: str, codes: list[str] | None = None) -> DepartmentRole:
    role = DepartmentRole.objects.create(department=dept, name=name)
    if codes:
        perms = [ensure_dept_perm(c) for c in codes]
        role.scoped_permissions.add(*perms)
    return role

def grant_assign_in_dept(user: User, dept: Department) -> DepartmentRole:
    role = make_role(dept, "assigner", ["assign_department_role"])
    EmployeeDepartment.objects.update_or_create(
        employee=user, department=dept,
        defaults={"is_active": True, "role": role},
    )
    return role

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
def test_list_filtered_by_department(api_client: APIClient):
    d1 = Department.objects.create(name="Dept A")
    d2 = Department.objects.create(name="Dept B")

    r1 = make_role(d1, "Engineer", [])
    r2 = make_role(d1, "Manager", [])
    r3 = make_role(d2, "Sales", [])

    user = make_user("u@example.com")
    api_client.force_authenticate(user=user)

    url = reverse("api:v1:department-roles-list")

    # без фильтра — все 3
    resp = api_client.get(url)
    assert resp.status_code == 200
    body = resp.json()
    items = body.get("results", body)
    ids = {it["id"] for it in items}
    assert ids == {r1.id, r2.id, r3.id}

    # с фильтром по d1 — только роли d1
    resp = api_client.get(url, {"department": d1.id})
    assert resp.status_code == 200
    body = resp.json()
    items = body.get("results", body)
    ids = {it["id"] for it in items}
    assert ids == {r1.id, r2.id}

@pytest.mark.django_db
def test_create_requires_assign_department_role(api_client: APIClient):
    d = Department.objects.create(name="Dept")
    user = make_user("m@example.com")
    api_client.force_authenticate(user=user)

    url = reverse("api:v1:department-roles-list")

    # без прав — 403
    resp = api_client.post(url, {"department": d.id, "name": "Worker"}, format="json")
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # выдаём право assign_department_role в этом отделе
    grant_assign_in_dept(user, d)

    # теперь можно создать
    resp = api_client.post(url, {"department": d.id, "name": "Worker"}, format="json")
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["department"] == d.id
    # back-compat поле присутствует
    assert "permissions" in data and isinstance(data["permissions"], list)

@pytest.mark.django_db
def test_update_and_destroy_scope_enforced(api_client: APIClient):
    d1 = Department.objects.create(name="Dept1")
    d2 = Department.objects.create(name="Dept2")
    user = make_user("m@example.com")
    api_client.force_authenticate(user=user)

    # роль в другом отделе
    role_other = make_role(d2, "Other", [])
    url_detail_other = reverse("api:v1:department-roles-detail", args=[role_other.id])

    # нет прав в d2 -> 403
    resp = api_client.patch(url_detail_other, {"name": "X"}, format="json")
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # выдаём права в d1 — всё ещё 403 для d2
    grant_assign_in_dept(user, d1)
    resp = api_client.patch(url_detail_other, {"name": "X"}, format="json")
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # выдаём права в d2 — теперь можно
    grant_assign_in_dept(user, d2)
    resp = api_client.patch(url_detail_other, {"name": "X"}, format="json")
    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["name"] == "X"

    # destroy с правами — 204/200
    resp = api_client.delete(url_detail_other)
    assert resp.status_code in (status.HTTP_204_NO_CONTENT, status.HTTP_200_OK)

@pytest.mark.django_db
def test_perm_choices_and_perms_and_set_perms(api_client: APIClient):
    # засеем три стандартных кода
    ensure_dept_perm("manage_department", "Управлять отделом")
    ensure_dept_perm("change_department_head", "Назначать руководителя")
    ensure_dept_perm("assign_department_role", "Назначать роли")

    d = Department.objects.create(name="Dept")
    user = make_user("m@example.com")
    api_client.force_authenticate(user=user)
    grant_assign_in_dept(user, d)

    role = make_role(d, "Engineer", [])

    # perm_choices
    url_choices = reverse("api:v1:department-roles-perm-choices")
    resp = api_client.get(url_choices)
    assert resp.status_code == 200
    codes = {row["code"] for row in resp.json().get("results", [])}
    assert {"manage_department", "change_department_head", "assign_department_role"}.issubset(codes)
    assert "manage_department_events" not in codes
    assert "publish_department_post" not in codes
    assert "view_request" not in codes
    assert "view_requestcomment" not in codes
    assert "add_requestcomment" not in codes
    process_choice = next(
        item
        for item in resp.json().get("results", [])
        if item["code"] == "can_process_requests"
    )
    assert process_choice["name"] == "Согласование закупок отдела"

    # set_perms (codes)
    url_set = reverse("api:v1:department-roles-set-perms", args=[role.id])
    resp = api_client.post(url_set, {"permission_codes": ["manage_department", "assign_department_role"]}, format="json")
    assert resp.status_code == 200
    data = resp.json()
    verbose = {p["code"] for p in data.get("permissions_verbose", [])}
    assert verbose == {"manage_department", "assign_department_role"}

    # perms (GET)
    url_perms = reverse("api:v1:department-roles-perms", args=[role.id])
    resp = api_client.get(url_perms)
    assert resp.status_code == 200
    codes_now = {p["code"] for p in resp.json().get("results", [])}
    assert codes_now == {"manage_department", "assign_department_role"}

    # set_perms (ids) — заменим на один id
    dp_manage = DepartmentPermission.objects.get(code="manage_department")
    resp = api_client.post(url_set, {"permission_ids": [dp_manage.id]}, format="json")
    assert resp.status_code == 200
    role.refresh_from_db()
    assert set(role.scoped_permissions.values_list("code", flat=True)) == {"manage_department"}

    # set_perms (пусто) — очистить все
    resp = api_client.post(url_set, {"permission_codes": []}, format="json")
    assert resp.status_code == 200
    role.refresh_from_db()
    assert role.scoped_permissions.count() == 0

@pytest.mark.django_db
def test_set_perms_validates_payload(api_client: APIClient):
    d = Department.objects.create(name="Dept")
    user = make_user("m@example.com")
    api_client.force_authenticate(user=user)
    grant_assign_in_dept(user, d)

    role = make_role(d, "QA", [])

    # несуществующий код -> 400
    url_set = reverse("api:v1:department-roles-set-perms", args=[role.id])
    resp = api_client.post(url_set, {"permission_codes": ["no_such_code"]}, format="json")
    assert resp.status_code == 400

    # несуществующий id -> 400
    resp = api_client.post(url_set, {"permission_ids": [999999]}, format="json")
    assert resp.status_code == 400

@pytest.mark.django_db
def test_back_compat_permissions_field_contains_ids(api_client: APIClient):
    d = Department.objects.create(name="Dept")
    user = make_user("m@example.com")
    api_client.force_authenticate(user=user)
    grant_assign_in_dept(user, d)

    role = make_role(d, "Dev", [])
    dp_manage = ensure_dept_perm("manage_department")
    dp_assign = ensure_dept_perm("assign_department_role")
    role.scoped_permissions.add(dp_manage, dp_assign)

    url_detail = reverse("api:v1:department-roles-detail", args=[role.id])
    resp = api_client.get(url_detail)
    assert resp.status_code == 200
    data = resp.json()
    assert set(data["permissions"]) == {dp_manage.id, dp_assign.id}
    assert data["active_assignments_count"] == 0
    assert data["ldap_linked"] is False


@pytest.mark.django_db
def test_update_role_name_and_permissions_and_reject_department_move(api_client: APIClient):
    d1 = Department.objects.create(name="Dept1")
    d2 = Department.objects.create(name="Dept2")
    user = make_user("role-editor@example.com")
    api_client.force_authenticate(user=user)
    grant_assign_in_dept(user, d1)

    ensure_dept_perm("manage_department")
    ensure_dept_perm("assign_department_role")
    role = make_role(d1, "Reviewer", ["manage_department"])
    url_detail = reverse("api:v1:department-roles-detail", args=[role.id])

    resp = api_client.patch(
        url_detail,
        {
            "name": "Lead Reviewer",
            "scoped_permission_codes": ["assign_department_role"],
        },
        format="json",
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "Lead Reviewer"
    assert {p["code"] for p in data["permissions_verbose"]} == {
        "assign_department_role"
    }

    role.refresh_from_db()
    assert role.department_id == d1.id
    assert set(role.scoped_permissions.values_list("code", flat=True)) == {
        "assign_department_role"
    }

    resp = api_client.patch(
        url_detail,
        {"department": d2.id},
        format="json",
    )
    assert resp.status_code == 400
    role.refresh_from_db()
    assert role.department_id == d1.id


@pytest.mark.django_db
def test_delete_assigned_role_requires_force(api_client: APIClient):
    dept = Department.objects.create(name="Dept")
    manager = make_user("role-manager@example.com")
    employee = make_user("role-holder@example.com")
    legacy_employee = make_user("legacy-role-holder@example.com")
    api_client.force_authenticate(user=manager)
    grant_assign_in_dept(manager, dept)

    role = make_role(dept, "Operator", [])
    RoleAssignment.objects.create(employee=employee, role=role, assigned_by=manager)
    EmployeeDepartment.objects.create(
        employee=legacy_employee,
        department=dept,
        is_active=True,
        role=role,
    )

    url_detail = reverse("api:v1:department-roles-detail", args=[role.id])
    resp = api_client.delete(url_detail)
    assert resp.status_code == status.HTTP_409_CONFLICT
    assert resp.json()["active_assignments_count"] == 2
    assert DepartmentRole.objects.filter(id=role.id).exists()

    resp = api_client.delete(f"{url_detail}?force=true")
    assert resp.status_code == status.HTTP_204_NO_CONTENT
    assert not DepartmentRole.objects.filter(id=role.id).exists()
    assert not RoleAssignment.objects.filter(role_id=role.id).exists()
    assert EmployeeDepartment.objects.get(
        employee=legacy_employee, department=dept
    ).role_id is None


@pytest.mark.django_db
@override_settings(LDAP_ENABLED=True)
def test_delete_role_triggers_ldap_signal_not_view_service(api_client: APIClient):
    with override_settings(LDAP_ENABLED=False):
        dept = Department.objects.create(name="Dept LDAP Delete")
        staff = make_user("staff-delete-ldap@example.com", staff=True)
        role = DepartmentRole.objects.create(
            department=dept,
            name="LDAP Linked",
            ldap_group_dn="CN=ROLE_LDAP_Linked,OU=Dept,DC=example,DC=local",
        )

    api_client.force_authenticate(user=staff)
    url_detail = reverse("api:v1:department-roles-detail", args=[role.id])

    with patch(
        "employees.signals.ldap.role.DepartmentService.sync_role_delete"
    ) as mock_sync:
        resp = api_client.delete(url_detail)

    assert resp.status_code == status.HTTP_204_NO_CONTENT
    mock_sync.assert_called_once()

@pytest.mark.django_db
def test_create_with_scoped_permission_codes_and_update_name(api_client: APIClient):
    d = Department.objects.create(name="Dept")
    ensure_dept_perm("manage_department")

    m = make_user("m@example.com")
    api_client.force_authenticate(user=m)
    grant_assign_in_dept(m, d)

    url_list = reverse("api:v1:department-roles-list")

    # create с codes
    resp = api_client.post(
        url_list,
        {
            "department": d.id,
            "name": "Lead",
            "scoped_permission_codes": ["manage_department"],
        },
        format="json",
    )
    assert resp.status_code == 201


@pytest.mark.django_db
@override_settings(LDAP_ENABLED=True)
def test_create_role_triggers_ldap_sync(api_client: APIClient):
    with override_settings(LDAP_ENABLED=False):
        d = Department.objects.create(name="Dept LDAP")
        staff = make_user("staff-ldap@example.com", staff=True)

    api_client.force_authenticate(user=staff)
    url = reverse("api:v1:department-roles-list")

    with patch(
        "employees.signals.ldap.role.DepartmentService.sync_role_state"
    ) as mock_sync:
        resp = api_client.post(
            url,
            {"department": d.id, "name": "Worker LDAP"},
            format="json",
        )

    assert resp.status_code == status.HTTP_201_CREATED
    mock_sync.assert_called_once()
    rid = resp.json()["id"]

    # update имени (PATCH)
    url_detail = reverse("api:v1:department-roles-detail", args=[rid])
    resp = api_client.patch(url_detail, {"name": "Lead+1"}, format="json")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Lead+1"

@pytest.mark.django_db
def test_cross_department_access_denied_for_set_perms(api_client: APIClient):
    d1 = Department.objects.create(name="Dept1")
    d2 = Department.objects.create(name="Dept2")

    user = make_user("m@example.com")
    api_client.force_authenticate(user=user)
    grant_assign_in_dept(user, d1)  # права только в Dept1

    role_d2 = make_role(d2, "R", [])
    url_set = reverse("api:v1:department-roles-set-perms", args=[role_d2.id])

    resp = api_client.post(url_set, {"permission_codes": ["manage_department"]}, format="json")
    assert resp.status_code == 403
