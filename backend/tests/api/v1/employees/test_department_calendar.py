import itertools
from datetime import timedelta

import pytest
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient
from schedule.models import CalendarRelation, Event

from employees.models import (
    Department,
    DepartmentRole,
    EmployeeDepartment,
    RoleAssignment,
)
from scheduling.models import CalendarBinding


pytestmark = pytest.mark.django_db

_phone_seq = itertools.count(5000)


def _unique_phone() -> str:
    return f"+7999666{next(_phone_seq):04d}"


@pytest.fixture
def api_client():
    return APIClient()


def make_user(email: str, *, first_name: str = "FN", last_name: str = "LN"):
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create(
        email=email,
        phone_number=_unique_phone(),
        first_name=first_name,
        last_name=last_name,
        is_active=True,
        email_verified=True,
    )
    user.set_password("pass")
    user.save()
    return user


def department_calendar_url(department_id: int) -> str:
    base = reverse("api:v1:departments-detail", args=[department_id])
    return f"{base}calendar/"


def test_department_calendar_endpoint_creates_binding_and_syncs_participants(
    api_client: APIClient,
):
    head = make_user("head@example.com", first_name="Head")
    member = make_user("member@example.com", first_name="Member")
    role_only = make_user("role@example.com", first_name="Role")
    outsider = make_user("outsider@example.com", first_name="Out")

    department = Department.objects.create(name="Finance", head=head)
    EmployeeDepartment.objects.create(
        employee=member,
        department=department,
        is_active=True,
    )
    role = DepartmentRole.objects.create(
        department=department,
        name="Analyst",
    )
    RoleAssignment.objects.create(
        employee=role_only,
        role=role,
        is_active=True,
    )

    api_client.force_authenticate(user=outsider)
    response = api_client.get(department_calendar_url(department.id))

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["calendar_type"] == "department"
    assert payload["context_type"] == "department"
    assert payload["context_object_id"] == department.id

    binding = CalendarBinding.objects.select_related("calendar").get(
        calendar_id=payload["calendar_id"]
    )
    assert binding.type == CalendarBinding.BindingType.DEPARTMENT
    assert binding.context_object == department

    user_ct = ContentType.objects.get_for_model(type(head))
    relations = {
        relation.object_id: relation.distinction
        for relation in CalendarRelation.objects.filter(
            calendar=binding.calendar,
            content_type=user_ct,
        )
    }
    assert relations[head.id] == "owner"
    assert relations[member.id] == "editor"
    assert relations[role_only.id] == "editor"
    assert outsider.id not in relations


def test_department_calendar_visibility_is_limited_to_synced_participants(
    api_client: APIClient,
):
    head = make_user("head@example.com")
    member = make_user("member@example.com")
    outsider = make_user("outsider@example.com")
    department = Department.objects.create(name="Accounting", head=head)
    EmployeeDepartment.objects.create(
        employee=member,
        department=department,
        is_active=True,
    )

    api_client.force_authenticate(user=head)
    payload = api_client.get(department_calendar_url(department.id)).json()
    calendar_id = payload["calendar_id"]

    response = api_client.get("/api/v1/schedule/calendars/")
    calendar_ids = [item["id"] for item in response.data]
    assert calendar_id in calendar_ids

    api_client.force_authenticate(user=member)
    response = api_client.get("/api/v1/schedule/calendars/")
    calendar_ids = [item["id"] for item in response.data]
    assert calendar_id in calendar_ids

    api_client.force_authenticate(user=outsider)
    response = api_client.get("/api/v1/schedule/calendars/")
    calendar_ids = [item["id"] for item in response.data]
    assert calendar_id not in calendar_ids

    response = api_client.get(department_calendar_url(department.id))
    assert response.status_code == status.HTTP_200_OK
    assert response.data["calendar_id"] == calendar_id


def test_department_calendar_event_permissions_for_non_member_and_member(
    api_client: APIClient,
):
    head = make_user("head@example.com")
    member = make_user("member@example.com")
    outsider = make_user("outsider@example.com")
    department = Department.objects.create(name="Ops", head=head)
    EmployeeDepartment.objects.create(
        employee=member,
        department=department,
        is_active=True,
    )

    api_client.force_authenticate(user=member)
    calendar_id = api_client.get(department_calendar_url(department.id)).data[
        "calendar_id"
    ]

    api_client.force_authenticate(user=outsider)
    create_response = api_client.post(
        "/api/v1/schedule/events/",
        {
            "calendar": calendar_id,
            "title": "Outsider event",
            "start": "2026-04-20T09:00:00+03:00",
            "end": "2026-04-20T10:00:00+03:00",
        },
        format="json",
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    event_id = create_response.data["id"]

    patch_response = api_client.patch(
        f"/api/v1/schedule/events/{event_id}/",
        {"title": "Outsider event updated"},
        format="json",
    )
    assert patch_response.status_code == status.HTTP_200_OK

    api_client.force_authenticate(user=member)
    patch_response = api_client.patch(
        f"/api/v1/schedule/events/{event_id}/",
        {"title": "Member edited outsider event"},
        format="json",
    )
    assert patch_response.status_code == status.HTTP_200_OK

    api_client.force_authenticate(user=outsider)
    start = timezone.now()
    member_event = Event.objects.create(
        calendar_id=calendar_id,
        title="Member event",
        start=start,
        end=start + timedelta(hours=1),
        creator=member,
    )
    forbidden_response = api_client.patch(
        f"/api/v1/schedule/events/{member_event.id}/",
        {"title": "Outsider cannot edit this"},
        format="json",
    )
    assert forbidden_response.status_code == status.HTTP_403_FORBIDDEN

    forbidden_delete = api_client.delete(
        f"/api/v1/schedule/events/{member_event.id}/"
    )
    assert forbidden_delete.status_code == status.HTTP_403_FORBIDDEN


def test_department_calendar_membership_sync_removes_inactive_member(
    api_client: APIClient,
):
    head = make_user("head@example.com")
    member = make_user("member@example.com")
    department = Department.objects.create(name="Legal", head=head)
    link = EmployeeDepartment.objects.create(
        employee=member,
        department=department,
        is_active=True,
    )

    api_client.force_authenticate(user=head)
    calendar_id = api_client.get(department_calendar_url(department.id)).data[
        "calendar_id"
    ]

    user_ct = ContentType.objects.get_for_model(type(head))
    assert CalendarRelation.objects.filter(
        calendar_id=calendar_id,
        content_type=user_ct,
        object_id=member.id,
    ).exists()

    link.is_active = False
    link.save(update_fields=["is_active"])

    assert not CalendarRelation.objects.filter(
        calendar_id=calendar_id,
        content_type=user_ct,
        object_id=member.id,
    ).exists()


def test_department_calendar_rejects_manual_participant_changes(
    api_client: APIClient,
):
    head = make_user("head@example.com")
    member = make_user("member@example.com")
    outsider = make_user("outsider@example.com")
    department = Department.objects.create(name="Audit", head=head)
    EmployeeDepartment.objects.create(
        employee=member,
        department=department,
        is_active=True,
    )

    api_client.force_authenticate(user=head)
    calendar_id = api_client.get(department_calendar_url(department.id)).data[
        "calendar_id"
    ]

    add_response = api_client.post(
        f"/api/v1/schedule/calendars/{calendar_id}/add-participant/",
        {"user_id": outsider.id, "role": "viewer"},
        format="json",
    )
    assert add_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "синхронизируются" in add_response.data["detail"]

    remove_response = api_client.delete(
        f"/api/v1/schedule/calendars/{calendar_id}/remove-participant/{member.id}/"
    )
    assert remove_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "синхронизируются" in remove_response.data["detail"]


def test_department_calendar_participants_include_avatar_and_email(
    api_client: APIClient,
):
    head = make_user("head@example.com", first_name="Head", last_name="User")
    head.avatar = "avatars/head-calendar.jpg"
    head.save(update_fields=["avatar"])

    department = Department.objects.create(name="HR", head=head)

    api_client.force_authenticate(user=head)
    calendar_id = api_client.get(department_calendar_url(department.id)).data[
        "calendar_id"
    ]

    response = api_client.get(
        f"/api/v1/schedule/calendars/{calendar_id}/participants/"
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    participant = response.data[0]
    assert participant["user"]["id"] == head.id
    assert participant["user"]["email"] == head.email
    assert participant["user"]["avatar"] == head.avatar.url
    assert participant["user"]["first_name"] == "Head"
    assert participant["user"]["last_name"] == "User"


def test_department_calendar_occurrences_allow_outsider_but_keep_permissions(
    api_client: APIClient,
):
    head = make_user("head@example.com")
    member = make_user("member@example.com")
    outsider = make_user("outsider@example.com")
    department = Department.objects.create(name="Treasury", head=head)
    EmployeeDepartment.objects.create(
        employee=member,
        department=department,
        is_active=True,
    )

    api_client.force_authenticate(user=member)
    calendar_id = api_client.get(department_calendar_url(department.id)).data[
        "calendar_id"
    ]

    start = timezone.now().replace(microsecond=0)
    member_event = Event.objects.create(
        calendar_id=calendar_id,
        title="Member-only event",
        start=start,
        end=start + timedelta(hours=1),
        creator=member,
    )

    api_client.force_authenticate(user=outsider)
    response = api_client.get(
        "/api/v1/schedule/events/occurrences/",
        {
            "calendar": calendar_id,
            "start": (start - timedelta(minutes=5)).isoformat(),
            "end": (start + timedelta(hours=2)).isoformat(),
        },
    )

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data) == 1
    occurrence = response.data[0]
    assert occurrence["event_id"] == member_event.id
    assert occurrence["can_edit"] is False
    assert occurrence["can_delete"] is False
