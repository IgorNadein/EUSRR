"""
Бизнес-логика отправки уведомлений для модуля Documents.

Функции:
- notify_document_ready - уведомление о новом документе
- notify_all_employees - уведомление всем сотрудникам
- notify_specific_users - уведомление конкретным пользователям
- notify_department_employees - уведомление сотрудникам отделов
- notify_all_acknowledged - уведомление о завершении ознакомления
- notify_document_comment - уведомление о комментарии к документу
"""

import logging

from django.contrib.auth import get_user_model
from notifications.signals import notify

from .config import (
    NotificationVerbs,
    MessageTemplates,
    ActionURLs,
    get_bulk_threshold,
    get_uploader_name,
)

logger = logging.getLogger(__name__)
Employee = get_user_model()


def notify_document_ready(document, recipient):
    """
    Отправляет уведомление конкретному получателю о новом документе.

    Args:
        document: Объект Document
        recipient: Объект Employee
    """
    logger.info(
        f"[handlers] create_document_ready_notification "
        f"doc={document.id} recipient={recipient.id}"
    )

    uploader_name = get_uploader_name(document.uploaded_by)

    notify.send(
        sender=document.uploaded_by,
        recipient=recipient,
        verb=NotificationVerbs.DOCUMENT_READY,
        action_object=document,
        description=MessageTemplates.document_ready(uploader_name, document.title),
        action_url=ActionURLs.DOCUMENTS,
        data={
            'title': MessageTemplates.document_ready_title(),
            'document_id': document.id,
            'uploaded_by_id': document.uploaded_by.id if document.uploaded_by else None,
            'sent_to_all': document.sent_to_all,
        },
    )


def notify_all_employees(document):
    """
    Отправляет уведомление о новом документе всем активным сотрудникам.

    Args:
        document: Объект Document
    """
    logger.info(
        f"[handlers] notify_all_employees doc={document.id}"
    )

    active_employees = Employee.objects.filter(is_active=True)

    # Исключаем загрузившего документ
    if document.uploaded_by:
        active_employees = active_employees.exclude(id=document.uploaded_by.id)

    count = active_employees.count()
    logger.info(
        f"[handlers] Creating {count} notifications "
        f"(web immediately, email/telegram deferred)"
    )

    # Создаём уведомления
    created_count = 0
    uploader_name = get_uploader_name(document.uploaded_by)

    for employee in active_employees:
        try:
            notify.send(
                sender=document.uploaded_by,
                recipient=employee,
                verb=NotificationVerbs.DOCUMENT_READY,
                action_object=document,
                description=MessageTemplates.document_ready(
                    uploader_name,
                    document.title),
                action_url=ActionURLs.DOCUMENTS,
                data={
                    'title': MessageTemplates.document_ready_title(),
                    'document_id': document.id,
                    'uploaded_by_id': (
                        document.uploaded_by.id if document.uploaded_by else None),
                    'sent_to_all': document.sent_to_all,
                },
            )
            created_count += 1
        except Exception as e:
            logger.error(
                f"[handlers] Error creating notification for user {employee.id}: {e}"
            )

    logger.info(
        f"[handlers] Created {created_count}/{count} notifications "
        f"for doc={document.id}. Web sent immediately, email/telegram pending."
    )

    # Запускаем асинхронную отправку email/telegram
    try:
        from django.core.management import call_command
        import threading

        def send_pending():
            try:
                call_command('send_pending_notifications', '--batch-size=100')
            except Exception as e:
                logger.error(f"[handlers] Error in background send: {e}")

        # Запускаем в отдельном потоке
        thread = threading.Thread(target=send_pending, daemon=True)
        thread.start()
        logger.info("[handlers] Started background email/telegram send")
    except Exception as e:
        logger.error(f"[handlers] Error starting background send: {e}")


def notify_specific_users(document, user_ids):
    """
    Уведомляет конкретных получателей о документе.

    Args:
        document: Объект Document
        user_ids: Набор ID пользователей
    """
    recipient_count = len(user_ids or [])
    logger.info(
        f"[handlers] Processing {recipient_count} specific recipients"
    )

    # Определяем, это массовая рассылка или нет
    is_bulk = recipient_count >= get_bulk_threshold()

    if is_bulk:
        logger.info(
            f"[handlers] Bulk mode activated "
            f"({recipient_count} >= {get_bulk_threshold()})"
        )

    # Уведомляем получателей
    created_count = 0
    uploader_name = get_uploader_name(document.uploaded_by)

    for user_id in user_ids:
        try:
            user = Employee.objects.get(id=user_id)
            logger.debug(
                f"[handlers] Creating notification for user={user_id}"
            )
            notify.send(
                sender=document.uploaded_by,
                recipient=user,
                verb=NotificationVerbs.DOCUMENT_READY,
                action_object=document,
                description=MessageTemplates.document_ready(
                    uploader_name,
                    document.title),
                action_url=ActionURLs.DOCUMENTS,
                data={
                    'title': MessageTemplates.document_ready_title(),
                    'document_id': document.id,
                    'uploaded_by_id': (
                        document.uploaded_by.id if document.uploaded_by else None),
                    'sent_to_all': document.sent_to_all,
                },
            )
            created_count += 1
        except Employee.DoesNotExist:
            logger.warning(f"[handlers] User {user_id} not found, skipping")
        except Exception as e:
            logger.error(
                f"[handlers] Error creating notification for user {user_id}: {e}")

    logger.info(f"[handlers] Created {created_count} notifications")


def notify_department_employees(document, department_ids):
    """
    Уведомляет всех сотрудников выбранных отделов о документе.

    Args:
        document: Объект Document
        department_ids: Набор ID отделов
    """
    logger.info(
        f"[handlers] Processing {len(department_ids)} departments"
    )

    if not department_ids:
        logger.warning("[handlers] No departments provided")
        return

    # Получаем всех активных сотрудников выбранных отделов
    from employees.models import Department

    all_employees = set()
    for dept_id in department_ids:
        try:
            department = Department.objects.get(id=dept_id)
            dept_employees = department.active_employees
            logger.info(
                f"[handlers] Department '{department.name}' "
                f"has {len(dept_employees)} active employees: "
                f"{[e.id for e in dept_employees]}"
            )
            all_employees.update(dept_employees)
            logger.info(
                f"[handlers] After update, all_employees has: "
                f"{[e.id for e in all_employees]}"
            )
        except Department.DoesNotExist:
            logger.warning(
                f"[handlers] Department {dept_id} not found"
            )
            continue

    # Исключаем загрузившего
    if document.uploaded_by and document.uploaded_by in all_employees:
        all_employees.remove(document.uploaded_by)

    recipient_count = len(all_employees)
    logger.info(
        f"[handlers] Processing {recipient_count} employees "
        f"from {len(department_ids)} departments"
    )

    # Определяем режим рассылки
    is_bulk = recipient_count >= get_bulk_threshold()

    if is_bulk:
        logger.info(
            f"[handlers] Bulk mode activated "
            f"({recipient_count} >= {get_bulk_threshold()})"
        )

    # Создаём уведомления
    created_count = 0
    uploader_name = get_uploader_name(document.uploaded_by)

    for employee in all_employees:
        try:
            notify.send(
                sender=document.uploaded_by,
                recipient=employee,
                verb=NotificationVerbs.DOCUMENT_READY,
                action_object=document,
                description=MessageTemplates.document_ready(
                    uploader_name,
                    document.title),
                action_url=ActionURLs.DOCUMENTS,
                data={
                    'title': MessageTemplates.document_ready_title(),
                    'document_id': document.id,
                    'uploaded_by_id': (
                        document.uploaded_by.id if document.uploaded_by else None),
                    'sent_to_all': document.sent_to_all,
                },
            )
            created_count += 1
        except Exception as e:
            logger.error(
                f"[handlers] Error creating notification for employee {
                    employee.id}: {e}")

    logger.info(f"[handlers] Created {created_count} notifications")


def notify_all_acknowledged(document, total_recipients, acknowledged_count):
    """
    Уведомляет загрузившего о том, что все ознакомились с документом.

    Args:
        document: Объект Document
        total_recipients: Общее количество получателей
        acknowledged_count: Количество ознакомившихся
    """
    if not document.uploaded_by:
        logger.info(
            "[handlers] Document has no uploader, skipping acknowledgement notification"
        )
        return

    logger.info(
        f"[handlers] Notifying uploader about full acknowledgement "
        f"({acknowledged_count}/{total_recipients})"
    )

    notify.send(
        sender=None,
        recipient=document.uploaded_by,
        verb=NotificationVerbs.DOCUMENT_SIGNED_ALL,
        action_object=document,
        description=MessageTemplates.all_acknowledged(document.title),
        action_url=ActionURLs.DOCUMENTS,
        data={
            'title': MessageTemplates.all_acknowledged_title(),
            'document_id': document.id,
            'total_recipients': total_recipients,
            'acknowledged_count': acknowledged_count,
        }
    )
