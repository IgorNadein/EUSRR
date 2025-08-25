import pytest
from django.urls import reverse
from django.contrib.auth.models import Permission
from rest_framework import status

from employees.models import Employee, Department, DepartmentRole, EmployeeDepartment

# --- helpers ---

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
        email=_unique_email(), password="pass", phone_number=_unique_phone(),
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
    # сброс кэша прав на всякий случай
    for attr in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        if hasattr(user, attr):
            try: delattr(user, attr)
            except: pass
    return p

# --- tests ---

@pytest.mark.django_db
def test_list_and_filter_requires_auth(api_client):
    url = reverse("api:api_v1:department-roles-list")

    # unauth -> 401/403
    resp = api_client.get(url)
    assert resp.status_code in (401, 403)

    # auth -> 200, фильтр по department
    user = _make_user()
    api_client.force_authenticate(user=user)
    d1 = Department.objects.create(name="Sales")
    d2 = Department.objects.create(name="Support")
    DepartmentRole.objects.create(department=d1, name="Manager")
    DepartmentRole.objects.create(department=d2, name="Operator")

    resp = api_client.get(url)
    assert resp.status_code == 200
    assert len(resp.data) == 2

    resp = api_client.get(url, {"department": d1.id})
    assert resp.status_code == 200
    assert len(resp.data) == 1
    assert resp.data[0]["name"] == "Manager"

@pytest.mark.django_db
def test_head_can_crud_in_own_department(api_client):
    head = _make_user()
    api_client.force_authenticate(user=head)
    dept = Department.objects.create(name="R&D", head=head)
    # гарантируем активную связь головы с отделом
    EmployeeDepartment.objects.get_or_create(employee=head, department=dept, defaults={"is_active": True})

    url = reverse("api:api_v1:department-roles-list")

    # create в своём отделе
    resp = api_client.post(url, {"department": dept.id, "name": "Lead"}, format="json")
    assert resp.status_code == status.HTTP_201_CREATED
    role_id = resp.data["id"]

    # update
    url_detail = reverse("api:api_v1:department-roles-detail", args=[role_id])
    resp = api_client.patch(url_detail, {"name": "Lead++"}, format="json")
    assert resp.status_code == 200

    # delete
    resp = api_client.delete(url_detail)
    assert resp.status_code == status.HTTP_204_NO_CONTENT

@pytest.mark.django_db
def test_head_cannot_crud_in_foreign_department(api_client):
    head = _make_user()
    api_client.force_authenticate(user=head)
    own = Department.objects.create(name="Own", head=head)
    foreign = Department.objects.create(name="Foreign")
    EmployeeDepartment.objects.get_or_create(employee=head, department=own, defaults={"is_active": True})

    # попытка создать роль в чужом отделе -> 403
    url = reverse("api:api_v1:department-roles-list")
    resp = api_client.post(url, {"department": foreign.id, "name": "X"}, format="json")
    assert resp.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
def test_non_head_needs_manage_for_crud_and_assign_for_perms(api_client):
    user = _make_user()
    api_client.force_authenticate(user=user)
    dept = Department.objects.create(name="Ops")
    # нет ни head, ни ролей — CRUD запрещён
    url = reverse("api:api_v1:department-roles-list")
    resp = api_client.post(url, {"department": dept.id, "name": "Role"}, format="json")
    assert resp.status_code == 403

    # даём право manage_department -> можно создавать/редактировать/удалять
    _grant_perm(user, "employees.manage_department")
    resp = api_client.post(url, {"department": dept.id, "name": "Role"}, format="json")
    assert resp.status_code == 201
    role_id = resp.data["id"]

    url_detail = reverse("api:api_v1:department-roles-detail", args=[role_id])
    resp = api_client.patch(url_detail, {"name": "Role2"}, format="json")
    assert resp.status_code == 200

    # но set_perms всё ещё нельзя: нужен assign_department_role
    url_set = reverse("api:api_v1:department-roles-set-perms", args=[role_id])
    resp = api_client.post(url_set, {"permission_ids": []}, format="json")
    assert resp.status_code == 403

    # выдаём assign_department_role -> теперь можно
    _grant_perm(user, "employees.assign_department_role")
    # выберем 2 реальных права из employees
    p1 = Permission.objects.get(content_type__app_label="employees", codename="manage_department")
    p2 = Permission.objects.get(content_type__app_label="employees", codename="assign_department_role")
    resp = api_client.post(url_set, {"permission_ids": [p1.id, p2.id]}, format="json")
    assert resp.status_code == 200
    assert set(DepartmentRole.objects.get(id=role_id).permissions.values_list("id", flat=True)) == {p1.id, p2.id}

@pytest.mark.django_db
def test_perms_listing_and_add_remove(api_client):
    head = _make_user()
    api_client.force_authenticate(user=head)
    dept = Department.objects.create(name="QA", head=head)
    EmployeeDepartment.objects.get_or_create(employee=head, department=dept, defaults={"is_active": True})

    role = DepartmentRole.objects.create(department=dept, name="Reviewer")
    p_view = Permission.objects.get(content_type__app_label="employees", codename="view_employee")
    p_manage = Permission.objects.get(content_type__app_label="employees", codename="manage_department")

    # add_perms (как head)
    url_add = reverse("api:api_v1:department-roles-add-perms", args=[role.id])
    resp = api_client.post(url_add, {"permission_ids": [p_view.id]}, format="json")
    assert resp.status_code == 200

    # perms (GET)
    url_perms = reverse("api:api_v1:department-roles-perms", args=[role.id])
    resp = api_client.get(url_perms)
    assert resp.status_code == 200
    codes = {row["codename"] for row in resp.data["results"]}
    assert "employees.view_employee" in codes

    # remove_perms
    url_rm = reverse("api:api_v1:department-roles-remove-perms", args=[role.id])
    resp = api_client.post(url_rm, {"permission_ids": [p_view.id]}, format="json")
    assert resp.status_code == 200
    assert set(role.permissions.values_list("id", flat=True)) == set()

    # set_perms
    url_set = reverse("api:api_v1:department-roles-set-perms", args=[role.id])
    resp = api_client.post(url_set, {"permission_ids": [p_manage.id]}, format="json")
    assert resp.status_code == 200
    assert set(role.permissions.values_list("id", flat=True)) == {p_manage.id}
