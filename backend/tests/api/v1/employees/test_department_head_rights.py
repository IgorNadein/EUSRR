import pytest
from django.urls import reverse
from django.utils import timezone
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

def _dept_set_head(api_client, dept_id, head_id):
    url = reverse("api:v1:departments-set-head", args=[dept_id])
    payload = {"head_id": head_id} if head_id is not None else {"head_id": None}
    return api_client.post(url, payload, format="json")

# --- tests ---

@pytest.mark.django_db
def test_old_head_loses_rights_after_change(api_client):
    # setup: old head
    old_head = _make_user()
    api_client.force_authenticate(user=old_head)
    dept = Department.objects.create(name="Alpha", head=old_head)

    # Как глава — может править отдел (partial_update требует manage_department)
    url_detail = reverse("api:v1:departments-detail", args=[dept.id])
    resp = api_client.patch(url_detail, {"description": "init"}, format="json")
    assert resp.status_code == 200

    # Назначаем нового главу (делает текущий глава)
    new_head = _make_user()
    resp = _dept_set_head(api_client, dept.id, new_head.id)
    assert resp.status_code == 200
    assert resp.data["head_id"] == new_head.id

    # Старый глава больше не глава -> прав на управление отделом больше нет
    resp = api_client.patch(url_detail, {"description": "should fail"}, format="json")
    assert resp.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
def test_new_head_gets_rights_and_membership_created(api_client):
    # setup: без главы
    creator = _make_user()  # просто актор для вызовов
    api_client.force_authenticate(user=creator)
    dept = Department.objects.create(name="Beta")

    # Назначаем нового главу (создатель не обязан иметь права — у вас это ограничивается IsDeptManagerForWrite;
    # для чистоты будем действовать от staff)
    staff = _make_user(staff=True)
    api_client.force_authenticate(user=staff)
    new_head = _make_user()

    resp = _dept_set_head(api_client, dept.id, new_head.id)
    assert resp.status_code == 200

    # У нового главы есть права управления отделом
    api_client.force_authenticate(user=new_head)
    url_detail = reverse("api:v1:departments-detail", args=[dept.id])
    resp = api_client.patch(url_detail, {"description": "ok"}, format="json")
    assert resp.status_code == 200

    # И ему создана активная связь членства
    link = EmployeeDepartment.objects.filter(employee=new_head, department=dept, is_active=True).first()
    assert link is not None
    assert link.date_from is not None

@pytest.mark.django_db
def test_remove_head_deactivates_membership_and_revokes_rights(api_client):
    # setup: есть глава
    head = _make_user()
    staff = _make_user(staff=True)
    dept = Department.objects.create(name="Gamma", head=head)

    # как глава он может управлять
    api_client.force_authenticate(user=head)
    url_detail = reverse("api:v1:departments-detail", args=[dept.id])
    assert api_client.patch(url_detail, {"description": "ok"}, format="json").status_code == 200

    # staff снимает главу (head -> null)
    api_client.force_authenticate(user=staff)
    resp = _dept_set_head(api_client, dept.id, None)
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    # связь старого главы должна стать неактивной и получить date_to
    link = EmployeeDepartment.objects.filter(employee=head, department=dept).first()
    assert link is not None
    assert link.is_active is False
    assert link.date_to is not None

    # и прав больше нет
    api_client.force_authenticate(user=head)
    resp = api_client.patch(url_detail, {"description": "nope"}, format="json")
    assert resp.status_code == status.HTTP_403_FORBIDDEN

@pytest.mark.django_db
def test_old_head_keeps_rights_if_role_grants_after_change(api_client):
    # setup: старый глава
    old_head = _make_user()
    dept = Department.objects.create(name="Delta", head=old_head)

    # подготовим роль отдела с manage_department и назначим её старому главе (как обычному члену)
    role = DepartmentRole.objects.create(department=dept, name="ManagerRole")
    p_manage = Permission.objects.get(content_type__app_label="employees", codename="manage_department")
    role.permissions.add(p_manage)
    EmployeeDepartment.objects.update_or_create(
        employee=old_head, department=dept, defaults={"role": role, "is_active": True, "date_from": timezone.now().date()}
    )

    # меняем главу
    staff = _make_user(staff=True)
    api_client.force_authenticate(user=staff)
    new_head = _make_user()
    assert _dept_set_head(api_client, dept.id, new_head.id).status_code == 200

    # старый глава уже не head, но он обладает ролью с manage_department -> должен иметь доступ
    api_client.force_authenticate(user=old_head)
    url_detail = reverse("api:v1:departments-detail", args=[dept.id])
    resp = api_client.patch(url_detail, {"description": "still ok"}, format="json")
    assert resp.status_code == 200

@pytest.mark.django_db
def test_change_head_does_not_deactivate_old_membership_by_default(api_client):
    # при смене head -> старый head остаётся активным членом (согласно текущей логике save())
    old_head = _make_user()
    staff = _make_user(staff=True)
    api_client.force_authenticate(user=staff)
    dept = Department.objects.create(name="Epsilon", head=old_head)

    new_head = _make_user()
    assert _dept_set_head(api_client, dept.id, new_head.id).status_code == 200

    # Проверяем, что связь старого главы осталась активной (деактивируется только когда head -> None)
    link = EmployeeDepartment.objects.filter(employee=old_head, department=dept).first()
    assert link is not None
    assert link.is_active is True
