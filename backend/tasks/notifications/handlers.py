from __future__ import annotations

from datetime import datetime, time, timedelta

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from notifications.models import Notification
from notifications.signals import notify

from tasks.models import Task, TaskLinkedObject, TaskLinkedObjectKind

from .config import ActionURLs, MessageTemplates, NotificationVerbs

User = get_user_model()


def _actor_id(actor) -> int | None:
    return getattr(actor, "id", None)


def _actor_name(actor) -> str:
    if not actor:
        return "Система"
    return actor.get_full_name() or getattr(actor, "email", "") or str(actor)


def _task_data(task: Task, title: str, extra: dict | None = None) -> dict:
    data = {
        "title": title,
        "task_id": task.id,
        "task_title": task.title,
        "board_id": task.board_id,
        "board_name": task.board.name,
        "column_id": task.column_id,
        "column_name": task.column.name,
    }
    if extra:
        data.update(extra)
    return data


def _send_task_notification(
    *,
    recipient,
    verb: str,
    task: Task,
    title: str,
    description: str,
    actor=None,
    action_object=None,
    extra_data: dict | None = None,
):
    if not recipient or not getattr(recipient, "is_active", False):
        return
    if _actor_id(actor) and recipient.id == _actor_id(actor):
        return

    notify.send(
        sender=actor,
        recipient=recipient,
        verb=verb,
        action_object=action_object or task,
        target=task,
        description=description,
        action_url=ActionURLs.task_detail(task),
        data=_task_data(task, title, extra_data),
    )


def _notify_many(
    recipients,
    *,
    verb: str,
    task: Task,
    title: str,
    description: str,
    actor=None,
    action_object=None,
    extra_data: dict | None = None,
):
    seen = set()
    for recipient in recipients:
        if not recipient or recipient.id in seen:
            continue
        seen.add(recipient.id)
        _send_task_notification(
            recipient=recipient,
            verb=verb,
            task=task,
            title=title,
            description=description,
            actor=actor,
            action_object=action_object,
            extra_data=extra_data,
        )


def _linked_employee_ids(task: Task) -> set[int]:
    employee_ct = ContentType.objects.get_for_model(User)
    return set(
        task.linked_objects.filter(
            kind=TaskLinkedObjectKind.EMPLOYEE,
            content_type=employee_ct,
        ).values_list("object_id", flat=True)
    )


def _task_recipient_ids(
    task: Task,
    *,
    include_created_by: bool = True,
    include_assignee: bool = True,
    include_linked_employees: bool = True,
    include_commenters: bool = False,
) -> set[int]:
    recipient_ids = set()
    if include_created_by and task.created_by_id:
        recipient_ids.add(task.created_by_id)
    if include_assignee and task.assignee_id:
        recipient_ids.add(task.assignee_id)
    if include_linked_employees:
        recipient_ids.update(_linked_employee_ids(task))
    if include_commenters:
        from communications import comments_helpers

        recipient_ids.update(
            message.author_id
            for message in comments_helpers.get_comments(task)
            if message.author_id
        )
    return recipient_ids


def _task_recipients(task: Task, **kwargs):
    recipient_ids = _task_recipient_ids(task, **kwargs)
    if not recipient_ids:
        return []
    return User.objects.filter(id__in=recipient_ids, is_active=True)


def notify_task_created(task: Task, actor=None):
    if not task.assignee_id:
        return
    title, description = MessageTemplates.task_assigned(task, _actor_name(actor))
    _send_task_notification(
        recipient=task.assignee,
        verb=NotificationVerbs.TASK_ASSIGNED,
        task=task,
        title=title,
        description=description,
        actor=actor,
        extra_data={"assignee_id": task.assignee_id},
    )


def notify_task_updated(task: Task, actor, previous: dict, current: dict):
    previous_assignee_id = previous.get("assignee_id")
    current_assignee_id = current.get("assignee_id")
    if previous_assignee_id != current_assignee_id:
        title, description = (
            MessageTemplates.task_assigned(task, _actor_name(actor))
            if previous_assignee_id is None
            else MessageTemplates.task_reassigned(task, _actor_name(actor))
        )
        recipients = []
        if current_assignee_id:
            recipients.extend(User.objects.filter(id=current_assignee_id))
        if previous_assignee_id:
            recipients.extend(User.objects.filter(id=previous_assignee_id))
        _notify_many(
            recipients,
            verb=(
                NotificationVerbs.TASK_ASSIGNED
                if previous_assignee_id is None
                else NotificationVerbs.TASK_REASSIGNED
            ),
            task=task,
            title=title,
            description=description,
            actor=actor,
            extra_data={
                "old_assignee_id": previous_assignee_id,
                "assignee_id": current_assignee_id,
            },
        )

    if previous.get("due_date") != current.get("due_date"):
        title, description = MessageTemplates.task_due_date_changed(
            task,
            _actor_name(actor),
            previous.get("due_date"),
            current.get("due_date"),
        )
        _notify_many(
            _task_recipients(task, include_commenters=True),
            verb=NotificationVerbs.TASK_DUE_DATE_CHANGED,
            task=task,
            title=title,
            description=description,
            actor=actor,
            extra_data={
                "old_due_date": previous.get("due_date"),
                "due_date": current.get("due_date"),
            },
        )


def notify_task_moved(task: Task, actor, old_column, new_column):
    if old_column.id == new_column.id:
        return
    if new_column.is_done and not old_column.is_done:
        title, description = MessageTemplates.task_completed(
            task,
            _actor_name(actor),
        )
        verb = NotificationVerbs.TASK_COMPLETED
    elif old_column.is_done and not new_column.is_done:
        title, description = MessageTemplates.task_reopened(
            task,
            _actor_name(actor),
        )
        verb = NotificationVerbs.TASK_REOPENED
    else:
        return

    _notify_many(
        _task_recipients(task, include_commenters=True),
        verb=verb,
        task=task,
        title=title,
        description=description,
        actor=actor,
        extra_data={
            "from_column_id": old_column.id,
            "from_column": old_column.name,
            "to_column_id": new_column.id,
            "to_column": new_column.name,
        },
    )


def notify_task_comment(task: Task, message):
    actor = message.author
    title, description = MessageTemplates.task_comment(
        task,
        _actor_name(actor),
        message.content or "",
    )
    _notify_many(
        _task_recipients(task, include_commenters=True),
        verb=NotificationVerbs.TASK_COMMENT,
        task=task,
        title=title,
        description=description,
        actor=actor,
        action_object=message,
        extra_data={"comment_id": message.id},
    )


def notify_task_linked_object(link: TaskLinkedObject):
    task = link.task
    actor = link.created_by
    object_type = link.get_kind_display()
    title, description = MessageTemplates.task_linked_object_added(
        task,
        _actor_name(actor),
        object_type,
    )
    recipient_ids = _task_recipient_ids(task, include_commenters=True)
    if link.kind == TaskLinkedObjectKind.EMPLOYEE:
        recipient_ids.add(int(link.object_id))
    recipients = User.objects.filter(id__in=recipient_ids, is_active=True)
    _notify_many(
        recipients,
        verb=NotificationVerbs.TASK_LINKED_OBJECT_ADDED,
        task=task,
        title=title,
        description=description,
        actor=actor,
        action_object=link,
        extra_data={
            "linked_object_id": link.id,
            "linked_object_kind": link.kind,
            "linked_object_type": object_type,
            "linked_object_pk": link.object_id,
        },
    )


def notify_board_members_added(board, actor, members):
    title, description = MessageTemplates.board_member_added(
        board,
        _actor_name(actor),
    )
    for member in members:
        if not member or not getattr(member, "is_active", False):
            continue
        if _actor_id(actor) and member.id == _actor_id(actor):
            continue
        notify.send(
            sender=actor,
            recipient=member,
            verb=NotificationVerbs.TASK_BOARD_MEMBER_ADDED,
            action_object=board,
            description=description,
            action_url=ActionURLs.board_detail(board),
            data={
                "title": title,
                "board_id": board.id,
                "board_name": board.name,
            },
        )


def _already_sent_today(*, recipient_id: int, verb: str, task: Task) -> bool:
    task_ct = ContentType.objects.get_for_model(Task)
    today = timezone.localdate()
    start = timezone.make_aware(
        datetime.combine(today, time.min)
    )
    end = start + timedelta(days=1)
    return Notification.objects.filter(
        recipient_id=recipient_id,
        verb=verb,
        target_content_type=task_ct,
        target_object_id=str(task.id),
        timestamp__gte=start,
        timestamp__lt=end,
    ).exists()


def dispatch_task_due_notifications() -> dict[str, int]:
    today = timezone.localdate()
    due_soon_count = 0
    overdue_count = 0
    queryset = (
        Task.objects.filter(
            due_date__isnull=False,
            assignee__isnull=False,
            completed_at__isnull=True,
            column__is_done=False,
            board__is_archived=False,
        )
        .select_related("board", "column", "assignee", "created_by")
        .order_by("id")
    )
    for task in queryset:
        if task.due_date < today:
            verb = NotificationVerbs.TASK_OVERDUE
            title, description = MessageTemplates.task_overdue(task)
        elif task.due_date == today:
            verb = NotificationVerbs.TASK_DUE_SOON
            title, description = MessageTemplates.task_due_soon(task)
        else:
            continue

        if _already_sent_today(
            recipient_id=task.assignee_id,
            verb=verb,
            task=task,
        ):
            continue
        _send_task_notification(
            recipient=task.assignee,
            verb=verb,
            task=task,
            title=title,
            description=description,
            actor=None,
            extra_data={"due_date": task.due_date.isoformat()},
        )
        if verb == NotificationVerbs.TASK_OVERDUE:
            overdue_count += 1
        else:
            due_soon_count += 1

    return {"due_soon": due_soon_count, "overdue": overdue_count}
