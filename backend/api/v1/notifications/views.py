"""
API endpoints для работы с уведомлениями (версия 1).
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from notifications.models import Notification, NotificationCategory, NotificationType
from notifications.services import NotificationService



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
                'message': n.message,
                'short_message': n.short_message or n.message[:150],  # Краткое сообщение для превью
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
            'email_frequency': settings.email_frequency,
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
        
        if 'email_frequency' in request.data:
            settings.email_frequency = request.data['email_frequency']
        
        if 'telegram_enabled' in request.data:
            settings.send_telegram = request.data['telegram_enabled']
        
        settings.save()
        updated_count += 1
    
    return Response({
        'status': 'success',
        'updated_count': updated_count
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_telegram_link_status(request):
    """Получить статус привязки Telegram аккаунта"""
    from notifications.telegram_models import TelegramUser
    
    try:
        tg_user = TelegramUser.objects.get(
            user=request.user,
            is_active=True,
            telegram_id__isnull=False
        )
        
        return Response({
            'is_linked': True,
            'telegram_username': tg_user.telegram_username,
            'first_name': tg_user.first_name,
            'last_name': tg_user.last_name,
            'linked_at': tg_user.linked_at,
            'is_blocked': tg_user.is_blocked,
        })
    except TelegramUser.DoesNotExist:
        # Проверяем, может быть есть незавершенная привязка с кодом
        pending = TelegramUser.objects.filter(
            user=request.user,
            link_code__isnull=False
        ).first()
        
        response_data = {'is_linked': False}
        
        if pending and pending.is_link_code_valid():
            response_data['link_code'] = pending.link_code
        
        return Response(response_data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def generate_telegram_link_code(request):
    """Сгенерировать код для привязки Telegram аккаунта"""
    from notifications.telegram_models import TelegramUser
    
    # Проверяем что аккаунт еще не привязан
    existing = TelegramUser.objects.filter(
        user=request.user,
        is_active=True,
        telegram_id__isnull=False
    ).first()
    
    if existing:
        return Response({
            'status': 'error',
            'message': 'Telegram аккаунт уже привязан'
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Получаем или создаем запись БЕЗ telegram_id (он будет установлен при привязке)
    tg_user = TelegramUser.objects.filter(
        user=request.user
    ).first()
    
    if not tg_user:
        tg_user = TelegramUser.objects.create(
            user=request.user,
            is_active=False
        )
    
    # Генерируем новый код (даже если уже был старый)
    link_code = tg_user.generate_link_code()
    
    from django.conf import settings
    bot_username = getattr(settings, 'TELEGRAM_BOT_USERNAME', 'eusrr_bot')
    
    return Response({
        'status': 'success',
        'link_code': link_code,
        'bot_username': bot_username,
        'bot_link': f'https://t.me/{bot_username}',
        'expires_in_seconds': 900,  # 15 минут
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unlink_telegram(request):
    """Отвязать Telegram аккаунт"""
    from notifications.telegram_models import TelegramUser
    
    try:
        tg_user = TelegramUser.objects.get(
            user=request.user,
            is_active=True
        )
        
        tg_user.is_active = False
        tg_user.save()
        
        return Response({
            'status': 'success',
            'message': 'Telegram аккаунт отвязан'
        })
    except TelegramUser.DoesNotExist:
        return Response({
            'status': 'error',
            'message': 'Telegram аккаунт не привязан'
        }, status=status.HTTP_404_NOT_FOUND)


# ============================================
# Web Push API (для браузерных уведомлений)
# ============================================

from django.conf import settings
from push_notifications.models import WebPushDevice
import logging

logger = logging.getLogger(__name__)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_vapid_public_key(request):
    """
    Получить публичный VAPID ключ для подписки на push-уведомления.
    Этот ключ нужен браузеру для создания подписки.
    """
    return Response({
        'vapid_public_key': settings.VAPID_PUBLIC_KEY
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def subscribe_push(request):
    """
    Подписаться на Web Push уведомления.
    
    Ожидаемые данные:
    {
        "endpoint": "https://fcm.googleapis.com/...",
        "keys": {
            "p256dh": "...",
            "auth": "..."
        },
        "user_agent": "...",  // опционально
        "device_name": "..."  // опционально
    }
    """
    try:
        endpoint = request.data.get('endpoint')
        keys = request.data.get('keys', {})
        p256dh_key = keys.get('p256dh')
        auth_key = keys.get('auth')
        user_agent = request.data.get('user_agent', '')
        device_name = request.data.get('device_name', '') or 'Unknown'
        
        if not endpoint or not p256dh_key or not auth_key:
            return Response({
                'status': 'error',
                'message': 'Отсутствуют обязательные поля: endpoint, keys.p256dh, keys.auth'
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Обновляем или создаем устройство (django-push-notifications)
        device, created = WebPushDevice.objects.update_or_create(
            user=request.user,
            registration_id=endpoint,
            defaults={
                'p256dh': p256dh_key,
                'auth': auth_key,
                'browser': device_name,
                'active': True,
            }
        )
        
        # Логируем только создание нового устройства, не обновление
        if created:
            logger.info(f"[WebPush] New device for user {request.user.id}")
        
        return Response({
            'status': 'success',
            'message': 'Подписка на push-уведомления активирована',
            'created': created
        })
        
    except Exception as e:
        logger.exception(f"[WebPush] Error subscribing user {request.user.id}: {e}")
        return Response({
            'status': 'error',
            'message': 'Ошибка при создании подписки'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def unsubscribe_push(request):
    """
    Отписаться от Web Push уведомлений.
    
    Ожидаемые данные:
    {
        "endpoint": "https://fcm.googleapis.com/..."
    }
    
    Если endpoint не указан - отписывает от всех подписок пользователя.
    """
    try:
        endpoint = request.data.get('endpoint')
        
        if endpoint:
            # Удаляем конкретное устройство
            deleted, _ = WebPushDevice.objects.filter(
                user=request.user,
                registration_id=endpoint
            ).delete()
            
            if deleted:
                logger.info(f"[WebPush] Deleted device for user {request.user.id} (endpoint: {endpoint[:50]}...)")
                return Response({
                    'status': 'success',
                    'message': 'Подписка удалена'
                })
            else:
                return Response({
                    'status': 'error',
                    'message': 'Подписка не найдена'
                }, status=status.HTTP_404_NOT_FOUND)
        else:
            # Удаляем все устройства пользователя
            deleted, _ = WebPushDevice.objects.filter(user=request.user).delete()
            logger.info(f"[WebPush] Deleted all ({deleted}) devices for user {request.user.id}")
            return Response({
                'status': 'success',
                'message': f'Удалено подписок: {deleted}'
            })
            
    except Exception as e:
        logger.exception(f"[WebPush] Error unsubscribing user {request.user.id}: {e}")
        return Response({
            'status': 'error',
            'message': 'Ошибка при удалении подписки'
        }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_push_subscriptions(request):
    """
    Получить список активных push-подписок пользователя.
    """
    devices = WebPushDevice.objects.filter(
        user=request.user,
        active=True
    ).order_by('-date_created')
    
    return Response({
        'subscriptions': [
            {
                'id': device.id,
                'device_name': device.browser or 'Неизвестное устройство',
                'user_agent': '',
                'created_at': device.date_created.isoformat(),
                'updated_at': device.date_created.isoformat(),
            }
            for device in devices
        ]
    })
