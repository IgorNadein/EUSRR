import pytest
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth.models import Permission
from rest_framework import status

from employees.models import Employee, Department, EmployeeDepartment, EmployeeAction
from employees.constants import ACTION_DISMISSED, ACTION_CHOICES

# helpers
_seq = 1


def _email(p="u"):
    global _seq
    _seq += 1
    return f"{p}{_seq}@example.com"


def _phone():
    global _seq
    _seq += 1
    return f"+7999{_seq:07d}"


def _user(staff=False, superuser=False) -> Employee:
    u = Employee.objects.create_user(
        email=_email(),
        password="pass",
        phone_number=_phone(),
        send_activation_email=False,
        first_name="T",
        last_name="U",
    )
    u.is_staff = staff
    u.is_superuser = superuser
    u.email_verified = True
    u.is_active = True
    u.save(update_fields=["is_staff", "is_superuser", "email_verified", "is_active"])
    return u


def _grant(user: Employee, code: str):
    app, codename = code.split(".", 1)
    p = Permission.objects.get(content_type__app_label=app, codename=codename)
    user.user_permissions.add(p)
    user.save()
    for a in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        if hasattr(user, a):
            try:
                delattr(user, a)
            except:
                pass
    return p


def _any_non_dismissed():
    for k, _ in ACTION_CHOICES:
        if k != ACTION_DISMISSED:
            return k
    pytest.skip("No non-dismissed action in ACTION_CHOICES")


@pytest.mark.django_db
def test_list_requires_auth_and_filtering(api_client):
    url = reverse("api:v1:employee-actions-list")
    # unauth
    assert api_client.get(url).status_code in (401, 403)

    actor = _user()
    api_client.force_authenticate(user=actor)
    emp = _user()
    other = _user()
    # фиксируем базовую линию: авто-события могли уже создаться сигналами
    baseline_all = set(EmployeeAction.objects.values_list("id", flat=True))
    baseline_emp = set(
        EmployeeAction.objects.filter(employee=emp).values_list("id", flat=True)
    )

    a1 = EmployeeAction.objects.create(
        employee=emp, action=_any_non_dismissed(), date=timezone.now()
    )
    a2 = EmployeeAction.objects.create(
        employee=other, action=_any_non_dismissed(), date=timezone.now()
    )

    resp = api_client.get(url)
    assert resp.status_code == 200
    got_all = {row["id"] for row in resp.data}
    assert got_all == baseline_all | {a1.id, a2.id}

    resp = api_client.get(url, {"employee": emp.id})
    assert resp.status_code == 200
    ids = {row["id"] for row in resp.data}
    assert ids == baseline_emp | {a1.id}


@pytest.mark.django_db
def test_create_requires_perm_or_staff(api_client):
    actor = _user()
    target = _user()
    api_client.force_authenticate(user=actor)
    url = reverse("api:v1:employee-actions-list")
    payload = {
        "employee": target.id,
        "action": _any_non_dismissed(),
        "date": timezone.now().isoformat(),
        "comment": "note",
        "extra": {"k": "v"},
    }

    # no perm -> 403
    resp = api_client.post(url, payload, format="json")
    assert resp.status_code == 403

    # grant add perm -> 201
    _grant(actor, "employees.add_employeeaction")
    baseline = EmployeeAction.objects.filter(employee=target).count()
    resp = api_client.post(url, payload, format="json")
    assert resp.status_code == 201
    assert EmployeeAction.objects.filter(employee=target).count() == baseline + 1

    # staff bypass -> 201
    staff = _user(staff=True)
    api_client.force_authenticate(user=staff)
    baseline2 = EmployeeAction.objects.filter(employee=target).count()
    resp = api_client.post(url, payload, format="json")
    assert resp.status_code == 201
    assert EmployeeAction.objects.filter(employee=target).count() == baseline2 + 1


@pytest.mark.django_db
def test_dismissal_deactivates_employee_and_links(api_client):
    staff = _user(staff=True)
    api_client.force_authenticate(user=staff)
    emp = _user()
    dept = Department.objects.create(name="D")
    EmployeeDepartment.objects.create(employee=emp, department=dept, is_active=True)

    url = reverse("api:v1:employee-actions-list")
    resp = api_client.post(
        url,
        {
            "employee": emp.id,
            "action": ACTION_DISMISSED,
            "date": timezone.now().isoformat(),
        },
        format="json",
    )
    assert resp.status_code == 201

    emp.refresh_from_db()
    assert emp.is_active is False
    link = EmployeeDepartment.objects.get(employee=emp, department=dept)
    assert link.is_active is False and link.date_to is not None


@pytest.mark.django_db
def test_non_dismissal_activates_employee(api_client):
    staff = _user(staff=True)
    api_client.force_authenticate(user=staff)
    emp = _user()
    emp.is_active = False
    emp.save(update_fields=["is_active"])

    url = reverse("api:v1:employee-actions-list")
    resp = api_client.post(
        url,
        {
            "employee": emp.id,
            "action": _any_non_dismissed(),
            "date": timezone.now().isoformat(),
        },
        format="json",
    )
    assert resp.status_code == 201
    emp.refresh_from_db()
    assert emp.is_active is True


@pytest.mark.django_db
def test_update_to_dismissed_applies_effects(api_client):
    actor = _user()
    api_client.force_authenticate(user=actor)
    _grant(actor, "employees.add_employeeaction")
    _grant(actor, "employees.change_employeeaction")

    emp = _user()
    act = EmployeeAction.objects.create(
        employee=emp, action=_any_non_dismissed(), date=timezone.now()
    )

    url_det = reverse("api:v1:employee-actions-detail", args=[act.id])
    resp = api_client.patch(url_det, {"action": ACTION_DISMISSED}, format="json")
    assert resp.status_code == 200
    emp.refresh_from_db()
    assert emp.is_active is False


@pytest.mark.django_db
def test_delete_requires_perm_or_staff(api_client):
    actor = _user()
    api_client.force_authenticate(user=actor)
    emp = _user()
    act = EmployeeAction.objects.create(
        employee=emp, action=_any_non_dismissed(), date=timezone.now()
    )
    url_det = reverse("api:v1:employee-actions-detail", args=[act.id])

    # no perm -> 403
    assert api_client.delete(url_det).status_code == 403

    # grant -> 204
    _grant(actor, "employees.delete_employeeaction")
    assert api_client.delete(url_det).status_code == 204
