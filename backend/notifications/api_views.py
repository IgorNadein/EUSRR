from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from .models import Notification, NotificationCategory, NotificationType
from .services import NotificationService


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    """Получить список уведомлений с пагинацией и фильтрами"""
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    category = request.GET.get('category')
    is_read = request.GET.get('is_read')
    search = request.GET.get('search', '').strip()
    unread_only = request.GET.get('unread_only', 'false').lower() == 'true'

    queryset = Notification.objects.filter(
        recipient=request.user,
        is_archived=False
    ).select_related(
        'notification_type',
        'notification_type__category'
    ).order_by('-created_at')

    # Фильтр по категории
    if category:
        queryset = queryset.filter(notification_type__category__code=category)

    # Фильтр по статусу прочитанности
    if is_read and is_read in ('true', 'false'):
        queryset = queryset.filter(is_read=(is_read == 'true'))
    elif unread_only:
        queryset = queryset.filter(is_read=False)

    # Поиск по заголовку и тексту
    if search:
        from django.db.models import Q
        queryset = queryset.filter(
            Q(title__icontains=search) |
            Q(message__icontains=search) |
            Q(short_message__icontains=search)
        )

    total = queryset.count()
    start = (page - 1) * page_size
    end = start + page_size

    notifications = queryset[start:end]

    data = {
        'total': total,
        'page': page,
        'page_size': page_size,
        'notifications': [
            {
                'id': n.id,
                'title': n.title,
                'message': n.message,  # Полное сообщение для списка
                'category': n.notification_type.category.code,
                'category_name': n.notification_type.category.name,
                'icon': n.notification_type.category.icon,
                'color': n.notification_type.category.color,
                'priority': n.notification_type.priority,
                'is_read': n.is_read,
                'action_url': n.action_url,
                'action_text': n.action_text,
                'created_at': n.created_at.isoformat(),
            }
            for n in notifications
        ]
    }

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_unread_count(request):
    """Получить количество непрочитанных уведомлений"""
    count = Notification.objects.filter(
        recipient=request.user,
        is_read=False,
        is_archived=False
    ).count()

    return Response({'count': count})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_as_read(request, notification_id):
    """Отметить уведомление как прочитанное"""
    success = NotificationService.mark_as_read(notification_id, request.user)

    if success:
        return Response({'status': 'success'})
    else:
        return Response(
            {'status': 'error', 'message': 'Notification not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_as_read(request):
    """Отметить все уведомления как прочитанные"""
    category = request.data.get('category')
    count = NotificationService.mark_all_as_read(request.user, category)

    return Response({'status': 'success', 'count': count})


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, notification_id):
    """Удалить уведомление (архивировать)"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            recipient=request.user
        )
        notification.archive()
        return Response({'status': 'success'})
    except Notification.DoesNotExist:
        return Response(
            {'status': 'error', 'message': 'Notification not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_categories(request):
    """Получить список категорий уведомлений"""
    categories = NotificationCategory.objects.filter(is_active=True)

    data = [
        {
            'code': cat.code,
            'name': cat.name,
            'icon': cat.icon,
            'color': cat.color,
        }
        for cat in categories
    ]

    return Response(data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_user_settings(request):
    """Получить настройки уведомлений пользователя по категориям"""
    categories = NotificationCategory.objects.filter(is_active=True)
    
    settings_by_category = {}
    
    for category in categories:
        # Получить типы уведомлений этой категории
        types = NotificationType.objects.filter(
            category=category,
            is_active=True
        )
        
        if not types.exists():
            continue
        
        # Получить настройки первого типа категории как представитель
        # (предполагается, что настройки одинаковы для всей категории)
        first_type = types.first()
        settings = NotificationService.get_user_settings(
            request.user, first_type
        )
        
        settings_by_category[category.code] = {
            'is_enabled': settings.is_enabled,
            'web_enabled': settings.send_web,
            'email_enabled': settings.send_email,
            'telegram_enabled': settings.send_telegram,
        }
    
    return Response({
        'settings': settings_by_category
    })


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_user_settings(request):
    """Обновить настройки уведомлений пользователя"""
    notification_type_code = request.data.get('notification_type_code')

    try:
        notification_type = NotificationType.objects.get(
            code=notification_type_code
        )
    except NotificationType.DoesNotExist:
        return Response(
            {'status': 'error', 'message': 'Notification type not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    settings = NotificationService.get_user_settings(
        request.user, notification_type
    )

    # Обновить настройки
    if 'is_enabled' in request.data and not notification_type.is_required:
        settings.is_enabled = request.data['is_enabled']

    if 'send_web' in request.data:
        settings.send_web = request.data['send_web']

    if 'send_email' in request.data:
        settings.send_email = request.data['send_email']

    if 'send_telegram' in request.data:
        settings.send_telegram = request.data['send_telegram']

    if 'send_whatsapp' in request.data:
        settings.send_whatsapp = request.data['send_whatsapp']

    if 'send_wechat' in request.data:
        settings.send_wechat = request.data['send_wechat']

    if 'quiet_hours_enabled' in request.data:
        settings.quiet_hours_enabled = request.data['quiet_hours_enabled']

    if 'quiet_start_time' in request.data:
        settings.quiet_start_time = request.data['quiet_start_time']

    if 'quiet_end_time' in request.data:
        settings.quiet_end_time = request.data['quiet_end_time']

    settings.save()

    return Response({'status': 'success'})


@api_view(['PUT'])
@permission_classes([IsAuthenticated])
def update_category_settings(request):
    """
    Обновить настройки для всех уведомлений категории
    """
    category_code = request.data.get('category')
    
    if not category_code:
        return Response(
            {'status': 'error', 'message': 'Category is required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        category = NotificationCategory.objects.get(code=category_code)
    except NotificationCategory.DoesNotExist:
        return Response(
            {'status': 'error', 'message': 'Category not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Получить все типы уведомлений категории
    notification_types = NotificationType.objects.filter(
        category=category,
        is_active=True
    )
    
    # Обновить настройки для каждого типа
    updated_count = 0
    for notification_type in notification_types:
        settings = NotificationService.get_user_settings(
            request.user, notification_type
        )
        
        # Обновить поля
        if 'is_enabled' in request.data and not notification_type.is_required:
            settings.is_enabled = request.data['is_enabled']
        
        if 'web_enabled' in request.data:
            settings.send_web = request.data['web_enabled']
        
        if 'email_enabled' in request.data:
            settings.send_email = request.data['email_enabled']
        
        if 'telegram_enabled' in request.data:
            settings.send_telegram = request.data['telegram_enabled']
        
        settings.save()
        updated_count += 1
    
    return Response({
        'status': 'success',
        'updated_count': updated_count
    })

