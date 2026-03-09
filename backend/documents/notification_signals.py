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
from notifications.services import NotificationService

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
    from django.db import transaction
    from notifications.tasks import process_document_notifications_task
    
    logger.info(
        f"[notification_signals] post_save Document id={instance.pk} "
        f"created={created} sent_to_all={instance.sent_to_all}"
    )
    
    if not created:
        return
    
    document = instance
    
    # Если документ отправляется всем - создаем уведомления сразу асинхронно
    if document.sent_to_all:
        logger.info(
            f"[notification_signals] Queuing task for doc={document.pk} (sent_to_all=True)"
        )
        
        def send_task():
            """Отложенная отправка задачи после commit транзакции"""
            try:
                process_document_notifications_task.delay(document_id=document.pk)
            except Exception as e:
                logger.warning(
                    f"Failed to queue document notifications task: {e}, "
                    f"falling back to sync"
                )
                # Fallback на старую логику
                notify_all_employees(document)
        
        transaction.on_commit(send_task)
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
            
            # Для массовой рассылки - без немедленной отправки
            notification = create_document_ready_notification(
                document, 
                user,
                send_immediately=not is_bulk  # False для массовой
            )
            
            # Для массовой - отправляем только веб сразу
            if is_bulk and notification:
                try:
                    settings = NotificationService.get_user_settings(
                        user,
                        notification.notification_type
                    )
                    
                    if settings.send_web:
                        NotificationService.send_web_socket(notification)
                        notification.sent_web = True
                        notification.save(update_fields=['sent_web'])
                except Exception as e:
                    logger.error(f"Error sending web notification: {e}")
            
            created_count += 1
        except Employee.DoesNotExist:
            logger.warning(
                f"[notification_signals] User {user_id} not found"
            )
            continue
    
    logger.info(
        f"[notification_signals] Created {created_count}/{recipient_count} "
        f"notifications (bulk={is_bulk})"
    )
    
    # Для массовой рассылки - запускаем фоновую отправку
    if is_bulk:
        try:
            from django.core.management import call_command
            import threading
            
            def send_pending():
                try:
                    call_command(
                        'send_pending_notifications', 
                        '--batch-size=100'
                    )
                except Exception as e:
                    logger.error(f"Error in background send: {e}")
            
            thread = threading.Thread(target=send_pending, daemon=True)
            thread.start()
            logger.info(
                "[notification_signals] Started background email/telegram send"
            )
        except Exception as e:
            logger.error(f"Error starting background send: {e}")


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
    for employee in all_employees:
        try:
            notification = create_document_ready_notification(
                document,
                employee,
                send_immediately=not is_bulk
            )
            
            # Для массовой - отправляем только веб сразу
            if is_bulk and notification:
                try:
                    settings_obj = NotificationService.get_user_settings(
                        employee,
                        notification.notification_type
                    )
                    
                    if settings_obj.send_web:
                        NotificationService.send_web_socket(notification)
                        notification.sent_web = True
                        notification.save(update_fields=['sent_web'])
                except Exception as e:
                    logger.error(f"Error sending web notification: {e}")
            
            created_count += 1
        except Exception as e:
            logger.error(
                f"Error creating notification for user {employee.id}: {e}"
            )
    
    logger.info(
        f"[notification_signals] Created {created_count}/{recipient_count} "
        f"notifications (bulk={is_bulk})"
    )
    
    # Для массовой рассылки - запускаем фоновую отправку
    if is_bulk:
        try:
            from django.core.management import call_command
            import threading
            
            def send_pending():
                try:
                    call_command(
                        'send_pending_notifications',
                        '--batch-size=100'
                    )
                except Exception as e:
                    logger.error(f"Error in background send: {e}")
            
            thread = threading.Thread(target=send_pending, daemon=True)
            thread.start()
            logger.info(
                "[notification_signals] Started background email/telegram send"
            )
        except Exception as e:
            logger.error(f"Error starting background send: {e}")


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
        
        NotificationService.create_notification_async(
            recipient=document.uploaded_by,
            notification_type_code='document_signed_all',
            title='Все ознакомились с документом',
            message=(
                f'Все сотрудники ознакомились с документом '
                f'"{document.title}"'
            ),
            content_object=document,
            action_url='/documents',
            metadata={
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
    for employee in active_employees:
        try:
            notification = create_document_ready_notification(
                document,
                employee,
                send_immediately=False  # Не отправляем email/telegram сразу
            )
            
            # Отправляем только веб-уведомление (быстро, через WebSocket)
            if notification:
                try:
                    from notifications.services import NotificationService
                    settings = NotificationService.get_user_settings(
                        employee,
                        notification.notification_type
                    )
                    
                    # Только веб
                    if settings.send_web:
                        NotificationService.send_web_socket(notification)
                        notification.sent_web = True
                        notification.save(update_fields=['sent_web'])
                except Exception as e:
                    logger.error(f"Error sending web notification: {e}")
            
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
    
    Args:
        document: Документ
        recipient: Получатель
        send_immediately: Отправить сразу или отложить (для массовых рассылок)
    """
    logger.info(
        f"[notification_signals] create_document_ready_notification "
        f"doc={document.id} recipient={recipient.id} "
        f"send_immediately={send_immediately}"
    )
    
    uploader_name = (
        document.uploaded_by.get_full_name()
        if document.uploaded_by
        else 'Администратор'
    )
    
    notification = NotificationService.create_notification_async(
        recipient=recipient,
        notification_type_code='document_ready',
        title='Новый документ на ознакомление',
        message=(
            f'{uploader_name} загрузил документ "{document.title}". '
            f'Требуется ознакомление.'
        ),
        content_object=document,
        action_url='/documents',
        metadata={
            'document_id': document.id,
            'uploaded_by_id': (
                document.uploaded_by.id if document.uploaded_by else None
            ),
            'sent_to_all': document.sent_to_all,
        },
    )
    
    if notification:
        logger.debug(
            f"[notification_signals] Created notification id={notification.id} "
            f"for user={recipient.id}"
        )
    else:
        logger.warning(
            f"[notification_signals] Failed to create notification "
            f"for user={recipient.id}"
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
        
        # Используем новый тип document_comment_reply
        NotificationService.create_notification_async(
            recipient=parent_author,
            notification_type_code='document_comment_reply',
            title=f'Ответ на ваш комментарий',
            message=(
                f'{author.get_full_name() or author.username} ответил на ваш '
                f'комментарий к документу "{document.title}"'
            ),
            content_object=comment,
            action_url='/documents',
            action_text='Посмотреть',
            metadata={
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
        
        NotificationService.create_notification_async(
            recipient=doc_author,
            notification_type_code='document_comment',
            title=f'Новый комментарий к документу',
            message=(
                f'{author.get_full_name() or author.username} оставил комментарий '
                f'к вашему документу "{document.title}"'
            ),
            content_object=comment,  
            action_url='/documents',
            action_text='Посмотреть',
            metadata={
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
        
        # Используем новый тип document_related
        NotificationService.create_notification_async(
            recipient=related_doc.uploaded_by,
            notification_type_code='document_related',
            title=f'Документ связан с другим',
            message=(
                f'Ваш документ "{related_doc.title}" связан '
                f'с документом "{main_document.title}"'
            ),
            content_object=main_document,
            action_url='/documents',
            action_text='Посмотреть',
            metadata={
                'document_id': main_document.id,
                'related_document_id': related_doc.id,
            },
        )
