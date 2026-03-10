"""
Обработчики (handlers) для отправки уведомлений о заявлениях.

Содержит бизнес-логику формирования и отправки уведомлений
для различных событий в модуле Requests.
"""

import logging
from django.contrib.auth import get_user_model
from notifications.signals import notify

from .constants import NotificationVerbs, MessageTemplates, ActionURLs

Employee = get_user_model()
logger = logging.getLogger(__name__)


def notify_new_request(request_obj):
    """
    Отправляет уведомление о новом заявлении:
    - Всем основным получателям (recipients) - адресованное им
    - Всем в копии (cc_users) - с пометкой "в копии"
    - Согласующему (approver)
    - Руководителям отделов
    - Пользователям с правом can_process_requests

    При sent_to_all_department=True отправляет всем сотрудникам отделов
    
    Args:
        request_obj: Объект Request
    """
    logger.info(
        f"\n{'=' * 80}\n"
        f"[notify_new_request] 📨 НАЧАЛО ОТПРАВКИ УВЕДОМЛЕНИЙ\n"
        f"  Request ID: {request_obj.id}\n"
        f"  Тип: {request_obj.get_type_display()}\n"
        f"  Сотрудник: {request_obj.employee}\n"
        f"  Статус: {request_obj.status}\n"
        f"{'=' * 80}"
    )

    print(
        f"📨 [notify_new_request] Начинаем обработку "
        f"заявления #{request_obj.id}"
    )

    recipients_set = set()

    # 1. Основные получатели
    recipients_count = request_obj.recipients.count()
    logger.info(
        f"[notify_new_request] Основные получатели: {recipients_count}"
    )
    print(f"   Recipients в БД: {recipients_count}")
    for recipient in request_obj.recipients.filter(is_active=True):
        recipients_set.add(recipient)
        logger.info(
            f"[notify_new_request] ✅ Основной получатель: "
            f"{recipient.username} (ID={recipient.id})"
        )
        print(
            f"   ✅ Добавлен основной получатель: "
            f"{recipient.username} (ID: {recipient.id})"
        )

    # 2. Копия (CC)
    cc_count = request_obj.cc_users.count()
    logger.info(f"[notify_new_request] CC users: {cc_count}")
    print(f"   CC users в БД: {cc_count}")
    for cc_user in request_obj.cc_users.filter(is_active=True):
        recipients_set.add(cc_user)
        logger.info(
            f"[notify_new_request] ✅ CC получатель: "
            f"{cc_user.username} (ID={cc_user.id})"
        )
        print(f"   ✅ Добавлен CC: {cc_user.username} (ID: {cc_user.id})")

    # 3. Если sent_to_all_department - все сотрудники отделов
    if request_obj.sent_to_all_department:
        dept_employees = (
            Employee.objects.filter(
                departments_links__department__in=(
                    request_obj.departments.all()
                ),
                departments_links__is_active=True,
                is_active=True,
            )
            .exclude(id=request_obj.employee.id)
            .distinct()
        )
        recipients_set.update(dept_employees)

    # 4. Согласующий
    if (
        request_obj.approver
        and request_obj.approver.id != request_obj.employee.id
    ):
        recipients_set.add(request_obj.approver)

    # 5. Руководители отделов
    for department in request_obj.departments.all():
        if department.head and department.head.id != request_obj.employee.id:
            recipients_set.add(department.head)

    # Также проверяем старое поле department для обратной совместимости
    if request_obj.department and request_obj.department.head:
        if request_obj.department.head.id != request_obj.employee.id:
            recipients_set.add(request_obj.department.head)

    # 6. Пользователи с правом обрабатывать заявки в этих отделах
    dept_ids = list(request_obj.departments.values_list("id", flat=True))
    if request_obj.department_id and request_obj.department_id not in dept_ids:
        dept_ids.append(request_obj.department_id)

    if dept_ids:
        dept_processors = (
            Employee.objects.filter(
                departments_links__department_id__in=dept_ids,
                departments_links__is_active=True,
                departments_links__role__scoped_permissions__code=(
                    "can_process_requests"
                ),
                is_active=True,
            )
            .exclude(id=request_obj.employee.id)
            .distinct()
        )
        recipients_set.update(dept_processors)

    # Итоговое логирование
    logger.info(
        f"[notify_new_request] 📊 ИТОГО получателей: "
        f"{len(recipients_set)}"
    )
    print(
        f"📊 [notify_new_request] Всего получателей для заявления "
        f"#{request_obj.id}: {len(recipients_set)}"
    )
    
    if len(recipients_set) == 0:
        logger.warning(
            f"[notify_new_request] ⚠️ НЕТ ПОЛУЧАТЕЛЕЙ! "
            f"request_id={request_obj.id}"
        )
        print(
            "⚠️  [notify_new_request] НЕТ ПОЛУЧАТЕЛЕЙ! "
            "Уведомления не будут отправлены."
        )
        return

    for r in recipients_set:
        logger.info(
            f"[notify_new_request]   👤 {r.username} (ID={r.id})"
        )
        print(f"      👤 {r.username} (ID: {r.id})")

    # Подготовка общих данных
    author_name = request_obj.employee.get_full_name() or request_obj.employee.username
    request_type = request_obj.get_type_display()
    comment_preview = (
        request_obj.comment[:150] if request_obj.comment else "Без комментария"
    )

    logger.info(
        f"[notify_new_request] Начало отправки {len(recipients_set)} уведомлений..."
    )

    # Отправка уведомлений каждому получателю
    for recipient in recipients_set:
        _send_new_request_notification(
            request_obj=request_obj,
            recipient=recipient,
            author_name=author_name,
            request_type=request_type,
            comment_preview=comment_preview,
        )


def _send_new_request_notification(request_obj, recipient, author_name, request_type, comment_preview):
    """
    Отправляет уведомление о новом заявлении конкретному получателю.
    
    Определяет роль получателя и формирует соответствующее сообщение.
    
    Args:
        request_obj: Объект Request
        recipient: Получатель (Employee)
        author_name: Имя автора заявления
        request_type: Тип заявления (отображаемое название)
        comment_preview: Превью комментария
    """
    # Определяем роль получателя
    is_primary = request_obj.recipients.filter(id=recipient.id).exists()
    is_cc = request_obj.cc_users.filter(id=recipient.id).exists()
    is_approver = request_obj.approver_id == recipient.id

    logger.info(
        f"[notify_new_request] 📤 Отправка для {recipient.username}: "
        f"primary={is_primary}, cc={is_cc}, approver={is_approver}"
    )
    print(
        f"   📤 Отправка уведомления для {recipient.username}: "
        f"primary={is_primary}, cc={is_cc}, approver={is_approver}"
    )

    # Формируем заголовок и сообщение с учетом роли
    if is_primary:
        title, message = MessageTemplates.new_request_primary(
            author_name, request_type, comment_preview
        )
    elif is_cc:
        title, message = MessageTemplates.new_request_cc(
            author_name, request_type, comment_preview
        )
    elif is_approver:
        title, message = MessageTemplates.new_request_approver(
            author_name, request_type, comment_preview
        )
    else:
        title, message = MessageTemplates.new_request_department(
            author_name, request_type, comment_preview
        )

    logger.info(
        f"[notify_new_request] ➡️ Отправка notify.send для {recipient.username}"
    )

    notify.send(
        sender=request_obj.employee,
        recipient=recipient,
        verb=NotificationVerbs.REQUEST_NEW,
        action_object=request_obj,
        description=message,
        action_url=ActionURLs.REQUESTS_LIST,
        data={
            'title': title,
            'request_id': request_obj.id,
            'request_type': request_obj.type,
            'employee_id': request_obj.employee.id,
            'employee_name': author_name,
            'is_primary_recipient': is_primary,
            'is_cc': is_cc,
            'is_approver': is_approver,
        },
    )


def notify_status_change(request_obj, old_status, new_status):
    """
    Уведомляет о изменении статуса:
    - Всех получателей (recipients)
    - Всех в копии (cc_users)
    - Сотрудников отделов (если sent_to_all_department)

    ВАЖНО:
    - Автор (employee) ВСЕГДА получает уведомление о решении (approve/reject)
    - Approver (тот кто принял решение) НЕ получает уведомление о своем же решении
    
    Args:
        request_obj: Объект Request
        old_status: Старый статус
        new_status: Новый статус
    """
    recipients_to_notify = set()

    # ID пользователей которых НЕ нужно уведомлять при approve/reject
    exclude_ids = set()
    if new_status in ("approved", "rejected"):
        # ВАЖНО: Уведомляем автора заявки о решении - это единственный способ
        # информировать его, так как alert() был убран из UI (коммит 935c12a)
        # Не уведомляем только того кто принял решение (он сам нажал кнопку)
        if request_obj.approver_id:
            exclude_ids.add(request_obj.approver_id)

    # 1. Автор - УВЕДОМЛЯЕМ всегда (даже при approved/rejected, это важно!)
    recipients_to_notify.add(request_obj.employee)

    # 2. Основные получатели (исключая тех кто в exclude_ids)
    recipients_to_notify.update(
        request_obj.recipients.filter(is_active=True).exclude(id__in=exclude_ids)
    )

    # 3. Копия (исключая тех кто в exclude_ids)
    recipients_to_notify.update(
        request_obj.cc_users.filter(is_active=True).exclude(id__in=exclude_ids)
    )

    # 4. Если sent_to_all_department - все сотрудники отделов (исключая exclude_ids)
    if request_obj.sent_to_all_department:
        # При approve/reject также исключаем approver
        all_exclude_ids = {request_obj.employee.id}
        all_exclude_ids.update(exclude_ids)

        dept_employees = (
            Employee.objects.filter(
                departments_links__department__in=request_obj.departments.all(),
                departments_links__is_active=True,
                is_active=True,
            )
            .exclude(id__in=all_exclude_ids)
            .distinct()
        )
        recipients_to_notify.update(dept_employees)

    # Подготовка общих данных
    request_type = request_obj.get_type_display()
    employee_name = (
        request_obj.employee.get_full_name() or request_obj.employee.username
    )
    approver_name = (
        request_obj.approver.get_full_name() if request_obj.approver else "Руководитель"
    )

    # Отправка уведомлений каждому получателю
    for recipient in recipients_to_notify:
        _send_status_change_notification(
            request_obj=request_obj,
            recipient=recipient,
            new_status=new_status,
            old_status=old_status,
            employee_name=employee_name,
            request_type=request_type,
            approver_name=approver_name,
        )


def _send_status_change_notification(
    request_obj, recipient, new_status, old_status, employee_name, request_type, approver_name
):
    """
    Отправляет уведомление об изменении статуса конкретному получателю.
    
    Args:
        request_obj: Объект Request
        recipient: Получатель (Employee)
        new_status: Новый статус
        old_status: Старый статус
        employee_name: Имя автора заявления
        request_type: Тип заявления
        approver_name: Имя согласующего
    """
    # Определяем тип уведомления и формируем сообщение
    if new_status == 'approved':
        verb = NotificationVerbs.REQUEST_APPROVED
        title, message = MessageTemplates.status_approved(
            employee_name, request_type, approver_name
        )
    elif new_status == 'rejected':
        verb = NotificationVerbs.REQUEST_REJECTED
        title, message = MessageTemplates.status_rejected(
            employee_name, request_type, approver_name
        )
    else:
        verb = NotificationVerbs.REQUEST_STATUS_CHANGED
        title, message = MessageTemplates.status_changed(
            employee_name, request_type, old_status, new_status
        )

    notify.send(
        sender=request_obj.approver if request_obj.approver else None,
        recipient=recipient,
        verb=verb,
        action_object=request_obj,
        description=message,
        action_url=ActionURLs.REQUESTS_LIST,
        data={
            'title': title,
            'request_id': request_obj.id,
            'request_type': request_obj.type,
            'employee_id': request_obj.employee.id,
            'employee_name': employee_name,
            'old_status': old_status,
            'new_status': new_status,
            'approver_id': (
                request_obj.approver.id if request_obj.approver else None
            ),
            'approver_name': approver_name,
        },
    )


def notify_comment(comment_obj):
    """
    Отправляет уведомления о новом комментарии к заявлению.
    
    Уведомляет:
    - Автора заявления
    - Всех получателей
    - Всех в копии
    - Согласующего
    - Сотрудников отделов (если sent_to_all_department)
    
    Args:
        comment_obj: Объект RequestComment
    """
    author = comment_obj.author
    recipients_set = set()
    request_obj = comment_obj.request

    # Автор заявки
    if request_obj.employee.id != author.id:
        recipients_set.add(request_obj.employee)

    # Получатели
    recipients_set.update(
        request_obj.recipients.filter(is_active=True).exclude(id=author.id)
    )

    # CC
    recipients_set.update(
        request_obj.cc_users.filter(is_active=True).exclude(id=author.id)
    )

    # Согласующий
    if request_obj.approver and request_obj.approver.id != author.id:
        recipients_set.add(request_obj.approver)

    # Если sent_to_all_department - все сотрудники отделов
    if request_obj.sent_to_all_department:
        dept_employees = (
            Employee.objects.filter(
                departments_links__department__in=request_obj.departments.all(),
                departments_links__is_active=True,
                is_active=True,
            )
            .exclude(id__in=[author.id, request_obj.employee.id])
            .distinct()
        )
        recipients_set.update(dept_employees)

    # Подготовка данных
    author_name = author.get_full_name() or author.username
    request_type = request_obj.get_type_display()
    employee_name = (
        request_obj.employee.get_full_name() or request_obj.employee.username
    )

    # Отправка уведомлений
    for recipient in recipients_set:
        # Не отправляем уведомление тому, кто сам написал комментарий
        if recipient.id == author.id:
            continue

        title, description = MessageTemplates.comment(
            author_name, request_type, employee_name, comment_obj.text
        )

        notify.send(
            sender=author,
            recipient=recipient,
            verb=NotificationVerbs.REQUEST_COMMENT,
            action_object=request_obj,
            description=description,
            action_url=ActionURLs.REQUESTS_LIST,
            data={
                'title': title,
                'request_id': request_obj.id,
                'request_type': request_obj.type,
                'comment_id': comment_obj.id,
                'author_id': author.id,
            },
        )
