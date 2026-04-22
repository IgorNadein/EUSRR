from unittest.mock import patch
from datetime import datetime

import pytest
from django.urls import reverse
from django.utils import timezone

from attendance.models import AttendanceAnalysisRun, AttendanceRecord
from employees.constants import ACTION_ON_LEAVE, ACTION_RETURNED_FROM_LEAVE
from employees.models import EmployeeAction

pytestmark = pytest.mark.django_db


def _analyze_url():
    return reverse("api:v1:logstorm-attendance-analyze")


def _records_url():
    return reverse("api:v1:attendance-records")


def _monthly_matrix_url():
    return reverse("api:v1:attendance-monthly-matrix")


def _record_detail_url(record_id):
    return reverse("api:v1:attendance-record-detail", args=[record_id])


def _record_comments_url(record_id):
    return reverse("api:v1:attendance-record-comments", args=[record_id])


def _record_comment_detail_url(record_id, comment_id):
    return reverse(
        "api:v1:attendance-record-comment-detail", args=[record_id, comment_id]
    )


def _payload(employee_id, **overrides):
    payload = {
        "employee_id": employee_id,
        "period_start": "2026-04-20",
        "period_end": "2026-04-21",
    }
    payload.update(overrides)
    return payload


def _logstorm_result():
    return {
        "records": [
            {
                "date": "2026-04-20",
                "employee_id": "42",
                "display_name": "Ivan Petrov",
                "arrival_time": "09:15",
                "departure_time": "18:00",
                "work_hours": 8.75,
                "expected_hours": 9,
                "is_workday": True,
                "is_late": True,
                "late_minutes": 15,
                "is_early_leave": False,
                "early_leave_minutes": None,
                "is_underwork": True,
                "underwork_hours": 0.25,
                "is_overtime": False,
                "overtime_hours": None,
                "is_absent": False,
                "statuses": ["late", "underwork"],
                "employee_issues": ["late"],
                "technical_issues": [],
            },
            {
                "date": "2026-04-21",
                "employee_id": "42",
                "display_name": "Ivan Petrov",
                "arrival_time": None,
                "departure_time": None,
                "work_hours": 0,
                "expected_hours": 9,
                "is_workday": True,
                "is_absent": True,
                "statuses": ["absence"],
                "employee_issues": ["absence"],
                "technical_issues": [],
            },
        ]
    }


def _aware_datetime(year, month, day):
    return timezone.make_aware(datetime(year, month, day))


def _move_auto_hired_before_test_period(employee):
    employee.actions.filter(action="hired").update(date=_aware_datetime(2026, 1, 1))


def test_analyze_saves_run_and_records(auth_client_factory, user_factory):
    staff = user_factory(staff=True)
    employee = user_factory(first_name="Ivan", last_name="Petrov")
    client = auth_client_factory(staff)

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value=_logstorm_result(),
    ):
        response = client.post(_analyze_url(), _payload(employee.id), format="json")

    assert response.status_code == 200
    assert AttendanceAnalysisRun.objects.count() == 1
    assert AttendanceRecord.objects.count() == 2

    run = AttendanceAnalysisRun.objects.get()
    assert run.employee == employee
    assert run.triggered_by == staff
    assert run.period_start.isoformat() == "2026-04-20"
    assert run.period_end.isoformat() == "2026-04-21"
    assert run.request_payload["employee_id"] == str(employee.id)

    record = AttendanceRecord.objects.get(employee=employee, date="2026-04-20")
    assert record.analysis_run == run
    assert record.arrival_time == "09:15"
    assert record.is_late is True
    assert record.effective_is_workday is True
    assert record.personnel_status == "normal"
    assert record.statuses == ["late", "underwork"]
    assert record.raw_data["employee_id"] == "42"


def test_analyze_updates_existing_daily_record(auth_client_factory, user_factory):
    staff = user_factory(staff=True)
    employee = user_factory()
    _move_auto_hired_before_test_period(employee)
    client = auth_client_factory(staff)

    first_result = _logstorm_result()
    second_result = {
        "records": [
            {
                **first_result["records"][0],
                "arrival_time": "08:55",
                "is_late": False,
                "late_minutes": None,
                "statuses": [],
                "employee_issues": [],
            }
        ]
    }

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value=first_result,
    ):
        client.post(_analyze_url(), _payload(employee.id), format="json")

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value=second_result,
    ):
        response = client.post(_analyze_url(), _payload(employee.id), format="json")

    assert response.status_code == 200
    assert AttendanceAnalysisRun.objects.count() == 2
    assert (
        AttendanceRecord.objects.filter(employee=employee, date="2026-04-20").count()
        == 1
    )

    record = AttendanceRecord.objects.get(employee=employee, date="2026-04-20")
    assert record.arrival_time == "08:55"
    assert record.is_late is False
    assert record.statuses == []


def test_records_endpoint_returns_saved_records(auth_client_factory, user_factory):
    staff = user_factory(staff=True)
    employee = user_factory()
    other = user_factory()
    client = auth_client_factory(staff)

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value=_logstorm_result(),
    ):
        client.post(_analyze_url(), _payload(employee.id), format="json")
        client.post(_analyze_url(), _payload(other.id), format="json")

    response = client.get(
        _records_url(),
        {
            "employee_id": employee.id,
            "date_from": "2026-04-20",
            "date_to": "2026-04-21",
        },
    )

    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 2
    assert {item["employee"] for item in results} == {employee.id}
    assert {item["date"] for item in results} == {"2026-04-20", "2026-04-21"}


def test_monthly_matrix_endpoint_returns_excel_like_month(
    auth_client_factory,
    user_factory,
):
    staff = user_factory(staff=True)
    employee = user_factory(first_name="Ivan", last_name="Petrov")
    other = user_factory(first_name="Anna", last_name="Sidorova")
    client = auth_client_factory(staff)

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value=_logstorm_result(),
    ):
        client.post(_analyze_url(), _payload(employee.id), format="json")
        client.post(_analyze_url(), _payload(other.id), format="json")

    response = client.get(
        _monthly_matrix_url(),
        {
            "employee_ids": f"{employee.id},{other.id}",
            "month": "2026-04",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["month"] == "2026-04"
    assert payload["month_label"] == "Апрель 2026"
    assert [item["id"] for item in payload["employees"]] == [employee.id, other.id]
    assert len(payload["rows"]) == 30

    target_row = next(row for row in payload["rows"] if row["date"] == "2026-04-20")
    employee_cell = target_row["cells"][str(employee.id)]
    assert employee_cell["arrival_time"] == "09:15"
    assert employee_cell["departure_time"] == "18:00"
    assert employee_cell["status"] == "underwork"

    summary_by_key = {item["key"]: item for item in payload["summary"]}
    assert summary_by_key["late_days"]["values"][str(employee.id)] == 1
    assert summary_by_key["absent_days"]["values"][str(employee.id)] == 1
    assert summary_by_key["worked_hours"]["values"][str(employee.id)] == 8.75


def test_user_can_read_own_attendance_records(auth_client_factory, user_factory):
    user = user_factory(staff=False)
    other = user_factory()
    staff = user_factory(staff=True)
    staff_client = auth_client_factory(staff)
    client = auth_client_factory(user)

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value=_logstorm_result(),
    ):
        staff_client.post(_analyze_url(), _payload(user.id), format="json")
        staff_client.post(_analyze_url(), _payload(other.id), format="json")

    response = client.get(_records_url())

    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 2
    assert {item["employee"] for item in results} == {user.id}


def test_user_cannot_read_other_employee_attendance_records(
    auth_client_factory,
    user_factory,
):
    user = user_factory(staff=False)
    other = user_factory()
    client = auth_client_factory(user)

    response = client.get(_records_url(), {"employee_id": other.id})
    assert response.status_code == 403


def test_staff_can_update_attendance_record(auth_client_factory, user_factory):
    staff = user_factory(staff=True)
    employee = user_factory()
    client = auth_client_factory(staff)

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value=_logstorm_result(),
    ):
        client.post(_analyze_url(), _payload(employee.id), format="json")

    record = AttendanceRecord.objects.get(employee=employee, date="2026-04-20")
    patch_payload = {
        "arrival_time": "09:00",
        "departure_time": "18:05",
        "work_hours": 9.08,
        "is_late": False,
        "late_minutes": None,
        "is_underwork": False,
        "underwork_hours": None,
    }
    with patch(
        "api.v1.attendance.views.LogStormClient.update_attendance_override",
        return_value={"id": 1, "patch": patch_payload},
    ) as logstorm_update:
        response = client.patch(
            _record_detail_url(record.id),
            patch_payload,
            format="json",
        )

    assert response.status_code == 200
    logstorm_update.assert_called_once()
    record.refresh_from_db()
    assert record.arrival_time == "09:00"
    assert record.work_hours == 9.08
    assert record.is_late is False
    assert record.is_manually_edited is True
    assert record.manual_edit_payload["arrival_time"] == "09:00"
    assert "late" not in record.statuses
    assert response.json()["arrival_time"] == "09:00"

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value=_logstorm_result(),
    ):
        client.post(_analyze_url(), _payload(employee.id), format="json")

    record.refresh_from_db()
    assert record.arrival_time == "09:00"
    assert record.is_manually_edited is True
    assert record.manual_edit_payload["arrival_time"] == "09:00"


def test_user_cannot_update_attendance_record(auth_client_factory, user_factory):
    user = user_factory(staff=False)
    staff = user_factory(staff=True)
    staff_client = auth_client_factory(staff)
    client = auth_client_factory(user)

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value=_logstorm_result(),
    ):
        staff_client.post(_analyze_url(), _payload(user.id), format="json")

    record = AttendanceRecord.objects.get(employee=user, date="2026-04-20")
    response = client.patch(
        _record_detail_url(record.id),
        {"arrival_time": "09:00"},
        format="json",
    )

    assert response.status_code == 403


def test_user_can_analyze_own_attendance(auth_client_factory, user_factory):
    user = user_factory(staff=False)
    client = auth_client_factory(user)

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value=_logstorm_result(),
    ):
        response = client.post(_analyze_url(), _payload(user.id), format="json")

    assert response.status_code == 200
    assert AttendanceRecord.objects.filter(employee=user).count() == 2


def test_user_cannot_analyze_other_employee_attendance(
    auth_client_factory,
    user_factory,
):
    user = user_factory(staff=False)
    other = user_factory()
    client = auth_client_factory(user)

    response = client.post(_analyze_url(), _payload(other.id), format="json")

    assert response.status_code == 403


def test_personnel_non_working_state_is_saved_and_suppresses_absence(
    auth_client_factory,
    user_factory,
):
    staff = user_factory(staff=True)
    employee = user_factory()
    _move_auto_hired_before_test_period(employee)
    client = auth_client_factory(staff)
    leave_action = EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_ON_LEAVE,
        date=_aware_datetime(2026, 4, 20),
    )

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value=_logstorm_result(),
    ):
        response = client.post(_analyze_url(), _payload(employee.id), format="json")

    assert response.status_code == 200
    absent_record = AttendanceRecord.objects.get(employee=employee, date="2026-04-21")
    assert absent_record.personnel_status == ACTION_ON_LEAVE
    assert absent_record.personnel_action == leave_action
    assert absent_record.effective_is_workday is False
    assert absent_record.is_absent is False
    assert absent_record.employee_issues == []
    assert absent_record.statuses == []


def test_calendar_non_working_day_suppresses_absence_without_personnel_state(
    auth_client_factory,
    user_factory,
):
    staff = user_factory(staff=True)
    employee = user_factory()
    client = auth_client_factory(staff)
    weekend_absence_result = {
        "records": [
            {
                "date": "2026-04-19",
                "employee_id": str(employee.id),
                "display_name": "Weekend User",
                "arrival_time": None,
                "departure_time": None,
                "work_hours": 0,
                "expected_hours": 9,
                "is_workday": False,
                "is_absent": True,
                "statuses": ["День критического отсутствия (100% отсутствуют)"],
                "employee_issues": ["absence"],
                "technical_issues": [
                    "День критического отсутствия (100% отсутствуют)"
                ],
            }
        ]
    }

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value=weekend_absence_result,
    ):
        response = client.post(
            _analyze_url(),
            _payload(employee.id, period_start="2026-04-19", period_end="2026-04-19"),
            format="json",
        )

    assert response.status_code == 200
    record = AttendanceRecord.objects.get(employee=employee, date="2026-04-19")
    assert record.is_workday is False
    assert record.effective_is_workday is False
    assert record.is_absent is False
    assert record.statuses == []
    assert record.employee_issues == []
    assert record.technical_issues == []

    records_response = client.get(
        _records_url(),
        {
            "employee_id": employee.id,
            "date_from": "2026-04-19",
            "date_to": "2026-04-19",
        },
    )
    assert records_response.status_code == 200
    assert records_response.json()["results"][0]["non_working_reason"] == (
        "Выходной по графику/календарю"
    )

    matrix_response = client.get(
        _monthly_matrix_url(),
        {
            "employee_ids": str(employee.id),
            "month": "2026-04",
        },
    )
    matrix_row = next(
        row for row in matrix_response.json()["rows"] if row["date"] == "2026-04-19"
    )
    matrix_cell = matrix_row["cells"][str(employee.id)]
    assert matrix_cell["status"] == "non_working"
    assert matrix_cell["issues"] == []


def test_personnel_non_working_state_counts_work_as_overtime(
    auth_client_factory,
    user_factory,
):
    staff = user_factory(staff=True)
    employee = user_factory()
    _move_auto_hired_before_test_period(employee)
    client = auth_client_factory(staff)
    EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_ON_LEAVE,
        date=_aware_datetime(2026, 4, 20),
    )

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value=_logstorm_result(),
    ):
        response = client.post(_analyze_url(), _payload(employee.id), format="json")

    assert response.status_code == 200
    worked_record = AttendanceRecord.objects.get(employee=employee, date="2026-04-20")
    assert worked_record.personnel_status == ACTION_ON_LEAVE
    assert worked_record.effective_is_workday is False
    assert worked_record.is_late is False
    assert worked_record.is_underwork is False
    assert worked_record.is_overtime is True
    assert worked_record.overtime_hours == worked_record.work_hours
    assert worked_record.employee_issues == []
    assert worked_record.statuses == ["work_outside_personnel_schedule"]


def test_personnel_state_is_recalculated_when_actions_change(
    auth_client_factory,
    user_factory,
):
    staff = user_factory(staff=True)
    employee = user_factory()
    _move_auto_hired_before_test_period(employee)
    client = auth_client_factory(staff)
    EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_ON_LEAVE,
        date=_aware_datetime(2026, 4, 20),
    )

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value=_logstorm_result(),
    ):
        client.post(_analyze_url(), _payload(employee.id), format="json")

    first_record = AttendanceRecord.objects.get(employee=employee, date="2026-04-21")
    assert first_record.personnel_status == ACTION_ON_LEAVE
    assert first_record.is_absent is False

    EmployeeAction.objects.create(
        employee=employee,
        action=ACTION_RETURNED_FROM_LEAVE,
        date=_aware_datetime(2026, 4, 21),
    )

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value=_logstorm_result(),
    ):
        response = client.post(_analyze_url(), _payload(employee.id), format="json")

    assert response.status_code == 200
    updated_record = AttendanceRecord.objects.get(employee=employee, date="2026-04-21")
    assert updated_record.personnel_status == "normal"
    assert updated_record.effective_is_workday is True
    assert updated_record.is_absent is True
    assert updated_record.employee_issues == ["absence"]


def test_attendance_record_comments_use_communications(
    auth_client_factory, user_factory
):
    staff = user_factory(staff=True, first_name="Admin", last_name="User")
    employee = user_factory()
    client = auth_client_factory(staff)

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value=_logstorm_result(),
    ):
        client.post(_analyze_url(), _payload(employee.id), format="json")

    record = AttendanceRecord.objects.get(employee=employee, date="2026-04-20")

    create_response = client.post(
        _record_comments_url(record.id),
        {"text": "Проверить причину опоздания"},
        format="json",
    )
    assert create_response.status_code == 201
    comment = create_response.json()
    assert comment["record"] == record.id
    assert comment["text"] == "Проверить причину опоздания"
    assert comment["author"]["id"] == staff.id

    list_response = client.get(_record_comments_url(record.id))
    assert list_response.status_code == 200
    assert [item["text"] for item in list_response.json()] == [
        "Проверить причину опоздания"
    ]

    records_response = client.get(_records_url(), {"employee_id": employee.id})
    assert records_response.status_code == 200
    target = next(
        item for item in records_response.json()["results"] if item["id"] == record.id
    )
    assert target["comments_count"] == 1


def test_attendance_record_comment_delete_is_author_only(
    auth_client_factory,
    user_factory,
):
    author = user_factory(staff=True)
    other_staff = user_factory(staff=True)
    employee = user_factory()
    author_client = auth_client_factory(author)
    other_client = auth_client_factory(other_staff)

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value=_logstorm_result(),
    ):
        author_client.post(_analyze_url(), _payload(employee.id), format="json")

    record = AttendanceRecord.objects.get(employee=employee, date="2026-04-20")
    comment_id = author_client.post(
        _record_comments_url(record.id),
        {"text": "Комментарий автора"},
        format="json",
    ).json()["id"]

    forbidden_response = other_client.delete(
        _record_comment_detail_url(record.id, comment_id)
    )
    assert forbidden_response.status_code == 403

    delete_response = author_client.delete(
        _record_comment_detail_url(record.id, comment_id)
    )
    assert delete_response.status_code == 204
    assert author_client.get(_record_comments_url(record.id)).json() == []


def test_user_can_comment_own_attendance_record(auth_client_factory, user_factory):
    user = user_factory(staff=False)
    staff = user_factory(staff=True)
    staff_client = auth_client_factory(staff)
    client = auth_client_factory(user)

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value=_logstorm_result(),
    ):
        staff_client.post(_analyze_url(), _payload(user.id), format="json")

    record = AttendanceRecord.objects.get(employee=user, date="2026-04-20")

    create_response = client.post(
        _record_comments_url(record.id),
        {"text": "Мой комментарий"},
        format="json",
    )

    assert create_response.status_code == 201
    assert create_response.json()["author"]["id"] == user.id
    assert client.get(_record_comments_url(record.id)).json()[0]["text"] == (
        "Мой комментарий"
    )


def test_user_cannot_comment_other_employee_attendance_record(
    auth_client_factory,
    user_factory,
):
    user = user_factory(staff=False)
    other = user_factory()
    staff = user_factory(staff=True)
    staff_client = auth_client_factory(staff)
    client = auth_client_factory(user)

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value=_logstorm_result(),
    ):
        staff_client.post(_analyze_url(), _payload(other.id), format="json")

    record = AttendanceRecord.objects.get(employee=other, date="2026-04-20")

    response = client.post(
        _record_comments_url(record.id),
        {"text": "Чужая запись"},
        format="json",
    )

    assert response.status_code == 404
