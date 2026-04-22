from unittest.mock import patch

import pytest
from django.urls import reverse

from common.logstorm_client import LogStormClientError

pytestmark = pytest.mark.django_db


def _url():
    return reverse("api:v1:logstorm-attendance-analyze")


def _payload(employee_id, **overrides):
    payload = {
        "employee_id": employee_id,
        "period_start": "2026-04-20",
        "period_end": "2026-04-20",
    }
    payload.update(overrides)
    return payload


def test_logstorm_attendance_api_allows_user_self_analysis(
    auth_client_factory,
    user_factory,
):
    user = user_factory(staff=False)
    client = auth_client_factory(user)

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value={"records": []},
    ):
        response = client.post(_url(), _payload(user.id), format="json")

    assert response.status_code == 200


def test_logstorm_attendance_api_rejects_other_employee_for_user(
    auth_client_factory,
    user_factory,
):
    user = user_factory(staff=False)
    other = user_factory()
    client = auth_client_factory(user)

    response = client.post(_url(), _payload(other.id), format="json")

    assert response.status_code == 403


def test_logstorm_attendance_api_uses_default_schedule_when_schedule_omitted(
    auth_client_factory,
    user_factory,
):
    staff = user_factory(staff=True)
    employee = user_factory(first_name="Ivan", last_name="Petrov")
    client = auth_client_factory(staff)

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value={"records": []},
    ) as analyze:
        response = client.post(_url(), _payload(employee.id), format="json")

    assert response.status_code == 200
    assert response.json() == {"records": []}
    kwargs = analyze.call_args.kwargs
    assert kwargs["employee"] == employee
    assert kwargs["schedule"] == {
        "start_time": "08:00",
        "end_time": "17:00",
        "expected_hours": 9,
        "workdays": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"],
        "date_overrides": [],
    }


def test_logstorm_attendance_api_passes_schedule(
    auth_client_factory,
    user_factory,
):
    staff = user_factory(staff=True)
    employee = user_factory()
    client = auth_client_factory(staff)
    schedule = {
        "start_time": "09:00",
        "end_time": "18:00",
        "expected_hours": 9,
        "workdays": ["Monday"],
        "date_overrides": [
            {"date": "2026-04-20", "is_workday": False, "reason": "holiday"}
        ],
    }

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        return_value={"records": []},
    ) as analyze:
        response = client.post(
            _url(),
            _payload(employee.id, schedule=schedule),
            format="json",
        )

    assert response.status_code == 200
    assert analyze.call_args.kwargs["schedule"]["start_time"] == "09:00"
    assert (
        analyze.call_args.kwargs["schedule"]["date_overrides"][0]["is_workday"] is False
    )


def test_logstorm_attendance_api_rejects_invalid_period(
    auth_client_factory,
    user_factory,
):
    staff = user_factory(staff=True)
    client = auth_client_factory(staff)

    response = client.post(
        _url(),
        {
            "employee_id": staff.id,
            "period_start": "2026-04-21",
            "period_end": "2026-04-20",
        },
        format="json",
    )

    assert response.status_code == 400


def test_logstorm_attendance_api_returns_404_for_unknown_employee(
    auth_client_factory,
    user_factory,
):
    staff = user_factory(staff=True)
    client = auth_client_factory(staff)

    response = client.post(_url(), _payload(999999), format="json")

    assert response.status_code == 404


def test_logstorm_attendance_api_maps_logstorm_errors_to_502(
    auth_client_factory,
    user_factory,
):
    staff = user_factory(staff=True)
    employee = user_factory()
    client = auth_client_factory(staff)

    with patch(
        "api.v1.attendance.views.analyze_employee_attendance",
        side_effect=LogStormClientError("timeout"),
    ):
        response = client.post(_url(), _payload(employee.id), format="json")

    assert response.status_code == 502
    assert response.json()["error"] == "logstorm_unavailable"
