from __future__ import annotations

from typing import Any

import pytest
from django.db import models
from rest_framework.test import APIClient

from requests_app.enums import RequestStatus, RequestType
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


def test_list_unauth_401(api_client: APIClient) -> None:
    """Неаутентифицированный доступ к списку → 401."""
    resp = api_client.get(API_BASE)
    assert resp.status_code == 401


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
