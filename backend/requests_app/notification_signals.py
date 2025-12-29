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
    Уведомляет:
    - Автора заявки
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
        dept_employees = Employee.objects.filter(
            departments_links__department__in=request_obj.departments.all(),
            departments_links__is_active=True,
            is_active=True
        ).exclude(id__in=[author.id, request_obj.employee.id]).distinct()
        
        recipients_set.update(dept_employees)
    
    # Отправляем уведомления
    for recipient in recipients_set:
        NotificationService.create_notification(
            recipient=recipient,
            notification_type_code='request_comment',
            title='Новый комментарий к заявке',
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
    Отправляет уведомление о новой заявке:
    - Всем основным получателям (recipients)
    - Всем в копии (cc_users)
    - Согласующему (approver)
    - Руководителям отделов
    - Пользователям с правом can_process_requests
    
    При sent_to_all_department=True отправляет всем сотрудникам отделов
    """
    recipients_set = set()
    
    # 1. Основные получатели
    for recipient in request_obj.recipients.filter(is_active=True):
        recipients_set.add(recipient)
    
    # 2. Копия (CC)
    for cc_user in request_obj.cc_users.filter(is_active=True):
        recipients_set.add(cc_user)
    
    # 3. Если sent_to_all_department - все сотрудники отделов
    if request_obj.sent_to_all_department:
        dept_employees = Employee.objects.filter(
            departments_links__department__in=request_obj.departments.all(),
            departments_links__is_active=True,
            is_active=True
        ).exclude(id=request_obj.employee.id).distinct()
        
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
    dept_ids = list(request_obj.departments.values_list('id', flat=True))
    if request_obj.department_id and request_obj.department_id not in dept_ids:
        dept_ids.append(request_obj.department_id)
    
    if dept_ids:
        dept_processors = Employee.objects.filter(
            departments_links__department_id__in=dept_ids,
            departments_links__is_active=True,
            departments_links__role__scoped_permissions__code='can_process_requests',
            is_active=True
        ).exclude(id=request_obj.employee.id).distinct()
        
        recipients_set.update(dept_processors)
    
    # Определяем тип уведомления для каждого получателя
    author_name = (
        request_obj.employee.get_full_name() or 
        request_obj.employee.username
    )
    
    for recipient in recipients_set:
        # Определяем роль получателя
        is_primary = request_obj.recipients.filter(id=recipient.id).exists()
        is_cc = request_obj.cc_users.filter(id=recipient.id).exists()
        is_approver = request_obj.approver_id == recipient.id
        
        # Формируем заголовок и сообщение
        if is_approver:
            title = f'Новая заявка на согласование от {author_name}'
            notification_type = 'request_new'
        elif is_primary:
            title = f'Вам адресована заявка от {author_name}'
            notification_type = 'request_new'
        elif is_cc:
            title = f'Вы в копии заявки от {author_name}'
            notification_type = 'request_new'
        else:
            title = f'Новая заявка в отделе от {author_name}'
            notification_type = 'request_new'
        
        message = (
            f'Тип: {request_obj.get_type_display()}. '
            f'{request_obj.comment[:100] if request_obj.comment else ""}'
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
                'employee_id': request_obj.employee.id,
                'is_primary_recipient': is_primary,
                'is_cc': is_cc,
                'is_approver': is_approver,
            }
        )


def notify_status_change(request_obj, old_status, new_status):
    """
    Уведомляет о изменении статуса:
    - Всех получателей (recipients)
    - Всех в копии (cc_users)
    - Сотрудников отделов (если sent_to_all_department)
    
    ВАЖНО: автор не получает уведомление о решении (approve/reject), 
    так как он видит результат на странице request_process.html
    """
    recipients_to_notify = set()
    
    # 1. Автор - НЕ уведомляем при approved/rejected
    # (автор видит результат прямо на странице)
    if new_status not in ('approved', 'rejected'):
        recipients_to_notify.add(request_obj.employee)
    
    # 2. Основные получатели
    recipients_to_notify.update(
        request_obj.recipients.filter(is_active=True)
    )
    
    # 3. Копия
    recipients_to_notify.update(
        request_obj.cc_users.filter(is_active=True)
    )
    
    # 4. Если sent_to_all_department - все сотрудники отделов
    if request_obj.sent_to_all_department:
        dept_employees = Employee.objects.filter(
            departments_links__department__in=request_obj.departments.all(),
            departments_links__is_active=True,
            is_active=True
        ).exclude(id=request_obj.employee.id).distinct()
        
        recipients_to_notify.update(dept_employees)
    
    # Формируем уведомления
    for recipient in recipients_to_notify:
        if new_status == 'approved':
            notification_type = 'request_approved'
            title = 'Заявка одобрена'
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
            title = 'Заявка отклонена'
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
