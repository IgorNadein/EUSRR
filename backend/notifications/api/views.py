"""
API endpoints для системы уведомлений v2.0

Новая архитектура:
- Notification с GenericForeignKey (actor/action_object/target)
- verb вместо category/type
- UserChannelPreferences для настроек каналов
"""
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db import models

from ..models import Notification, UserChannelPreferences


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    """
    Получить список уведомлений с пагинацией и фильтрами
    
    Query params:
        - page: номер страницы (default: 1)
        - page_size: размер страницы (default: 20)
        - verb: фильтр по типу действия (liked, commented, mentioned и т.д.)
        - unread_only: только непрочитанные (true/false)
        - search: поиск по описанию
    """
    page = int(request.GET.get('page', 1))
    page_size = int(request.GET.get('page_size', 20))
    verb = request.GET.get('verb')
    unread_only = request.GET.get('unread_only', 'false').lower() == 'true'
    search = request.GET.get('search', '').strip()

    # Базовый queryset
    queryset = Notification.objects.filter(
        recipient=request.user,
        deleted=False,
    ).order_by('-timestamp')

    # Фильтры
    if verb:
        queryset = queryset.filter(verb=verb)
    
    if unread_only:
        queryset = queryset.unread()
    
    if search:
        queryset = queryset.filter(description__icontains=search)

    # Пагинация
    total = queryset.count()
    start = (page - 1) * page_size
    end = start + page_size
    notifications = queryset[start:end]

    # Сериализация
    data = {
        'total': total,
        'page': page,
        'page_size': page_size,
        'unread_count': queryset.filter(unread=True).count(),
        'notifications': [
            {
                'id': n.id,
                'verb': n.verb,
                'description': n.description,
                'actor': {
                    'id': n.actor.id if n.actor else None,
                    'name': str(n.actor) if n.actor else 'Система',
                    'type': n.actor_content_type.model if n.actor else None,
                } if n.actor else None,
                'action_url': n.action_url,
                'unread': n.unread,
                'public': n.public,
                'deleted': n.deleted,
                'emailed': n.emailed,
                'timestamp': n.timestamp.isoformat(),
                'timesince': n.timesince(),
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
        unread=True,
        deleted=False,
    ).count()

    return Response({'count': count})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_as_read(request, notification_id):
    """Отметить уведомление как прочитанное"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            recipient=request.user
        )
        notification.mark_as_read()
        
        return Response({
            'status': 'success',
            'notification_id': notification_id
        })
        
    except Notification.DoesNotExist:
        return Response(
            {'status': 'error', 'message': 'Notification not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_as_unread(request, notification_id):
    """Отметить уведомление как непрочитанное"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            recipient=request.user
        )
        notification.mark_as_unread()
        
        return Response({
            'status': 'success',
            'notification_id': notification_id
        })
        
    except Notification.DoesNotExist:
        return Response(
            {'status': 'error', 'message': 'Notification not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_all_as_read(request):
    """Отметить все уведомления как прочитанные"""
    verb = request.data.get('verb')  # Опционально - только определенный тип
    
    queryset = Notification.objects.filter(
        recipient=request.user,
        unread=True,
        deleted=False,
    )
    
    if verb:
        queryset = queryset.filter(verb=verb)
    
    count = queryset.mark_all_as_read()

    return Response({
        'status': 'success',
        'count': count
    })


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_notification(request, notification_id):
    """Удалить уведомление (soft delete)"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            recipient=request.user
        )
        notification.deleted = True
        notification.save(update_fields=['deleted'])
        
        return Response({'status': 'success'})
        
    except Notification.DoesNotExist:
        return Response(
            {'status': 'error', 'message': 'Notification not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_all_read(request):
    """Удалить все прочитанные уведомления"""
    count = Notification.objects.filter(
        recipient=request.user,
        unread=False,
        deleted=False,
    ).update(deleted=True)

    return Response({
        'status': 'success',
        'count': count
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_verb_types(request):
    """
    Получить список типов (verb) уведомлений с количеством
    
    Возвращает статистику по типам уведомлений пользователя.
    """
    from django.db.models import Count, Q
    
    verb_stats = Notification.objects.filter(
        recipient=request.user,
        deleted=False,
    ).values('verb').annotate(
        total=Count('id'),
        unread=Count('id', filter=Q(unread=True))
    ).order_by('-total')

    # Маппинг verb → человекочитаемое название
    verb_names = {
        'liked': 'Понравилось',
        'commented': 'Прокомментировал',
        'mentioned': 'Упомянул',
        'messaged': 'Отправил сообщение',
        'shared': 'Поделился',
        'posted': 'Опубликовал',
        'created': 'Создал',
        'updated': 'Обновил',
        'approved': 'Одобрил',
        'rejected': 'Отклонил',
        'scheduled': 'Запланировал',
        'notified': 'Уведомил',
    }
    
    data = [
        {
            'verb': item['verb'],
            'name': verb_names.get(item['verb'], item['verb'].title()),
            'total': item['total'],
            'unread': item['unread'],
        }
        for item in verb_stats
    ]

    return Response({'verb_types': data})


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def channel_preferences(request):
    """
    Получить или обновить настройки каналов уведомлений
    
    GET: Возвращает текущие настройки
    PUT: Обновляет настройки
    
    Настройки:
        - web_enabled: WebSocket уведомления (bool)
        - email_enabled: Email уведомления (bool)
        - email_frequency: instant/daily/weekly/disabled
        - push_enabled: Web Push уведомления (bool)
        - dnd_enabled: Режим "Не беспокоить" (bool)
        - dnd_start_time: Начало DND (HH:MM)
        - dnd_end_time: Конец DND (HH:MM)
        - disabled_verbs: Список отключенных типов (array)
    """
    # Получаем или создаем настройки
    prefs, created = UserChannelPreferences.objects.get_or_create(
        user=request.user
    )
    
    if request.method == 'GET':
        data = {
            'web_enabled': prefs.web_enabled,
            'email_enabled': prefs.email_enabled,
            'email_frequency': prefs.email_frequency,
            'push_enabled': prefs.push_enabled,
            'dnd_enabled': prefs.dnd_enabled,
            'dnd_start_time': prefs.dnd_start_time.strftime('%H:%M') if prefs.dnd_start_time else None,
            'dnd_end_time': prefs.dnd_end_time.strftime('%H:%M') if prefs.dnd_end_time else None,
            'disabled_verbs': prefs.disabled_verbs,
        }
        return Response(data)
    
    elif request.method == 'PUT':
        # Обновляем настройки
        if 'web_enabled' in request.data:
            prefs.web_enabled = request.data['web_enabled']
        
        if 'email_enabled' in request.data:
            prefs.email_enabled = request.data['email_enabled']
        
        if 'email_frequency' in request.data:
            frequency = request.data['email_frequency']
            if frequency in ['instant', 'daily', 'weekly', 'disabled']:
                prefs.email_frequency = frequency
        
        if 'push_enabled' in request.data:
            prefs.push_enabled = request.data['push_enabled']
        
        if 'dnd_enabled' in request.data:
            prefs.dnd_enabled = request.data['dnd_enabled']
        
        if 'dnd_start_time' in request.data:
            from datetime import datetime
            time_str = request.data['dnd_start_time']
            if time_str:
                prefs.dnd_start_time = datetime.strptime(time_str, '%H:%M').time()
        
        if 'dnd_end_time' in request.data:
            from datetime import datetime
            time_str = request.data['dnd_end_time']
            if time_str:
                prefs.dnd_end_time = datetime.strptime(time_str, '%H:%M').time()
        
        if 'disabled_verbs' in request.data:
            prefs.disabled_verbs = request.data['disabled_verbs']
        
        prefs.save()
        
        return Response({
            'status': 'success',
            'message': 'Preferences updated'
        })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def subscribe_push(request):
    """
    Подписка на Web Push уведомления
    
    Body:
        - subscription: объект subscription от браузера
    """
    from push_notifications.models import WebPushDevice
    
    subscription_data = request.data.get('subscription')
    
    if not subscription_data:
        return Response(
            {'status': 'error', 'message': 'Subscription data required'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Регистрируем устройство
    device, created = WebPushDevice.objects.update_or_create(
        user=request.user,
        registration_id=subscription_data.get('endpoint'),
        defaults={
            'p256dh': subscription_data.get('keys', {}).get('p256dh'),
            'auth': subscription_data.get('keys', {}).get('auth'),
            'browser': request.data.get('browser', 'unknown'),
            'active': True,
        }
    )
    
    return Response({
        'status': 'success',
        'created': created,
        'device_id': device.id
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def unsubscribe_push(request):
    """Отписка от Web Push уведомлений"""
    from push_notifications.models import WebPushDevice
    
    endpoint = request.data.get('endpoint')
    
    if endpoint:
        deleted_count, _ = WebPushDevice.objects.filter(
            user=request.user,
            registration_id=endpoint
        ).delete()
    else:
        # Удалить все устройства пользователя
        deleted_count, _ = WebPushDevice.objects.filter(
            user=request.user
        ).delete()
    
    return Response({
        'status': 'success',
        'deleted_count': deleted_count
    })
