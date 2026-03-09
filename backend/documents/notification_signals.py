"""
Signals для автоматической генерации уведомлений в модуле Documents.

Обрабатывает события:
- Новый документ на ознакомление
- Все сотрудники ознакомились
- Напоминание о необходимости ознакомления (через Celery task)
"""

import logging

from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import Document, DocumentAcknowledgement, DocumentComment
from notifications.signals import notify

logger = logging.getLogger(__name__)
Employee = get_user_model()


@receiver(post_save, sender=Document)
def create_document_notification(sender, instance, created, **kwargs):
    """
    Создает уведомления при создании нового документа асинхронно.
    
    Уведомления отправляются:
    - Всем активным сотрудникам (если sent_to_all=True)
    - Сотрудникам выбранных отделов (через m2m_changed signal)
    - Выбранным получателям (через m2m_changed signal)
    """
    logger.info(
        f"[notification_signals] post_save Document id={instance.pk} "
        f"created={created} sent_to_all={instance.sent_to_all}"
    )
    
    if not created:
        return
    
    document = instance
    
    # Если документ отправляется всем - создаем уведомления напрямую
    # channels.py автоматически отправит через Celery
    if document.sent_to_all:
        logger.info(
            f"[notification_signals] Creating notifications for doc={document.pk} (sent_to_all=True)"
        )
        notify_all_employees(document)
    else:
        logger.info(
            f"[notification_signals] Skipping notifications (sent_to_all=False), "
            f"waiting for m2m_changed"
        )


@receiver(m2m_changed, sender=Document.recipients.through)
def notify_specific_recipients(sender, instance, action, pk_set, **kwargs):
    """
    Уведомляет конкретных получателей при добавлении в список.
    Использует быструю обработку для большого количества получателей.
    """
    logger.info(
        f"[notification_signals] m2m_changed Document id={instance.pk} "
        f"action={action} pk_set={pk_set} sent_to_all={instance.sent_to_all}"
    )
    
    if action != 'post_add':
        logger.info(
            f"[notification_signals] Skipping (action={action} != 'post_add')"
        )
        return
    
    document = instance
    
    # Не отправляем индивидуальные уведомления если документ для всех
    if document.sent_to_all:
        logger.info(
            f"[notification_signals] Skipping (sent_to_all=True)"
        )
        return
    
    recipient_count = len(pk_set or [])
    logger.info(
        f"[notification_signals] Processing {recipient_count} recipients"
    )
    
    # Определяем, это массовая рассылка или нет
    from django.conf import settings
    BULK_THRESHOLD = getattr(settings, 'NOTIFICATION_BULK_THRESHOLD', 10)
    is_bulk = recipient_count >= BULK_THRESHOLD
    
    if is_bulk:
        logger.info(
            f"[notification_signals] Bulk mode activated "
            f"({recipient_count} >= {BULK_THRESHOLD})"
        )
    
    # Уведомляем новых получателей
    created_count = 0
    for user_id in pk_set:
        try:
            user = Employee.objects.get(id=user_id)
            logger.debug(
                f"[notification_signals] Creating notification for user={user_id}"
            )
            uploader_name = (
                document.uploaded_by.get_full_name()
                if document.uploaded_by
                else 'Администратор'
            )
            notify.send(
                sender=document.uploaded_by,
                recipient=user,
                verb='document_ready',
                action_object=document,
                description=(
                    f'{uploader_name} загрузил документ "{document.title}". '
                    f'Требуется ознакомление.'
                ),
                action_url='/documents',
                data={
                    'title': 'Новый документ на ознакомление',
                    'document_id': document.id,
                    'uploaded_by_id': (
                        document.uploaded_by.id if document.uploaded_by else None
                    ),
                    'sent_to_all': document.sent_to_all,
                },
            )
            created_count += 1
        except Employee.DoesNotExist:
            logger.warning(f"[notification_signals] User {user_id} not found, skipping")
        except Exception as e:
            logger.error(f"[notification_signals] Error creating notification for user {user_id}: {e}")

    logger.info(f"[notification_signals] Created {created_count} notifications")


@receiver(m2m_changed, sender=Document.departments.through)
def notify_department_employees(sender, instance, action, pk_set, **kwargs):
    """
    Уведомляет всех сотрудников выбранных отделов при добавлении отделов.
    Уведомления получат ВСЕ текущие и будущие сотрудники этих отделов.
    """
    logger.info(
        f"[notification_signals] m2m_changed Document.departments "
        f"id={instance.pk} action={action} pk_set={pk_set}"
    )
    
    if action != 'post_add':
        logger.info(
            f"[notification_signals] Skipping (action={action} != 'post_add')"
        )
        return
    
    document = instance
    
    # Не отправляем если документ для всех
    if document.sent_to_all:
        logger.info(
            "[notification_signals] Skipping (sent_to_all=True)"
        )
        return
    
    if not pk_set:
        logger.warning("[notification_signals] No departments provided")
        return
    
    # Получаем всех активных сотрудников выбранных отделов
    from employees.models import Department
    
    all_employees = set()
    for dept_id in pk_set:
        try:
            department = Department.objects.get(id=dept_id)
            dept_employees = department.active_employees
            logger.info(
                f"[notification_signals] Department '{department.name}' "
                f"has {len(dept_employees)} active employees: "
                f"{[e.id for e in dept_employees]}"
            )
            all_employees.update(dept_employees)
            logger.info(
                f"[notification_signals] After update, all_employees has: "
                f"{[e.id for e in all_employees]}"
            )
        except Department.DoesNotExist:
            logger.warning(
                f"[notification_signals] Department {dept_id} not found"
            )
            continue
    
    # Исключаем загрузившего
    if document.uploaded_by and document.uploaded_by in all_employees:
        all_employees.remove(document.uploaded_by)
    
    recipient_count = len(all_employees)
    logger.info(
        f"[notification_signals] Processing {recipient_count} employees "
        f"from {len(pk_set)} departments"
    )
    
    # Определяем режим рассылки
    from django.conf import settings
    BULK_THRESHOLD = getattr(settings, 'NOTIFICATION_BULK_THRESHOLD', 10)
    is_bulk = recipient_count >= BULK_THRESHOLD
    
    if is_bulk:
        logger.info(
            f"[notification_signals] Bulk mode activated "
            f"({recipient_count} >= {BULK_THRESHOLD})"
        )
    
    # Создаём уведомления
    created_count = 0
    uploader_name = (
        document.uploaded_by.get_full_name()
        if document.uploaded_by
        else 'Администратор'
    )
    for employee in all_employees:
        try:
            notify.send(
                sender=document.uploaded_by,
                recipient=employee,
                verb='document_ready',
                action_object=document,
                description=(
                    f'{uploader_name} загрузил документ "{document.title}". '
                    f'Требуется ознакомление.'
                ),
                action_url='/documents',
                data={
                    'title': 'Новый документ на ознакомление',
                    'document_id': document.id,
                    'uploaded_by_id': (
                        document.uploaded_by.id if document.uploaded_by else None
                    ),
                    'sent_to_all': document.sent_to_all,
                },
            )
            created_count += 1
        except Exception as e:
            logger.error(f"[notification_signals] Error creating notification for employee {employee.id}: {e}")

    logger.info(f"[notification_signals] Created {created_count} notifications")


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
    
    # Определяем общее количество получателей
    if document.sent_to_all:
        total_recipients = Employee.objects.filter(is_active=True).count()
    else:
        # Считаем получателей из recipients + departments
        recipients_count = document.recipients.count()
        
        # Добавляем сотрудников из отделов
        from employees.models import Department
        department_employees = set()
        for department in document.departments.all():
            department_employees.update(department.active_employees)
        
        # Исключаем дубликаты с recipients
        total_recipients = recipients_count + len(department_employees)
    
    # Проверяем количество ознакомившихся
    acknowledged_count = document.acknowledgements.count()
    
    # Если все ознакомились - уведомляем загрузившего
    if (acknowledged_count >= total_recipients and 
        total_recipients > 0 and
        document.uploaded_by):

        notify.send(
            sender=None,
            recipient=document.uploaded_by,
            verb='document_signed_all',
            action_object=document,
            description=(
                f'Все сотрудники ознакомились с документом '
                f'"{document.title}"'
            ),
            action_url='/documents',
            data={
                'title': 'Все ознакомились с документом',
                'document_id': document.id,
                'total_recipients': total_recipients,
                'acknowledged_count': acknowledged_count,
            }
        )


# ===== Вспомогательные функции =====

def notify_all_employees(document):
    """
    Отправляет уведомление о новом документе всем активным сотрудникам.
    Веб-уведомления отправляются сразу, email/Telegram - асинхронно.
    """
    logger.info(
        f"[notification_signals] notify_all_employees doc={document.id}"
    )
    
    active_employees = Employee.objects.filter(is_active=True)
    
    # Исключаем загрузившего документ
    if document.uploaded_by:
        active_employees = active_employees.exclude(
            id=document.uploaded_by.id
        )
    
    count = active_employees.count()
    logger.info(
        f"[notification_signals] Creating {count} notifications "
        f"(web immediately, email/telegram deferred)"
    )
    
    # Создаём уведомления с ЧАСТИЧНОЙ отправкой
    created_count = 0
    uploader_name = (
        document.uploaded_by.get_full_name()
        if document.uploaded_by
        else 'Администратор'
    )
    for employee in active_employees:
        try:
            notify.send(
                sender=document.uploaded_by,
                recipient=employee,
                verb='document_ready',
                action_object=document,
                description=(
                    f'{uploader_name} загрузил документ "{document.title}". '
                    f'Требуется ознакомление.'
                ),
                action_url='/documents',
                data={
                    'title': 'Новый документ на ознакомление',
                    'document_id': document.id,
                    'uploaded_by_id': (
                        document.uploaded_by.id if document.uploaded_by else None
                    ),
                    'sent_to_all': document.sent_to_all,
                },
            )
            created_count += 1
        except Exception as e:
            logger.error(
                f"Error creating notification for user {employee.id}: {e}"
            )
    
    logger.info(
        f"[notification_signals] Created {created_count}/{count} notifications "
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
                logger.error(f"Error in background send: {e}")
        
        # Запускаем в отдельном потоке
        thread = threading.Thread(target=send_pending, daemon=True)
        thread.start()
        logger.info("[notification_signals] Started background email/telegram send")
    except Exception as e:
        logger.error(f"Error starting background send: {e}")
def create_document_ready_notification(document, recipient, send_immediately=True):
    """
    Создает уведомление о новом документе для конкретного получателя.
    """
    logger.info(
        f"[notification_signals] create_document_ready_notification "
        f"doc={document.id} recipient={recipient.id}"
    )

    uploader_name = (
        document.uploaded_by.get_full_name()
        if document.uploaded_by
        else 'Администратор'
    )

    notify.send(
        sender=document.uploaded_by,
        recipient=recipient,
        verb='document_ready',
        action_object=document,
        description=(
            f'{uploader_name} загрузил документ "{document.title}". '
            f'Требуется ознакомление.'
        ),
        action_url='/documents',
        data={
            'title': 'Новый документ на ознакомление',
            'document_id': document.id,
            'uploaded_by_id': (
                document.uploaded_by.id if document.uploaded_by else None
            ),
            'sent_to_all': document.sent_to_all,
        },
    )


# =============================================================================
# НОВЫЕ СИГНАЛЫ ДЛЯ КОММЕНТАРИЕВ И СВЯЗАННЫХ ДОКУМЕНТОВ
# =============================================================================

@receiver(post_save, sender=DocumentComment)
def notify_on_new_comment(sender, instance, created, **kwargs):
    """
    Отправка уведомлений при создании нового комментария.
    
    - Если это ответ на комментарий (parent != None): уведомить автора родительского комментария
    - Если это обычный комментарий: уведомить автора документа (если он не автор комментария)
    """
    if not created:
        return
    
    comment = instance
    document = comment.document
    author = comment.author
    
    logger.info(
        f"[notification_signals] New comment on document={document.pk} "
        f"by user={author.pk} parent={comment.parent_id}"
    )
    
    # Если это ответ на комментарий
    if comment.parent:
        parent_author = comment.parent.author
        
        # Не уведомляем самого себя
        if parent_author.id == author.id:
            logger.info(
                f"[notification_signals] Skipping self-reply notification"
            )
            return
        
        logger.info(
            f"[notification_signals] Notifying parent author={parent_author.pk} "
            f"about reply"
        )
        
        notify.send(
            sender=author,
            recipient=parent_author,
            verb='document_comment_reply',
            action_object=comment,
            description=(
                f'{author.get_full_name() or author.username} ответил на ваш '
                f'комментарий к документу "{document.title}"'
            ),
            action_url='/documents',
            data={
                'title': 'Ответ на ваш комментарий',
                'document_id': document.id,
                'comment_id': comment.id,
                'parent_comment_id': comment.parent_id,
                'author_id': author.id,
            },
        )
    else:
        # Обычный комментарий - уведомляем автора документа
        if not document.uploaded_by:
            logger.info(
                f"[notification_signals] Document has no author, skipping"
            )
            return
        
        doc_author = document.uploaded_by
        
        # Не уведомляем самого себя
        if doc_author.id == author.id:
            logger.info(
                f"[notification_signals] Skipping self-comment notification"
            )
            return
        
        logger.info(
            f"[notification_signals] Notifying document author={doc_author.pk} "
            f"about new comment"
        )
        
        notify.send(
            sender=author,
            recipient=doc_author,
            verb='document_comment',
            action_object=comment,
            description=(
                f'{author.get_full_name() or author.username} оставил комментарий '
                f'к вашему документу "{document.title}"'
            ),
            action_url='/documents',
            data={
                'title': 'Новый комментарий к документу',
                'document_id': document.id,
                'comment_id': comment.id,
                'author_id': author.id,
            },
        )


@receiver(m2m_changed, sender=Document.related_documents.through)
def notify_on_related_document_added(sender, instance, action, pk_set, **kwargs):
    """
    Уведомление при добавлении связанного документа.
    Уведомляем автора связанного документа (если это не тот же пользователь).
    """
    if action != 'post_add':
        return
    
    if not pk_set:
        return
    
    main_document = instance
    
    logger.info(
        f"[notification_signals] Related documents added to doc={main_document.pk} "
        f"related_ids={pk_set}"
    )
    
    # Получаем связанные документы
    related_documents = Document.objects.filter(pk__in=pk_set).select_related('uploaded_by')
    
    for related_doc in related_documents:
        # Если у связанного документа есть автор
        if not related_doc.uploaded_by:
            continue
        
        # Не уведомляем если авторы совпадают
        if (main_document.uploaded_by and 
            related_doc.uploaded_by.id == main_document.uploaded_by.id):
            continue
        
        logger.info(
            f"[notification_signals] Notifying author={related_doc.uploaded_by.pk} "
            f"that their document was linked"
        )
        
        notify.send(
            sender=main_document.uploaded_by,
            recipient=related_doc.uploaded_by,
            verb='document_related',
            action_object=main_document,
            description=(
                f'Ваш документ "{related_doc.title}" связан '
                f'с документом "{main_document.title}"'
            ),
            action_url='/documents',
            data={
                'title': 'Документ связан с другим',
                'document_id': main_document.id,
                'related_document_id': related_doc.id,
            },
        )
