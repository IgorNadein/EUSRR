import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.contrib.auth.models import Permission
from employees.models import Department
from calendar_app.models import CompanyEvent, DepartmentEvent, Recurrence

User = get_user_model()


@pytest.mark.django_db
def test_department_event_clean_invalid_range():
    dep = Department.objects.create(name="QA")
    ev = DepartmentEvent(
        department=dep,
        title="Спринт",
        start_date="2025-05-10",
        end_date="2025-05-01",  # раньше начала
    )
    with pytest.raises(Exception):
        ev.full_clean()


@pytest.mark.django_db
def test_department_event_db_constraint_invalid_range():
    dep = Department.objects.create(name="DevOps")
    # обходим full_clean и проверяем именно DB-constraint
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DepartmentEvent.objects.create(
                department=dep, title="Bad", start_date="2025-05-10", end_date="2025-05-01"
            )


@pytest.mark.django_db
def test_created_by_set_null_on_user_delete():
    dep = Department.objects.create(name="HR")
    user = User.objects.create_user(phone_number="+70000000001", email="u@x.io", password="x")
    ev = DepartmentEvent.objects.create(department=dep, title="1:1", start_date="2025-06-01", created_by=user)
    user.delete()
    ev.refresh_from_db()
    assert ev.created_by is None


@pytest.mark.django_db
def test_company_event_str_and_recurrence():
    user = User.objects.create_user(phone_number="+70000000002", email="c@x.io", password="x")
    ev = CompanyEvent.objects.create(
        title="ДР компании", date="2025-01-15", recurrence=Recurrence.ANNUAL, created_by=user
    )
    assert "ДР компании" in str(ev)
    assert ev.recurrence == Recurrence.ANNUAL


@pytest.mark.django_db
def test_permission_exists():
    assert Permission.objects.filter(codename="manage_department_events").exists()
