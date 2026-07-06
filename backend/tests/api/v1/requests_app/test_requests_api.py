from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pytest
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone
from notifications.models import Notification
from rest_framework.test import APIClient

from requests_app.enums import RequestStatus, RequestType
from requests_app.models import Request as EmployeeRequest
from tasks.models import (
    Task,
    TaskBoard,
    TaskColumn,
    TaskLinkedObject,
    TaskLinkedObjectKind,
)
from tests.test_config import API_REQUESTS_URL


pytestmark = pytest.mark.django_db

API_BASE = API_REQUESTS_URL


def _results(payload: Any) -> list[dict[str, Any]]:
    """Нормализует DRF-пагинацию в список объектов."""
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "results" in payload:
        return payload["results"] or []
    return []


def _result_ids(payload: Any) -> set[int]:
    return {item["id"] for item in _results(payload)}


def test_list_unauth_401(api_client: APIClient) -> None:
    """Неаутентифицированный доступ к списку → 401."""
    resp = api_client.get(API_BASE)
    assert resp.status_code == 401


def test_statistics_requires_privileged_access(
    auth_client, regular_user: models.Model, make_user
) -> None:
    """Статистика недоступна обычному пользователю без спецправ."""
    employee = make_user(email="stats-target@example.com")

    resp = auth_client(regular_user).get(
        f"{API_BASE}statistics/?employee_id={employee.id}&period=all"
    )

    assert resp.status_code == 403


def test_statistics_counts_all_employee_requests_for_admin(
    auth_client,
    admin_user: models.Model,
    make_user,
    make_request,
) -> None:
    """Админ получает полную статистику по сотруднику, а не только видимые заявки."""
    employee = make_user(email="stats-admin-target@example.com")
    make_request(
        employee=employee,
        type_=RequestType.SICK_LEAVE,
        status=RequestStatus.APPROVED,
    )
    make_request(
        employee=employee,
        type_=RequestType.DAY_OFF,
        status=RequestStatus.PENDING,
    )
    maternity = make_request(
        employee=employee,
        type_=RequestType.MATERNITY,
        status=RequestStatus.APPROVED,
    )
    maternity.date_from = datetime(2026, 4, 1).date()
    maternity.date_to = datetime(2026, 4, 10).date()
    maternity.save(update_fields=["date_from", "date_to"])

    resp = auth_client(admin_user).get(
        f"{API_BASE}statistics/?employee_id={employee.id}&period=all"
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["employee_id"] == employee.id
    assert payload["period"] == "all"
    assert payload["date_from"] is None
    assert payload["date_to"] is None
    assert payload["total_submitted_requests"] == 3
    assert payload["sick_leave_requests_count"] == 1
    assert payload["day_off_requests_count"] == 1
    assert payload["maternity_requests_count"] == 1
    assert payload["maternity_days"] == 10


def test_statistics_custom_period_filters_request_counts_and_absence_days(
    auth_client,
    admin_user: models.Model,
    make_user,
    make_request,
) -> None:
    """Custom период фильтрует заявки по дате отправки и дни по пересечению периода."""
    employee = make_user(email="stats-custom-target@example.com")

    matching = make_request(
        employee=employee,
        type_=RequestType.VACATION,
        status=RequestStatus.APPROVED,
        comment="отпуск за свой счет",
    )
    matching.created_at = datetime(
        2026, 4, 10, 12, 0, tzinfo=timezone.get_current_timezone()
    )
    matching.date_from = datetime(2026, 4, 5).date()
    matching.date_to = datetime(2026, 4, 12).date()
    matching.save(
        update_fields=["created_at", "date_from", "date_to", "comment"]
    )

    outside_count = make_request(
        employee=employee,
        type_=RequestType.DAY_OFF,
        status=RequestStatus.APPROVED,
    )
    outside_count.created_at = datetime(
        2026, 3, 1, 12, 0, tzinfo=timezone.get_current_timezone()
    )
    outside_count.date_from = datetime(2026, 4, 11).date()
    outside_count.date_to = datetime(2026, 4, 11).date()
    outside_count.save(update_fields=["created_at", "date_from", "date_to"])

    resp = auth_client(admin_user).get(
        f"{API_BASE}statistics/?employee_id={employee.id}&period=custom"
        "&date_from=2026-04-10&date_to=2026-04-15"
    )

    assert resp.status_code == 200
    payload = resp.json()
    assert payload["period"] == "custom"
    assert payload["date_from"] == "2026-04-10"
    assert payload["date_to"] == "2026-04-15"
    assert payload["total_submitted_requests"] == 1
    assert payload["day_off_requests_count"] == 0
    assert payload["unpaid_vacation_days"] == 3


def test_statistics_custom_period_requires_valid_dates(
    auth_client, admin_user: models.Model, make_user
) -> None:
    """Custom период требует обе даты и валидный диапазон."""
    employee = make_user(email="stats-custom-validation@example.com")

    missing_resp = auth_client(admin_user).get(
        f"{API_BASE}statistics/?employee_id={employee.id}&period=custom"
    )
    invalid_resp = auth_client(admin_user).get(
        f"{API_BASE}statistics/?employee_id={employee.id}&period=custom"
        "&date_from=2026-04-20&date_to=2026-04-10"
    )

    assert missing_resp.status_code == 400
    assert invalid_resp.status_code == 400


def test_list_only_participants_see_requests(
    auth_client, regular_user: models.Model, make_user, make_request
) -> None:
    """В списке видны только свои, адресованные и заявки в копии."""
    recipient = make_user(email="participant-recipient@example.com")
    cc_user = make_user(email="participant-cc@example.com")
    foreign_user = make_user(email="foreign-owner@example.com")

    own_request = make_request(employee=regular_user, type_=RequestType.VACATION)
    recipient_request = make_request(
        employee=foreign_user, type_=RequestType.SICK_LEAVE
    )
    cc_request = make_request(employee=foreign_user, type_=RequestType.DAY_OFF)
    hidden_request = make_request(
        employee=foreign_user, type_=RequestType.OTHER
    )

    recipient_request.recipients.add(regular_user, recipient)
    cc_request.cc_users.add(regular_user, cc_user)

    client = auth_client(regular_user)
    resp = client.get(API_BASE)

    assert resp.status_code == 200
    ids = {item["id"] for item in _results(resp.json())}
    assert own_request.id in ids
    assert recipient_request.id in ids
    assert cc_request.id in ids
    assert hidden_request.id not in ids


def test_list_addressed_to_me_shows_only_recipient_and_cc_requests(
    auth_client, regular_user: models.Model, make_user, make_request
) -> None:
    """Фильтр addressed_to_me исключает собственные заявки."""
    foreign_user = make_user(email="addressed-owner@example.com")

    own_request = make_request(employee=regular_user)
    recipient_request = make_request(employee=foreign_user)
    cc_request = make_request(employee=foreign_user)

    recipient_request.recipients.add(regular_user)
    cc_request.cc_users.add(regular_user)

    client = auth_client(regular_user)
    resp = client.get(f"{API_BASE}?addressed_to_me=true")

    assert resp.status_code == 200
    ids = {item["id"] for item in _results(resp.json())}
    assert own_request.id not in ids
    assert recipient_request.id in ids
    assert cc_request.id in ids


def test_list_period_filter_matches_overlap_and_excludes_missing_period(
    auth_client, regular_user: models.Model, make_request
) -> None:
    """Фильтр периода ищет пересечение интервалов и не подтягивает заявки без дат."""
    no_period = make_request(employee=regular_user, type_=RequestType.OTHER)

    single_day = make_request(employee=regular_user, type_=RequestType.OTHER)
    single_day.date_from = date(2026, 4, 10)
    single_day.date_to = None
    single_day.save(update_fields=["date_from", "date_to"])

    spanning = make_request(employee=regular_user, type_=RequestType.OTHER)
    spanning.date_from = date(2026, 4, 5)
    spanning.date_to = date(2026, 4, 12)
    spanning.save(update_fields=["date_from", "date_to"])

    before = make_request(employee=regular_user, type_=RequestType.OTHER)
    before.date_from = date(2026, 4, 1)
    before.date_to = date(2026, 4, 3)
    before.save(update_fields=["date_from", "date_to"])

    after = make_request(employee=regular_user, type_=RequestType.OTHER)
    after.date_from = date(2026, 4, 20)
    after.date_to = None
    after.save(update_fields=["date_from", "date_to"])

    resp = auth_client(regular_user).get(
        f"{API_BASE}?date_from=2026-04-10&date_to=2026-04-10"
    )

    assert resp.status_code == 200
    ids = _result_ids(resp.json())
    assert single_day.id in ids
    assert spanning.id in ids
    assert no_period.id not in ids
    assert before.id not in ids
    assert after.id not in ids


def test_list_period_filter_with_single_boundary_handles_single_day_requests(
    auth_client, regular_user: models.Model, make_request
) -> None:
    """Одна граница периода корректно работает для date_from без date_to."""
    no_period = make_request(employee=regular_user, type_=RequestType.OTHER)

    old_single_day = make_request(employee=regular_user, type_=RequestType.OTHER)
    old_single_day.date_from = date(2026, 4, 1)
    old_single_day.date_to = None
    old_single_day.save(update_fields=["date_from", "date_to"])

    target_single_day = make_request(employee=regular_user, type_=RequestType.OTHER)
    target_single_day.date_from = date(2026, 4, 10)
    target_single_day.date_to = None
    target_single_day.save(update_fields=["date_from", "date_to"])

    future_single_day = make_request(employee=regular_user, type_=RequestType.OTHER)
    future_single_day.date_from = date(2026, 4, 20)
    future_single_day.date_to = None
    future_single_day.save(update_fields=["date_from", "date_to"])

    from_resp = auth_client(regular_user).get(f"{API_BASE}?date_from=2026-04-10")
    to_resp = auth_client(regular_user).get(f"{API_BASE}?date_to=2026-04-10")

    assert from_resp.status_code == 200
    from_ids = _result_ids(from_resp.json())
    assert target_single_day.id in from_ids
    assert future_single_day.id in from_ids
    assert old_single_day.id not in from_ids
    assert no_period.id not in from_ids

    assert to_resp.status_code == 200
    to_ids = _result_ids(to_resp.json())
    assert old_single_day.id in to_ids
    assert target_single_day.id in to_ids
    assert future_single_day.id not in to_ids
    assert no_period.id not in to_ids


def test_list_created_date_filter_includes_same_day_boundaries(
    auth_client, regular_user: models.Model, make_request
) -> None:
    """Одинаковые created_from/created_to выбирают весь календарный день."""
    tz = timezone.get_current_timezone()
    previous = make_request(employee=regular_user, type_=RequestType.OTHER)
    previous.created_at = datetime(2026, 4, 9, 23, 59, tzinfo=tz)
    previous.save(update_fields=["created_at"])

    morning = make_request(employee=regular_user, type_=RequestType.OTHER)
    morning.created_at = datetime(2026, 4, 10, 0, 1, tzinfo=tz)
    morning.save(update_fields=["created_at"])

    evening = make_request(employee=regular_user, type_=RequestType.OTHER)
    evening.created_at = datetime(2026, 4, 10, 23, 59, tzinfo=tz)
    evening.save(update_fields=["created_at"])

    next_day = make_request(employee=regular_user, type_=RequestType.OTHER)
    next_day.created_at = datetime(2026, 4, 11, 0, 1, tzinfo=tz)
    next_day.save(update_fields=["created_at"])

    resp = auth_client(regular_user).get(
        f"{API_BASE}?created_from=2026-04-10&created_to=2026-04-10"
    )

    assert resp.status_code == 200
    ids = _result_ids(resp.json())
    assert morning.id in ids
    assert evening.id in ids
    assert previous.id not in ids
    assert next_day.id not in ids


def test_list_includes_accessible_linked_tasks(
    auth_client, regular_user: models.Model, make_user, make_request
) -> None:
    """Список заявлений отдаёт task-пилюли только с доступных досок."""
    author = make_user(email="request-task-author@example.com")
    hidden_user = make_user(email="request-task-hidden@example.com")
    employee_request = make_request(
        employee=author,
        type_=RequestType.DAY_OFF,
        comment="Заявление со связанной задачей",
    )
    employee_request.recipients.add(regular_user)

    visible_board = TaskBoard.objects.create(
        name="Видимая доска заявлений",
        created_by=author,
    )
    visible_board.members.add(regular_user)
    visible_column = TaskColumn.objects.create(
        board=visible_board,
        name="В работе",
        position=1000,
        color="#f59e0b",
    )
    visible_task = Task.objects.create(
        board=visible_board,
        column=visible_column,
        title="Доступная задача по заявлению",
        created_by=author,
        priority="high",
    )

    hidden_board = TaskBoard.objects.create(
        name="Скрытая доска заявлений",
        created_by=hidden_user,
    )
    hidden_board.members.add(hidden_user)
    hidden_column = TaskColumn.objects.create(
        board=hidden_board,
        name="Новые",
        position=1000,
        color="#38bdf8",
    )
    hidden_task = Task.objects.create(
        board=hidden_board,
        column=hidden_column,
        title="Недоступная задача по заявлению",
        created_by=hidden_user,
    )

    request_ct = ContentType.objects.get_for_model(EmployeeRequest)
    visible_link = TaskLinkedObject.objects.create(
        task=visible_task,
        kind=TaskLinkedObjectKind.REQUEST,
        content_type=request_ct,
        object_id=employee_request.id,
        created_by=author,
    )
    TaskLinkedObject.objects.create(
        task=hidden_task,
        kind=TaskLinkedObjectKind.REQUEST,
        content_type=request_ct,
        object_id=employee_request.id,
        created_by=hidden_user,
    )

    resp = auth_client(regular_user).get(API_BASE)

    assert resp.status_code == 200
    result = next(
        item for item in _results(resp.json()) if item["id"] == employee_request.id
    )
    assert result["linked_tasks"] == [
        {
            "link_id": visible_link.id,
            "id": visible_task.id,
            "title": "Доступная задача по заявлению",
            "board_id": visible_board.id,
            "board_name": "Видимая доска заявлений",
            "column_id": visible_column.id,
            "column_name": "В работе",
            "column_color": "#f59e0b",
            "priority": "high",
            "priority_display": "Высокий",
        }
    ]


def test_list_admin_without_participation_sees_nothing(
    auth_client, admin_user: models.Model, make_user, make_request
) -> None:
    """Админ без участия в заявках не получает доступ через обычный API."""
    owner = make_user(email="admin-hidden-owner@example.com")
    make_request(employee=owner, type_=RequestType.VACATION)
    make_request(employee=owner, type_=RequestType.SICK_LEAVE)

    client = auth_client(admin_user)
    resp = client.get(API_BASE)

    assert resp.status_code == 200
    assert _results(resp.json()) == []


def test_list_model_permission_does_not_bypass_visibility(
    auth_client, make_user, grant_model_perm, make_request
) -> None:
    """Глобальные model permissions не раскрывают чужие заявки."""
    manager = make_user(email="manager-view@example.com")
    owner = make_user(email="manager-view-owner@example.com")
    grant_model_perm(manager, "requests_app.view_request")

    hidden_request = make_request(employee=owner)

    client = auth_client(manager)
    resp = client.get(API_BASE)

    assert resp.status_code == 200
    ids = {item["id"] for item in _results(resp.json())}
    assert hidden_request.id not in ids


def test_detail_only_participants_can_view_request(
    auth_client, admin_user: models.Model, make_user, grant_model_perm, make_request
) -> None:
    """Детали видны только участникам даже при наличии глобальных прав."""
    owner = make_user(email="detail-owner@example.com")
    recipient = make_user(email="detail-recipient@example.com")
    cc_user = make_user(email="detail-cc@example.com")
    outsider = make_user(email="detail-outsider@example.com")
    privileged = make_user(email="detail-privileged@example.com")
    grant_model_perm(privileged, "requests_app.view_request")

    req = make_request(employee=owner)
    req.recipients.add(recipient)
    req.cc_users.add(cc_user)

    assert auth_client(owner).get(f"{API_BASE}{req.id}/").status_code == 200
    assert auth_client(recipient).get(f"{API_BASE}{req.id}/").status_code == 200
    assert auth_client(cc_user).get(f"{API_BASE}{req.id}/").status_code == 200
    assert auth_client(outsider).get(f"{API_BASE}{req.id}/").status_code == 403
    assert auth_client(privileged).get(f"{API_BASE}{req.id}/").status_code == 403
    assert auth_client(admin_user).get(f"{API_BASE}{req.id}/").status_code == 403


def test_create_regular_user_and_admin_forced_to_self(
    auth_client, regular_user: models.Model, admin_user: models.Model, make_user
) -> None:
    """Обычный пользователь и админ не могут создать заявку от чужого имени через API."""
    recipient = make_user(email="create-recipient@example.com")
    other = make_user(email="create-other@example.com")

    regular_payload = {
        "type": RequestType.OTHER,
        "comment": "Отпуск",
        "employee": other.id,
        "status": RequestStatus.APPROVED,
        "recipient_ids": [recipient.id],
    }
    admin_payload = {
        "type": RequestType.OTHER,
        "comment": "Больничный",
        "employee": other.id,
        "recipient_ids": [recipient.id],
    }

    regular_resp = auth_client(regular_user).post(
        API_BASE, data=regular_payload, format="json"
    )
    admin_resp = auth_client(admin_user).post(
        API_BASE, data=admin_payload, format="json"
    )

    assert regular_resp.status_code == 201
    assert admin_resp.status_code == 201
    assert str(regular_resp.json()["employee"]["id"]) == str(regular_user.id)
    assert str(admin_resp.json()["employee"]["id"]) == str(admin_user.id)
    assert regular_resp.json()["status"] in (
        RequestStatus.DRAFT,
        RequestStatus.PENDING,
    )
    assert admin_resp.json()["status"] in (
        RequestStatus.DRAFT,
        RequestStatus.PENDING,
    )


def test_maternity_request_requires_and_accepts_period(
    auth_client, regular_user: models.Model, make_user
) -> None:
    recipient = make_user(email="maternity-recipient@example.com")

    missing_date_resp = auth_client(regular_user).post(
        API_BASE,
        data={
            "type": RequestType.MATERNITY,
            "date_from": "2026-04-20",
            "recipient_ids": [recipient.id],
        },
        format="json",
    )
    assert missing_date_resp.status_code == 400
    assert "date_to" in missing_date_resp.json()

    ok_resp = auth_client(regular_user).post(
        API_BASE,
        data={
            "type": RequestType.MATERNITY,
            "date_from": "2026-04-20",
            "date_to": "2026-09-06",
            "recipient_ids": [recipient.id],
        },
        format="json",
    )
    assert ok_resp.status_code == 201
    assert ok_resp.json()["type"] == RequestType.MATERNITY


def test_day_off_request_requires_full_period(
    auth_client, regular_user: models.Model, make_user
) -> None:
    recipient = make_user(email="day-off-recipient@example.com")

    resp = auth_client(regular_user).post(
        API_BASE,
        data={
            "type": RequestType.DAY_OFF,
            "date_from": "2026-04-20",
            "recipient_ids": [recipient.id],
        },
        format="json",
    )

    assert resp.status_code == 400
    assert "date_to" in resp.json()


def test_create_request_sends_notification_to_cc_users(
    auth_client, regular_user: models.Model, make_user
) -> None:
    """При создании заявки через API пользователь в копии получает request_new."""
    recipient = make_user(email="create-cc-recipient@example.com")
    cc_user = make_user(email="create-cc-user@example.com")

    Notification.objects.all().delete()

    resp = auth_client(regular_user).post(
        API_BASE,
        data={
            "type": RequestType.OTHER,
            "title": "Заявка с копией",
            "comment": "Проверка уведомления для копии",
            "recipient_ids": [recipient.id],
            "cc_user_ids": [cc_user.id],
        },
        format="json",
    )

    assert resp.status_code == 201
    cc_notification = Notification.objects.filter(
        recipient=cc_user,
        verb="request_new",
    ).first()
    assert cc_notification is not None
    assert cc_notification.data["is_cc"] is True
    author_name = regular_user.get_full_name() or regular_user.username
    assert cc_notification.data["title"] == "Новое заявление"
    assert (
        f"{author_name} поставил вас в копию заявления"
        in cc_notification.description
    )


def test_create_draft_allows_minimal_payload(
    auth_client, regular_user: models.Model
) -> None:
    """Черновик можно сохранить без типа, получателей и отделов."""
    resp = auth_client(regular_user).post(
        f"{API_BASE}?save_as=draft",
        data={"title": "Минимальный черновик"},
        format="json",
    )

    assert resp.status_code == 201
    data = resp.json()
    assert data["status"] == RequestStatus.DRAFT
    assert data["title"] == "Минимальный черновик"
    assert data["type"] == ""
    assert data["recipients"] == []
    assert data["cc_users"] == []


def test_submit_requires_full_validation_even_for_existing_draft(
    auth_client, regular_user: models.Model
) -> None:
    """Неполный черновик не переходит в pending без обязательных данных."""
    create_resp = auth_client(regular_user).post(
        f"{API_BASE}?save_as=draft",
        data={"title": "Неполный черновик"},
        format="json",
    )
    assert create_resp.status_code == 201
    req_id = create_resp.json()["id"]

    submit_resp = auth_client(regular_user).patch(
        f"{API_BASE}{req_id}/?save_as=submit",
        data={},
        format="json",
    )

    assert submit_resp.status_code == 400
    errors = submit_resp.json()
    assert "type" in errors or "recipient_ids" in errors


def test_update_and_delete_require_author_even_for_admin(
    auth_client, regular_user: models.Model, admin_user: models.Model, make_user, make_request
) -> None:
    """Редактирование и удаление через API доступны только автору."""
    owner = make_user(email="update-owner@example.com")
    recipient = make_user(email="update-recipient@example.com")
    req = make_request(employee=owner, status=RequestStatus.PENDING)
    req.recipients.add(recipient)

    recipient_client = auth_client(recipient)
    admin_client = auth_client(admin_user)

    recipient_patch = recipient_client.patch(
        f"{API_BASE}{req.id}/", data={"comment": "try"}, format="json"
    )
    admin_patch = admin_client.patch(
        f"{API_BASE}{req.id}/", data={"comment": "try"}, format="json"
    )
    recipient_delete = recipient_client.delete(f"{API_BASE}{req.id}/")
    admin_delete = admin_client.delete(f"{API_BASE}{req.id}/")

    assert recipient_patch.status_code == 403
    assert admin_patch.status_code in (403, 404)
    assert recipient_delete.status_code == 403
    assert admin_delete.status_code in (403, 404)

    own_recipient = make_user(email="own-update-recipient@example.com")
    own_pending = make_request(
        employee=regular_user,
        type_=RequestType.OTHER,
        status=RequestStatus.PENDING,
    )
    own_pending.recipients.add(own_recipient)
    own_final = make_request(
        employee=regular_user,
        type_=RequestType.OTHER,
        status=RequestStatus.APPROVED,
    )
    own_final.recipients.add(own_recipient)
    own_client = auth_client(regular_user)

    assert own_client.patch(
        f"{API_BASE}{own_pending.id}/",
        data={"comment": "обновлено"},
        format="json",
    ).status_code == 200
    assert own_client.patch(
        f"{API_BASE}{own_final.id}/",
        data={"comment": "нельзя"},
        format="json",
    ).status_code in (400, 403)
    assert own_client.delete(f"{API_BASE}{own_pending.id}/").status_code in (
        200,
        204,
    )
    assert own_client.delete(f"{API_BASE}{own_final.id}/").status_code == 403


def test_multiple_recipients_can_decide_until_request_becomes_final(
    auth_client, make_user, make_request
) -> None:
    """Несколько прямых получателей могут решать только пока заявка не финализирована."""
    owner = make_user(email="multi-owner@example.com")
    recipient_one = make_user(email="multi-recipient-one@example.com")
    recipient_two = make_user(email="multi-recipient-two@example.com")

    req = make_request(employee=owner, status=RequestStatus.PENDING)
    req.recipients.add(recipient_one, recipient_two)

    first_resp = auth_client(recipient_one).post(
        f"{API_BASE}{req.id}/approve/", data={}, format="json"
    )
    second_resp = auth_client(recipient_two).post(
        f"{API_BASE}{req.id}/reject/", data={}, format="json"
    )

    assert first_resp.status_code == 200
    assert first_resp.json()["status"] == RequestStatus.APPROVED
    assert second_resp.status_code in (400, 403)


def test_only_direct_recipients_can_decide(
    auth_client, admin_user: models.Model, make_user, make_request
) -> None:
    """Автор, CC, посторонний и админ без recipients не могут принять решение."""
    owner = make_user(email="decision-owner@example.com")
    cc_user = make_user(email="decision-cc@example.com")
    outsider = make_user(email="decision-outsider@example.com")

    req = make_request(employee=owner, status=RequestStatus.PENDING)
    req.cc_users.add(cc_user)

    assert auth_client(owner).post(f"{API_BASE}{req.id}/approve/").status_code == 403
    assert auth_client(cc_user).post(f"{API_BASE}{req.id}/approve/").status_code == 403
    assert auth_client(outsider).post(f"{API_BASE}{req.id}/approve/").status_code == 403
    assert auth_client(admin_user).post(f"{API_BASE}{req.id}/approve/").status_code == 403


def test_admin_can_decide_only_if_explicitly_added_to_recipients(
    auth_client, admin_user: models.Model, make_user, make_request
) -> None:
    """Админ в обычном API ведёт себя как обычный прямой получатель."""
    owner = make_user(email="admin-recipient-owner@example.com")
    req = make_request(employee=owner, status=RequestStatus.PENDING)
    req.recipients.add(admin_user)

    resp = auth_client(admin_user).post(
        f"{API_BASE}{req.id}/reject/", data={}, format="json"
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == RequestStatus.REJECTED


def test_cc_user_receives_status_notification(
    auth_client, make_user, make_request
) -> None:
    """Пользователь в копии получает уведомление о решении по заявке."""
    owner = make_user(email="status-cc-owner@example.com")
    recipient = make_user(email="status-cc-recipient@example.com")
    cc_user = make_user(email="status-cc-user@example.com")

    req = make_request(employee=owner, status=RequestStatus.PENDING)
    req.recipients.add(recipient)
    req.cc_users.add(cc_user)

    Notification.objects.all().delete()

    resp = auth_client(recipient).post(
        f"{API_BASE}{req.id}/approve/", data={}, format="json"
    )

    assert resp.status_code == 200
    cc_notification = Notification.objects.filter(
        recipient=cc_user,
        verb="request_approved",
    ).first()
    assert cc_notification is not None
    assert cc_notification.data["new_status"] == RequestStatus.APPROVED


def test_draft_is_visible_only_to_author(
    auth_client, admin_user: models.Model, make_user, make_request
) -> None:
    """Черновик остаётся только у автора и не попадает во входящие адресатам."""
    owner = make_user(email="draft-owner@example.com")
    recipient = make_user(email="draft-recipient@example.com")
    cc_user = make_user(email="draft-cc@example.com")
    outsider = make_user(email="draft-outsider@example.com")

    req = make_request(employee=owner, status=RequestStatus.DRAFT)
    req.recipients.add(recipient)
    req.cc_users.add(cc_user)

    owner_ids = {
        item["id"]
        for item in _results(auth_client(owner).get(API_BASE).json())
    }
    recipient_ids = {
        item["id"]
        for item in _results(auth_client(recipient).get(API_BASE).json())
    }
    cc_ids = {
        item["id"] for item in _results(auth_client(cc_user).get(API_BASE).json())
    }

    assert req.id in owner_ids
    assert req.id not in recipient_ids
    assert req.id not in cc_ids
    assert (
        req.id
        not in {
            item["id"]
            for item in _results(
                auth_client(recipient).get(
                    f"{API_BASE}?addressed_to_me=true"
                ).json()
            )
        }
    )
    assert (
        req.id
        not in {
            item["id"]
            for item in _results(
                auth_client(cc_user).get(
                    f"{API_BASE}?addressed_to_me=true"
                ).json()
            )
        }
    )

    assert auth_client(owner).get(f"{API_BASE}{req.id}/").status_code == 200
    assert auth_client(recipient).get(f"{API_BASE}{req.id}/").status_code == 403
    assert auth_client(cc_user).get(f"{API_BASE}{req.id}/").status_code == 403
    assert auth_client(outsider).get(f"{API_BASE}{req.id}/").status_code == 403
    assert auth_client(admin_user).get(f"{API_BASE}{req.id}/").status_code == 403


def test_comments_and_decisions_are_forbidden_for_draft(
    auth_client, make_user, make_request
) -> None:
    """По черновику нельзя комментировать и нельзя принимать решение."""
    owner = make_user(email="draft-comments-owner@example.com")
    recipient = make_user(email="draft-comments-recipient@example.com")
    cc_user = make_user(email="draft-comments-cc@example.com")

    req = make_request(employee=owner, status=RequestStatus.DRAFT)
    req.recipients.add(recipient)
    req.cc_users.add(cc_user)

    assert auth_client(owner).get(f"{API_BASE}{req.id}/comments/").status_code == 403
    assert auth_client(owner).post(
        f"{API_BASE}{req.id}/comments/",
        data={"text": "owner draft comment"},
        format="json",
    ).status_code == 403
    assert (
        auth_client(recipient).post(
            f"{API_BASE}{req.id}/approve/", data={}, format="json"
        ).status_code
        == 403
    )
    assert (
        auth_client(recipient).post(
            f"{API_BASE}{req.id}/reject/", data={}, format="json"
        ).status_code
        == 403
    )
    assert auth_client(cc_user).get(f"{API_BASE}{req.id}/comments/").status_code == 403


def test_author_can_submit_draft_explicitly_to_pending(
    auth_client, make_user
) -> None:
    """Черновик переходит в pending только по явному save_as=submit."""
    owner = make_user(email="draft-submit-owner@example.com")
    recipient = make_user(email="draft-submit-recipient@example.com")

    create_resp = auth_client(owner).post(
        f"{API_BASE}?save_as=draft",
        data={
            "type": RequestType.OTHER,
            "title": "Черновик на отправку",
            "recipient_ids": [recipient.id],
        },
        format="json",
    )
    assert create_resp.status_code == 201
    req_id = create_resp.json()["id"]
    assert create_resp.json()["status"] == RequestStatus.DRAFT

    assert auth_client(recipient).get(f"{API_BASE}{req_id}/").status_code == 403

    submit_resp = auth_client(owner).patch(
        f"{API_BASE}{req_id}/?save_as=submit",
        data={},
        format="json",
    )

    assert submit_resp.status_code == 200
    assert submit_resp.json()["status"] == RequestStatus.PENDING
    assert auth_client(recipient).get(f"{API_BASE}{req_id}/").status_code == 200


def test_comments_available_to_participants_only(
    auth_client, admin_user: models.Model, make_user, make_request
) -> None:
    """Комментарии доступны автору, прямому получателю и CC, но не посторонним."""
    owner = make_user(email="comments-owner@example.com")
    recipient = make_user(email="comments-recipient@example.com")
    cc_user = make_user(email="comments-cc@example.com")
    outsider = make_user(email="comments-outsider@example.com")

    req = make_request(employee=owner)
    req.recipients.add(recipient)
    req.cc_users.add(cc_user)

    owner_client = auth_client(owner)
    recipient_client = auth_client(recipient)
    cc_client = auth_client(cc_user)

    assert owner_client.get(f"{API_BASE}{req.id}/comments/").status_code == 200
    assert recipient_client.get(f"{API_BASE}{req.id}/comments/").status_code == 200
    assert cc_client.get(f"{API_BASE}{req.id}/comments/").status_code == 200
    assert owner_client.post(
        f"{API_BASE}{req.id}/comments/",
        data={"text": "owner"},
        format="json",
    ).status_code == 201
    assert recipient_client.post(
        f"{API_BASE}{req.id}/comments/",
        data={"text": "recipient"},
        format="json",
    ).status_code == 201
    assert cc_client.post(
        f"{API_BASE}{req.id}/comments/",
        data={"text": "cc"},
        format="json",
    ).status_code == 201

    assert auth_client(outsider).get(f"{API_BASE}{req.id}/comments/").status_code == 403
    assert auth_client(outsider).post(
        f"{API_BASE}{req.id}/comments/",
        data={"text": "outsider"},
        format="json",
    ).status_code == 403
    assert auth_client(admin_user).get(f"{API_BASE}{req.id}/comments/").status_code == 403
    assert auth_client(admin_user).post(
        f"{API_BASE}{req.id}/comments/",
        data={"text": "admin"},
        format="json",
    ).status_code == 403


def test_cc_user_receives_comment_notification(
    auth_client, make_user, make_request
) -> None:
    """Пользователь в копии получает уведомление о новом комментарии к заявке."""
    owner = make_user(email="comment-cc-owner@example.com")
    recipient = make_user(email="comment-cc-recipient@example.com")
    cc_user = make_user(email="comment-cc-user@example.com")

    req = make_request(employee=owner)
    req.recipients.add(recipient)
    req.cc_users.add(cc_user)

    Notification.objects.all().delete()

    resp = auth_client(recipient).post(
        f"{API_BASE}{req.id}/comments/",
        data={"text": "Комментарий для проверки уведомлений"},
        format="json",
    )

    assert resp.status_code == 201
    cc_notification = Notification.objects.filter(
        recipient=cc_user,
        verb="commented",
    ).first()
    assert cc_notification is not None
    assert cc_notification.data["object_type"] == "Request"
    assert cc_notification.data["object_id"] == req.id


def test_detail_exposes_can_decide_only_for_direct_recipients(
    auth_client, admin_user: models.Model, make_user, make_request
) -> None:
    """`can_decide` служит UI-контрактом и true только для direct recipients."""
    owner = make_user(email="serializer-owner@example.com")
    recipient = make_user(email="serializer-recipient@example.com")
    cc_user = make_user(email="serializer-cc@example.com")

    req = make_request(employee=owner, status=RequestStatus.PENDING)
    req.recipients.add(recipient)
    req.cc_users.add(cc_user)

    owner_data = auth_client(owner).get(f"{API_BASE}{req.id}/").json()
    recipient_data = auth_client(recipient).get(f"{API_BASE}{req.id}/").json()
    cc_data = auth_client(cc_user).get(f"{API_BASE}{req.id}/").json()

    assert owner_data["can_decide"] is False
    assert recipient_data["can_decide"] is True
    assert cc_data["can_decide"] is False
    assert recipient_data["is_recipient"] is True
    assert cc_data["is_recipient"] is True
    assert auth_client(admin_user).get(f"{API_BASE}{req.id}/").status_code == 403


def test_comment_author_can_delete_own_comment(
    auth_client,
    regular_user: models.Model,
    make_request,
) -> None:
    """Автор комментария может удалить свой комментарий."""
    req = make_request(employee=regular_user)
    client = auth_client(regular_user)

    post_resp = client.post(
        f"{API_BASE}{req.id}/comments/",
        data={"text": "удаляемый комментарий"},
        format="json",
    )
    assert post_resp.status_code == 201
    comment_id = post_resp.json()["id"]

    delete_resp = client.delete(f"{API_BASE}{req.id}/comments/{comment_id}/")
    assert delete_resp.status_code == 204

    list_resp = client.get(f"{API_BASE}{req.id}/comments/")
    assert list_resp.status_code == 200
    ids = {item["id"] for item in _results(list_resp.json())}
    assert comment_id not in ids


@pytest.mark.parametrize(
    ("flt", "expected_status"),
    [
        ("?type=vacation", RequestType.VACATION),
        ("?status=pending", RequestStatus.PENDING),
    ],
)
def test_filters_apply_within_participant_scope(
    auth_client,
    regular_user: models.Model,
    make_user,
    make_request,
    flt: str,
    expected_status: str,
) -> None:
    """Фильтры работают поверх уже вычисленной participant-only области."""
    other = make_user(email="filter-owner@example.com")
    my_request = make_request(
        employee=regular_user,
        type_=RequestType.VACATION,
        status=RequestStatus.PENDING,
    )
    foreign_request = make_request(
        employee=other,
        type_=RequestType.SICK_LEAVE,
        status=RequestStatus.REJECTED,
    )
    foreign_request.recipients.add(regular_user)

    resp = auth_client(regular_user).get(f"{API_BASE}{flt}")

    assert resp.status_code == 200
    items = _results(resp.json())
    assert items
    for item in items:
        if flt.startswith("?type="):
            assert item["type"] == expected_status
        else:
            assert item["status"] == expected_status
    assert my_request.id in {item["id"] for item in _results(auth_client(regular_user).get(API_BASE).json())}


def test_invalid_filter_does_not_crash(
    auth_client, regular_user: models.Model
) -> None:
    """Странные значения фильтров не приводят к 500."""
    client = auth_client(regular_user)
    resp = client.get(f"{API_BASE}?type=__sql__' OR 1=1 --&status=")
    assert resp.status_code == 200
