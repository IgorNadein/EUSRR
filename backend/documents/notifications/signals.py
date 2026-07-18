"""
Django signals для автоматической генерации уведомлений в модуле Documents.

Обрабатывает события:
- post_save для Document - создание нового документа
- m2m_changed для Document.recipients - добавление конкретных получателей
- m2m_changed для Document.departments - добавление отделов
- post_save для DocumentAcknowledgement - проверка полного ознакомления
"""

import logging

from django.contrib.auth import get_user_model
from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver

from ..models import Document, DocumentAcknowledgement
from .handlers import (
    notify_all_employees,
    notify_specific_users,
    notify_department_employees,
    notify_all_acknowledged,
)

logger = logging.getLogger(__name__)
Employee = get_user_model()


@receiver(post_save, sender=Document)
def create_document_notification(sender, instance, created, **kwargs):
    """
    Создает уведомления при создании нового документа.

    Уведомления отправляются:
    - Всем активным сотрудникам (если sent_to_all=True)
    - Сотрудникам выбранных отделов (через m2m_changed signal)
    - Выбранным получателям (через m2m_changed signal)
    """
    logger.info(
        f"[signals] post_save Document id={instance.pk} "
        f"created={created} sent_to_all={instance.sent_to_all}"
    )

    if getattr(instance, "_suppress_document_notifications", False):
        return

    if not created:
        return

    document = instance

    # Если документ отправляется всем - создаем уведомления напрямую
    # channels.py автоматически отправит через Celery
    if document.sent_to_all:
        logger.info(
            f"[signals] Creating notifications for doc={
                document.pk
            } (sent_to_all=True)"
        )
        notify_all_employees(document)
    else:
        logger.info(
            "[signals] Skipping notifications (sent_to_all=False), "
            "waiting for m2m_changed"
        )


@receiver(m2m_changed, sender=Document.recipients.through)
def notify_specific_recipients(sender, instance, action, pk_set, **kwargs):
    """
    Уведомляет конкретных получателей при добавлении в список.
    Использует быструю обработку для большого количества получателей.
    """
    logger.info(
        f"[signals] m2m_changed Document id={instance.pk} "
        f"action={action} pk_set={pk_set} sent_to_all={instance.sent_to_all}"
    )

    if getattr(instance, "_suppress_document_notifications", False):
        return

    if action != "post_add":
        logger.info(f"[signals] Skipping (action={action} != 'post_add')")
        return

    document = instance

    # Не отправляем индивидуальные уведомления если документ для всех
    if document.sent_to_all:
        logger.info("[signals] Skipping (sent_to_all=True)")
        return

    # Отправляем уведомления через handlers
    notify_specific_users(document, pk_set)


@receiver(m2m_changed, sender=Document.departments.through)
def notify_department_employees_signal(
    sender, instance, action, pk_set, **kwargs
):
    """
    Уведомляет всех сотрудников выбранных отделов при добавлении отделов.
    Уведомления получат ВСЕ текущие и будущие сотрудники этих отделов.
    """
    logger.info(
        f"[signals] m2m_changed Document.departments "
        f"id={instance.pk} action={action} pk_set={pk_set}"
    )

    if getattr(instance, "_suppress_document_notifications", False):
        return

    if action != "post_add":
        logger.info(f"[signals] Skipping (action={action} != 'post_add')")
        return

    document = instance

    # Не отправляем если документ для всех
    if document.sent_to_all:
        logger.info("[signals] Skipping (sent_to_all=True)")
        return

    # Отправляем уведомления через handlers
    notify_department_employees(document, pk_set)


@receiver(post_save, sender=DocumentAcknowledgement)
def check_all_acknowledged(sender, instance, created, **kwargs):
    """
    Проверяет, все ли получатели ознакомились с документом.
    Если да - уведомляет загрузившего.
    """
    if not created:
        return

    acknowledgement = instance
    document = acknowledgement.document
    if not document.acknowledgement_required:
        logger.info(
            "[signals] Skipping full acknowledgement notification "
            f"for optional document id={document.pk}"
        )
        return

    from documents.audience import document_acknowledgement_audience

    acknowledgement_audience = document_acknowledgement_audience(document)
    total_recipients = acknowledgement_audience.count()

    # Проверяем количество ознакомившихся
    acknowledged_count = document.acknowledgements.filter(
        user__in=acknowledgement_audience
    ).count()

    # Если все ознакомились - уведомляем загрузившего
    if (
        acknowledged_count >= total_recipients
        and total_recipients > 0
        and document.uploaded_by
    ):
        notify_all_acknowledged(document, total_recipients, acknowledged_count)
