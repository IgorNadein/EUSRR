from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from attendance.models import EmployeeWorkSchedule, StandardWorkSchedule
from finance.models import (
    PayrollAuditEvent,
    PayrollDailyWorkEntry,
    PayrollPeriod,
    PayrollWorkSettings,
    PayrollWorkRecord,
)

pytestmark = pytest.mark.django_db


def api_url():
    return reverse("api:v1:finance-payroll:own-work-records")


def make_period(*, creator, code="2026-06", status="open"):
    return PayrollPeriod.objects.create(
        code=code,
        name="Июнь 2026",
        date_from="2026-06-01",
        date_to="2026-06-30",
        pay_date="2026-07-05",
        currency="RUB",
        status=status,
        created_by=creator,
    )


def test_daily_work_api_requires_authentication(auth_client_factory):
    response = auth_client_factory().get(api_url())

    assert response.status_code in {401, 403}
    assert "no-store" in response["Cache-Control"]


def test_daily_work_defaults_to_period_nearest_to_today(
    user_factory,
    auth_client_factory,
):
    employee = user_factory(email="daily.nearest.employee@example.test")
    manager = user_factory(email="daily.nearest.manager@example.test")
    today = timezone.localdate()

    close_past = PayrollPeriod.objects.create(
        code="nearest-past",
        name="Ближайший прошедший",
        date_from=today - timedelta(days=12),
        date_to=today - timedelta(days=2),
        pay_date=today + timedelta(days=3),
        currency="RUB",
        status="open",
        created_by=manager,
    )
    current = PayrollPeriod.objects.create(
        code="nearest-current",
        name="Текущий",
        date_from=today - timedelta(days=1),
        date_to=today + timedelta(days=1),
        pay_date=today + timedelta(days=5),
        currency="RUB",
        status="calculated",
        created_by=manager,
    )
    far_future = PayrollPeriod.objects.create(
        code="nearest-future",
        name="Дальний будущий",
        date_from=today + timedelta(days=30),
        date_to=today + timedelta(days=60),
        pay_date=today + timedelta(days=65),
        currency="RUB",
        status="open",
        created_by=manager,
    )
    client = auth_client_factory(employee)

    response = client.get(api_url())

    assert response.status_code == 200, response.content
    assert response.json()["selected_period_id"] == current.pk

    current.delete()
    response_without_current = client.get(api_url())
    assert response_without_current.status_code == 200
    assert response_without_current.json()["selected_period_id"] == close_past.pk

    explicit = client.get(api_url(), {"period_id": far_future.pk})
    assert explicit.status_code == 200
    assert explicit.json()["selected_period_id"] == far_future.pk


def test_employee_daily_entries_are_isolated_and_aggregated(
    user_factory,
    auth_client_factory,
):
    employee = user_factory(email="daily.work.employee@example.test")
    stranger = user_factory(email="daily.work.stranger@example.test")
    manager = user_factory(email="daily.work.manager@example.test")
    period = make_period(creator=manager)
    client = auth_client_factory(employee)

    first = client.post(
        api_url(),
        {
            "period_id": period.pk,
            "work_date": "2026-06-02",
            "target_points": "999.0000",
            "actual_points": "10.0000",
            "note": "Первая смена",
        },
        format="json",
    )

    assert first.status_code == 201, first.content
    assert first.json()["operation"] == "created"
    assert first.json()["entry"]["work_date"] == "2026-06-02"
    assert first.json()["entry"]["target_points"] == "5.0000"
    assert first.json()["record"]["target_points"] == "110.0000"
    assert first.json()["record"]["actual_points"] == "10.0000"
    assert first.json()["record"]["status"] == "draft"
    aggregate_id = first.json()["record"]["id"]

    second = client.post(
        api_url(),
        {
            "period_id": period.pk,
            "work_date": "2026-06-03",
            "actual_points": "7.0000",
            "note": "Вторая смена",
        },
        format="json",
    )

    assert second.status_code == 201, second.content
    assert second.json()["record"]["id"] == aggregate_id
    assert second.json()["record"]["target_points"] == "110.0000"
    assert second.json()["record"]["actual_points"] == "17.0000"

    first_entry = PayrollDailyWorkEntry.objects.get(
        employee=employee,
        work_date="2026-06-02",
    )
    updated = client.post(
        api_url(),
        {
            "period_id": period.pk,
            "work_date": "2026-06-02",
            "actual_points": "12.0000",
            "note": "Уточнённый результат",
            "expected_lock_version": first_entry.lock_version,
        },
        format="json",
    )

    assert updated.status_code == 200, updated.content
    assert updated.json()["operation"] == "updated"
    assert updated.json()["entry"]["lock_version"] == 1
    assert updated.json()["record"]["target_points"] == "110.0000"
    assert updated.json()["record"]["actual_points"] == "19.0000"

    stale = client.post(
        api_url(),
        {
            "period_id": period.pk,
            "work_date": "2026-06-02",
            "actual_points": "20.0000",
            "expected_lock_version": 0,
        },
        format="json",
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "STALE_DAILY_WORK_ENTRY"

    auth_client_factory(stranger).post(
        api_url(),
        {
            "period_id": period.pk,
            "work_date": "2026-06-02",
            "actual_points": "5.0000",
        },
        format="json",
    )
    workspace = client.get(api_url(), {"period_id": period.pk})
    assert workspace.status_code == 200
    assert workspace.json()["daily_target_points"] == "5"
    assert workspace.json()["selected_period_id"] == period.pk
    assert len(workspace.json()["entries"]) == 2
    assert {
        entry["actual_points"] for entry in workspace.json()["entries"]
    } == {"12.0000", "7.0000"}
    assert "employee" not in workspace.json()["entries"][0]
    period_payload = workspace.json()["periods"][0]
    assert period_payload["editable"] is True
    assert period_payload["record"]["actual_points"] == "19.0000"
    assert "expected_gross" not in period_payload["record"]

    aggregate = PayrollWorkRecord.objects.get(pk=aggregate_id)
    assert aggregate.employee == employee
    assert aggregate.created_by == employee
    assert aggregate.target_points == Decimal("110")
    assert aggregate.actual_points == Decimal("19")
    assert aggregate.source == "api"
    assert PayrollAuditEvent.objects.filter(
        actor=employee,
        action="payroll.daily_work_entry_created",
        period=period,
    ).count() == 2
    assert PayrollAuditEvent.objects.filter(
        actor=employee,
        action="payroll.daily_work_entry_updated",
        period=period,
    ).count() == 1


def test_daily_work_change_creates_revision_of_approved_aggregate(
    user_factory,
    auth_client_factory,
):
    employee = user_factory(email="daily.revision.employee@example.test")
    manager = user_factory(email="daily.revision.manager@example.test")
    period = make_period(creator=manager)
    client = auth_client_factory(employee)
    created = client.post(
        api_url(),
        {
            "period_id": period.pk,
            "work_date": "2026-06-10",
            "actual_points": "8.0000",
        },
        format="json",
    )
    source = PayrollWorkRecord.objects.get(pk=created.json()["record"]["id"])
    source.status = "approved"
    source.approved_by = manager
    source.approved_at = timezone.now()
    source.save(update_fields=["status", "approved_by", "approved_at"])
    entry = PayrollDailyWorkEntry.objects.get(employee=employee, period=period)

    response = client.post(
        api_url(),
        {
            "period_id": period.pk,
            "work_date": "2026-06-10",
            "actual_points": "9.0000",
            "expected_lock_version": entry.lock_version,
        },
        format="json",
    )

    assert response.status_code == 200, response.content
    source.refresh_from_db()
    revision = PayrollWorkRecord.objects.get(replaces=source)
    assert source.status == "approved"
    assert revision.status == "draft"
    assert revision.revision == 2
    assert revision.actual_points == Decimal("9")
    assert revision.created_by == employee
    assert response.json()["record"]["id"] == revision.pk
    assert PayrollAuditEvent.objects.filter(
        action="payroll.daily_work_aggregate_revision_created",
        object_id=str(revision.pk),
        period=period,
    ).exists()


def test_daily_work_rejects_locked_period_and_date_outside_period(
    user_factory,
    auth_client_factory,
):
    employee = user_factory(email="daily.locked.employee@example.test")
    manager = user_factory(email="daily.locked.manager@example.test")
    period = make_period(creator=manager)
    client = auth_client_factory(employee)

    outside = client.post(
        api_url(),
        {
            "period_id": period.pk,
            "work_date": "2026-07-01",
            "actual_points": "8.0000",
        },
        format="json",
    )
    assert outside.status_code == 409
    assert outside.json()["code"] == "WORK_DATE_OUTSIDE_PERIOD"

    period.status = "calculated"
    period.save(update_fields=["status"])
    locked = client.post(
        api_url(),
        {
            "period_id": period.pk,
            "work_date": "2026-06-15",
            "actual_points": "8.0000",
        },
        format="json",
    )
    assert locked.status_code == 409
    assert locked.json()["code"] == "WORK_PERIOD_LOCKED"
    assert not PayrollDailyWorkEntry.objects.filter(employee=employee).exists()


def test_global_daily_target_applies_to_new_entries_and_preserves_history(
    user_factory,
    auth_client_factory,
):
    employee = user_factory(email="daily.target.employee@example.test")
    manager = user_factory(email="daily.target.manager@example.test")
    period = make_period(creator=manager)
    settings = PayrollWorkSettings.objects.create(daily_target_points="7.5")
    client = auth_client_factory(employee)

    first = client.post(
        api_url(),
        {
            "period_id": period.pk,
            "work_date": "2026-06-02",
            "actual_points": "8.0000",
        },
        format="json",
    )

    assert first.status_code == 201, first.content
    assert first.json()["entry"]["target_points"] == "7.5000"
    settings.daily_target_points = Decimal("9")
    settings.save(update_fields=["daily_target_points", "updated_at"])

    existing_entry = PayrollDailyWorkEntry.objects.get(
        employee=employee,
        work_date="2026-06-02",
    )
    updated = client.post(
        api_url(),
        {
            "period_id": period.pk,
            "work_date": "2026-06-02",
            "actual_points": "8.5000",
            "expected_lock_version": existing_entry.lock_version,
        },
        format="json",
    )
    second = client.post(
        api_url(),
        {
            "period_id": period.pk,
            "work_date": "2026-06-03",
            "actual_points": "9.0000",
        },
        format="json",
    )
    workspace = client.get(api_url(), {"period_id": period.pk})

    assert updated.status_code == 200, updated.content
    assert updated.json()["entry"]["target_points"] == "7.5000"
    assert second.status_code == 201, second.content
    assert second.json()["entry"]["target_points"] == "9.0000"
    assert updated.json()["record"]["target_points"] == "198.0000"
    assert second.json()["record"]["target_points"] == "198.0000"
    assert workspace.json()["daily_target_points"] == "9.0000"


def test_period_summary_is_calculated_without_creating_database_record(
    user_factory,
    auth_client_factory,
):
    employee = user_factory(email="daily.summary.employee@example.test")
    manager = user_factory(email="daily.summary.manager@example.test")
    period = make_period(creator=manager)

    client = auth_client_factory(employee)
    response = client.get(
        api_url(),
        {"period_id": period.pk},
    )

    assert response.status_code == 200
    period_payload = response.json()["periods"][0]
    assert period_payload["record"] is None
    assert period_payload["summary"] == {
        "target_points": "110.0000",
        "actual_points": "0.0000",
        "target_source": "default_schedule",
        "workdays_count": 22,
    }
    assert not PayrollWorkRecord.objects.filter(
        employee=employee,
        period=period,
    ).exists()


def test_period_summary_uses_individual_schedule_before_standard_schedule(
    user_factory,
    auth_client_factory,
):
    employee = user_factory(email="daily.schedule.employee@example.test")
    manager = user_factory(email="daily.schedule.manager@example.test")
    period = make_period(creator=manager)
    PayrollWorkSettings.objects.create(daily_target_points="7.5")
    StandardWorkSchedule.objects.create(
        workdays=["Monday", "Tuesday"],
        date_overrides=[
            {"date": "2026-06-02", "is_workday": False},
            {"date": "2026-06-06", "is_workday": True},
        ],
    )
    client = auth_client_factory(employee)

    standard_response = client.get(api_url(), {"period_id": period.pk})

    assert standard_response.json()["periods"][0]["summary"] == {
        "target_points": "75.0000",
        "actual_points": "0.0000",
        "target_source": "standard_schedule",
        "workdays_count": 10,
    }

    EmployeeWorkSchedule.objects.create(
        employee=employee,
        workdays=["Wednesday"],
        date_overrides=[
            {"date": "2026-06-06", "is_workday": True},
        ],
    )
    individual_response = client.get(api_url(), {"period_id": period.pk})

    assert individual_response.json()["periods"][0]["summary"] == {
        "target_points": "37.5000",
        "actual_points": "0.0000",
        "target_source": "individual_schedule",
        "workdays_count": 5,
    }


def test_saved_manual_target_has_priority_over_schedule_calculation(
    user_factory,
    auth_client_factory,
):
    employee = user_factory(email="daily.manual.employee@example.test")
    manager = user_factory(email="daily.manual.manager@example.test")
    period = make_period(creator=manager)
    PayrollWorkRecord.objects.create(
        period=period,
        employee=employee,
        target_points="42",
        actual_points="3",
        source="manual",
        created_by=manager,
    )

    client = auth_client_factory(employee)
    response = client.get(
        api_url(),
        {"period_id": period.pk},
    )

    summary = response.json()["periods"][0]["summary"]
    assert summary["target_points"] == "42.0000"
    assert summary["actual_points"] == "3.0000"
    assert summary["target_source"] == "saved_record"

    saved = client.post(
        api_url(),
        {
            "period_id": period.pk,
            "work_date": "2026-06-02",
            "actual_points": "6.0000",
        },
        format="json",
    )

    assert saved.status_code == 201, saved.content
    record = PayrollWorkRecord.objects.get(period=period, employee=employee)
    assert record.target_points == Decimal("42")
    assert record.actual_points == Decimal("6")
    assert record.source == "manual"
