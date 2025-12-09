"""
Celery задачи для модуля закупок.
Асинхронная отправка уведомлений.
"""

from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string

from .models import ProcurementRequest, Approval


@shared_task
def send_approval_request_email(request_id, approver_id):
    """
    Отправить email с запросом на согласование.
    
    Args:
        request_id: ID заявки на закупку
        approver_id: ID согласующего сотрудника
    """
    try:
        request = ProcurementRequest.objects.get(pk=request_id)
        approval = request.approvals.get(approver_id=approver_id)
        
        subject = f'Требуется согласование заявки: {request.title}'
        
        context = {
            'request': request,
            'approval': approval,
            'approver': approval.approver,
        }
        
        # Попробуем использовать шаблон, если существует
        try:
            html_message = render_to_string(
                'procurement/emails/approval_request.html',
                context
            )
        except Exception:
            # Если шаблона нет, используем простое текстовое сообщение
            html_message = None
        
        message = (
            f'Здравствуйте, {approval.approver.get_full_name()}!\n\n'
            f'Требуется ваше согласование заявки на закупку:\n'
            f'Название: {request.title}\n'
            f'Описание: {request.description}\n'
            f'Сумма: {request.estimated_cost}₽\n'
            f'Отдел: {request.department.name}\n'
            f'Срочность: {request.get_urgency_display()}\n\n'
            f'Для согласования перейдите в систему.'
        )
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[approval.approver.email],
            html_message=html_message,
            fail_silently=False,
        )
        
        return f'Email sent to {approval.approver.email}'
    
    except Exception as e:
        return f'Error sending email: {str(e)}'


@shared_task
def send_status_change_email(request_id, new_status):
    """
    Отправить email о изменении статуса заявки.
    
    Args:
        request_id: ID заявки на закупку
        new_status: Новый статус заявки
    """
    try:
        request = ProcurementRequest.objects.get(pk=request_id)
        
        status_messages = {
            'approved': 'одобрена',
            'rejected': 'отклонена',
            'in_progress': 'в работе',
            'completed': 'завершена',
            'cancelled': 'отменена',
        }

        status_text = status_messages.get(
            new_status,
            f'изменён на "{request.get_status_display()}"'
        )
        
        subject = f'Статус заявки изменён: {request.title}'
        
        message = (
            f'Здравствуйте, {request.requestor.get_full_name()}!\n\n'
            f'Статус вашей заявки на закупку был изменён.\n'
            f'Название: {request.title}\n'
            f'Новый статус: {status_text}\n\n'
        )
        
        if new_status == 'rejected':
            # Добавляем комментарии отклонивших
            rejections = request.approvals.filter(status='rejected')
            if rejections.exists():
                message += 'Комментарии:\n'
                for rejection in rejections:
                    message += (
                        f'- {rejection.approver.get_full_name()}: '
                        f'{rejection.comment}\n'
                    )
        
        message += '\nДля подробной информации перейдите в систему.'
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.requestor.email],
            fail_silently=False,
        )
        
        return f'Email sent to {request.requestor.email}'
    
    except Exception as e:
        return f'Error sending email: {str(e)}'


@shared_task
def send_approval_notification_email(approval_id):
    """
    Отправить email об изменении статуса согласования.
    
    Args:
        approval_id: ID записи согласования
    """
    try:
        approval = Approval.objects.select_related(
            'request', 'approver', 'request__requestor'
        ).get(pk=approval_id)
        
        request = approval.request
        
        if approval.status == 'approved':
            subject = f'Этап согласования пройден: {request.title}'
            message = (
                f'Здравствуйте, {request.requestor.get_full_name()}!\n\n'
                f'{approval.approver.get_full_name()} одобрил '
                f'вашу заявку на закупку "{request.title}".\n\n'
            )
            
            # Проверяем, все ли согласования пройдены
            pending_approvals = request.approvals.filter(
                status='pending'
            ).count()
            
            if pending_approvals > 0:
                message += (
                    f'Ожидается согласование ещё от '
                    f'{pending_approvals} человек(а).\n'
                )
            else:
                message += 'Все согласования получены! Можно приступать к закупке.\n'
        
        elif approval.status == 'rejected':
            subject = f'Заявка отклонена: {request.title}'
            message = (
                f'Здравствуйте, {request.requestor.get_full_name()}!\n\n'
                f'{approval.approver.get_full_name()} отклонил '
                f'вашу заявку на закупку "{request.title}".\n\n'
                f'Причина: {approval.comment}\n\n'
                f'Пожалуйста, внесите необходимые изменения и '
                f'отправьте заявку повторно.\n'
            )
        else:
            # Не отправляем email для других статусов
            return 'No email needed for this status'
        
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[request.requestor.email],
            fail_silently=False,
        )
        
        return f'Email sent to {request.requestor.email}'
    
    except Exception as e:
        return f'Error sending email: {str(e)}'


@shared_task
def send_budget_alert_email(department_id):
    """
    Отправить предупреждение о превышении бюджета.
    
    Args:
        department_id: ID отдела
    """
    from employees.models import Department
    
    try:
        department = Department.objects.get(pk=department_id)
        
        # Получаем текущий бюджет отдела
        from .models import Budget
        current_budget = Budget.objects.filter(
            department=department
        ).order_by('-year', '-quarter').first()
        
        if not current_budget:
            return 'No budget found'
        
        utilization = current_budget.utilization_percentage
        
        subject = f'Предупреждение о бюджете: {department.name}'
        
        message = (
            f'Здравствуйте!\n\n'
            f'Бюджет отдела "{department.name}" израсходован на {utilization}%.\n'
            f'Выделено: {current_budget.allocated_amount}₽\n'
            f'Потрачено: {current_budget.spent_amount}₽\n'
            f'Остаток: {current_budget.remaining_amount}₽\n\n'
        )
        
        if utilization >= 90:
            message += (
                'ВНИМАНИЕ: Бюджет почти исчерпан! '
                'Требуется срочное планирование.\n'
            )
        elif utilization >= 75:
            message += (
                'Бюджет активно расходуется. '
                'Рекомендуется контроль новых заявок.\n'
            )
        
        # Отправляем руководителю отдела и финансовому директору
        recipients = []
        if department.head and department.head.email:
            recipients.append(department.head.email)
        
        # TODO: Добавить email финансового директора из настроек
        
        if recipients:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                fail_silently=False,
            )
            return f'Budget alert sent to {", ".join(recipients)}'
        
        return 'No recipients found'
    
    except Exception as e:
        return f'Error sending budget alert: {str(e)}'
