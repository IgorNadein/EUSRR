"""
Signals для автоматической генерации уведомлений в модуле Requests.

Обрабатывает события:
- Новая заявка (для ответственных/руководителей)
- Одобрение заявки
- Отклонение заявки
- Комментарий к заявке
- Изменение статуса заявки
"""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.contrib.auth import get_user_model

from .models import Request, RequestComment
from notifications.services import NotificationService

Employee = get_user_model()


@receiver(post_save, sender=Request)
def create_request_notifications(sender, instance, created, **kwargs):
    """
    Создает уведомления при создании или изменении заявки.
    
    Обрабатывает:
    1. Новая заявка - уведомление руководителю/ответственным
    2. Изменение статуса - уведомление автору
    """
    request_obj = instance
    
    if created and request_obj.status != 'draft':
        # Новая заявка - уведомляем ответственных
        notify_new_request(request_obj)
    elif not created:
        # Проверяем изменение статуса
        # Получаем предыдущее состояние из БД
        try:
            old_request = Request.objects.get(pk=request_obj.pk)
            if hasattr(request_obj, '_old_status'):
                old_status = request_obj._old_status
                new_status = request_obj.status
                
                if old_status != new_status:
                    notify_status_change(request_obj, old_status, new_status)
        except Request.DoesNotExist:
            pass


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


@receiver(post_save, sender=RequestComment)
def create_comment_notification(sender, instance, created, **kwargs):
    """
    Создает уведомление при добавлении комментария к заявке.
    """
    if not created:
        return
    
    comment = instance
    request_obj = comment.request
    author = comment.author
    
    # Уведомляем автора заявки (если комментарий не от него)
    if request_obj.employee.id != author.id:
        NotificationService.create_notification(
            recipient=request_obj.employee,
            notification_type_code='request_comment',
            title='Новый комментарий к вашей заявке',
            message=(
                f'{author.get_full_name() or author.username} '
                f'прокомментировал заявку: {comment.text[:100]}'
            ),
            content_object=request_obj,
            action_url=f'/requests/{request_obj.id}/',
            metadata={
                'request_id': request_obj.id,
                'request_type': request_obj.type,
                'comment_id': comment.id,
                'author_id': author.id,
            }
        )
    
    # Также уведомляем согласующего (если есть и это не он)
    if (request_obj.approver and 
        request_obj.approver.id != author.id and
        request_obj.approver.id != request_obj.employee.id):
        NotificationService.create_notification(
            recipient=request_obj.approver,
            notification_type_code='request_comment',
            title='Комментарий к заявке',
            message=(
                f'{author.get_full_name() or author.username} '
                f'прокомментировал заявку: {comment.text[:100]}'
            ),
            content_object=request_obj,
            action_url=f'/requests/{request_obj.id}/',
            metadata={
                'request_id': request_obj.id,
                'request_type': request_obj.type,
                'comment_id': comment.id,
                'author_id': author.id,
            }
        )


# ===== Вспомогательные функции =====

def notify_new_request(request_obj):
    """
    Отправляет уведомление о новой заявке ответственным лицам.
    """
    # Определяем получателей в зависимости от типа заявки
    recipients = []
    
    # 1. Руководитель отдела сотрудника
    if request_obj.department and request_obj.department.head:
        head = request_obj.department.head
        if head.id != request_obj.employee.id:
            recipients.append(head)
    
    # 2. Если есть назначенный согласующий
    if request_obj.approver:
        if request_obj.approver not in recipients:
            recipients.append(request_obj.approver)
    
    # 3. Пользователи с правом обрабатывать заявки
    users_with_permission = Employee.objects.filter(
        user_permissions__codename='can_process_requests'
    ).exclude(id=request_obj.employee.id)
    
    for user in users_with_permission:
        if user not in recipients:
            recipients.append(user)
    
    # Отправляем уведомления
    for recipient in recipients:
        NotificationService.create_notification(
            recipient=recipient,
            notification_type_code='request_new',
            title=f'Новая заявка от {request_obj.employee.get_full_name()}',
            message=(
                f'Тип: {request_obj.get_type_display()}. '
                f'{request_obj.comment[:100] if request_obj.comment else ""}'
            ),
            content_object=request_obj,
            action_url=f'/requests/{request_obj.id}/',
            metadata={
                'request_id': request_obj.id,
                'request_type': request_obj.type,
                'employee_id': request_obj.employee.id,
                'department_id': (
                    request_obj.department.id 
                    if request_obj.department else None
                ),
            }
        )


def notify_status_change(request_obj, old_status, new_status):
    """
    Отправляет уведомление при изменении статуса заявки.
    """
    # Уведомляем автора заявки
    recipient = request_obj.employee
    
    # Определяем тип уведомления и сообщение
    if new_status == 'approved':
        notification_type = 'request_approved'
        title = 'Ваша заявка одобрена'
        approver_name = (
            request_obj.approver.get_full_name() 
            if request_obj.approver else 'Руководитель'
        )
        message = (
            f'Заявка "{request_obj.get_type_display()}" '
            f'одобрена пользователем {approver_name}'
        )
    elif new_status == 'rejected':
        notification_type = 'request_rejected'
        title = 'Ваша заявка отклонена'
        approver_name = (
            request_obj.approver.get_full_name() 
            if request_obj.approver else 'Руководитель'
        )
        message = (
            f'Заявка "{request_obj.get_type_display()}" '
            f'отклонена пользователем {approver_name}'
        )
    else:
        # Общее уведомление об изменении статуса
        notification_type = 'request_status_changed'
        title = 'Статус заявки изменен'
        message = (
            f'Статус заявки "{request_obj.get_type_display()}" '
            f'изменен: {old_status} → {new_status}'
        )
    
    NotificationService.create_notification(
        recipient=recipient,
        notification_type_code=notification_type,
        title=title,
        message=message,
        content_object=request_obj,
        action_url=f'/requests/{request_obj.id}/',
        metadata={
            'request_id': request_obj.id,
            'request_type': request_obj.type,
            'old_status': old_status,
            'new_status': new_status,
            'approver_id': (
                request_obj.approver.id if request_obj.approver else None
            ),
        }
    )
