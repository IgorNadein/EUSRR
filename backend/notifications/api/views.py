"""
API endpoints для системы уведомлений v2.0


Новая архитектура:
- Notification с GenericForeignKey (actor/action_object/target)
- verb вместо category/type
- UserChannelPreferences для настроек каналов
"""
from datetime import datetime

from drf_spectacular.utils import OpenApiParameter, extend_schema
from django.db.models import Count, Q
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..models import Notification, UserChannelPreferences
from ..realtime import (
    send_notification_read_event,
    send_notifications_read_all_event,
)
from .serializers import (
    ChannelPreferencesSerializer,
    CountResponseSerializer,
    MarkAllAsReadRequestSerializer,
    MarkCategoryAsReadRequestSerializer,
    NotificationsListResponseSerializer,
    StatusResponseSerializer,
    SubscribePushRequestSerializer,
    UnsubscribePushRequestSerializer,
    UpdateChannelPreferencesSerializer,
    VapidPublicKeyResponseSerializer,
    VerbTypesResponseSerializer,
)


def _format_time_or_none(value):
    if value is None:
        return None
    return value.strftime('%H:%M')


def _parse_time_or_none(value):
    if not value:
        return None
    return datetime.strptime(value, '%H:%M').time()


@extend_schema(
    tags=["Notifications"],
    summary="Получить список уведомлений",
    parameters=[
        OpenApiParameter("page", int, OpenApiParameter.QUERY),
        OpenApiParameter("page_size", int, OpenApiParameter.QUERY),
        OpenApiParameter("verb", str, OpenApiParameter.QUERY),
        OpenApiParameter("unread_only", bool, OpenApiParameter.QUERY),
        OpenApiParameter("search", str, OpenApiParameter.QUERY),
    ],
    responses=NotificationsListResponseSerializer,
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_notifications(request):
    """
    Получить список уведомлений с пагинацией и фильтрами.

    Query params:
        - page: номер страницы (default: 1)
        - page_size: размер страницы (default: 20)
        - verb: фильтр по типу действия (liked, commented, mentioned и т.д.)
        - unread_only: только непрочитанные (true/false)
        - search: поиск по описанию
    """
    try:
        page = int(request.GET.get('page', 1))
    except (ValueError, TypeError):
        page = 1
    try:
        page_size = int(request.GET.get('page_size', 20))
    except (ValueError, TypeError):
        page_size = 20
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

    # Сериализация (совместимость с frontend)
    data = {
        'total': total,
        'page': page,
        'page_size': page_size,
        'unread_count': queryset.filter(unread=True).count(),
        'notifications': [
            {
                'id': n.id,
                # Frontend ожидает title, message, is_read, created_at
                'title': (
                    n.data['title']
                    if n.data and 'title' in n.data
                    else n.verb.replace('_', ' ').title()
                ),
                'message': n.description,
                'short_message': (
                    n.description[:100] + '...'
                    if len(n.description) > 100
                    else n.description
                ),
                'is_read': not n.unread,
                'created_at': n.timestamp.isoformat(),
                'category': n.verb,
                'action_url': n.action_url,
                # Дополнительные поля для обратной совместимости
                'verb': n.verb,
                'description': n.description,
                'actor': {
                    'id': n.actor.id if n.actor else None,
                    'name': str(n.actor) if n.actor else 'Система',
                    'type': n.actor_content_type.model if n.actor else None,
                } if n.actor else None,
                'unread': n.unread,
                'public': n.public,
                'deleted': n.deleted,
                'emailed': n.emailed,
                'timestamp': n.timestamp.isoformat(),
                'timesince': n.timesince,
            }
            for n in notifications
        ]
    }

    return Response(data)


@extend_schema(
    tags=["Notifications"],
    summary="Получить количество непрочитанных уведомлений",
    responses=CountResponseSerializer,
)
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


@extend_schema(
    tags=["Notifications"],
    summary="Отметить уведомление как прочитанное",
    request=None,
    responses={200: StatusResponseSerializer, 404: StatusResponseSerializer},
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_as_read(request, notification_id):
    """Отметить уведомление как прочитанное"""
    try:
        notification = Notification.objects.get(
            id=notification_id,
            recipient=request.user
        )
        was_unread = notification.unread
        notification.mark_as_read()

        if was_unread:
            send_notification_read_event(request.user.id, notification_id)

        return Response({
            'status': 'success',
            'notification_id': notification_id
        })

    except Notification.DoesNotExist:
        return Response(
            {'status': 'error', 'message': 'Notification not found'},
            status=status.HTTP_404_NOT_FOUND
        )


@extend_schema(
    tags=["Notifications"],
    summary="Отметить уведомление как непрочитанное",
    request=None,
    responses={200: StatusResponseSerializer, 404: StatusResponseSerializer},
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


@extend_schema(
    tags=["Notifications"],
    summary="Отметить все уведомления как прочитанные",
    request=MarkAllAsReadRequestSerializer,
    responses=StatusResponseSerializer,
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

    notification_ids = list(queryset.values_list('id', flat=True))
    count = queryset.mark_all_as_read()

    if notification_ids:
        send_notifications_read_all_event(
            request.user.id,
            notification_ids,
            category=verb,
        )

    return Response({
        'status': 'success',
        'count': count
    })


@extend_schema(
    tags=["Notifications"],
    summary="Отметить группу уведомлений как прочитанную",
    request=MarkCategoryAsReadRequestSerializer,
    responses={200: StatusResponseSerializer, 400: StatusResponseSerializer},
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_category_as_read(request):
    """
    Отметить группу уведомлений по списку verb'ов как прочитанные

    Body:
        - verbs: список verb'ов для отметки (array)
        - category: название категории (опционально, для логирования)

    Example:
        POST /api/v1/notifications/category/read/
        {
            "verbs": ["request_new", "request_updated"],
            "category": "Заявки"
        }
    """
    verbs = request.data.get('verbs', [])

    if not verbs or not isinstance(verbs, list):
        return Response(
            {'status': 'error', 'message': 'verbs array is required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Отмечаем все уведомления с этими verb'ами
    queryset = Notification.objects.filter(
        recipient=request.user,
        unread=True,
        deleted=False,
        verb__in=verbs,
    )

    notification_ids = list(queryset.values_list('id', flat=True))
    count = queryset.mark_all_as_read()

    if notification_ids:
        send_notifications_read_all_event(
            request.user.id,
            notification_ids,
            category=request.data.get('category'),
        )

    return Response({
        'status': 'success',
        'verbs': verbs,
        'count': count
    })


@extend_schema(
    tags=["Notifications"],
    summary="Удалить уведомление",
    responses={200: StatusResponseSerializer, 404: StatusResponseSerializer},
)
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


@extend_schema(
    tags=["Notifications"],
    summary="Удалить все прочитанные уведомления",
    responses=StatusResponseSerializer,
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


@extend_schema(
    tags=["Notifications"],
    summary="Получить статистику по типам уведомлений",
    responses=VerbTypesResponseSerializer,
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_verb_types(request):
    """
    Получить список типов (verb) уведомлений с количеством.

    Возвращает статистику по типам уведомлений пользователя.
    """
    verb_stats = Notification.objects.filter(
        recipient=request.user,
        deleted=False,
    ).values('verb').annotate(
        total=Count('id'),
        unread=Count('id', filter=Q(unread=True))
    ).order_by('-total')

    # Возвращаем verb как есть - фронтенд сам сделает перевод
    data = [
        {
            'verb': item['verb'],
            'name': item['verb'],  # Фронтенд переведет
            'total': item['total'],
            'unread': item['unread'],
        }
        for item in verb_stats
    ]

    return Response({'verb_types': data})


@extend_schema(
    methods=['GET'],
    tags=["Notifications"],
    summary="Получить настройки каналов уведомлений",
    responses=ChannelPreferencesSerializer,
)
@extend_schema(
    methods=['PUT'],
    tags=["Notifications"],
    summary="Обновить настройки каналов уведомлений",
    request=UpdateChannelPreferencesSerializer,
    responses=StatusResponseSerializer,
)
@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def channel_preferences(request):
    """
    Получить или обновить настройки каналов уведомлений.

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
    prefs, _created = UserChannelPreferences.objects.get_or_create(
        user=request.user
    )

    if request.method == 'GET':
        data = {
            'web_enabled': prefs.web_enabled,
            'email_enabled': prefs.email_enabled,
            'email_frequency': prefs.email_frequency,
            'push_enabled': prefs.push_enabled,
            'dnd_enabled': prefs.dnd_enabled,
            'dnd_start_time': _format_time_or_none(prefs.dnd_start_time),
            'dnd_end_time': _format_time_or_none(prefs.dnd_end_time),
            'disabled_verbs': prefs.disabled_verbs,
        }
        return Response(data)

    if request.method == 'PUT':
        # Обновляем настройки
        if 'web_enabled' in request.data:
            prefs.web_enabled = request.data.get('web_enabled')

        if 'email_enabled' in request.data:
            prefs.email_enabled = request.data.get('email_enabled')

        if 'email_frequency' in request.data:
            frequency = request.data.get('email_frequency')
            if frequency in ['instant', 'daily', 'weekly', 'disabled']:
                prefs.email_frequency = frequency

        if 'push_enabled' in request.data:
            prefs.push_enabled = request.data.get('push_enabled')

        if 'dnd_enabled' in request.data:
            prefs.dnd_enabled = request.data.get('dnd_enabled')

        if 'dnd_start_time' in request.data:
            time_str = request.data.get('dnd_start_time')
            prefs.dnd_start_time = _parse_time_or_none(time_str)

        if 'dnd_end_time' in request.data:
            time_str = request.data.get('dnd_end_time')
            prefs.dnd_end_time = _parse_time_or_none(time_str)

        if 'disabled_verbs' in request.data:
            prefs.disabled_verbs = request.data.get('disabled_verbs')

        prefs.save()

        return Response({
            'status': 'success',
            'message': 'Preferences updated'
        })

    return Response(
        {'status': 'error', 'message': 'Method not allowed'},
        status=status.HTTP_405_METHOD_NOT_ALLOWED,
    )


@extend_schema(
    tags=["Notifications"],
    summary="Получить публичный VAPID ключ",
    responses={
        200: VapidPublicKeyResponseSerializer,
        503: VapidPublicKeyResponseSerializer,
    },
)
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_vapid_public_key(request):
    """
    Получить публичный VAPID ключ для Web Push подписки.

    Returns:
        - vapid_public_key: публичный ключ в формате base64url
    """
    from django.conf import settings

    vapid_key = getattr(settings, 'VAPID_PUBLIC_KEY', None)

    if not vapid_key:
        return Response(
            {
                'status': 'error',
                'message': 'VAPID keys not configured',
                'vapid_public_key': None
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE
        )

    return Response({
        'status': 'success',
        'vapid_public_key': vapid_key
    })


@extend_schema(
    tags=["Notifications"],
    summary="Подписаться на Web Push",
    request=SubscribePushRequestSerializer,
    responses={200: StatusResponseSerializer, 400: StatusResponseSerializer},
)
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def subscribe_push(request):
    """
    Подписка на Web Push уведомления.

    Body:
        - endpoint: URL для отправки push
        - keys: {p256dh, auth} ключи шифрования
        - device_name: название устройства/браузера (опционально)
    """
    from push_notifications.models import WebPushDevice

    endpoint = request.data.get('endpoint')
    keys = request.data.get('keys', {})
    device_name = request.data.get('device_name', 'unknown')

    if not endpoint or not keys:
        return Response(
            {'status': 'error', 'message': 'endpoint and keys required'},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Регистрируем устройство
    device, created = WebPushDevice.objects.update_or_create(
        user=request.user,
        registration_id=endpoint,
        defaults={
            'p256dh': keys.get('p256dh', ''),
            'auth': keys.get('auth', ''),
            'browser': device_name,
            'active': True,
        }
    )

    return Response({
        'status': 'success',
        'message': (
            'Push subscription created'
            if created
            else 'Push subscription updated'
        ),
        'created': created,
        'device_id': device.id
    })


@extend_schema(
    methods=['POST', 'DELETE'],
    tags=["Notifications"],
    summary="Отписаться от Web Push",
    request=UnsubscribePushRequestSerializer,
    responses=StatusResponseSerializer,
)
@api_view(['POST', 'DELETE'])
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
        'message': f'Deleted {deleted_count} push subscription(s)',
        'deleted_count': deleted_count
    })
