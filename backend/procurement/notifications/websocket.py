"""
WebSocket broadcast для real-time уведомлений в модуле Procurement.

Отправляет события через Django Channels о изменениях заявок на закупку.
"""

import logging
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

logger = logging.getLogger(__name__)


def broadcast_request_update(request, event_type='request_updated'):
    """
    Отправить WebSocket событие об обновлении заявки.
    
    Отправляет уведомления:
    - Всем пользователям отдела
    - Создателю заявки
    
    Args:
        request: Объект ProcurementRequest
        event_type: Тип события (request_created, request_status_changed, etc.)
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            logger.debug("[Procurement WS] Channel layer не настроен")
            return

        # Данные заявки для broadcast
        data = {
            'id': request.id,
            'title': request.title,
            'status': request.status,
            'status_display': request.get_status_display(),
            'department_id': request.department_id,
            'requestor_id': request.requestor_id,
        }

        # Отправляем всем пользователям отдела
        group_name = f'procurement_dept_{request.department_id}'
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'procurement_update',
                'event': event_type,
                'data': data,
            }
        )

        # Отправляем создателю заявки
        async_to_sync(channel_layer.group_send)(
            f'user_{request.requestor_id}',
            {
                'type': 'procurement_update',
                'event': event_type,
                'data': data,
            }
        )

        logger.debug(
            f"[Procurement WS] Broadcast {event_type} "
            f"для заявки #{request.id}"
        )
        
    except Exception as e:
        logger.warning(f"[Procurement WS] Broadcast failed: {e}")


def broadcast_request_created(request):
    """
    Broadcast о создании новой заявки.
    
    Args:
        request: Объект ProcurementRequest
    """
    broadcast_request_update(request, 'request_created')


def broadcast_request_status_changed(request):
    """
    Broadcast об изменении статуса заявки.
    
    Args:
        request: Объект ProcurementRequest
    """
    broadcast_request_update(request, 'request_status_changed')
