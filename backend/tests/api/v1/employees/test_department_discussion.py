import itertools

import pytest
from communications.comments_helpers import create_comment
from communications.models import Chat, Message
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from employees.models import (
    Department,
    DepartmentRole,
    EmployeeDepartment,
    RoleAssignment,
)
from rest_framework import status
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

User = get_user_model()

_phone_seq = itertools.count(3000)


def _unique_phone() -> str:
    return f"+7999555{next(_phone_seq):04d}"


@pytest.fixture
def api_client():
    return APIClient()


def make_user(
    email: str,
    *,
    first_name: str = "FN",
    last_name: str = "LN",
    active: bool = True,
):
    user = User.objects.create(
        email=email,
        phone_number=_unique_phone(),
        first_name=first_name,
        last_name=last_name,
        is_active=active,
        email_verified=True,
    )
    user.set_password("pass")
    user.save()
    return user


def discussion_chat_url(department_id: int) -> str:
    base = reverse("api:v1:departments-detail", args=[department_id])
    return f"{base}discussion-chat/"


def test_department_creation_does_not_create_auto_channel_chat():
    department = Department.objects.create(name="Finance")
    dept_ct = ContentType.objects.get_for_model(Department)

    assert not Chat.objects.filter(
        type="channel",
        context_content_type=dept_ct,
        context_object_id=department.id,
    ).exists()


def test_department_discussion_chat_endpoint_returns_comments_chat(
    api_client: APIClient,
):
    user = make_user("user@example.com")
    department = Department.objects.create(name="Support")
    api_client.force_authenticate(user=user)

    response = api_client.get(discussion_chat_url(department.id))

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["chat_type"] == "comments"
    assert payload["name"] == department.name

    chat = Chat.objects.get(id=payload["chat_id"])
    assert chat.type == "comments"
    assert chat.context_object == department
    assert chat.created_by is None
    assert chat.flags.get("show_in_messages") is True


def test_department_discussion_chat_endpoint_clears_legacy_owner(
    api_client: APIClient,
):
    user = make_user("user@example.com")
    department = Department.objects.create(name="Support")
    api_client.force_authenticate(user=user)

    chat = Chat.objects.create(
        type="comments",
        name=f"Комментарии: {department.name}",
        created_by=user,
        context_content_type=ContentType.objects.get_for_model(Department),
        context_object_id=department.id,
    )

    response = api_client.get(discussion_chat_url(department.id))

    assert response.status_code == status.HTTP_200_OK
    chat.refresh_from_db()
    assert chat.created_by is None
    assert chat.name == department.name
    assert chat.flags.get("show_in_messages") is True


def test_any_active_user_can_retrieve_department_comments_chat(
    api_client: APIClient,
):
    department = Department.objects.create(name="HR")
    member = make_user("member@example.com")
    outsider = make_user("outsider@example.com")
    EmployeeDepartment.objects.create(
        employee=member,
        department=department,
        is_active=True,
    )

    chat = create_comment(
        department,
        author=member,
        content="Первое сообщение",
    ).chat

    api_client.force_authenticate(user=outsider)
    response = api_client.get(f"/api/v1/communications/chats/{chat.id}/")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["id"] == chat.id
    assert response.data["type"] == "comments"


def test_any_active_user_can_send_message_to_department_comments_chat(
    api_client: APIClient,
):
    department = Department.objects.create(name="Accounting")
    member = make_user("member@example.com")
    outsider = make_user("outsider@example.com")
    EmployeeDepartment.objects.create(
        employee=member,
        department=department,
        is_active=True,
    )

    chat = create_comment(
        department,
        author=member,
        content="Старт обсуждения",
    ).chat

    api_client.force_authenticate(user=outsider)
    bootstrap_response = api_client.get(discussion_chat_url(department.id))
    assert bootstrap_response.status_code == status.HTTP_200_OK
    chat.refresh_from_db()
    assert chat.created_by is None
    assert chat.name == department.name

    response = api_client.post(
        "/api/v1/communications/messages/upload/",
        {"chat_id": chat.id, "content": "Пишу в чат отдела"},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert Message.objects.filter(
        chat=chat,
        author=outsider,
        content="Пишу в чат отдела",
    ).exists()
    chat.refresh_from_db()
    assert chat.created_by is None
    assert chat.name == department.name
    assert chat.flags.get("show_in_messages") is True


def test_department_comment_notifications_only_include_department_and_role_only(
    monkeypatch,
):
    department = Department.objects.create(name="Backoffice")
    member = make_user("member@example.com")
    role_only = make_user("role-only@example.com")
    previous_commenter = make_user("previous@example.com")

    EmployeeDepartment.objects.create(
        employee=member,
        department=department,
        is_active=True,
    )
    dept_role = DepartmentRole.objects.create(
        department=department,
        name="Consultant",
    )
    RoleAssignment.objects.create(
        employee=role_only,
        role=dept_role,
        is_active=True,
    )

    create_comment(
        department,
        author=previous_commenter,
        content="Первый комментарий",
    )

    sent_notifications = []

    def capture_notification(**kwargs):
        sent_notifications.append(kwargs)

    monkeypatch.setattr(
        "communications.notifications.handlers._send_notification",
        capture_notification,
    )

    message = create_comment(
        department,
        author=member,
        content="Новый комментарий",
    )

    recipient_ids = {payload["recipient"].id for payload in sent_notifications}

    assert role_only.id in recipient_ids
    assert previous_commenter.id not in recipient_ids
    assert member.id not in recipient_ids
    assert sent_notifications
    for payload in sent_notifications:
        assert payload["action_url"] == f"/messages/{message.chat_id}"
        assert payload["data"]["chat_id"] == message.chat_id


def test_department_comment_reply_notifies_reply_target_outside_department(
    monkeypatch,
):
    department = Department.objects.create(name="Operations")
    member = make_user("member@example.com")
    outsider = make_user("outsider@example.com")

    EmployeeDepartment.objects.create(
        employee=member,
        department=department,
        is_active=True,
    )

    first_comment = create_comment(
        department,
        author=outsider,
        content="Вопрос от сотрудника вне отдела",
    )

    sent_notifications = []

    def capture_notification(**kwargs):
        sent_notifications.append(kwargs)

    monkeypatch.setattr(
        "communications.notifications.handlers._send_notification",
        capture_notification,
    )

    reply = create_comment(
        department,
        author=member,
        content="Ответ сотруднику",
        reply_to=first_comment,
    )

    recipient_ids = {payload["recipient"].id for payload in sent_notifications}

    assert outsider.id in recipient_ids
    assert member.id not in recipient_ids
    for payload in sent_notifications:
        assert payload["action_url"] == f"/messages/{reply.chat_id}"
        assert payload["data"]["chat_id"] == reply.chat_id


def test_department_chat_visible_in_messages_list_but_generic_comments_hidden(
    api_client: APIClient,
):
    user = make_user("user@example.com")
    department = Department.objects.create(name="Finance")
    api_client.force_authenticate(user=user)

    visible_chat_response = api_client.get(discussion_chat_url(department.id))
    assert visible_chat_response.status_code == status.HTTP_200_OK
    visible_chat_id = visible_chat_response.json()["chat_id"]

    hidden_comments_chat = Chat.objects.create(
        type="comments",
        name="Скрытый object chat",
    )

    response = api_client.get("/api/v1/communications/chats/")

    assert response.status_code == status.HTTP_200_OK
    payload = response.data
    items = payload["results"] if isinstance(payload, dict) and "results" in payload else payload
    returned_ids = {item["id"] for item in items}
    assert visible_chat_id in returned_ids
    assert hidden_comments_chat.id not in returned_ids
