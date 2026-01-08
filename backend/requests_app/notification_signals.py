"""
Signals для автоматической генерации уведомлений в модуле Requests.

Обрабатывает события:
- Новое заявление (для ответственных/руководителей)
- Одобрение заявления
- Отклонение заявления
- Комментарий к заявлению
- Изменение статуса заявления
"""

import logging

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models.signals import m2m_changed, post_save, pre_save
from django.dispatch import receiver
from notifications.services import NotificationService

from .models import Request, RequestComment

Employee = get_user_model()
logger = logging.getLogger(__name__)


# Флаг для отслеживания новых заявлений, ожидающих уведомления
_pending_new_requests = set()


@receiver(post_save, sender=Request)
def create_request_notifications(sender, instance, created, **kwargs):
    """
    Создает уведомления при создании или изменении заявления.

    Обрабатывает:
    1. Новое заявление - помечаем для отправки уведомлений после установки recipients
    2. Изменение статуса - уведомление автору
    """
    try:
        request_obj = instance

        # Логирование для отладки
        print(
            f"🔔 [SIGNAL] create_request_notifications: created={created}, status={request_obj.status}, id={request_obj.id}"
        )

        if created and request_obj.status != "draft":
            # Помечаем заявление как ожидающее отправки уведомлений
            # Уведомления будут отправлены после установки recipients через m2m_changed
            print(
                f"📌 [SIGNAL] Помечаем заявление #{request_obj.id} для отправки уведомлений после установки recipients"
            )
            _pending_new_requests.add(request_obj.id)
        else:
            print(
                f"⏭️  [SIGNAL] Пропускаем: created={created}, status={request_obj.status}"
            )

        if not created:
            # Проверяем изменение статуса через сохраненный атрибут _old_status
            if hasattr(request_obj, "_old_status"):
                old_status = request_obj._old_status
                new_status = request_obj.status

                if old_status != new_status:
                    # Передаем текущий request_obj с актуальным approver_id
                    notify_status_change(request_obj, old_status, new_status)
    except Exception as e:
        logger.exception(f"[SIGNAL ERROR] create_request_notifications: {e}")
        print(f"❌ [SIGNAL ERROR] create_request_notifications: {e}")


@receiver(pre_save, sender=Request)
def track_status_change(sender, instance, **kwargs):
    """
    Сохраняем старый статус перед обновлением для отслеживания изменений.
    """
    if instance.pk:
        try:
            old_instance = Request.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Request.DoesNotExist:
            instance._old_status = None


@receiver(m2m_changed, sender=Request.recipients.through)
def notify_on_recipients_changed(sender, instance, action, **kwargs):
    """
    Отправляет уведомления о новом заявлении ПОСЛЕ установки recipients.

    Срабатывает когда recipients устанавливаются через .set(), .add() и т.д.
    """
    try:
        # Проверяем что это завершение операции установки recipients
        if action == "post_add" and instance.id in _pending_new_requests:
            print(
                f"🎯 [M2M_SIGNAL] Recipients установлены для заявления #{instance.id}, отправляем уведомления"
            )
            _pending_new_requests.discard(instance.id)
            notify_new_request(instance)
    except Exception as e:
        logger.exception(f"[SIGNAL ERROR] notify_on_recipients_changed: {e}")
        print(f"❌ [SIGNAL ERROR] notify_on_recipients_changed: {e}")


@receiver(m2m_changed, sender=Request.cc_users.through)
def notify_on_cc_users_changed(sender, instance, action, **kwargs):
    """
    Дополнительная проверка для cc_users.

    Если recipients не были установлены, но установлены cc_users,
    также отправляем уведомления.
    """
    try:
        # Если это завершение добавления cc_users И заявление все еще ожидает уведомлений
        if action == "post_add" and instance.id in _pending_new_requests:
            # Проверяем что recipients пусты (значит уведомления еще не отправлены)
            if instance.recipients.count() == 0:
                print(
                    f"🎯 [M2M_SIGNAL] CC users установлены для заявления #{instance.id} (без recipients), отправляем уведомления"
                )
                _pending_new_requests.discard(instance.id)
                notify_new_request(instance)
    except Exception as e:
        logger.exception(f"[SIGNAL ERROR] notify_on_cc_users_changed: {e}")
        print(f"❌ [SIGNAL ERROR] notify_on_cc_users_changed: {e}")


@receiver(post_save, sender=RequestComment)
def create_comment_notification(sender, instance, created, **kwargs):
    """
    Создает уведомление при добавлении комментария к заявлению.
    Уведомляет:
    - Автора заявления
    - Всех получателей
    - Всех в копии
    - Согласующего
    - Сотрудников отделов (если sent_to_all_department)
    """
    if not created:
        return

    comment = instance
    request_obj = comment.request
    author = comment.author
    recipients_set = set()

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

    # Отправляем уведомления
    author_name = author.get_full_name() or author.username
    request_type = request_obj.get_type_display()
    employee_name = (
        request_obj.employee.get_full_name() or request_obj.employee.username
    )

    for recipient in recipients_set:
        NotificationService.create_notification_async(
            recipient=recipient,
            notification_type_code="request_comment",
            title=f"💬 Новый комментарий к заявлению от {employee_name}",
            message=(
                f"{author_name} прокомментировал заявление "
                f'"{request_type}": {comment.text[:100]}'
            ),
            content_object=request_obj,
            action_url=f"/requests/{request_obj.id}/",
            metadata={
                "request_id": request_obj.id,
                "request_type": request_obj.type,
                "comment_id": comment.id,
                "author_id": author.id,
            },
        )


# ===== Вспомогательные функции =====


def notify_new_request(request_obj):
    """
    Отправляет уведомление о новом заявлении:
    - Всем основным получателям (recipients) - адресованное им
    - Всем в копии (cc_users) - с пометкой "в копии"
    - Согласующему (approver)
    - Руководителям отделов
    - Пользователям с правом can_process_requests

    При sent_to_all_department=True отправляет всем сотрудникам отделов
    """
    logger.info(
        f"\n{'=' * 80}\n"
        f"[notify_new_request] 📨 НАЧАЛО ОТПРАВКИ УВЕДОМЛЕНИЙ О НОВОМ ЗАЯВЛЕНИИ\n"
        f"  Request ID: {request_obj.id}\n"
        f"  Тип: {request_obj.get_type_display()}\n"
        f"  Сотрудник: {request_obj.employee}\n"
        f"  Статус: {request_obj.status}\n"
        f"{'=' * 80}"
    )

    print(f"📨 [notify_new_request] Начинаем обработку заявления #{request_obj.id}")

    recipients_set = set()

    # 1. Основные получатели
    recipients_count = request_obj.recipients.count()
    logger.info(
        f"[notify_new_request] Основные получатели (recipients): {recipients_count}"
    )
    print(f"   Recipients в БД: {recipients_count}")
    for recipient in request_obj.recipients.filter(is_active=True):
        recipients_set.add(recipient)
        logger.info(
            f"[notify_new_request] ✅ Основной получатель: {recipient.username} (ID={recipient.id}, email={recipient.email})"
        )
        print(
            f"   ✅ Добавлен основной получатель: {recipient.username} (ID: {recipient.id})"
        )

    # 2. Копия (CC)
    cc_count = request_obj.cc_users.count()
    logger.info(f"[notify_new_request] CC users: {cc_count}")
    print(f"   CC users в БД: {cc_count}")
    for cc_user in request_obj.cc_users.filter(is_active=True):
        recipients_set.add(cc_user)
        logger.info(
            f"[notify_new_request] ✅ CC получатель: {cc_user.username} (ID={cc_user.id}, email={cc_user.email})"
        )
        print(f"   ✅ Добавлен CC: {cc_user.username} (ID: {cc_user.id})")

    # 3. Если sent_to_all_department - все сотрудники отделов
    if request_obj.sent_to_all_department:
        dept_employees = (
            Employee.objects.filter(
                departments_links__department__in=request_obj.departments.all(),
                departments_links__is_active=True,
                is_active=True,
            )
            .exclude(id=request_obj.employee.id)
            .distinct()
        )

        recipients_set.update(dept_employees)

    # 4. Согласующий
    if request_obj.approver and request_obj.approver.id != request_obj.employee.id:
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
                departments_links__role__scoped_permissions__code="can_process_requests",
                is_active=True,
            )
            .exclude(id=request_obj.employee.id)
            .distinct()
        )

        recipients_set.update(dept_processors)

    # Итоговое логирование
    logger.info(f"[notify_new_request] 📊 ИТОГО получателей: {len(recipients_set)}")
    print(
        f"📊 [notify_new_request] Всего получателей для заявления #{request_obj.id}: {len(recipients_set)}"
    )
    if len(recipients_set) == 0:
        logger.warning(
            f"[notify_new_request] ⚠️ НЕТ ПОЛУЧАТЕЛЕЙ! Уведомления не отправлены для request_id={request_obj.id}"
        )
        print(
            f"⚠️  [notify_new_request] НЕТ ПОЛУЧАТЕЛЕЙ! Уведомления не будут отправлены."
        )
        return

    for r in recipients_set:
        logger.info(
            f"[notify_new_request]   👤 {r.username} (ID={r.id}, email={r.email})"
        )
        print(f"      👤 {r.username} (ID: {r.id})")

    # Определяем тип уведомления для каждого получателя
    author_name = request_obj.employee.get_full_name() or request_obj.employee.username
    request_type = request_obj.get_type_display()
    comment_preview = (
        request_obj.comment[:150] if request_obj.comment else "Без комментария"
    )

    logger.info(
        f"[notify_new_request] Начало отправки {len(recipients_set)} уведомлений..."
    )

    for recipient in recipients_set:
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
            # Основной получатель - требует действия
            title = f"📩 Вам адресовано заявление от {author_name}"
            message = f'Тип: "{request_type}". {comment_preview}'
            notification_type = "request_new"  # Используем общий тип
        elif is_cc:
            # Копия - информирование
            title = f"📋 Вы в копии заявления от {author_name}"
            message = f'Тип: "{request_type}". {comment_preview}'
            notification_type = "request_new"  # Используем общий тип
        elif is_approver:
            title = f"✅ Новое заявление на согласование от {author_name}"
            message = f'Тип: "{request_type}". {comment_preview}'
            notification_type = "request_new"  # Используем общий тип
        else:
            # Руководитель отдела или обработчик
            title = f"📝 Новое заявление в отделе от {author_name}"
            message = f'Тип: "{request_type}". {comment_preview}'
            notification_type = "request_new"  # Используем общий тип

        logger.info(
            f"[notify_new_request] ➡️ Вызов NotificationService.create_notification_async для {recipient.username}"
        )

        NotificationService.create_notification_async(
            recipient=recipient,
            notification_type_code=notification_type,
            title=title,
            message=message,
            content_object=request_obj,
            action_url=f"/requests/{request_obj.id}/",
            metadata={
                "request_id": request_obj.id,
                "request_type": request_obj.type,
                "employee_id": request_obj.employee.id,
                "employee_name": author_name,
                "is_primary_recipient": is_primary,
                "is_cc": is_cc,
                "is_approver": is_approver,
            },
        )


def notify_status_change(request_obj, old_status, new_status):
    """
    Уведомляет о изменении статуса:
    - Всех получателей (recipients)
    - Всех в копии (cc_users)
    - Сотрудников отделов (если sent_to_all_department)

    ВАЖНО:
    - Автор (employee) не получает уведомление о решении (approve/reject)
    - Approver (тот кто принял решение) не получает уведомление о своем же решении
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

    # Формируем уведомления с подробной информацией
    request_type = request_obj.get_type_display()
    employee_name = (
        request_obj.employee.get_full_name() or request_obj.employee.username
    )
    approver_name = (
        request_obj.approver.get_full_name() if request_obj.approver else "Руководитель"
    )

    for recipient in recipients_to_notify:
        if new_status == "approved":
            notification_type = "request_approved"
            title = f"✅ Заявление одобрено: {request_type}"
            message = (
                f'Заявление от {employee_name} "{request_type}" '
                f"одобрено пользователем {approver_name}"
            )
        elif new_status == "rejected":
            notification_type = "request_rejected"
            title = f"❌ Заявление отклонено: {request_type}"
            message = (
                f'Заявление от {employee_name} "{request_type}" '
                f"отклонено пользователем {approver_name}"
            )
        else:
            # Общее уведомление об изменении статуса
            notification_type = "request_status_changed"
            title = f"🔄 Статус заявления изменен: {request_type}"
            message = (
                f'Статус заявления от {employee_name} "{request_type}" '
                f"изменен: {old_status} → {new_status}"
            )

        NotificationService.create_notification_async(
            recipient=recipient,
            notification_type_code=notification_type,
            title=title,
            message=message,
            content_object=request_obj,
            action_url=f"/requests/{request_obj.id}/",
            metadata={
                "request_id": request_obj.id,
                "request_type": request_obj.type,
                "employee_id": request_obj.employee.id,
                "employee_name": employee_name,
                "old_status": old_status,
                "new_status": new_status,
                "approver_id": (
                    request_obj.approver.id if request_obj.approver else None
                ),
                "approver_name": approver_name,
            },
        )
