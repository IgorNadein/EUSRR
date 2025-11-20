"""
Тестовый view для создания уведомлений
"""
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from notifications.services import NotificationService


@login_required
def create_test_notification(request):
    """Создать тестовое уведомление для текущего пользователя"""
    notification = NotificationService.create_notification(
        recipient=request.user,
        notification_type_code='system_announcement',
        title='🎉 Тестовое уведомление',
        message='Это тестовое сообщение отправлено через API. Вы должны увидеть toast!',
        action_url='/',
    )
    
    if notification:
        return JsonResponse({
            'success': True,
            'notification_id': notification.id,
            'message': 'Уведомление создано и отправлено'
        })
    else:
        return JsonResponse({
            'success': False,
            'message': 'Не удалось создать уведомление'
        }, status=400)
