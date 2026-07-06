# tests/api/v1/employees/test_employees.py
import itertools
import datetime as dt

import pytest
from attendance.models import AttendanceAnalysisRun, AttendanceRecord
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from employees.models import (
    Department,
    Employee,
    EmployeeAction,
    EmployeeDepartment,
    Position,
    Skill,
)
from employees.constants import ACTION_DISMISSED  # для фильтра actually_active
from tasks.models import (
    Task,
    TaskBoard,
    TaskColumn,
    TaskLinkedObject,
    TaskLinkedObjectKind,
)
from tests.conftest import _unique_phone

pytestmark = pytest.mark.django_db

User = get_user_model()

# ---------- fixtures / helpers ----------

@pytest.fixture
def api_client():
    return APIClient()

_phone_seq = itertools.count(2000)

def _unique_phone() -> str:
    # валидный уникальный E.164
    return f"+7999000{next(_phone_seq):03d}"

def make_user(
    email: str,
    *,
    staff: bool = False,
    superuser: bool = False,
    verified: bool = True,
    active: bool = True,
    **extra,
) -> User:
    u = User.objects.create(
        email=email,
        phone_number=extra.pop("phone_number", _unique_phone()),
        first_name=extra.pop("first_name", "FN"),
        last_name=extra.pop("last_name", "LN"),
        is_staff=staff,
        is_superuser=superuser,
        is_active=active,
        email_verified=verified,
        **extra,
    )
    u.set_password("pass")
    u.save()
    return u

def extract_results(data):
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data

# ---------- basic auth / list / retrieve ----------

def test_list_requires_auth(api_client: APIClient):
    url = reverse("api:v1:employees-list")
    resp = api_client.get(url)
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

def test_list_ok_for_authenticated(api_client: APIClient):
    user = make_user("u@example.com")
    e1 = make_user("a@example.com")
    e2 = make_user("b@example.com")

    api_client.force_authenticate(user=user)
    url = reverse("api:v1:employees-list")
    resp = api_client.get(url)
    assert resp.status_code == status.HTTP_200_OK

    items = extract_results(resp.json())
    ids = {it["id"] for it in items}
    assert e1.id in ids and e2.id in ids


def test_list_includes_visible_linked_tasks_only(api_client: APIClient):
    user = make_user("employee-link-user@example.com")
    target = make_user("employee-link-target@example.com")
    hidden_member = make_user("employee-link-hidden@example.com")
    visible_board = TaskBoard.objects.create(
        name="Видимая доска сотрудника",
        created_by=user,
    )
    visible_column = TaskColumn.objects.create(
        board=visible_board,
        name="Новые",
        position=1000,
        color="#38bdf8",
    )
    visible_task = Task.objects.create(
        board=visible_board,
        column=visible_column,
        title="Видимая задача сотрудника",
        created_by=user,
        priority="high",
    )
    hidden_board = TaskBoard.objects.create(
        name="Скрытая доска сотрудника",
        created_by=hidden_member,
    )
    hidden_board.members.add(hidden_member)
    hidden_column = TaskColumn.objects.create(
        board=hidden_board,
        name="Новые",
        position=1000,
        color="#ef4444",
    )
    hidden_task = Task.objects.create(
        board=hidden_board,
        column=hidden_column,
        title="Скрытая задача сотрудника",
        created_by=hidden_member,
        priority="critical",
    )
    employee_ct = ContentType.objects.get_for_model(User)
    visible_link = TaskLinkedObject.objects.create(
        task=visible_task,
        kind=TaskLinkedObjectKind.EMPLOYEE,
        content_type=employee_ct,
        object_id=target.id,
        created_by=user,
    )
    TaskLinkedObject.objects.create(
        task=hidden_task,
        kind=TaskLinkedObjectKind.EMPLOYEE,
        content_type=employee_ct,
        object_id=target.id,
        created_by=hidden_member,
    )

    api_client.force_authenticate(user=user)
    response = api_client.get(reverse("api:v1:employees-list"))

    assert response.status_code == status.HTTP_200_OK
    items = extract_results(response.json())
    target_payload = next(item for item in items if item["id"] == target.id)
    assert target_payload["linked_tasks"] == [
        {
            "link_id": visible_link.id,
            "id": visible_task.id,
            "title": "Видимая задача сотрудника",
            "board_id": visible_board.id,
            "board_name": "Видимая доска сотрудника",
            "column_id": visible_column.id,
            "column_name": "Новые",
            "column_color": "#38bdf8",
            "priority": "high",
            "priority_display": "Высокий",
        }
    ]


def test_retrieve_requires_auth(api_client: APIClient):
    e = make_user("x@example.com")
    url = reverse("api:v1:employees-detail", args=[e.pk])
    assert api_client.get(url).status_code == status.HTTP_401_UNAUTHORIZED

def test_retrieve_ok(api_client: APIClient):
    user = make_user("u@example.com")
    e = make_user("x@example.com")
    api_client.force_authenticate(user=user)

    url = reverse("api:v1:employees-detail", args=[e.pk])
    resp = api_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data["id"] == e.id
    assert data["email"] == e.email


def test_retrieve_exposes_last_attendance_status_to_authenticated_users(
    api_client: APIClient,
):
    viewer = make_user("attendance-viewer@example.com")
    target = make_user("attendance-target@example.com")
    run = AttendanceAnalysisRun.objects.create(
        employee=target,
        period_start=dt.date(2026, 4, 1),
        period_end=dt.date(2026, 4, 30),
    )
    AttendanceRecord.objects.create(
        analysis_run=run,
        employee=target,
        date=dt.date(2026, 4, 10),
        arrival_time="08:35",
    )
    latest = AttendanceRecord.objects.create(
        analysis_run=run,
        employee=target,
        date=dt.date(2026, 4, 11),
        arrival_time="08:20",
        departure_time="17:45",
    )

    api_client.force_authenticate(user=viewer)
    response = api_client.get(reverse("api:v1:employees-detail", args=[target.pk]))

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["attendance_status"]
    assert payload == {
        "record_id": latest.id,
        "date": "2026-04-11",
        "time": "17:45",
        "event": "departure",
        "label": "Уход",
        "display": "Уход · 11.04.2026, 17:45",
    }


def test_retrieve_last_attendance_status_uses_arrival_when_no_departure(
    api_client: APIClient,
):
    viewer = make_user("attendance-arrival-viewer@example.com")
    target = make_user("attendance-arrival-target@example.com")
    run = AttendanceAnalysisRun.objects.create(
        employee=target,
        period_start=dt.date(2026, 4, 1),
        period_end=dt.date(2026, 4, 30),
    )
    record = AttendanceRecord.objects.create(
        analysis_run=run,
        employee=target,
        date=dt.date(2026, 4, 12),
        arrival_time="09:05",
        departure_time=None,
    )

    api_client.force_authenticate(user=viewer)
    response = api_client.get(reverse("api:v1:employees-detail", args=[target.pk]))

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()["attendance_status"]
    assert payload["record_id"] == record.id
    assert payload["date"] == "2026-04-12"
    assert payload["time"] == "09:05"
    assert payload["event"] == "arrival"
    assert payload["label"] == "Приход"


def test_update_attendance_aliases_normalizes_values(api_client: APIClient):
    staff = make_user("staff@example.com", staff=True)
    employee = make_user("alias@example.com")
    api_client.force_authenticate(user=staff)

    url = reverse("api:v1:employees-detail", args=[employee.pk])
    resp = api_client.patch(
        url,
        {"attendance_aliases": [" 200 ", "200", "", "300"]},
        format="json",
    )

    assert resp.status_code == status.HTTP_200_OK
    assert resp.json()["attendance_aliases"] == ["200", "300"]
    employee.refresh_from_db()
    assert employee.attendance_aliases == ["200", "300"]

# ---------- search & ordering ----------

def test_search_by_email_and_last_name(api_client: APIClient):
    me = make_user("me@example.com")
    api_client.force_authenticate(user=me)

    a = make_user("alpha@example.com", first_name="Alice", last_name="Alpha")
    b = make_user("beta@example.com", first_name="Bob", last_name="Beta")
    _ = make_user("gamma@example.com", first_name="Garry", last_name="Gamma")

    url = reverse("api:v1:employees-list")

    # поиск по части email
    r = api_client.get(url, {"search": "bet"})
    assert r.status_code == 200
    emails = [x["email"] for x in extract_results(r.json())]
    assert emails == ["beta@example.com"]

    # поиск по фамилии
    r = api_client.get(url, {"search": "alp"})
    emails = [x["email"] for x in extract_results(r.json())]
    assert emails == ["alpha@example.com"]

    # ordering по -last_name
    r = api_client.get(url, {"ordering": "-last_name"})
    last_names = [x["last_name"] for x in extract_results(r.json())]
    assert last_names == sorted(last_names, reverse=True)

    # ordering по id (ASC)
    r = api_client.get(url, {"ordering": "id"})
    ids = [x["id"] for x in extract_results(r.json())]
    assert ids == sorted(ids)

# ---------- filters ----------

def test_filter_by_department_includes_members_and_head(api_client: APIClient):
    u = make_user("u@example.com")
    api_client.force_authenticate(user=u)

    head = make_user("head@example.com", last_name="Head")
    member = make_user("mem@example.com", last_name="Member")
    outsider = make_user("out@example.com", last_name="Out")

    d = Department.objects.create(name="Dept", head=head)
    EmployeeDepartment.objects.create(employee=member, department=d, is_active=True)

    url = reverse("api:v1:employees-list")
    r = api_client.get(url, {"department": d.id})
    assert r.status_code == 200
    ids = {it["id"] for it in extract_results(r.json())}
    assert ids == {head.id, member.id}
    assert outsider.id not in ids

def test_filter_by_position(api_client: APIClient):
    u = make_user("u@example.com")
    api_client.force_authenticate(user=u)

    p1 = Position.objects.create(name="Dev")
    p2 = Position.objects.create(name="QA")

    e1 = make_user("d1@example.com")
    e1.position = p1
    e1.save()

    e2 = make_user("d2@example.com")
    e2.position = p1
    e2.save()

    _ = make_user("q1@example.com", position=p2)

    url = reverse("api:v1:employees-list")
    r = api_client.get(url, {"position": p1.id})
    assert r.status_code == 200
    ids = {it["id"] for it in extract_results(r.json())}
    assert ids == {e1.id, e2.id}

def test_filter_by_skills_any_of(api_client: APIClient):
    u = make_user("u@example.com")
    api_client.force_authenticate(user=u)

    s1 = Skill.objects.create(name="Python")
    s2 = Skill.objects.create(name="JS")

    e1 = make_user("e1@example.com")
    e1.skills.add(s1)

    e2 = make_user("e2@example.com")
    e2.skills.add(s2)

    _ = make_user("e3@example.com")  # без навыков

    url = reverse("api:v1:employees-list")
    r = api_client.get(url, [("skill", s1.id), ("skill", s2.id)])
    assert r.status_code == 200
    ids = {it["id"] for it in extract_results(r.json())}
    assert ids == {e1.id, e2.id}

def test_filter_by_email_verified_and_active(api_client: APIClient):
    u = make_user("u@example.com")
    api_client.force_authenticate(user=u)

    v1 = make_user("v1@example.com", verified=True, active=True)
    v0 = make_user("v0@example.com", verified=False, active=True)
    a0 = make_user("a0@example.com", verified=True, active=False)

    url = reverse("api:v1:employees-list")

    r = api_client.get(url, {"email_verified": "true"})
    ids = {it["id"] for it in extract_results(r.json())}
    assert v1.id in ids and a0.id in ids and v0.id not in ids

    r = api_client.get(url, {"active": "true"})
    ids = {it["id"] for it in extract_results(r.json())}
    assert v1.id in ids and v0.id in ids and a0.id not in ids

def test_filter_actually_active_logic(api_client: APIClient):
    u = make_user("u@example.com")
    api_client.force_authenticate(user=u)

    # e_ok: email_verified=True, нет действий, is_active=True => считается активным
    e_ok = make_user("ok@example.com", verified=True, active=True)

    # e_dismissed: email_verified=True, последнее действие — DISMISSED => не активен
    e_d = make_user("d@example.com", verified=True, active=True)
    EmployeeAction.objects.create(
        employee=e_d, action=ACTION_DISMISSED, date=dt.datetime.now(dt.timezone.utc)
    )

    # e_unver: email_verified=False, даже при active=True — не включается при actually_active=true
    e_unver = make_user("unver@example.com", verified=False, active=True)

    url = reverse("api:v1:employees-list")

    r = api_client.get(url, {"actually_active": "true"})
    ids = {it["id"] for it in extract_results(r.json())}
    assert e_ok.id in ids
    assert e_d.id not in ids
    assert e_unver.id not in ids

    r = api_client.get(url, {"actually_active": "false"})
    ids = {it["id"] for it in extract_results(r.json())}
    # среди "не реально активных" должны быть уволенный и/или не верифицированный
    assert e_d.id in ids or e_unver.id in ids

# ---------- create (staff only) + validation + skills ----------

def test_create_requires_staff(api_client: APIClient):
    user = make_user("u@example.com")
    api_client.force_authenticate(user=user)

    url = reverse("api:v1:employees-list")
    payload = {
        "email": "new@example.com",
        "phone_number": _unique_phone(),
        "last_name": "New",
        "first_name": "User",
    }
    resp = api_client.post(url, payload, format="json")
    assert resp.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED)

    # staff -> создание разрешено
    staff = make_user("staff@example.com", staff=True)
    api_client.force_authenticate(user=staff)
    resp = api_client.post(url, payload, format="json")
    assert resp.status_code == status.HTTP_201_CREATED
    data = resp.json()
    assert data["email"] == "new@example.com"
    assert Employee.objects.filter(email="new@example.com").exists()

# ---------- update / partial_update (IsSelfOrStaff) ----------

def test_partial_update_self_allowed(api_client: APIClient):
    e = make_user("self@example.com")
    api_client.force_authenticate(user=e)
    url = reverse("api:v1:employees-detail", args=[e.pk])

    resp = api_client.patch(url, {"first_name": "Me"}, format="json")
    assert resp.status_code == status.HTTP_200_OK
    e.refresh_from_db()
    assert e.first_name == "Me"

def test_partial_update_other_forbidden_for_regular_user(api_client: APIClient):
    owner = make_user("owner@example.com")
    other = make_user("other@example.com")
    api_client.force_authenticate(user=other)
    url = reverse("api:v1:employees-detail", args=[owner.pk])

    resp = api_client.patch(url, {"first_name": "Hack"}, format="json")
    assert resp.status_code == status.HTTP_403_FORBIDDEN

def test_partial_update_other_allowed_for_staff(api_client: APIClient):
    target = make_user("target@example.com")
    staff = make_user("admin@example.com", staff=True)
    api_client.force_authenticate(user=staff)
    url = reverse("api:v1:employees-detail", args=[target.pk])

    resp = api_client.patch(url, {"first_name": "Ok"}, format="json")
    assert resp.status_code == status.HTTP_200_OK
    target.refresh_from_db()
    assert target.first_name == "Ok"

def test_destroy_requires_admin(api_client: APIClient):
    victim = make_user("victim@example.com")
    regular = make_user("regular@example.com")
    staff = make_user("staff@example.com", staff=True)

    url = reverse("api:v1:employees-detail", args=[victim.pk])

    api_client.force_authenticate(user=regular)
    assert api_client.delete(url).status_code in (
        status.HTTP_403_FORBIDDEN,
        status.HTTP_401_UNAUTHORIZED,
    )

    api_client.force_authenticate(user=staff)
    resp = api_client.delete(url)
    assert resp.status_code == status.HTTP_204_NO_CONTENT
    assert not Employee.objects.filter(pk=victim.pk).exists()


def test_destroy_self_forbidden_for_regular_user(api_client: APIClient):
    me = make_user("self-delete@example.com")
    api_client.force_authenticate(user=me)
    url = reverse("api:v1:employees-detail", args=[me.pk])

    resp = api_client.delete(url)
    assert resp.status_code in (
        status.HTTP_403_FORBIDDEN,
        status.HTTP_401_UNAUTHORIZED,
    )
    assert Employee.objects.filter(pk=me.pk).exists()

# ---------- action: me (GET/PATCH) ----------

def test_me_get_returns_current_user(api_client: APIClient):
    me = make_user("me@example.com")
    api_client.force_authenticate(user=me)

    url = reverse("api:v1:employees-me")
    r = api_client.get(url)
    assert r.status_code == 200
    assert r.json()["id"] == me.id

def test_me_patch_updates_profile(api_client: APIClient):
    me = make_user("me@example.com", telegram="@me")  # уже есть контакт
    api_client.force_authenticate(user=me)

    url = reverse("api:v1:employees-me")
    r = api_client.patch(url, {"first_name": "Updated"}, format="json")
    assert r.status_code == 200
    me.refresh_from_db()
    assert me.first_name == "Updated"


def test_add_skill_allowed_for_any_authenticated_user(api_client: APIClient):
    actor = make_user("actor@example.com")
    target = make_user("target-skill@example.com")
    skill = Skill.objects.create(name="Python")

    api_client.force_authenticate(user=actor)
    url = reverse("api:v1:employees-add-skill", args=[target.pk])

    resp = api_client.post(url, {"skill_id": skill.id}, format="json")
    assert resp.status_code == status.HTTP_200_OK

    target.refresh_from_db()
    assert target.skills.filter(pk=skill.pk).exists()


def test_add_skill_can_create_skill_by_name(api_client: APIClient):
    actor = make_user("actor2@example.com")
    target = make_user("target-create-skill@example.com")

    api_client.force_authenticate(user=actor)
    url = reverse("api:v1:employees-add-skill", args=[target.pk])

    resp = api_client.post(url, {"name": "TypeScript"}, format="json")
    assert resp.status_code == status.HTTP_200_OK

    created = Skill.objects.get(name="TypeScript")
    target.refresh_from_db()
    assert target.skills.filter(pk=created.pk).exists()
