"""
Signals для автоматической генерации уведомлений в модуле Documents.

Обрабатывает события:
- Новый документ на ознакомление
- Все сотрудники ознакомились
- Напоминание о необходимости ознакомления (через Celery task)
"""

from django.db.models.signals import post_save, m2m_changed
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import Document, DocumentAcknowledgement
from notifications.services import NotificationService

Employee = get_user_model()


@receiver(post_save, sender=Document)
def create_document_notification(sender, instance, created, **kwargs):
    """
    Создает уведомления при создании нового документа.
    
    Уведомления отправляются:
    - Всем активным сотрудникам (если sent_to_all=True)
    - Выбранным получателям (через m2m_changed signal)
    """
    if not created:
        return
    
    document = instance
    
    # Если документ отправляется всем - создаем уведомления сразу
    if document.sent_to_all:
        notify_all_employees(document)


@receiver(m2m_changed, sender=Document.recipients.through)
def notify_specific_recipients(sender, instance, action, pk_set, **kwargs):
    """
    Уведомляет конкретных получателей при добавлении в список.
    """
    if action != 'post_add':
        return
    
    document = instance
    
    # Не отправляем индивидуальные уведомления если документ для всех
    if document.sent_to_all:
        return
    
    # Уведомляем новых получателей
    for user_id in pk_set:
        try:
            user = Employee.objects.get(id=user_id)
            create_document_ready_notification(document, user)
        except Employee.DoesNotExist:
            continue


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
        total_recipients = document.recipients.count()
    
    # Проверяем количество ознакомившихся
    acknowledged_count = document.acknowledgements.count()
    
    # Если все ознакомились - уведомляем загрузившего
    if (acknowledged_count >= total_recipients and 
        total_recipients > 0 and
        document.uploaded_by):
        
        NotificationService.create_notification(
            recipient=document.uploaded_by,
            notification_type_code='document_signed_all',
            title='Все ознакомились с документом',
            message=(
                f'Все сотрудники ознакомились с документом '
                f'"{document.title}"'
            ),
            content_object=document,
            action_url=f'/documents/{document.id}/',
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
    """
    active_employees = Employee.objects.filter(is_active=True)
    
    # Исключаем загрузившего документ
    if document.uploaded_by:
        active_employees = active_employees.exclude(
            id=document.uploaded_by.id
        )
    
    for employee in active_employees:
        create_document_ready_notification(document, employee)


def create_document_ready_notification(document, recipient):
    """
    Создает уведомление о новом документе для конкретного получателя.
    """
    uploader_name = (
        document.uploaded_by.get_full_name()
        if document.uploaded_by
        else 'Администратор'
    )
    
    NotificationService.create_notification(
        recipient=recipient,
        notification_type_code='document_ready',
        title='Новый документ на ознакомление',
        message=(
            f'{uploader_name} загрузил документ "{document.title}". '
            f'Требуется ознакомление.'
        ),
        content_object=document,
        action_url=f'/documents/{document.id}/',
        metadata={
            'document_id': document.id,
            'uploaded_by_id': (
                document.uploaded_by.id if document.uploaded_by else None
            ),
            'sent_to_all': document.sent_to_all,
        }
    )
