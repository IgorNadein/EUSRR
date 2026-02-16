# backend/tests/api/v1/employees/test_department_roles.py
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from employees.models import (
    Department,
    DepartmentRole,
    DepartmentPermission,
    EmployeeDepartment,  # <-- если у тебя EmployeeDepartmentLink, замени импорт и упоминания ниже
)
from tests.conftest import _unique_phone
from tests.api.v1.employees.test_helpers import make_user, grant_permission, make_department, extract_results

User = get_user_model()

# =========================
# Helpers
# =========================

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
def test_list_filtered_by_department(api_client: APIClient, ensure_ldap_disabled):
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
def test_create_requires_assign_department_role(api_client: APIClient, ensure_ldap_disabled):
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
def test_update_and_destroy_scope_enforced(api_client: APIClient, ensure_ldap_disabled):
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
def test_perm_choices_and_perms_and_set_perms(api_client: APIClient, ensure_ldap_disabled):
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
def test_set_perms_validates_payload(api_client: APIClient, ensure_ldap_disabled):
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
def test_back_compat_permissions_field_contains_ids(api_client: APIClient, ensure_ldap_disabled):
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

@pytest.mark.django_db
def test_create_with_scoped_permission_codes_and_update_name(api_client: APIClient, ensure_ldap_disabled):
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
    rid = resp.json()["id"]

    # update имени (PATCH)
    url_detail = reverse("api:v1:department-roles-detail", args=[rid])
    resp = api_client.patch(url_detail, {"name": "Lead+1"}, format="json")
    assert resp.status_code == 200
    assert resp.json()["name"] == "Lead+1"

@pytest.mark.django_db
def test_cross_department_access_denied_for_set_perms(api_client: APIClient, ensure_ldap_disabled):
    d1 = Department.objects.create(name="Dept1")
    d2 = Department.objects.create(name="Dept2")

    user = make_user("m@example.com")
    api_client.force_authenticate(user=user)
    grant_assign_in_dept(user, d1)  # права только в Dept1

    role_d2 = make_role(d2, "R", [])
    url_set = reverse("api:v1:department-roles-set-perms", args=[role_d2.id])

    resp = api_client.post(url_set, {"permission_codes": ["manage_department"]}, format="json")
    assert resp.status_code == 403
