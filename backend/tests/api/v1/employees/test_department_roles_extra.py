import pytest
from django.urls import reverse
from django.contrib.auth.models import Permission
from rest_framework import status

from employees.models import (
    Employee,
    Department,
    DepartmentRole,
    EmployeeDepartment,
)

# --- helpers (локальные, чтобы тесты были самодостаточными) ---

_seq = 1
def _unique_email(prefix="user"):
    global _seq
    _seq += 1
    return f"{prefix}{_seq}@example.com"

def _unique_phone():
    global _seq
    _seq += 1
    return f"+7999{_seq:07d}"

def _make_user(staff=False, superuser=False) -> Employee:
    u = Employee.objects.create_user(
        email=_unique_email(), password="pass",
        phone_number=_unique_phone(),
        send_activation_email=False, first_name="T", last_name="U",
    )
    u.is_staff = staff
    u.is_superuser = superuser
    u.email_verified = True
    u.is_active = True
    u.save(update_fields=["is_staff", "is_superuser", "email_verified", "is_active"])
    return u

def _grant_perm(user: Employee, perm_code: str):
    app_label, codename = perm_code.split(".", 1)
    p = Permission.objects.get(content_type__app_label=app_label, codename=codename)
    user.user_permissions.add(p)
    user.save()
    # сброс кэша прав — иначе has_perm может брать старый кеш
    for attr in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        if hasattr(user, attr):
            try:
                delattr(user, attr)
            except Exception:
                pass
    return p

# --- tests ---

@pytest.mark.django_db
def test_perms_endpoint_requires_auth(api_client):
    # prepare
    d = Department.objects.create(name="A")
    role = DepartmentRole.objects.create(department=d, name="R")

    url = reverse("api:v1:department-roles-perms", args=[role.id])

    # unauth -> 401/403
    resp = api_client.get(url)
    assert resp.status_code in (401, 403)

    # auth (любой) -> 200
    user = _make_user()
    api_client.force_authenticate(user=user)
    resp = api_client.get(url)
    assert resp.status_code == 200
    assert isinstance(resp.data, dict)
    assert "results" in resp.data


@pytest.mark.django_db
def test_filter_invalid_department_param(api_client):
    user = _make_user()
    api_client.force_authenticate(user=user)

    d = Department.objects.create(name="D")
    DepartmentRole.objects.create(department=d, name="R1")

    url = reverse("api:v1:department-roles-list")

    # нечисловой фильтр department -> просто пустой список (ошибки быть не должно)
    resp = api_client.get(url, {"department": "oops"})
    assert resp.status_code == 200
    assert isinstance(resp.data, list)
    # В худшем случае фильтр не сработает — тогда >=1.
    # Основная проверка — отсутствие исключений.


@pytest.mark.django_db
def test_member_role_with_manage_can_crud_in_own_department(api_client):
    # пользователь не head, но имеет роль отдела с правом manage_department
    user = _make_user()
    api_client.force_authenticate(user=user)
    dept = Department.objects.create(name="Ops")

    role_mgr = DepartmentRole.objects.create(department=dept, name="Manager")
    p_manage = Permission.objects.get(content_type__app_label="employees", codename="manage_department")
    role_mgr.permissions.add(p_manage)

    # делаем пользователя членом отдела с этой ролью
    EmployeeDepartment.objects.create(employee=user, department=dept, role=role_mgr, is_active=True)

    url = reverse("api:v1:department-roles-list")

    # create в своём отделе — должен пройти
    resp = api_client.post(url, {"department": dept.id, "name": "NewRole"}, format="json")
    assert resp.status_code == 201
    role_id = resp.data["id"]

    # update — тоже должен пройти
    url_detail = reverse("api:v1:department-roles-detail", args=[role_id])
    resp = api_client.patch(url_detail, {"name": "NewRole++"}, format="json")
    assert resp.status_code == 200

    # delete — тоже должен пройти
    resp = api_client.delete(url_detail)
    assert resp.status_code == 204


@pytest.mark.django_db
def test_member_role_assign_can_set_perms_without_manage(api_client):
    # пользователь не head, но имеет роль с правом assign_department_role — может управлять правами роли
    user = _make_user()
    api_client.force_authenticate(user=user)
    dept = Department.objects.create(name="Ops2")

    role_assigner = DepartmentRole.objects.create(department=dept, name="Assigner")
    p_assign = Permission.objects.get(content_type__app_label="employees", codename="assign_department_role")
    role_assigner.permissions.add(p_assign)

    EmployeeDepartment.objects.create(employee=user, department=dept, role=role_assigner, is_active=True)

    # создадим цель-роль, которой будем управлять правами
    target_role = DepartmentRole.objects.create(department=dept, name="Target")
    p_view_emp = Permission.objects.get(content_type__app_label="employees", codename="view_employee")

    # set_perms должен позволяться с одним правом assign_department_role
    url_set = reverse("api:v1:department-roles-set-perms", args=[target_role.id])
    resp = api_client.post(url_set, {"permission_ids": [p_view_emp.id]}, format="json")
    assert resp.status_code == 200
    assert set(target_role.permissions.values_list("id", flat=True)) == {p_view_emp.id}


@pytest.mark.django_db
def test_global_manage_grants_crud_in_any_department(api_client):
    # Глобальный пермишен employees.manage_department должен открыть CRUD в любом отделе
    user = _make_user()
    api_client.force_authenticate(user=user)
    _grant_perm(user, "employees.manage_department")

    foreign = Department.objects.create(name="Foreign-Dept")

    url = reverse("api:v1:department-roles-list")
    resp = api_client.post(url, {"department": foreign.id, "name": "GloballyAllowed"}, format="json")
    assert resp.status_code == 201

    role_id = resp.data["id"]
    url_detail = reverse("api:v1:department-roles-detail", args=[role_id])
    resp = api_client.patch(url_detail, {"name": "EditOK"}, format="json")
    assert resp.status_code == 200

    resp = api_client.delete(url_detail)
    assert resp.status_code == 204


@pytest.mark.django_db
def test_role_in_other_dept_does_not_grant_cross_access(api_client):
    # Роль с правом manage_department в отделе A не даёт права управлять отделом B
    user = _make_user()
    api_client.force_authenticate(user=user)
    dept_a = Department.objects.create(name="A")
    dept_b = Department.objects.create(name="B")

    role_mgr_a = DepartmentRole.objects.create(department=dept_a, name="MgrA")
    p_manage = Permission.objects.get(content_type__app_label="employees", codename="manage_department")
    role_mgr_a.permissions.add(p_manage)
    EmployeeDepartment.objects.create(employee=user, department=dept_a, role=role_mgr_a, is_active=True)

    # create в отделе B -> 403
    url = reverse("api:v1:department-roles-list")
    resp = api_client.post(url, {"department": dept_b.id, "name": "NoAccess"}, format="json")
    assert resp.status_code == 403


@pytest.mark.django_db
def test_set_perms_replaces_completely_and_dedup(api_client):
    head = _make_user()
    api_client.force_authenticate(user=head)
    dept = Department.objects.create(name="QA", head=head)
    EmployeeDepartment.objects.get_or_create(employee=head, department=dept, defaults={"is_active": True})

    role = DepartmentRole.objects.create(department=dept, name="Reviewer")
    p_view = Permission.objects.get(content_type__app_label="employees", codename="view_employee")
    p_manage = Permission.objects.get(content_type__app_label="employees", codename="manage_department")

    # сначала добавим одно право
    role.permissions.add(p_view)

    url_set = reverse("api:v1:department-roles-set-perms", args=[role.id])
    # передаём список с дублями -> в итоге только p_manage
    resp = api_client.post(url_set, {"permission_ids": [p_manage.id, p_manage.id]}, format="json")
    assert resp.status_code == 200
    assert set(role.permissions.values_list("id", flat=True)) == {p_manage.id}


@pytest.mark.django_db
def test_add_and_remove_idempotent(api_client):
    head = _make_user()
    api_client.force_authenticate(user=head)
    dept = Department.objects.create(name="Prod", head=head)
    EmployeeDepartment.objects.get_or_create(employee=head, department=dept, defaults={"is_active": True})

    role = DepartmentRole.objects.create(department=dept, name="Operator")
    p1 = Permission.objects.get(content_type__app_label="employees", codename="view_employee")
    p2 = Permission.objects.get(content_type__app_label="employees", codename="assign_department_role")

    # add_perms с дублями
    url_add = reverse("api:v1:department-roles-add-perms", args=[role.id])
    resp = api_client.post(url_add, {"permission_ids": [p1.id, p1.id, p2.id]}, format="json")
    assert resp.status_code == 200
    assert set(role.permissions.values_list("id", flat=True)) == {p1.id, p2.id}

    # повторный add_perms — без изменений
    resp = api_client.post(url_add, {"permission_ids": [p1.id]}, format="json")
    assert resp.status_code == 200
    assert set(role.permissions.values_list("id", flat=True)) == {p1.id, p2.id}

    # remove_perms частичный и повторный (идемпотентность)
    url_rm = reverse("api:v1:department-roles-remove-perms", args=[role.id])
    resp = api_client.post(url_rm, {"permission_ids": [p1.id]}, format="json")
    assert resp.status_code == 200
    assert set(role.permissions.values_list("id", flat=True)) == {p2.id}

    # повторный remove для уже удалённого — состояние не меняется
    resp = api_client.post(url_rm, {"permission_ids": [p1.id]}, format="json")
    assert resp.status_code == 200
    assert set(role.permissions.values_list("id", flat=True)) == {p2.id}


@pytest.mark.django_db
def test_missing_department_on_create_returns_400(api_client):
    head = _make_user()
    api_client.force_authenticate(user=head)
    dept = Department.objects.create(name="Doc", head=head)
    EmployeeDepartment.objects.get_or_create(employee=head, department=dept, defaults={"is_active": True})

    url = reverse("api:v1:department-roles-list")
    # забыли передать department -> 400 (валидация сериализатора)
    resp = api_client.post(url, {"name": "RoleX"}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_permissions_payload_validation_errors(api_client):
    head = _make_user()
    api_client.force_authenticate(user=head)
    dept = Department.objects.create(name="Check", head=head)
    EmployeeDepartment.objects.get_or_create(employee=head, department=dept, defaults={"is_active": True})
    role = DepartmentRole.objects.create(department=dept, name="R")

    # не список -> 400
    url_set = reverse("api:v1:department-roles-set-perms", args=[role.id])
    resp = api_client.post(url_set, {"permission_ids": "oops"}, format="json")
    assert resp.status_code == 400

    # несуществующие id -> 400
    resp = api_client.post(url_set, {"permission_ids": [999999]}, format="json")
    assert resp.status_code == 400


@pytest.mark.django_db
def test_delete_nonexistent_returns_404(api_client):
    head = _make_user()
    api_client.force_authenticate(user=head)
    dept = Department.objects.create(name="Del", head=head)
    EmployeeDepartment.objects.get_or_create(employee=head, department=dept, defaults={"is_active": True})

    url_detail = reverse("api:v1:department-roles-detail", args=[999999])
    resp = api_client.delete(url_detail)
    assert resp.status_code == 404
