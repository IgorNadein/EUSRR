# backend/tests/api/v1/employees/test_department_roles_extra.py
import pytest
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status

from employees.models import (
    Department,
    DepartmentRole,
    DepartmentPermission,
    EmployeeDepartment,  # если у вас EmployeeDepartmentLink, замените импорт и упоминания ниже
)

User = get_user_model()


# =========================
# Helpers
# =========================


def _unique_phone() -> str:
    base = 79000000000  # 79 + 9 нулей
    return str(base + User.objects.count())


def make_user(email: str, staff: bool = False, verified: bool = True) -> User:
    extra = {
        "phone_number": _unique_phone(),
        "is_staff": staff,
        "send_activation_email": False,
    }
    # добавим verified если поле есть
    try:
        User._meta.get_field("verified")
        extra["verified"] = verified
    except Exception:
        pass
    return User.objects.create_user(email=email, password="pwd12345", **extra)


def ensure_perm(code: str, name: str | None = None) -> DepartmentPermission:
    return DepartmentPermission.objects.get_or_create(
        code=code, defaults={"name": name or code}
    )[0]


def make_role(
    dept: Department, name: str, codes: list[str] | None = None
) -> DepartmentRole:
    role = DepartmentRole.objects.create(department=dept, name=name)
    if codes:
        perms = [ensure_perm(c) for c in codes]
        role.scoped_permissions.add(*perms)
    return role


def grant_assign_in_dept(user: User, dept: Department) -> DepartmentRole:
    role = make_role(dept, "assigner", ["assign_department_role"])
    EmployeeDepartment.objects.update_or_create(
        employee=user,
        department=dept,
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
def test_unauth_cannot_list_or_get():
    client = APIClient()
    url_list = reverse("api:v1:department-roles-list")
    assert client.get(url_list).status_code in (401, 403)


@pytest.mark.django_db
def test_read_only_allowed_without_assign(api_client: APIClient):
    d = Department.objects.create(name="Dept")
    r = make_role(d, "Worker", [])
    u = make_user("u@example.com")
    api_client.force_authenticate(user=u)

    # list
    url_list = reverse("api:v1:department-roles-list")
    resp = api_client.get(url_list, {"department": d.id})
    assert resp.status_code == 200
    items = resp.json().get("results", resp.json())
    assert any(x["id"] == r.id for x in items)

    # retrieve
    url_detail = reverse("api:v1:department-roles-detail", args=[r.id])
    assert api_client.get(url_detail).status_code == 200


@pytest.mark.django_db
def test_staff_override_for_write(api_client: APIClient):
    d = Department.objects.create(name="Dept")
    staff = make_user("s@example.com", staff=True)
    api_client.force_authenticate(user=staff)

    # create
    url_list = reverse("api:v1:department-roles-list")
    resp = api_client.post(
        url_list, {"department": d.id, "name": "SRole"}, format="json"
    )
    assert resp.status_code == 201
    rid = resp.json()["id"]

    # update
    url_detail = reverse("api:v1:department-roles-detail", args=[rid])
    assert (
        api_client.patch(url_detail, {"name": "SRole+"}, format="json").status_code
        == 200
    )

    # set_perms
    ensure_perm("manage_department")
    url_set = reverse("api:v1:department-roles-set-perms", args=[rid])
    assert (
        api_client.post(
            url_set, {"permission_codes": ["manage_department"]}, format="json"
        ).status_code
        == 200
    )


@pytest.mark.django_db
def test_ordering_stable_by_name_then_id(api_client: APIClient):
    d1 = Department.objects.create(name="Dept1")
    d2 = Department.objects.create(name="Dept2")
    u = make_user("u@example.com")
    api_client.force_authenticate(user=u)

    # одинаковые имена в РАЗНЫХ отделах — не нарушаем уникальность (department, name)
    r1 = make_role(d1, "A", [])
    r2 = make_role(d2, "A", [])
    r3 = make_role(d1, "B", [])

    url = reverse("api:v1:department-roles-list")
    resp = api_client.get(url, {"ordering": "name"})  # без фильтра по department
    assert resp.status_code == 200
    items = resp.json().get("results", resp.json())

    picked = [x["id"] for x in items if x["id"] in {r1.id, r2.id, r3.id}]
    # Ожидаем: сначала две "A" по возрастанию id, затем "B"
    assert len(picked) == 3
    assert picked[0] in (r1.id, r2.id) and picked[1] in (r1.id, r2.id)
    assert picked[0] < picked[1]  # тай-брейк по id для одинаковых name
    assert picked[2] == r3.id


@pytest.mark.django_db
def test_set_perms_ids_take_precedence_over_codes(api_client: APIClient):
    d = Department.objects.create(name="Dept")
    u = make_user("u@example.com")
    api_client.force_authenticate(user=u)
    grant_assign_in_dept(u, d)

    role = make_role(d, "R", [])
    dp_manage = ensure_perm("manage_department")
    dp_assign = ensure_perm("assign_department_role")

    url = reverse("api:v1:department-roles-set-perms", args=[role.id])
    # передаём одновременно ids и codes — по вьюхе приоритет у ids
    resp = api_client.post(
        url,
        {
            "permission_ids": [dp_manage.id],
            "permission_codes": ["assign_department_role"],
        },
        format="json",
    )
    assert resp.status_code == 200
    role.refresh_from_db()
    codes = set(role.scoped_permissions.values_list("code", flat=True))
    assert codes == {"manage_department"}  # ids приоритетнее


@pytest.mark.django_db
def test_serializer_codes_override_scoped_permissions_on_create(api_client: APIClient):
    d = Department.objects.create(name="Dept")
    ensure_perm("manage_department")
    ensure_perm("assign_department_role")

    u = make_user("u@example.com")
    api_client.force_authenticate(user=u)
    grant_assign_in_dept(u, d)

    # создадим роль, передав и ids, и codes — в сериализаторе codes должны перезаписать ids
    dp_manage = DepartmentPermission.objects.get(code="manage_department")
    url = reverse("api:v1:department-roles-list")
    resp = api_client.post(
        url,
        {
            "department": d.id,
            "name": "Lead",
            "scoped_permissions": [dp_manage.id],  # сначала ids
            "scoped_permission_codes": [
                "assign_department_role"
            ],  # потом codes — должны победить
        },
        format="json",
    )
    assert resp.status_code == 201
    rid = resp.json()["id"]
    role = DepartmentRole.objects.get(id=rid)
    codes = set(role.scoped_permissions.values_list("code", flat=True))
    assert codes == {"assign_department_role"}


@pytest.mark.django_db
def test_perm_choices_fields_and_nonempty(api_client: APIClient):
    ensure_perm("manage_department", "Управлять")
    ensure_perm("change_department_head", "Глава")
    ensure_perm("assign_department_role", "Назначение")

    u = make_user("u@example.com")
    api_client.force_authenticate(user=u)
    url = reverse("api:v1:department-roles-perm-choices")
    resp = api_client.get(url)
    assert resp.status_code == 200
    results = resp.json().get("results", [])
    assert results and {"id", "code", "name"}.issubset(results[0].keys())


@pytest.mark.django_db
def test_destroy_requires_assign_in_same_department(api_client: APIClient):
    d1 = Department.objects.create(name="D1")
    d2 = Department.objects.create(name="D2")
    u = make_user("u@example.com")
    api_client.force_authenticate(user=u)

    role = make_role(d2, "R", [])

    # нет прав в d2 — 403
    url = reverse("api:v1:department-roles-detail", args=[role.id])
    assert api_client.delete(url).status_code == 403

    # права в d1 не помогают — всё ещё 403
    grant_assign_in_dept(u, d1)
    assert api_client.delete(url).status_code == 403

    # выдаём права в d2 — можно удалять
    grant_assign_in_dept(u, d2)
    assert api_client.delete(url).status_code in (204, 200)


@pytest.mark.django_db
def test_set_perms_dedup_and_replace_semantics(api_client: APIClient):
    d = Department.objects.create(name="Dept")
    u = make_user("u@example.com")
    api_client.force_authenticate(user=u)
    grant_assign_in_dept(u, d)

    role = make_role(d, "R", [])
    ensure_perm("manage_department")
    ensure_perm("assign_department_role")

    url = reverse("api:v1:department-roles-set-perms", args=[role.id])

    # сначала ставим один код
    resp = api_client.post(
        url, {"permission_codes": ["manage_department"]}, format="json"
    )
    assert resp.status_code == 200
    role.refresh_from_db()
    assert set(role.scoped_permissions.values_list("code", flat=True)) == {
        "manage_department"
    }

    # потом отправим дубликаты и другой код — должно быть два уникальных, и ПОЛНАЯ замена
    resp = api_client.post(
        url,
        {
            "permission_codes": [
                "manage_department",
                "manage_department",
                "assign_department_role",
            ]
        },
        format="json",
    )
    assert resp.status_code == 200
    role.refresh_from_db()
    assert set(role.scoped_permissions.values_list("code", flat=True)) == {
        "manage_department",
        "assign_department_role",
    }
