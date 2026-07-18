from unittest.mock import patch
from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from attendance.models import AttendanceAnalysisRun, AttendanceRecord
from communications.models import Chat, ChatMembership, Message
from documents.models import Document
from employees.models import Department, EmployeeDepartment, RoleAssignment
from feed.models import Post
from guests.models import Guest, GuestVisit
from procurement.constants import ProcurementStatus, UrgencyLevel
from procurement.models import ProcurementRequest
from requests_app.models import Request as EmployeeRequest
from schedule.models import Calendar, CalendarRelation, Event
from tasks.models import (
    Task,
    TaskAttachment,
    TaskBoard,
    TaskChecklistItem,
    TaskColumn,
    TaskExternalLink,
    TaskUserSettings,
)
from tasks.realtime import get_task_board_recipient_ids

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user():
    return User.objects.create_user(
        email="task-user@example.com",
        password="testpass123",
        phone_number="+79994440001",
        first_name="Иван",
        last_name="Задачев",
        is_active=True,
        email_verified=True,
        send_activation_email=False,
    )


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


def test_default_board_creates_work_columns(api_client, user):
    api_client.force_authenticate(user=user)
    url = reverse("api:v1:tasks:task-board-default")

    response = api_client.get(url)

    assert response.status_code == status.HTTP_200_OK
    assert response.data["name"] == "Рабочая доска"
    assert [column["name"] for column in response.data["columns"]] == [
        "Новые",
        "В работе",
        "На проверке",
        "Готово",
    ]
    assert TaskBoard.objects.count() == 1
    assert TaskColumn.objects.count() == 4


def test_user_can_set_personal_default_board(api_client, user):
    api_client.force_authenticate(user=user)
    first_board = api_client.get(
        reverse("api:v1:tasks:task-board-default")
    ).data
    second_board = TaskBoard.objects.create(
        name="Персональная доска по умолчанию",
        created_by=user,
    )
    TaskColumn.objects.create(
        board=second_board,
        name="Новые",
        position=1000,
    )

    set_response = api_client.post(
        reverse("api:v1:tasks:task-board-set-default", kwargs={"pk": second_board.id})
    )

    assert set_response.status_code == status.HTTP_200_OK
    assert set_response.data["id"] == second_board.id
    assert set_response.data["is_default_for_current_user"] is True
    assert TaskUserSettings.objects.get(user=user).default_board_id == second_board.id

    default_response = api_client.get(reverse("api:v1:tasks:task-board-default"))
    assert default_response.status_code == status.HTTP_200_OK
    assert default_response.data["id"] == second_board.id
    assert default_response.data["is_default_for_current_user"] is True

    other_user = make_user("task-default-other@example.com", "+79994440090")
    api_client.force_authenticate(user=other_user)
    other_default_response = api_client.get(reverse("api:v1:tasks:task-board-default"))
    assert other_default_response.status_code == status.HTTP_200_OK
    assert other_default_response.data["id"] == first_board["id"]
    assert other_default_response.data["is_default_for_current_user"] is False


def test_user_cannot_set_inaccessible_board_as_default(api_client):
    owner = make_user("task-default-owner@example.com", "+79994440091")
    outsider = make_user("task-default-outsider@example.com", "+79994440092")
    board = TaskBoard.objects.create(
        name="Закрытая доска",
        created_by=owner,
    )
    board.members.add(owner)

    api_client.force_authenticate(user=outsider)
    response = api_client.post(
        reverse("api:v1:tasks:task-board-set-default", kwargs={"pk": board.id})
    )

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert not TaskUserSettings.objects.filter(user=outsider).exists()


def test_create_task_and_move_to_done_column(api_client, user):
    api_client.force_authenticate(user=user)
    board_response = api_client.get(
        reverse("api:v1:tasks:task-board-default")
    )
    board_id = board_response.data["id"]
    columns = {column["name"]: column for column in board_response.data["columns"]}

    create_response = api_client.post(
        reverse("api:v1:tasks:task-list"),
        {
            "board": board_id,
            "column": columns["Новые"]["id"],
            "title": "Подготовить прототип доски",
            "description": "Собрать первый рабочий workflow",
            "assignee_id": user.id,
            "priority": "high",
        },
        format="json",
    )

    assert create_response.status_code == status.HTTP_201_CREATED
    task_id = create_response.data["id"]
    assert create_response.data["created_by"]["id"] == user.id
    assert create_response.data["assignee"]["id"] == user.id

    with patch("api.v1.tasks.views.send_task_board_update") as send_update:
        move_response = api_client.post(
            reverse("api:v1:tasks:task-move", kwargs={"pk": task_id}),
            {"column": columns["Готово"]["id"]},
            format="json",
        )

    assert move_response.status_code == status.HTTP_200_OK
    assert move_response.data["column"] == columns["Готово"]["id"]
    assert move_response.data["completed_at"] is not None
    send_update.assert_called_once()
    send_args, send_kwargs = send_update.call_args
    assert send_args[0].id == board_id
    assert send_args[1:4] == ("moved", "task", task_id)
    assert send_kwargs["extra"] == {"column_id": columns["Готово"]["id"]}

    task = Task.objects.get(id=task_id)
    assert task.column_id == columns["Готово"]["id"]
    assert task.completed_at is not None


def test_member_can_claim_unassigned_task(api_client, user):
    claimant = make_user("task-claimant@example.com", "+79994440095")
    other_member = make_user("task-claim-other@example.com", "+79994440096")
    board = TaskBoard.objects.create(name="Доска самоназначения", created_by=user)
    board.members.add(claimant, other_member)
    source_column = TaskColumn.objects.create(
        board=board,
        name="Новые",
        position=1000,
    )
    done_column = TaskColumn.objects.create(
        board=board,
        name="Готово",
        position=2000,
        is_done=True,
    )
    task = Task.objects.create(
        board=board,
        column=source_column,
        title="Свободная задача",
        created_by=user,
    )
    claim_url = reverse("api:v1:tasks:task-claim", kwargs={"pk": task.id})

    api_client.force_authenticate(user=claimant)
    with (
        patch("api.v1.tasks.views.notify_task_updated") as notify_updated,
        patch("api.v1.tasks.views.send_task_board_update") as send_update,
    ):
        claim_response = api_client.post(claim_url)

    assert claim_response.status_code == status.HTTP_200_OK
    assert claim_response.data["assignee"]["id"] == claimant.id
    assert claim_response.data["column"] == source_column.id
    task.refresh_from_db()
    assert task.assignee_id == claimant.id
    assert task.column_id == source_column.id
    claimed_activity = task.activities.get(action="claimed")
    assert claimed_activity.actor_id == claimant.id
    assert claimed_activity.metadata == {"assignee_id": claimant.id}
    notify_updated.assert_called_once()
    send_update.assert_called_once()
    send_args, send_kwargs = send_update.call_args
    assert send_args[1:4] == ("claimed", "task", task.id)
    assert send_kwargs["extra"] == {"assignee_id": claimant.id}

    with (
        patch("api.v1.tasks.views.notify_task_updated") as notify_updated,
        patch("api.v1.tasks.views.send_task_board_update") as send_update,
    ):
        repeated_response = api_client.post(claim_url)

    assert repeated_response.status_code == status.HTTP_200_OK
    assert task.activities.filter(action="claimed").count() == 1
    notify_updated.assert_not_called()
    send_update.assert_not_called()

    api_client.force_authenticate(user=other_member)
    conflict_response = api_client.post(claim_url)
    assert conflict_response.status_code == status.HTTP_409_CONFLICT
    assert conflict_response.data["detail"] == "У задачи уже есть исполнитель."
    task.refresh_from_db()
    assert task.assignee_id == claimant.id

    completed_task = Task.objects.create(
        board=board,
        column=done_column,
        title="Завершённая задача",
        created_by=user,
    )
    completed_response = api_client.post(
        reverse("api:v1:tasks:task-claim", kwargs={"pk": completed_task.id})
    )
    assert completed_response.status_code == status.HTTP_400_BAD_REQUEST
    assert completed_response.data["detail"] == "Нельзя взять в работу завершённую задачу."
    completed_task.refresh_from_db()
    assert completed_task.assignee_id is None


def test_only_assignee_can_complete_task_in_first_done_column(api_client, user):
    assignee = make_user("task-assignee@example.com", "+79994440093")
    member = make_user("task-member@example.com", "+79994440094")
    board = TaskBoard.objects.create(name="Доска завершения", created_by=user)
    board.members.add(assignee, member)
    source_column = TaskColumn.objects.create(
        board=board,
        name="В работе",
        position=1000,
    )
    first_done_column = TaskColumn.objects.create(
        board=board,
        name="Готово",
        position=2000,
        is_done=True,
    )
    TaskColumn.objects.create(
        board=board,
        name="Архив завершенных",
        position=3000,
        is_done=True,
    )
    task = Task.objects.create(
        board=board,
        column=source_column,
        title="Завершить исполнителем",
        created_by=user,
        assignee=assignee,
    )
    complete_url = reverse("api:v1:tasks:task-complete", kwargs={"pk": task.id})

    api_client.force_authenticate(user=member)
    forbidden_response = api_client.post(complete_url)
    assert forbidden_response.status_code == status.HTTP_403_FORBIDDEN
    task.refresh_from_db()
    assert task.column_id == source_column.id
    assert task.completed_at is None

    api_client.force_authenticate(user=assignee)
    with (
        patch("api.v1.tasks.views.notify_task_moved") as notify_moved,
        patch("api.v1.tasks.views.send_task_board_update") as send_update,
    ):
        complete_response = api_client.post(complete_url)

    assert complete_response.status_code == status.HTTP_200_OK
    assert complete_response.data["column"] == first_done_column.id
    assert complete_response.data["completed_at"] is not None
    task.refresh_from_db()
    assert task.column_id == first_done_column.id
    assert task.completed_at is not None
    moved_activity = task.activities.get(action="moved")
    assert moved_activity.actor_id == assignee.id
    assert moved_activity.metadata == {
        "from_column_id": source_column.id,
        "from_column": source_column.name,
        "to_column_id": first_done_column.id,
        "to_column": first_done_column.name,
    }
    notify_moved.assert_called_once()
    send_update.assert_called_once()

    with (
        patch("api.v1.tasks.views.notify_task_moved") as notify_moved,
        patch("api.v1.tasks.views.send_task_board_update") as send_update,
    ):
        repeated_response = api_client.post(complete_url)

    assert repeated_response.status_code == status.HTTP_200_OK
    assert task.activities.filter(action="moved").count() == 1
    notify_moved.assert_not_called()
    send_update.assert_not_called()


def test_assignee_cannot_complete_task_without_done_column(api_client, user):
    board = TaskBoard.objects.create(name="Доска без финала", created_by=user)
    column = TaskColumn.objects.create(board=board, name="В работе", position=1000)
    task = Task.objects.create(
        board=board,
        column=column,
        title="Некуда завершать",
        created_by=user,
        assignee=user,
    )
    api_client.force_authenticate(user=user)

    response = api_client.post(
        reverse("api:v1:tasks:task-complete", kwargs={"pk": task.id})
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.data["detail"] == "На доске не настроена завершающая колонка."
    task.refresh_from_db()
    assert task.column_id == column.id
    assert task.completed_at is None


def test_task_rejects_column_from_another_board(api_client, user):
    api_client.force_authenticate(user=user)
    first = api_client.get(reverse("api:v1:tasks:task-board-default")).data
    second_board = TaskBoard.objects.create(
        name="Вторая доска",
        created_by=user,
    )
    other_column = TaskColumn.objects.create(
        board=second_board,
        name="Чужая колонка",
        position=1000,
    )

    response = api_client.post(
        reverse("api:v1:tasks:task-list"),
        {
            "board": first["id"],
            "column": other_column.id,
            "title": "Невалидная задача",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "column" in response.data


def test_task_attachments_follow_board_access_and_support_full_lifecycle(
    api_client,
    user,
    tmp_path,
    settings,
    django_capture_on_commit_callbacks,
):
    settings.MEDIA_ROOT = tmp_path
    member = make_user("task-file-member@example.com", "+79994440101")
    outsider = make_user("task-file-outsider@example.com", "+79994440102")
    board = TaskBoard.objects.create(name="Доска с файлами", created_by=user)
    board.members.add(member)
    column = TaskColumn.objects.create(board=board, name="Новые", position=1000)
    task = Task.objects.create(
        board=board,
        column=column,
        title="Задача с файлами",
        created_by=user,
    )
    attachments_url = reverse(
        "api:v1:tasks:task-attachments",
        kwargs={"pk": task.id},
    )

    api_client.force_authenticate(user=member)
    upload_response = api_client.post(
        attachments_url,
        {
            "files": [
                SimpleUploadedFile(
                    "brief.txt",
                    b"task brief",
                    content_type="text/plain",
                ),
                SimpleUploadedFile(
                    "report.pdf",
                    b"pdf content",
                    content_type="application/pdf",
                ),
                SimpleUploadedFile(
                    "logs.tar.gz",
                    b"archive content",
                    content_type="application/gzip",
                ),
            ]
        },
        format="multipart",
    )

    assert upload_response.status_code == status.HTTP_201_CREATED
    assert [item["file_name"] for item in upload_response.data] == [
        "brief.txt",
        "report.pdf",
        "logs.tar.gz",
    ]
    assert all(item["uploaded_by"]["id"] == member.id for item in upload_response.data)
    assert TaskAttachment.objects.filter(task=task).count() == 3

    task_response = api_client.get(
        reverse("api:v1:tasks:task-detail", kwargs={"pk": task.id})
    )
    assert task_response.status_code == status.HTTP_200_OK
    assert task_response.data["attachments_count"] == 3

    attachment = TaskAttachment.objects.get(task=task, file_name="brief.txt")
    stored_name = attachment.file.name
    download_url = reverse(
        "api:v1:tasks:task-attachment-download",
        kwargs={"pk": task.id, "attachment_id": attachment.id},
    )
    download_response = api_client.get(download_url)
    assert download_response.status_code == status.HTTP_200_OK
    assert b"".join(download_response.streaming_content) == b"task brief"
    assert download_response["X-Content-Type-Options"] == "nosniff"
    assert "attachment" in download_response["Content-Disposition"]

    api_client.force_authenticate(user=outsider)
    assert api_client.get(attachments_url).status_code == status.HTTP_404_NOT_FOUND
    assert api_client.get(download_url).status_code == status.HTTP_404_NOT_FOUND

    api_client.force_authenticate(user=member)
    delete_url = reverse(
        "api:v1:tasks:task-attachment-detail",
        kwargs={"pk": task.id, "attachment_id": attachment.id},
    )
    with django_capture_on_commit_callbacks(execute=True):
        delete_response = api_client.delete(delete_url)

    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    assert not TaskAttachment.objects.filter(id=attachment.id).exists()
    assert not attachment.file.storage.exists(stored_name)


def test_task_attachment_has_no_size_limit(
    api_client,
    user,
    settings,
):
    settings.TASK_ATTACHMENT_MAX_SIZE = 4
    board = TaskBoard.objects.create(name="Доска лимитов", created_by=user)
    column = TaskColumn.objects.create(board=board, name="Новые", position=1000)
    task = Task.objects.create(
        board=board,
        column=column,
        title="Проверить лимит файла",
        created_by=user,
    )
    api_client.force_authenticate(user=user)

    response = api_client.post(
        reverse("api:v1:tasks:task-attachments", kwargs={"pk": task.id}),
        {
            "files": SimpleUploadedFile(
                "large.txt",
                b"12345",
                content_type="text/plain",
            )
        },
        format="multipart",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert TaskAttachment.objects.filter(task=task, file_name="large.txt").exists()


def test_task_external_links_follow_board_access_and_support_lifecycle(
    api_client,
    user,
):
    member = make_user("task-link-member@example.com", "+79994440103")
    outsider = make_user("task-link-outsider@example.com", "+79994440104")
    board = TaskBoard.objects.create(name="Доска со ссылками", created_by=user)
    board.members.add(member)
    column = TaskColumn.objects.create(board=board, name="Новые", position=1000)
    task = Task.objects.create(
        board=board,
        column=column,
        title="Задача со ссылкой",
        created_by=user,
    )
    links_url = reverse(
        "api:v1:tasks:task-external-links",
        kwargs={"pk": task.id},
    )

    api_client.force_authenticate(user=member)
    invalid_response = api_client.post(
        links_url,
        {"url": "javascript:alert(1)", "title": "Опасная ссылка"},
        format="json",
    )
    assert invalid_response.status_code == status.HTTP_400_BAD_REQUEST

    create_response = api_client.post(
        links_url,
        {"url": "https://example.com/service/item/42", "title": "Карточка сервиса"},
        format="json",
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    assert create_response.data["title"] == "Карточка сервиса"
    assert create_response.data["created_by"]["id"] == member.id
    link_id = create_response.data["id"]
    assert TaskExternalLink.objects.filter(task=task).count() == 1

    duplicate_response = api_client.post(
        links_url,
        {"url": "https://example.com/service/item/42", "title": "Обновленное название"},
        format="json",
    )
    assert duplicate_response.status_code == status.HTTP_200_OK
    assert duplicate_response.data["title"] == "Обновленное название"
    assert TaskExternalLink.objects.filter(task=task).count() == 1

    task_response = api_client.get(
        reverse("api:v1:tasks:task-detail", kwargs={"pk": task.id})
    )
    assert task_response.status_code == status.HTTP_200_OK
    assert task_response.data["linked_objects_count"] == 1

    api_client.force_authenticate(user=outsider)
    assert api_client.get(links_url).status_code == status.HTTP_404_NOT_FOUND

    api_client.force_authenticate(user=member)
    delete_response = api_client.delete(
        reverse(
            "api:v1:tasks:task-external-link-detail",
            kwargs={"pk": task.id, "link_id": link_id},
        )
    )
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    assert not TaskExternalLink.objects.filter(id=link_id).exists()


def test_task_checklist_follows_board_access_and_supports_full_lifecycle(
    api_client,
):
    owner = make_user("task-checklist-owner@example.com", "+79994440105")
    member = make_user("task-checklist-member@example.com", "+79994440106")
    outsider = make_user("task-checklist-outsider@example.com", "+79994440107")
    board = TaskBoard.objects.create(name="Доска с чек-листом", created_by=owner)
    board.members.add(member)
    column = TaskColumn.objects.create(board=board, name="Новые", position=1000)
    task = Task.objects.create(
        board=board,
        column=column,
        title="Подготовить релиз",
        created_by=owner,
    )
    checklist_url = reverse(
        "api:v1:tasks:task-checklist",
        kwargs={"pk": task.id},
    )

    api_client.force_authenticate(user=member)
    invalid_response = api_client.post(
        checklist_url,
        {"title": "   "},
        format="json",
    )
    assert invalid_response.status_code == status.HTTP_400_BAD_REQUEST

    first_response = api_client.post(
        checklist_url,
        {"title": "  Проверить миграции  "},
        format="json",
    )
    second_response = api_client.post(
        checklist_url,
        {"title": "Обновить документацию"},
        format="json",
    )
    assert first_response.status_code == status.HTTP_201_CREATED
    assert second_response.status_code == status.HTTP_201_CREATED
    assert first_response.data["title"] == "Проверить миграции"
    assert first_response.data["position"] == 1000
    assert second_response.data["position"] == 2000
    assert first_response.data["created_by"]["id"] == member.id

    item_id = first_response.data["id"]
    item_url = reverse(
        "api:v1:tasks:task-checklist-item-detail",
        kwargs={"pk": task.id, "item_id": item_id},
    )
    complete_response = api_client.patch(
        item_url,
        {"is_completed": True},
        format="json",
    )
    assert complete_response.status_code == status.HTTP_200_OK
    assert complete_response.data["is_completed"] is True
    assert complete_response.data["completed_by"]["id"] == member.id
    assert complete_response.data["completed_at"] is not None

    completed_at = complete_response.data["completed_at"]
    rename_response = api_client.patch(
        item_url,
        {"title": "Проверить миграции на стенде"},
        format="json",
    )
    assert rename_response.status_code == status.HTTP_200_OK
    assert rename_response.data["title"] == "Проверить миграции на стенде"
    assert rename_response.data["completed_by"]["id"] == member.id
    assert rename_response.data["completed_at"] == completed_at

    list_response = api_client.get(checklist_url)
    assert list_response.status_code == status.HTTP_200_OK
    assert [item["title"] for item in list_response.data] == [
        "Проверить миграции на стенде",
        "Обновить документацию",
    ]

    detail_response = api_client.get(
        reverse("api:v1:tasks:task-detail", kwargs={"pk": task.id})
    )
    assert detail_response.status_code == status.HTTP_200_OK
    assert detail_response.data["checklist_total"] == 2
    assert detail_response.data["checklist_completed"] == 1

    api_client.force_authenticate(user=outsider)
    assert api_client.get(checklist_url).status_code == status.HTTP_404_NOT_FOUND
    assert (
        api_client.patch(item_url, {"is_completed": False}, format="json").status_code
        == status.HTTP_404_NOT_FOUND
    )

    api_client.force_authenticate(user=member)
    delete_response = api_client.delete(item_url)
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    assert not TaskChecklistItem.objects.filter(id=item_id).exists()

    activity_response = api_client.get(
        reverse("api:v1:tasks:task-activity", kwargs={"pk": task.id})
    )
    assert activity_response.status_code == status.HTTP_200_OK
    assert {
        "checklist_item_added",
        "checklist_item_completed",
        "checklist_item_updated",
        "checklist_item_removed",
    }.issubset({item["action"] for item in activity_response.data})


def test_create_board_accepts_members_and_departments(api_client, user):
    member = make_user("task-member@example.com", "+79994440002")
    department = Department.objects.create(name="Проектный отдел")
    api_client.force_authenticate(user=user)

    response = api_client.post(
        reverse("api:v1:tasks:task-board-list"),
        {
            "name": "Приватная доска",
            "description": "Только для проектной группы",
            "members": [member.id],
            "departments": [department.id],
        },
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert response.data["access_scope"] == "restricted"
    assert response.data["members"] == [member.id]
    assert response.data["member_details"][0]["id"] == member.id
    assert response.data["departments"] == [department.id]
    assert response.data["department_details"][0]["name"] == department.name
    assert TaskColumn.objects.filter(board_id=response.data["id"]).count() == 4


def test_private_board_is_available_only_to_owner_and_admin(api_client):
    owner = make_user("task-private-owner@example.com", "+79994440901")
    selected_member = make_user("task-private-member@example.com", "+79994440902")
    department_member = make_user("task-private-dept@example.com", "+79994440903")
    outsider = make_user("task-private-outsider@example.com", "+79994440904")
    admin = make_user(
        "task-private-admin@example.com",
        "+79994440905",
        is_staff=True,
    )
    department = Department.objects.create(name="Приватный отдел")
    EmployeeDepartment.objects.create(
        employee=department_member,
        department=department,
        is_active=True,
    )
    api_client.force_authenticate(user=owner)

    create_response = api_client.post(
        reverse("api:v1:tasks:task-board-list"),
        {
            "name": "Личная доска",
            "access_scope": "private",
            "members": [selected_member.id],
            "departments": [department.id],
        },
        format="json",
    )

    assert create_response.status_code == status.HTTP_201_CREATED
    assert create_response.data["access_scope"] == "private"
    assert create_response.data["members"] == []
    assert create_response.data["departments"] == []
    board = TaskBoard.objects.get(id=create_response.data["id"])
    assert get_task_board_recipient_ids(board) == {owner.id, admin.id}

    for hidden_user in (selected_member, department_member, outsider):
        api_client.force_authenticate(user=hidden_user)
        list_response = api_client.get(reverse("api:v1:tasks:task-board-list"))
        assert list_response.status_code == status.HTTP_200_OK
        assert board.id not in {
            item["id"] for item in list_response.data["results"]
        }
        detail_response = api_client.get(
            reverse("api:v1:tasks:task-board-detail", kwargs={"pk": board.id})
        )
        assert detail_response.status_code == status.HTTP_404_NOT_FOUND

    api_client.force_authenticate(user=admin)
    admin_response = api_client.get(
        reverse("api:v1:tasks:task-board-detail", kwargs={"pk": board.id})
    )
    assert admin_response.status_code == status.HTTP_200_OK


def test_board_member_can_access_private_board(api_client):
    owner = make_user("task-owner@example.com", "+79994440003")
    member = make_user("task-member-2@example.com", "+79994440004")
    outsider = make_user("task-outsider@example.com", "+79994440005")
    board = TaskBoard.objects.create(name="Закрытая доска", created_by=owner)
    board.members.add(member)
    column = TaskColumn.objects.create(board=board, name="Новые", position=1000)

    api_client.force_authenticate(user=member)
    member_list = api_client.get(reverse("api:v1:tasks:task-board-list"))
    assert member_list.status_code == status.HTTP_200_OK
    assert [item["id"] for item in member_list.data["results"]] == [board.id]

    create_response = api_client.post(
        reverse("api:v1:tasks:task-list"),
        {
            "board": board.id,
            "column": column.id,
            "title": "Задача участника",
        },
        format="json",
    )
    assert create_response.status_code == status.HTTP_201_CREATED

    api_client.force_authenticate(user=outsider)
    outsider_list = api_client.get(reverse("api:v1:tasks:task-board-list"))
    assert outsider_list.status_code == status.HTTP_200_OK
    assert [item["id"] for item in outsider_list.data["results"]] == []

    detail_response = api_client.get(
        reverse("api:v1:tasks:task-board-detail", kwargs={"pk": board.id})
    )
    assert detail_response.status_code == status.HTTP_404_NOT_FOUND

    hidden_create_response = api_client.post(
        reverse("api:v1:tasks:task-list"),
        {
            "board": board.id,
            "column": column.id,
            "title": "Чужая задача",
        },
        format="json",
    )
    assert hidden_create_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "board" in hidden_create_response.data


def test_department_member_can_access_department_board(api_client):
    owner = make_user("task-board-owner@example.com", "+79994440006")
    department_user = make_user("task-department-user@example.com", "+79994440007")
    outsider = make_user("task-department-outsider@example.com", "+79994440008")
    department = Department.objects.create(name="Отдел внедрения")
    EmployeeDepartment.objects.create(
        employee=department_user,
        department=department,
        is_active=True,
    )
    board = TaskBoard.objects.create(name="Доска отдела", created_by=owner)
    board.departments.add(department)

    api_client.force_authenticate(user=department_user)
    department_response = api_client.get(reverse("api:v1:tasks:task-board-list"))
    assert department_response.status_code == status.HTTP_200_OK
    assert [item["id"] for item in department_response.data["results"]] == [board.id]

    api_client.force_authenticate(user=outsider)
    outsider_response = api_client.get(reverse("api:v1:tasks:task-board-list"))
    assert outsider_response.status_code == status.HTTP_200_OK
    assert [item["id"] for item in outsider_response.data["results"]] == []


def test_task_board_realtime_recipients_match_board_access():
    owner = make_user("task-rt-owner@example.com", "+79994440009")
    member = make_user("task-rt-member@example.com", "+79994440010")
    department_user = make_user("task-rt-dept@example.com", "+79994440011")
    role_user = make_user("task-rt-role@example.com", "+79994440012")
    outsider = make_user("task-rt-outsider@example.com", "+79994440013")
    admin = make_user(
        "task-rt-admin@example.com",
        "+79994440014",
        is_staff=True,
    )
    inactive_member = make_user(
        "task-rt-inactive@example.com",
        "+79994440015",
        is_active=False,
    )
    department = Department.objects.create(name="Realtime отдел")
    role = department.roles.create(name="Внешний участник")
    EmployeeDepartment.objects.create(
        employee=department_user,
        department=department,
        is_active=True,
    )
    RoleAssignment.objects.create(
        employee=role_user,
        role=role,
        is_active=True,
    )
    board = TaskBoard.objects.create(name="Закрытая realtime доска", created_by=owner)
    board.members.add(member, inactive_member)
    board.departments.add(department)

    recipients = get_task_board_recipient_ids(board)

    assert owner.id in recipients
    assert member.id in recipients
    assert department_user.id in recipients
    assert role_user.id in recipients
    assert admin.id in recipients
    assert outsider.id not in recipients
    assert inactive_member.id not in recipients


def test_public_task_board_realtime_recipients_include_active_users():
    owner = make_user("task-rt-public-owner@example.com", "+79994440016")
    active_user = make_user("task-rt-public-user@example.com", "+79994440017")
    inactive_user = make_user(
        "task-rt-public-inactive@example.com",
        "+79994440018",
        is_active=False,
    )
    board = TaskBoard.objects.create(name="Публичная realtime доска", created_by=owner)

    recipients = get_task_board_recipient_ids(board)

    assert owner.id in recipients
    assert active_user.id in recipients
    assert inactive_user.id not in recipients


def test_task_linked_message_is_visible_by_task_access(api_client):
    owner = make_user("task-link-owner@example.com", "+79994440019")
    board_member = make_user("task-link-member@example.com", "+79994440020")
    board = TaskBoard.objects.create(name="Доска со связями", created_by=owner)
    board.members.add(board_member)
    column = TaskColumn.objects.create(board=board, name="Новые", position=1000)
    task = Task.objects.create(
        board=board,
        column=column,
        title="Разобрать сообщение",
        created_by=owner,
    )
    chat = Chat.objects.create(name="Закрытый чат", type="group", created_by=owner)
    ChatMembership.objects.create(chat=chat, user=owner, role="admin")
    message = Message.objects.create(
        chat=chat,
        author=owner,
        content="Важный контекст для задачи",
    )

    api_client.force_authenticate(user=board_member)
    denied_response = api_client.post(
        reverse("api:v1:tasks:task-linked-messages", kwargs={"pk": task.id}),
        {"message_id": message.id},
        format="json",
    )
    assert denied_response.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=owner)
    link_response = api_client.post(
        reverse("api:v1:tasks:task-linked-messages", kwargs={"pk": task.id}),
        {"message_id": message.id},
        format="json",
    )
    assert link_response.status_code == status.HTTP_201_CREATED
    assert link_response.data["message"]["content"] == "Важный контекст для задачи"
    assert link_response.data["can_open"] is True
    assert link_response.data["object_url"] == (
        f"/messages/{chat.id}?message={message.id}"
    )

    api_client.force_authenticate(user=board_member)
    linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-messages", kwargs={"pk": task.id})
    )
    assert linked_response.status_code == status.HTTP_200_OK
    assert linked_response.data[0]["message_id"] == message.id
    assert linked_response.data[0]["message"]["content"] == "Важный контекст для задачи"
    assert linked_response.data[0]["can_open"] is False
    assert linked_response.data[0]["object_url"] is None


def test_task_linked_calendar_event_respects_event_access(api_client):
    owner = make_user("task-event-owner@example.com", "+79994440024")
    board_member = make_user("task-event-member@example.com", "+79994440025")
    board = TaskBoard.objects.create(name="Доска с событиями", created_by=owner)
    board.members.add(board_member)
    column = TaskColumn.objects.create(board=board, name="Новые", position=1000)
    task = Task.objects.create(
        board=board,
        column=column,
        title="Подготовить встречу",
        created_by=owner,
    )
    calendar = Calendar.objects.create(name="Закрытый календарь", slug="closed")
    CalendarRelation.objects.create(
        calendar=calendar,
        content_type=ContentType.objects.get_for_model(User),
        object_id=owner.id,
        distinction="owner",
        inheritable=True,
    )
    now = timezone.now()
    event = Event.objects.create(
        calendar=calendar,
        title="Встреча по задаче",
        description="Обсудить детали",
        start=now,
        end=now + timedelta(hours=1),
        creator=owner,
        color_event="#38bdf8",
    )

    api_client.force_authenticate(user=board_member)
    denied_response = api_client.post(
        reverse("api:v1:tasks:task-linked-events", kwargs={"pk": task.id}),
        {"event_id": event.id},
        format="json",
    )
    assert denied_response.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=owner)
    link_response = api_client.post(
        reverse("api:v1:tasks:task-linked-events", kwargs={"pk": task.id}),
        {"event_id": event.id},
        format="json",
    )
    assert link_response.status_code == status.HTTP_201_CREATED
    assert link_response.data["event"]["title"] == "Встреча по задаче"
    assert link_response.data["can_open"] is True
    assert link_response.data["object_url"] == (
        f"/calendar?calendar={calendar.id}&event={event.id}"
    )

    api_client.force_authenticate(user=board_member)
    linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-events", kwargs={"pk": task.id})
    )
    assert linked_response.status_code == status.HTTP_200_OK
    assert linked_response.data[0]["event_id"] == event.id
    assert linked_response.data[0]["event"]["title"] == "Встреча по задаче"
    assert linked_response.data[0]["can_open"] is False
    assert linked_response.data[0]["object_url"] is None

    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-event-tasks"),
        {"event_id": event.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=owner)
    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-event-tasks"),
        {"event_id": event.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_200_OK
    assert reverse_linked_response.data[0]["id"] == task.id
    assert reverse_linked_response.data[0]["title"] == "Подготовить встречу"
    assert reverse_linked_response.data[0]["board_name"] == "Доска с событиями"


def test_task_linked_document_respects_document_access(api_client):
    owner = make_user("task-doc-owner@example.com", "+79994440026")
    board_member = make_user("task-doc-member@example.com", "+79994440027")
    board = TaskBoard.objects.create(
        name="Доска с документами",
        created_by=owner,
    )
    board.members.add(board_member)
    column = TaskColumn.objects.create(
        board=board,
        name="Новые",
        position=1000,
    )
    task = Task.objects.create(
        board=board,
        column=column,
        title="Проверить регламент",
        created_by=owner,
    )
    document = Document.objects.create(
        title="Регламент доступа",
        description="Закрытый документ",
        uploaded_by=owner,
        sent_to_all=False,
        is_regulation=True,
    )

    api_client.force_authenticate(user=board_member)
    denied_response = api_client.post(
        reverse("api:v1:tasks:task-linked-documents", kwargs={"pk": task.id}),
        {"document_id": document.id},
        format="json",
    )
    assert denied_response.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=owner)
    link_response = api_client.post(
        reverse("api:v1:tasks:task-linked-documents", kwargs={"pk": task.id}),
        {"document_id": document.id},
        format="json",
    )
    assert link_response.status_code == status.HTTP_201_CREATED
    assert link_response.data["document"]["title"] == "Регламент доступа"
    assert link_response.data["document"]["is_regulation"] is True
    assert link_response.data["can_open"] is True
    assert link_response.data["object_url"] == (
        f"/documents?document={document.id}"
    )

    api_client.force_authenticate(user=board_member)
    linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-documents", kwargs={"pk": task.id})
    )
    assert linked_response.status_code == status.HTTP_200_OK
    assert linked_response.data[0]["document_id"] == document.id
    assert linked_response.data[0]["document"]["title"] == "Регламент доступа"
    assert linked_response.data[0]["can_open"] is False
    assert linked_response.data[0]["object_url"] is None

    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-document-tasks"),
        {"document_id": document.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=owner)
    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-document-tasks"),
        {"document_id": document.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_200_OK
    assert reverse_linked_response.data[0]["id"] == task.id
    assert reverse_linked_response.data[0]["title"] == "Проверить регламент"
    assert (
        reverse_linked_response.data[0]["linked_documents_count"] == 1
    )


def test_task_linked_request_respects_request_access(api_client):
    owner = make_user("task-request-owner@example.com", "+79994440028")
    board_member = make_user("task-request-member@example.com", "+79994440029")
    board = TaskBoard.objects.create(
        name="Доска с заявлениями",
        created_by=owner,
    )
    board.members.add(board_member)
    column = TaskColumn.objects.create(
        board=board,
        name="Новые",
        position=1000,
    )
    task = Task.objects.create(
        board=board,
        column=column,
        title="Проверить заявление",
        created_by=owner,
    )
    employee_request = EmployeeRequest.objects.create(
        employee=owner,
        type="vacation",
        title="Отпуск",
        comment="Заявление к задаче",
    )

    api_client.force_authenticate(user=board_member)
    denied_response = api_client.post(
        reverse("api:v1:tasks:task-linked-requests", kwargs={"pk": task.id}),
        {"request_id": employee_request.id},
        format="json",
    )
    assert denied_response.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=owner)
    link_response = api_client.post(
        reverse("api:v1:tasks:task-linked-requests", kwargs={"pk": task.id}),
        {"request_id": employee_request.id},
        format="json",
    )
    assert link_response.status_code == status.HTTP_201_CREATED
    assert link_response.data["request"]["title"] == "Отпуск"
    assert link_response.data["request"]["comment"] == "Заявление к задаче"
    assert link_response.data["can_open"] is True
    assert link_response.data["object_url"] == (
        f"/requests?request={employee_request.id}"
    )

    api_client.force_authenticate(user=board_member)
    linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-requests", kwargs={"pk": task.id})
    )
    assert linked_response.status_code == status.HTTP_200_OK
    assert linked_response.data[0]["request_id"] == employee_request.id
    assert linked_response.data[0]["request"]["title"] == "Отпуск"
    assert linked_response.data[0]["can_open"] is False
    assert linked_response.data[0]["object_url"] is None

    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-request-tasks"),
        {"request_id": employee_request.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=owner)
    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-request-tasks"),
        {"request_id": employee_request.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_200_OK
    assert reverse_linked_response.data[0]["id"] == task.id
    assert reverse_linked_response.data[0]["title"] == "Проверить заявление"
    assert (
        reverse_linked_response.data[0]["linked_requests_count"] == 1
    )


def test_task_linked_procurement_request_respects_procurement_access(api_client):
    owner = make_user("task-proc-owner@example.com", "+79994440030")
    board_member = make_user("task-proc-member@example.com", "+79994440031")
    department = Department.objects.create(name="Закупочный отдел тест")
    board = TaskBoard.objects.create(
        name="Доска с закупками",
        created_by=owner,
    )
    board.members.add(board_member)
    column = TaskColumn.objects.create(
        board=board,
        name="Новые",
        position=1000,
        color="#38bdf8",
    )
    task = Task.objects.create(
        board=board,
        column=column,
        title="Проверить закупку",
        created_by=owner,
    )
    procurement_request = ProcurementRequest.objects.create(
        title="Закупка мониторов",
        description="Закупка к задаче",
        department=department,
        requestor=owner,
        status=ProcurementStatus.DRAFT,
        urgency=UrgencyLevel.HIGH,
    )

    api_client.force_authenticate(user=board_member)
    denied_response = api_client.post(
        reverse(
            "api:v1:tasks:task-linked-procurement-requests",
            kwargs={"pk": task.id},
        ),
        {"procurement_request_id": procurement_request.id},
        format="json",
    )
    assert denied_response.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=owner)
    link_response = api_client.post(
        reverse(
            "api:v1:tasks:task-linked-procurement-requests",
            kwargs={"pk": task.id},
        ),
        {"procurement_request_id": procurement_request.id},
        format="json",
    )
    assert link_response.status_code == status.HTTP_201_CREATED
    assert link_response.data["procurement_request"]["title"] == "Закупка мониторов"
    assert link_response.data["procurement_request"]["status"] == ProcurementStatus.DRAFT
    assert link_response.data["procurement_request"]["urgency"] == UrgencyLevel.HIGH
    assert link_response.data["can_open"] is True
    assert link_response.data["object_url"] == (
        f"/procurement?request={procurement_request.id}"
    )

    api_client.force_authenticate(user=board_member)
    linked_response = api_client.get(
        reverse(
            "api:v1:tasks:task-linked-procurement-requests",
            kwargs={"pk": task.id},
        )
    )
    assert linked_response.status_code == status.HTTP_200_OK
    assert linked_response.data[0]["procurement_request_id"] == procurement_request.id
    assert linked_response.data[0]["procurement_request"]["title"] == (
        "Закупка мониторов"
    )
    assert linked_response.data[0]["can_open"] is False
    assert linked_response.data[0]["object_url"] is None

    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-procurement-request-tasks"),
        {"procurement_request_id": procurement_request.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=owner)
    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-procurement-request-tasks"),
        {"procurement_request_id": procurement_request.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_200_OK
    assert reverse_linked_response.data[0]["id"] == task.id
    assert reverse_linked_response.data[0]["title"] == "Проверить закупку"
    assert reverse_linked_response.data[0]["linked_procurement_requests_count"] == 1


def test_task_linked_employee_respects_task_board_access(api_client):
    owner = make_user("task-employee-owner@example.com", "+79994440032")
    board_member = make_user("task-employee-member@example.com", "+79994440033")
    outsider = make_user("task-employee-outsider@example.com", "+79994440034")
    linked_employee = make_user(
        "task-employee-linked@example.com",
        "+79994440035",
        first_name="Гарик",
        last_name="Мусик",
    )
    board = TaskBoard.objects.create(
        name="Доска с сотрудниками",
        created_by=owner,
    )
    board.members.add(board_member)
    column = TaskColumn.objects.create(
        board=board,
        name="Новые",
        position=1000,
        color="#38bdf8",
    )
    task = Task.objects.create(
        board=board,
        column=column,
        title="Подготовить сотрудника",
        created_by=owner,
    )

    api_client.force_authenticate(user=board_member)
    link_response = api_client.post(
        reverse("api:v1:tasks:task-linked-employees", kwargs={"pk": task.id}),
        {"employee_id": linked_employee.id},
        format="json",
    )
    assert link_response.status_code == status.HTTP_201_CREATED
    assert link_response.data["employee_id"] == linked_employee.id
    assert link_response.data["employee"]["full_name"] == "Мусик Гарик"
    assert link_response.data["can_open"] is True
    assert link_response.data["object_url"] == f"/users/{linked_employee.id}"

    linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-employees", kwargs={"pk": task.id})
    )
    assert linked_response.status_code == status.HTTP_200_OK
    assert linked_response.data[0]["employee"]["email"] == linked_employee.email

    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-employee-tasks"),
        {"employee_id": linked_employee.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_200_OK
    assert reverse_linked_response.data[0]["id"] == task.id
    assert reverse_linked_response.data[0]["linked_employees_count"] == 1

    api_client.force_authenticate(user=outsider)
    task_detail_response = api_client.get(
        reverse("api:v1:tasks:task-linked-employees", kwargs={"pk": task.id})
    )
    assert task_detail_response.status_code == status.HTTP_404_NOT_FOUND

    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-employee-tasks"),
        {"employee_id": linked_employee.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_200_OK
    assert reverse_linked_response.data == []


def test_task_linked_guest_respects_task_board_access(api_client):
    owner = make_user("task-guest-owner@example.com", "+79994440036")
    board_member = make_user("task-guest-member@example.com", "+79994440037")
    outsider = make_user("task-guest-outsider@example.com", "+79994440038")
    guest = Guest.objects.create(
        first_name="Иван",
        last_name="Гость",
        organization="Vendor",
        email="guest@example.com",
        created_by=owner,
    )
    board = TaskBoard.objects.create(
        name="Доска с гостями",
        created_by=owner,
    )
    board.members.add(board_member)
    column = TaskColumn.objects.create(
        board=board,
        name="Новые",
        position=1000,
        color="#38bdf8",
    )
    task = Task.objects.create(
        board=board,
        column=column,
        title="Проверить гостя",
        created_by=owner,
    )

    api_client.force_authenticate(user=board_member)
    link_response = api_client.post(
        reverse("api:v1:tasks:task-linked-guests", kwargs={"pk": task.id}),
        {"guest_id": guest.id},
        format="json",
    )
    assert link_response.status_code == status.HTTP_201_CREATED
    assert link_response.data["guest_id"] == guest.id
    assert link_response.data["guest"]["full_name"] == "Гость Иван"
    assert link_response.data["can_open"] is True
    assert link_response.data["object_url"] == f"/guests?guest={guest.id}"

    linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-guests", kwargs={"pk": task.id})
    )
    assert linked_response.status_code == status.HTTP_200_OK
    assert linked_response.data[0]["guest"]["email"] == guest.email

    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-guest-tasks"),
        {"guest_id": guest.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_200_OK
    assert reverse_linked_response.data[0]["id"] == task.id
    assert reverse_linked_response.data[0]["linked_guests_count"] == 1

    api_client.force_authenticate(user=outsider)
    task_detail_response = api_client.get(
        reverse("api:v1:tasks:task-linked-guests", kwargs={"pk": task.id})
    )
    assert task_detail_response.status_code == status.HTTP_404_NOT_FOUND

    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-guest-tasks"),
        {"guest_id": guest.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_200_OK
    assert reverse_linked_response.data == []


def test_task_linked_post_respects_task_board_access(api_client):
    owner = make_user("task-post-owner@example.com", "+79994440045")
    board_member = make_user("task-post-member@example.com", "+79994440046")
    outsider = make_user("task-post-outsider@example.com", "+79994440047")
    post = Post.objects.create(
        author=owner,
        type="company",
        title="Новости задач",
        body="Связать публикацию с задачей",
    )
    board = TaskBoard.objects.create(
        name="Доска с новостями",
        created_by=owner,
    )
    board.members.add(board_member)
    column = TaskColumn.objects.create(
        board=board,
        name="Новые",
        position=1000,
        color="#38bdf8",
    )
    task = Task.objects.create(
        board=board,
        column=column,
        title="Обработать новость",
        created_by=owner,
    )

    api_client.force_authenticate(user=board_member)
    link_response = api_client.post(
        reverse("api:v1:tasks:task-linked-posts", kwargs={"pk": task.id}),
        {"post_id": post.id},
        format="json",
    )
    assert link_response.status_code == status.HTTP_201_CREATED
    assert link_response.data["post_id"] == post.id
    assert link_response.data["post"]["title"] == "Новости задач"
    assert link_response.data["post"]["body"] == "Связать публикацию с задачей"
    assert link_response.data["can_open"] is True
    assert link_response.data["object_url"] == f"/?post={post.id}"

    linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-posts", kwargs={"pk": task.id})
    )
    assert linked_response.status_code == status.HTTP_200_OK
    assert linked_response.data[0]["post"]["author"]["id"] == owner.id

    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-post-tasks"),
        {"post_id": post.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_200_OK
    assert reverse_linked_response.data[0]["id"] == task.id
    assert reverse_linked_response.data[0]["linked_posts_count"] == 1

    api_client.force_authenticate(user=outsider)
    task_detail_response = api_client.get(
        reverse("api:v1:tasks:task-linked-posts", kwargs={"pk": task.id})
    )
    assert task_detail_response.status_code == status.HTTP_404_NOT_FOUND

    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-post-tasks"),
        {"post_id": post.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_200_OK
    assert reverse_linked_response.data == []


def test_task_linked_guest_visit_respects_visit_access(api_client):
    owner = make_user("task-guest-visit-owner@example.com", "+79994440039")
    inviter = make_user("task-guest-visit-inviter@example.com", "+79994440040")
    outsider = make_user("task-guest-visit-outsider@example.com", "+79994440041")
    guest = Guest.objects.create(
        first_name="Анна",
        last_name="Визит",
        created_by=owner,
    )
    visit = GuestVisit.objects.create(
        guest=guest,
        inviter=inviter,
        purpose="Встреча с подрядчиком",
        access_starts_at=timezone.now(),
        access_expires_at=timezone.now() + timedelta(days=1),
    )
    board = TaskBoard.objects.create(
        name="Доска с визитами",
        created_by=owner,
    )
    board.members.add(inviter)
    column = TaskColumn.objects.create(
        board=board,
        name="Новые",
        position=1000,
        color="#38bdf8",
    )
    task = Task.objects.create(
        board=board,
        column=column,
        title="Проверить гостевой визит",
        created_by=owner,
    )

    api_client.force_authenticate(user=inviter)
    link_response = api_client.post(
        reverse("api:v1:tasks:task-linked-guest-visits", kwargs={"pk": task.id}),
        {"guest_visit_id": visit.id},
        format="json",
    )
    assert link_response.status_code == status.HTTP_201_CREATED
    assert link_response.data["guest_visit_id"] == visit.id
    assert link_response.data["guest_visit"]["guest"]["full_name"] == "Визит Анна"
    assert link_response.data["can_open"] is True
    assert link_response.data["object_url"] == f"/guests?visit={visit.id}"

    linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-guest-visits", kwargs={"pk": task.id})
    )
    assert linked_response.status_code == status.HTTP_200_OK
    assert linked_response.data[0]["guest_visit"]["purpose"] == "Встреча с подрядчиком"

    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-guest-visit-tasks"),
        {"guest_visit_id": visit.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_200_OK
    assert reverse_linked_response.data[0]["id"] == task.id
    assert reverse_linked_response.data[0]["linked_guest_visits_count"] == 1

    api_client.force_authenticate(user=outsider)
    task_detail_response = api_client.get(
        reverse("api:v1:tasks:task-linked-guest-visits", kwargs={"pk": task.id})
    )
    assert task_detail_response.status_code == status.HTTP_404_NOT_FOUND

    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-guest-visit-tasks"),
        {"guest_visit_id": visit.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_403_FORBIDDEN


def test_task_linked_attendance_record_respects_record_access(api_client):
    owner = make_user("task-attendance-owner@example.com", "+79994440042")
    employee = make_user(
        "task-attendance-employee@example.com",
        "+79994440043",
        first_name="Петр",
        last_name="Посещаемый",
    )
    outsider = make_user("task-attendance-outsider@example.com", "+79994440044")
    run = AttendanceAnalysisRun.objects.create(
        employee=employee,
        period_start=date(2026, 4, 20),
        period_end=date(2026, 4, 20),
        triggered_by=owner,
    )
    record = AttendanceRecord.objects.create(
        analysis_run=run,
        employee=employee,
        date=date(2026, 4, 20),
        display_name="Посещаемый Петр",
        arrival_time="09:10",
        departure_time="18:05",
        work_hours=8.9,
        expected_hours=9,
        is_late=True,
        late_minutes=10,
    )
    board = TaskBoard.objects.create(
        name="Доска с посещаемостью",
        created_by=owner,
    )
    board.members.add(employee)
    column = TaskColumn.objects.create(
        board=board,
        name="Новые",
        position=1000,
        color="#38bdf8",
    )
    task = Task.objects.create(
        board=board,
        column=column,
        title="Проверить посещаемость",
        created_by=owner,
    )

    api_client.force_authenticate(user=employee)
    link_response = api_client.post(
        reverse(
            "api:v1:tasks:task-linked-attendance-records",
            kwargs={"pk": task.id},
        ),
        {"attendance_record_id": record.id},
        format="json",
    )
    assert link_response.status_code == status.HTTP_201_CREATED
    assert link_response.data["attendance_record_id"] == record.id
    assert link_response.data["attendance_record"]["employee"]["id"] == employee.id
    assert str(link_response.data["attendance_record"]["date"]) == "2026-04-20"
    assert link_response.data["can_open"] is True
    assert link_response.data["object_url"] == f"/attendance?record={record.id}"

    linked_response = api_client.get(
        reverse(
            "api:v1:tasks:task-linked-attendance-records",
            kwargs={"pk": task.id},
        )
    )
    assert linked_response.status_code == status.HTTP_200_OK
    assert linked_response.data[0]["attendance_record"]["arrival_time"] == "09:10"

    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-attendance-record-tasks"),
        {"attendance_record_id": record.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_200_OK
    assert reverse_linked_response.data[0]["id"] == task.id
    assert reverse_linked_response.data[0]["linked_attendance_records_count"] == 1

    api_client.force_authenticate(user=outsider)
    reverse_linked_response = api_client.get(
        reverse("api:v1:tasks:task-linked-attendance-record-tasks"),
        {"attendance_record_id": record.id},
    )
    assert reverse_linked_response.status_code == status.HTTP_403_FORBIDDEN


def test_task_activity_records_core_actions(api_client, user):
    api_client.force_authenticate(user=user)
    board_response = api_client.get(
        reverse("api:v1:tasks:task-board-default")
    )
    board_id = board_response.data["id"]
    columns = board_response.data["columns"]
    source_column = columns[0]
    target_column = columns[1]

    create_response = api_client.post(
        reverse("api:v1:tasks:task-list"),
        {
            "board": board_id,
            "column": source_column["id"],
            "title": "История задачи",
            "description": "",
            "priority": "medium",
        },
        format="json",
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    task_id = create_response.data["id"]

    update_response = api_client.patch(
        reverse("api:v1:tasks:task-detail", kwargs={"pk": task_id}),
        {"title": "История задачи обновлена"},
        format="json",
    )
    assert update_response.status_code == status.HTTP_200_OK

    move_response = api_client.post(
        reverse("api:v1:tasks:task-move", kwargs={"pk": task_id}),
        {"column": target_column["id"]},
        format="json",
    )
    assert move_response.status_code == status.HTTP_200_OK

    activity_response = api_client.get(
        reverse("api:v1:tasks:task-activity", kwargs={"pk": task_id})
    )
    assert activity_response.status_code == status.HTTP_200_OK
    actions = [item["action"] for item in activity_response.data]
    assert actions == ["moved", "updated", "created"]
    assert activity_response.data[0]["metadata"]["from_column"] == source_column["name"]
    assert activity_response.data[0]["metadata"]["to_column"] == target_column["name"]
    assert "title" in activity_response.data[1]["metadata"]["fields"]


def test_chat_message_serialization_shows_only_accessible_linked_tasks(api_client):
    owner = make_user("task-link-chat-owner@example.com", "+79994440021")
    visible_user = make_user("task-link-chat-visible@example.com", "+79994440022")
    hidden_user = make_user("task-link-chat-hidden@example.com", "+79994440023")
    board = TaskBoard.objects.create(name="Видимая доска", created_by=owner)
    board.members.add(visible_user)
    column = TaskColumn.objects.create(
        board=board,
        name="Новые",
        position=1000,
        color="#16a34a",
    )
    task = Task.objects.create(
        board=board,
        column=column,
        title="Задача из сообщения",
        created_by=owner,
        priority="critical",
    )
    chat = Chat.objects.create(name="Общий чат", type="group", created_by=owner)
    ChatMembership.objects.create(chat=chat, user=owner, role="admin")
    ChatMembership.objects.create(chat=chat, user=visible_user, role="member")
    ChatMembership.objects.create(chat=chat, user=hidden_user, role="member")
    message = Message.objects.create(
        chat=chat,
        author=owner,
        content="Сообщение с задачей",
    )

    api_client.force_authenticate(user=owner)
    api_client.post(
        reverse("api:v1:tasks:task-linked-messages", kwargs={"pk": task.id}),
        {"message_id": message.id},
        format="json",
    )

    api_client.force_authenticate(user=visible_user)
    visible_response = api_client.get(
        reverse("api:v1:chats-messages", kwargs={"pk": chat.id})
    )
    assert visible_response.status_code == status.HTTP_200_OK
    linked_task = visible_response.data["messages"][0]["linked_tasks"][0]
    assert linked_task["id"] == task.id
    assert linked_task["column_id"] == column.id
    assert linked_task["column_name"] == "Новые"
    assert linked_task["column_color"] == "#16a34a"
    assert linked_task["priority"] == "critical"
    assert linked_task["priority_display"] == "Критический"

    api_client.force_authenticate(user=hidden_user)
    hidden_response = api_client.get(
        reverse("api:v1:chats-messages", kwargs={"pk": chat.id})
    )
    assert hidden_response.status_code == status.HTTP_200_OK
    assert hidden_response.data["messages"][0]["linked_tasks"] == []


def test_task_comments_use_communications_and_update_count(api_client, user):
    api_client.force_authenticate(user=user)
    board = TaskBoard.objects.create(
        name="Доска с комментариями",
        created_by=user,
    )
    column = TaskColumn.objects.create(board=board, name="Новые", position=1000)
    task = Task.objects.create(
        board=board,
        column=column,
        title="Задача с обсуждением",
        created_by=user,
    )

    detail_response = api_client.get(
        reverse("api:v1:tasks:task-detail", kwargs={"pk": task.id})
    )
    assert detail_response.status_code == status.HTTP_200_OK
    assert detail_response.data["comments_count"] == 0

    empty_response = api_client.post(
        reverse("api:v1:tasks:task-comments", kwargs={"pk": task.id}),
        {"text": ""},
        format="json",
    )
    assert empty_response.status_code == status.HTTP_400_BAD_REQUEST

    create_response = api_client.post(
        reverse("api:v1:tasks:task-comments", kwargs={"pk": task.id}),
        {"text": "Нужно уточнить детали"},
        format="json",
    )
    assert create_response.status_code == status.HTTP_201_CREATED
    assert create_response.data["task"] == task.id
    assert create_response.data["text"] == "Нужно уточнить детали"
    assert create_response.data["author"]["id"] == user.id

    task_ct = ContentType.objects.get_for_model(Task)
    chat = Chat.objects.get(
        type="comments",
        context_content_type=task_ct,
        context_object_id=task.id,
    )
    message = Message.objects.get(chat=chat)
    assert message.content == "Нужно уточнить детали"
    assert message.author == user
    added_activity = task.activities.get(action="comment_added")
    assert added_activity.actor == user
    assert added_activity.object_kind == "comment"
    assert added_activity.object_id == message.id
    assert added_activity.metadata == {"comment_text": "Нужно уточнить детали"}

    comment_detail_url = reverse(
        "api:v1:tasks:task-delete-comment",
        kwargs={"pk": task.id, "comment_id": message.id},
    )
    other_user = make_user("task-comment-editor@example.com", "+79994440027")
    api_client.force_authenticate(user=other_user)
    forbidden_edit_response = api_client.patch(
        comment_detail_url,
        {"text": "Чужое изменение"},
        format="json",
    )
    assert forbidden_edit_response.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=user)
    empty_edit_response = api_client.patch(
        comment_detail_url,
        {"text": ""},
        format="json",
    )
    assert empty_edit_response.status_code == status.HTTP_400_BAD_REQUEST

    edit_response = api_client.patch(
        comment_detail_url,
        {"text": "Детали уже уточнены"},
        format="json",
    )
    assert edit_response.status_code == status.HTTP_200_OK
    assert edit_response.data["text"] == "Детали уже уточнены"
    assert edit_response.data["is_edited"] is True
    assert edit_response.data["edited_at"] is not None

    message.refresh_from_db()
    assert message.content == "Детали уже уточнены"
    edit_history = message.edit_history_records.get()
    assert edit_history.previous_content == "Нужно уточнить детали"
    assert edit_history.edited_by == user
    edited_activity = task.activities.get(action="comment_edited")
    assert edited_activity.actor == user
    assert edited_activity.object_kind == "comment"
    assert edited_activity.object_id == message.id
    assert edited_activity.metadata == {
        "previous_text": "Нужно уточнить детали",
        "comment_text": "Детали уже уточнены",
    }

    list_response = api_client.get(
        reverse("api:v1:tasks:task-comments", kwargs={"pk": task.id})
    )
    assert list_response.status_code == status.HTTP_200_OK
    assert [comment["text"] for comment in list_response.data] == [
        "Детали уже уточнены"
    ]
    assert list_response.data[0]["is_edited"] is True

    detail_response = api_client.get(
        reverse("api:v1:tasks:task-detail", kwargs={"pk": task.id})
    )
    assert detail_response.data["comments_count"] == 1

    delete_response = api_client.delete(
        comment_detail_url
    )
    assert delete_response.status_code == status.HTTP_204_NO_CONTENT
    message.refresh_from_db()
    assert message.is_deleted is True
    removed_activity = task.activities.get(action="comment_removed")
    assert removed_activity.actor == user
    assert removed_activity.object_kind == "comment"
    assert removed_activity.object_id == message.id
    assert removed_activity.metadata == {"comment_text": "Детали уже уточнены"}

    activity_response = api_client.get(
        reverse("api:v1:tasks:task-activity", kwargs={"pk": task.id})
    )
    assert activity_response.status_code == status.HTTP_200_OK
    assert [item["action"] for item in activity_response.data] == [
        "comment_removed",
        "comment_edited",
        "comment_added",
    ]

    assert api_client.get(
        reverse("api:v1:tasks:task-comments", kwargs={"pk": task.id})
    ).data == []
    assert api_client.get(
        reverse("api:v1:tasks:task-detail", kwargs={"pk": task.id})
    ).data["comments_count"] == 0


def test_task_comments_chat_access_follows_board_access(api_client):
    owner = make_user("task-comments-owner@example.com", "+79994440024")
    member = make_user("task-comments-member@example.com", "+79994440025")
    outsider = make_user("task-comments-outsider@example.com", "+79994440026")
    board = TaskBoard.objects.create(name="Закрытая доска", created_by=owner)
    board.members.add(member)
    column = TaskColumn.objects.create(board=board, name="Новые", position=1000)
    task = Task.objects.create(
        board=board,
        column=column,
        title="Закрытая задача",
        created_by=owner,
    )

    api_client.force_authenticate(user=owner)
    create_response = api_client.post(
        reverse("api:v1:tasks:task-comments", kwargs={"pk": task.id}),
        {"text": "Комментарий закрытой доски"},
        format="json",
    )
    assert create_response.status_code == status.HTTP_201_CREATED

    chat = Chat.objects.get(
        type="comments",
        context_content_type=ContentType.objects.get_for_model(Task),
        context_object_id=task.id,
    )

    api_client.force_authenticate(user=member)
    member_response = api_client.get(
        reverse("api:v1:chats-messages", kwargs={"pk": chat.id})
    )
    assert member_response.status_code == status.HTTP_200_OK
    assert member_response.data["messages"][0]["content"] == (
        "Комментарий закрытой доски"
    )

    api_client.force_authenticate(user=outsider)
    outsider_response = api_client.get(
        reverse("api:v1:chats-messages", kwargs={"pk": chat.id})
    )
    assert outsider_response.status_code == status.HTTP_403_FORBIDDEN
