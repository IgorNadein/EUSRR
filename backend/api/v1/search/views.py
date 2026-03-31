# backend/api/v1/search/views.py
"""
API views для глобального поиска через django-watson.
"""
from __future__ import annotations

from typing import Any, Dict, List
from collections import Counter

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request as DRFRequest
from rest_framework.response import Response
from django.utils.html import escape
from watson.search import search as watson_search

from .serializers import SearchResponseSerializer


def _get_model_name(obj: Any) -> str:
    """Определяет тип модели для результата поиска."""
    model = type(obj)
    model_name = model.__name__.lower()
    
    mapping = {
        "post": "post",
        "employee": "employee",
        "department": "department",
        "request": "request",
        "chat": "chat",
        "message": "message",
        "calendarevent": "event",
        "event": "schedule_event",  # django-scheduler Event
        "procurementrequest": "procurement_request",
        "equipment": "equipment",
        "document": "document",
        "notification": "notification",
    }
    
    return mapping.get(model_name, model_name)


def _format_employee(obj: Any) -> Dict[str, Any]:
    """Форматирует сотрудника для API."""
    return {
        "model_name": "employee",
        "object_id": obj.pk,
        "title": f"{obj.last_name} {obj.first_name} {obj.patronymic or ''}".strip(),
        "description": getattr(obj.position, "name", "") if hasattr(obj, "position") else "",
        "url": f"/employees/{obj.pk}/",
        "meta": {
            "email": obj.email,
            "phone": str(obj.phone_number) if obj.phone_number else "",
        }
    }


def _format_department(obj: Any) -> Dict[str, Any]:
    """Форматирует отдел для API."""
    return {
        "model_name": "department",
        "object_id": obj.pk,
        "title": obj.name,
        "description": obj.description or "",
        "url": f"/departments/{obj.pk}/",
        "meta": {
            "head": str(obj.head) if hasattr(obj, "head") and obj.head else None
        }
    }


def _format_post(obj: Any) -> Dict[str, Any]:
    """Форматирует пост для API."""
    return {
        "model_name": "post",
        "object_id": obj.pk,
        "title": obj.title,
        "description": obj.body[:200] + "..." if len(obj.body) > 200 else obj.body,
        "url": f"/feed/{obj.pk}/",
        "meta": {
            "author": str(obj.author) if hasattr(obj, "author") else None,
            "created_at": obj.created_at.isoformat() if hasattr(obj, "created_at") else None,
        }
    }


def _format_request(obj: Any) -> Dict[str, Any]:
    """Форматирует заявление для API."""
    return {
        "model_name": "request",
        "object_id": obj.pk,
        "title": obj.title or f"{obj.get_type_display()} - {obj.employee}",
        "description": obj.comment[:200] + "..." if obj.comment and len(obj.comment) > 200 else (obj.comment or ""),
        "url": f"/requests/{obj.pk}/",
        "meta": {
            "status": obj.status,
            "type": obj.type,
            "employee": str(obj.employee) if hasattr(obj, "employee") else None,
        }
    }


def _format_chat(obj: Any) -> Dict[str, Any]:
    """Форматирует чат для API."""
    return {
        "model_name": "chat",
        "object_id": obj.pk,
        "title": obj.name or f"Чат #{obj.pk}",
        "description": obj.description or "",
        "url": f"/messages?chat={obj.pk}",
        "meta": {
            "type": obj.type if hasattr(obj, "type") else None,
        }
    }


def _format_message(obj: Any) -> Dict[str, Any]:
    """Форматирует сообщение для API."""
    return {
        "model_name": "message",
        "object_id": obj.pk,
        "title": f"Сообщение от {obj.author}" if hasattr(obj, "author") else f"Сообщение #{obj.pk}",
        "description": obj.content[:200] + "..." if len(obj.content) > 200 else obj.content,
        "url": f"/messages?chat={obj.chat.pk if hasattr(obj, 'chat') else ''}#msg-{obj.pk}",
        "meta": {
            "author": str(obj.author) if hasattr(obj, "author") else None,
            "chat": str(obj.chat) if hasattr(obj, "chat") else None,
        }
    }


def _format_event(obj: Any) -> Dict[str, Any]:
    """Форматирует календарное событие (CalendarEvent) для API."""
    return {
        "model_name": "event",
        "object_id": obj.pk,
        "title": obj.title,
        "description": obj.description or "",
        "url": f"/calendar?event={obj.pk}",
        "meta": {
            "start_date": obj.start_date.isoformat() if hasattr(obj, "start_date") else None,
        }
    }


def _format_schedule_event(obj: Any) -> Dict[str, Any]:
    """Форматирует событие расписания (django-scheduler Event) для API."""
    return {
        "model_name": "schedule_event",
        "object_id": obj.pk,
        "title": obj.title,
        "description": obj.description or "",
        "url": "/calendar/",
        "meta": {
            "start": obj.start.isoformat() if hasattr(obj, "start") else None,
            "end": obj.end.isoformat() if hasattr(obj, "end") and obj.end else None,
        }
    }


def _format_procurement_request(obj: Any) -> Dict[str, Any]:
    """Форматирует заявку на закупку для API."""
    return {
        "model_name": "procurement_request",
        "object_id": obj.pk,
        "title": obj.title,
        "description": obj.description[:200] + "..." if len(obj.description) > 200 else obj.description,
        "url": f"/procurement/requests/{obj.pk}/",
        "meta": {
            "status": obj.status if hasattr(obj, "status") else None,
            "requestor": str(obj.requestor) if hasattr(obj, "requestor") else None,
            "department": str(obj.department) if hasattr(obj, "department") else None,
        }
    }


def _format_equipment(obj: Any) -> Dict[str, Any]:
    """Форматирует оборудование для API."""
    return {
        "model_name": "equipment",
        "object_id": obj.pk,
        "title": obj.name,
        "description": f"Инв. №: {obj.inventory_number}" + (f", Сер. №: {obj.serial_number}" if obj.serial_number else ""),
        "url": f"/procurement/equipment/{obj.pk}/",
        "meta": {
            "inventory_number": obj.inventory_number,
            "status": obj.status if hasattr(obj, "status") else None,
            "location": obj.location if hasattr(obj, "location") else None,
        }
    }


def _format_document(obj: Any) -> Dict[str, Any]:
    """Форматирует документ для API."""
    return {
        "model_name": "document",
        "object_id": obj.pk,
        "title": obj.title,
        "description": obj.description[:200] + "..." if obj.description and len(obj.description) > 200 else (obj.description or ""),
        "url": f"/documents/{obj.pk}/",
        "meta": {
            "uploaded_by": str(obj.uploaded_by) if hasattr(obj, "uploaded_by") and obj.uploaded_by else None,
            "uploaded_at": obj.uploaded_at.isoformat() if hasattr(obj, "uploaded_at") else None,
        }
    }


def _format_notification(obj: Any) -> Dict[str, Any]:
    """Форматирует уведомление для API."""
    return {
        "model_name": "notification",
        "object_id": obj.pk,
        "title": obj.title,
        "description": obj.short_message or (obj.message[:150] + "..." if len(obj.message) > 150 else obj.message),
        "url": obj.action_url if hasattr(obj, "action_url") and obj.action_url else "/notifications/",
        "meta": {
            "is_read": obj.is_read if hasattr(obj, "is_read") else False,
            "created_at": obj.created_at.isoformat() if hasattr(obj, "created_at") else None,
        }
    }


def _format_result(obj: Any, model_name: str) -> Dict[str, Any]:
    """Форматирует результат поиска в зависимости от типа модели."""
    formatters = {
        "employee": _format_employee,
        "department": _format_department,
        "post": _format_post,
        "request": _format_request,
        "chat": _format_chat,
        "message": _format_message,
        "event": _format_event,
        "schedule_event": _format_schedule_event,
        "procurement_request": _format_procurement_request,
        "equipment": _format_equipment,
        "document": _format_document,
        "notification": _format_notification,
    }
    
    formatter = formatters.get(model_name)
    if formatter:
        return formatter(obj)
    
    # Фоллбэк для неизвестных типов
    return {
        "model_name": model_name,
        "object_id": obj.pk,
        "title": str(obj),
        "description": "",
        "url": "#",
        "meta": {}
    }


def _is_hr(user: Any) -> bool:
    """Проверяет права на просмотр всех заявлений."""
    return user.has_perm("requests_app.can_view_all_requests") or user.has_perm(
        "requests_app.can_process_requests"
    )


@extend_schema(
    tags=["Search"],
    summary="Глобальный поиск по системе",
    parameters=[
        OpenApiParameter("q", str, OpenApiParameter.QUERY, required=True),
        OpenApiParameter("limit", int, OpenApiParameter.QUERY),
    ],
    responses=SearchResponseSerializer,
)
@api_view(["GET"])
@permission_classes([IsAuthenticated])
def search_api_view(request: DRFRequest) -> Response:
    """
    API для глобального поиска через django-watson.
    
    Query Parameters:
        - q (str): Поисковый запрос
        - limit (int): Максимальное количество результатов на тип (default: 10)
    
    Returns:
        {
            "query": "поисковый запрос",
            "results": [
                {
                    "model_name": "post|employee|department|request|chat|message|event|procurement_request|equipment|document|notification",
                    "object_id": 123,
                    "title": "Заголовок",
                    "description": "Описание",
                    "url": "/path/to/object/",
                    "meta": {...}
                },
                ...
            ],
            "counts": {
                "post": 5,
                "employee": 3,
                ...
            },
            "total": 15
        }
    """
    raw_q = request.query_params.get("q", "") or ""
    query = escape(raw_q.strip())
    try:
        limit = int(request.query_params.get("limit", 10))
    except (ValueError, TypeError):
        limit = 10
    
    if not query:
        return Response(
            {
                "query": "",
                "results": [],
                "counts": {},
                "total": 0
            },
            status=status.HTTP_200_OK
        )
    
    # Выполняем поиск через watson
    search_results = watson_search(query)
    
    # Группируем и форматируем результаты
    results = []
    model_counts: Dict[str, int] = {}
    
    for search_result in search_results:
        obj = search_result.object
        
        # Пропускаем удаленные объекты
        if obj is None:
            continue
        
        model_name = _get_model_name(obj)
        
        # Фильтрация по правам доступа
        if model_name == "request":
            is_hr = _is_hr(request.user)
            if not is_hr and hasattr(obj, 'employee') and obj.employee != request.user:  # type: ignore[attr-defined]
                continue  # Пропускаем чужие заявления
        
        # Фильтрация уведомлений - показываем только свои
        if model_name == "notification":
            if hasattr(obj, 'recipient') and obj.recipient != request.user:  # type: ignore[attr-defined]
                continue  # Пропускаем чужие уведомления
        
        # Подсчитываем
        model_counts[model_name] = model_counts.get(model_name, 0) + 1
        
        # Ограничиваем количество на тип
        if model_counts[model_name] <= limit:
            formatted = _format_result(obj, model_name)
            results.append(formatted)
    
    # Готовим ответ
    response_data = {
        "query": query,
        "results": results,
        "counts": model_counts,
        "total": sum(model_counts.values())
    }
    
    # Валидируем через сериализатор (опционально, для проверки структуры)
    serializer = SearchResponseSerializer(data=response_data)
    if serializer.is_valid():
        return Response(serializer.validated_data, status=status.HTTP_200_OK)
    
    # Если валидация не прошла, все равно возвращаем результат (для отладки)
    return Response(response_data, status=status.HTTP_200_OK)
