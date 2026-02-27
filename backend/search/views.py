# backend/search/views.py
"""
Полнотекстовый поиск через django-watson.

Заменяет предыдущую реализацию с ручными Q-объектами на 
автоматическую индексацию watson.
"""
from __future__ import annotations

from typing import Any, Dict, List, Literal, TypedDict
from collections import Counter

from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.html import escape
from watson.search import search as watson_search

from feed.models import Post
from employees.models import Employee, Department
from requests_app.models import Request


class SearchItem(TypedDict):
    """Элемент единой выдачи поиска.

    Attributes:
        model_name (Literal["post","employee","department","request","chat","message","event"]):
            Тип найденной сущности.
        object (Any): Экземпляр модели, который будет отрисован в шаблоне.
    """

    model_name: Literal[
        "post", "employee", "department", "request", "chat", "message", "event"
    ]
    object: Any


# ------------------------ ВСПОМОГАТЕЛЬНЫЕ УТИЛИТЫ ------------------------


def _is_hr(user: Employee) -> bool:
    """Проверяет расширенные права на просмотр заявлений.

    Args:
        user (Employee): Текущий пользователь.

    Returns:
        bool: True, если пользователь может видеть все заявления.

    Notes:
        Используются пермишены из requests_app.
    """
    return user.has_perm("requests_app.can_view_all_requests") or user.has_perm(
        "requests_app.can_process_requests"
    )

def _get_model_name(obj: Any) -> str:
    """Определяет тип модели для SearchItem.
    
    Args:
        obj: Объект модели из результатов поиска.
        
    Returns:
        str: Название типа модели (post, employee, department, etc.)
    """
    model = type(obj)
    model_name = model.__name__.lower()
    
    # Маппинг моделей на типы для SearchItem
    mapping = {
        "post": "post",
        "employee": "employee",
        "department": "department",
        "request": "request",
        "chat": "chat",
        "message": "message",
        "calendarevent": "event",
    }
    
    return mapping.get(model_name, model_name)


# -------------------------------- ВЬЮХА --------------------------------


@login_required
def search_view(request: HttpRequest) -> HttpResponse:
    """Единый поиск по системе через django-watson.

    Args:
        request (HttpRequest): Запрос (`GET["q"]`).

    Returns:
        HttpResponse: Рендер `templates/search/results.html` с плоским списком.

    Контекст шаблона:
        - query: str — исходная строка запроса
        - results: List[SearchItem] — плоский список элементов
        - counts: Dict[str, int] — счётчики по типам:
            keys: post, employee, department, request, chat, message, event
        - total: int — сумма всех счётчиков
    """
    raw_q = request.GET.get("q", "") or ""
    query = escape(raw_q.strip())

    items: List[SearchItem] = []
    counts: Dict[str, int] = {
        "post": 0,
        "employee": 0,
        "department": 0,
        "request": 0,
        "chat": 0,
        "message": 0,
        "event": 0,
    }

    if query:
        # Выполняем поиск через watson
        search_results = watson_search(query)
        
        # Группируем по типам моделей
        by_model: Dict[str, List[Any]] = {}
        for result in search_results:
            obj = result.object
            model_name = _get_model_name(obj)
            
            # Фильтрация заявлений по правам доступа
            if model_name == "request":
                is_hr = _is_hr(request.user)  # type: ignore[arg-type]
                # Проверяем, что объект - это действительно Request с полем employee
                if not is_hr and hasattr(obj, 'employee') and obj.employee != request.user:  # type: ignore[attr-defined]
                    continue  # Пропускаем чужие заявления
            
            if model_name not in by_model:
                by_model[model_name] = []
            by_model[model_name].append(obj)
        
        # Формируем итоговый список с ограничением 10 элементов на тип
        for model_name in ["post", "employee", "department", "request", 
                           "chat", "message", "event"]:
            objects = by_model.get(model_name, [])
            counts[model_name] = len(objects)
            
            # Берем первые 10 для отображения
            for obj in objects[:10]:
                items.append({
                    "model_name": model_name,  # type: ignore[typeddict-item]
                    "object": obj
                })

    ctx = {
        "query": query,
        "results": items,
        "counts": counts,
        "total": sum(counts.values()),
    }
    return render(request, "search/results.html", ctx)
