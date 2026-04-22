from datetime import date

import pytest

from common.logstorm_attendance import (
    analyze_employee_attendance,
    build_logstorm_attendance_payload,
    normalize_logstorm_schedule,
)

pytestmark = pytest.mark.django_db


class FakeLogStormClient:
    def __init__(self):
        self.payloads = []

    def analyze_attendance(self, payload):
        self.payloads.append(payload)
        return {"records": []}


def test_payload_omits_schedule_when_eusrr_has_no_schedule(user_factory):
    employee = user_factory(first_name="Ivan", last_name="Petrov")

    payload = build_logstorm_attendance_payload(
        employee=employee,
        period_start=date(2026, 4, 20),
        period_end=date(2026, 4, 21),
    )

    assert payload["employee_id"] == str(employee.id)
    assert payload["display_name"] == "Ivan Petrov"
    assert payload["period_start"] == "2026-04-20"
    assert payload["period_end"] == "2026-04-21"
    assert "schedule" not in payload


def test_payload_includes_schedule_and_date_overrides(user_factory):
    employee = user_factory(first_name="Ivan", last_name="Petrov")

    payload = build_logstorm_attendance_payload(
        employee=employee,
        period_start=date(2026, 4, 20),
        period_end=date(2026, 4, 26),
        schedule={
            "start_time": "09:00",
            "end_time": "18:00",
            "expected_hours": 9,
            "workdays": ["Monday"],
        },
        date_overrides=[
            {
                "date": date(2026, 4, 25),
                "is_workday": True,
                "reason": "transferred_workday",
                "start_time": "10:00",
                "end_time": "16:00",
                "expected_hours": 6,
            }
        ],
    )

    assert payload["schedule"] == {
        "start_time": "09:00",
        "end_time": "18:00",
        "expected_hours": 9,
        "workdays": ["Monday"],
        "date_overrides": [
            {
                "date": "2026-04-25",
                "is_workday": True,
                "reason": "transferred_workday",
                "start_time": "10:00",
                "end_time": "16:00",
                "expected_hours": 6,
            }
        ],
    }


def test_schedule_defaults_to_regular_workweek():
    schedule = normalize_logstorm_schedule({
        "start_time": "09:00",
        "end_time": "18:00",
        "expected_hours": 9,
    })

    assert schedule["workdays"] == [
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
    ]
    assert schedule["date_overrides"] == []


def test_analyze_employee_attendance_calls_logstorm_client(user_factory):
    employee = user_factory(first_name="Ivan", last_name="Petrov")
    client = FakeLogStormClient()

    result = analyze_employee_attendance(
        employee=employee,
        period_start=date(2026, 4, 20),
        period_end=date(2026, 4, 20),
        client=client,
    )

    assert result == {"records": []}
    assert client.payloads[0]["employee_id"] == str(employee.id)
    assert "schedule" not in client.payloads[0]
