from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from notifications.models import Notification
from tasks.models import Task, TaskBoard, TaskColumn
from tasks.notifications.config import NotificationVerbs
from tasks.notifications.handlers import dispatch_task_due_notifications


pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


def make_user(email, phone_number, **extra):
    defaults = {
        "password": "testpass123",
        "phone_number": phone_number,
        "first_name": "Тест",
        "last_name": "Сотрудник",
        "is_active": True,
        "email_verified": True,
        "send_activation_email": False,
    }
    defaults.update(extra)
    return User.objects.create_user(email=email, **defaults)


def make_board(owner, *, name="Доска уведомлений"):
    board = TaskBoard.objects.create(name=name, created_by=owner)
    column = TaskColumn.objects.create(
        board=board,
        name="Новые",
        position=1000,
    )
    done = TaskColumn.objects.create(
        board=board,
        name="Готово",
        position=2000,
        is_done=True,
    )
    return board, column, done


def make_task(owner, column, **extra):
    return Task.objects.create(
        board=column.board,
        column=column,
        title=extra.pop("title", "Проверить уведомления"),
        created_by=owner,
        **extra,
    )


def test_create_task_notifies_assignee(api_client):
    owner = make_user("task-notify-owner@example.com", "+79995550001")
    assignee = make_user("task-notify-assignee@example.com", "+79995550002")
    board, column, _done = make_board(owner)
    api_client.force_authenticate(user=owner)

    response = api_client.post(
        reverse("api:v1:tasks:task-list"),
        {
            "board": board.id,
            "column": column.id,
            "title": "Назначенная задача",
            "assignee_id": assignee.id,
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    notification = Notification.objects.get(
        recipient=assignee,
        verb=NotificationVerbs.TASK_ASSIGNED,
    )
    assert notification.target_object_id == str(response.data["id"])
    assert notification.data["task_id"] == response.data["id"]
    assert notification.action_url == (
        f"/tasks?board={board.id}&task={response.data['id']}"
    )
    assert not Notification.objects.filter(
        recipient=owner,
        verb=NotificationVerbs.TASK_ASSIGNED,
    ).exists()


def test_reassign_task_notifies_old_and_new_assignees(api_client):
    owner = make_user("task-reassign-owner@example.com", "+79995550003")
    old_assignee = make_user("task-reassign-old@example.com", "+79995550004")
    new_assignee = make_user("task-reassign-new@example.com", "+79995550005")
    board, column, _done = make_board(owner)
    task = make_task(owner, column, assignee=old_assignee)
    Notification.objects.all().delete()
    api_client.force_authenticate(user=owner)

    response = api_client.patch(
        reverse("api:v1:tasks:task-detail", kwargs={"pk": task.id}),
        {"assignee_id": new_assignee.id},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    recipients = set(
        Notification.objects.filter(
            verb=NotificationVerbs.TASK_REASSIGNED,
        ).values_list("recipient_id", flat=True)
    )
    assert recipients == {old_assignee.id, new_assignee.id}


def test_task_comment_notifies_connected_users_except_author(api_client):
    owner = make_user("task-comment-owner@example.com", "+79995550006")
    assignee = make_user("task-comment-assignee@example.com", "+79995550007")
    board, column, _done = make_board(owner)
    task = make_task(owner, column, assignee=assignee)
    Notification.objects.all().delete()
    api_client.force_authenticate(user=assignee)

    response = api_client.post(
        reverse("api:v1:tasks:task-comments", kwargs={"pk": task.id}),
        {"text": "Нужно проверить детали"},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    notification = Notification.objects.get(
        recipient=owner,
        verb=NotificationVerbs.TASK_COMMENT,
    )
    assert notification.data["comment_id"] == response.data["id"]
    assert not Notification.objects.filter(
        recipient=assignee,
        verb=NotificationVerbs.TASK_COMMENT,
    ).exists()


def test_board_member_added_notification(api_client):
    owner = make_user("task-board-notify-owner@example.com", "+79995550008")
    member = make_user("task-board-notify-member@example.com", "+79995550009")
    board, _column, _done = make_board(owner)
    api_client.force_authenticate(user=owner)

    response = api_client.patch(
        reverse("api:v1:tasks:task-board-detail", kwargs={"pk": board.id}),
        {"members": [member.id]},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    notification = Notification.objects.get(
        recipient=member,
        verb=NotificationVerbs.TASK_BOARD_MEMBER_ADDED,
    )
    assert notification.data["board_id"] == board.id
    assert notification.action_url == f"/tasks?board={board.id}"


def test_link_employee_notifies_linked_employee(api_client):
    owner = make_user("task-link-notify-owner@example.com", "+79995550010")
    employee = make_user("task-link-notify-employee@example.com", "+79995550011")
    board, column, _done = make_board(owner)
    task = make_task(owner, column)
    api_client.force_authenticate(user=owner)

    response = api_client.post(
        reverse("api:v1:tasks:task-linked-employees", kwargs={"pk": task.id}),
        {"employee_id": employee.id},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    notification = Notification.objects.get(
        recipient=employee,
        verb=NotificationVerbs.TASK_LINKED_OBJECT_ADDED,
    )
    assert notification.data["linked_object_kind"] == "employee"
    assert notification.data["task_id"] == task.id


def test_due_notification_dispatches_once_per_day():
    owner = make_user("task-due-owner@example.com", "+79995550012")
    assignee = make_user("task-due-assignee@example.com", "+79995550013")
    board, column, _done = make_board(owner)
    today = timezone.localdate()
    make_task(
        owner,
        column,
        title="Срок сегодня",
        assignee=assignee,
        due_date=today,
    )
    make_task(
        owner,
        column,
        title="Просрочена",
        assignee=assignee,
        due_date=today - timedelta(days=1),
    )

    first_result = dispatch_task_due_notifications()
    second_result = dispatch_task_due_notifications()

    assert first_result == {"due_soon": 1, "overdue": 1}
    assert second_result == {"due_soon": 0, "overdue": 0}
    assert Notification.objects.filter(
        recipient=assignee,
        verb=NotificationVerbs.TASK_DUE_SOON,
    ).count() == 1
    assert Notification.objects.filter(
        recipient=assignee,
        verb=NotificationVerbs.TASK_OVERDUE,
    ).count() == 1
