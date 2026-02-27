# backend/search/search_indexes.py
"""
Регистрация моделей для полнотекстового поиска через django-watson.

Этот файл автоматически загружается при запуске Django если следовать
стандартной структуре watson.
"""
from __future__ import annotations

from watson.search import register
from django.apps import apps


def get_model_safe(app_label: str, model_name: str):
    """Безопасное получение модели (если приложение установлено)."""
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


# ==================== РЕГИСТРАЦИЯ МОДЕЛЕЙ ====================

# 1. Посты (Feed)
Post = get_model_safe("feed", "Post")
if Post:
    register(
        Post,
        fields=("title", "body"),
        store=("title", "created_at"),
    )

# 2. Сотрудники (Employees)
Employee = get_model_safe("employees", "Employee")
if Employee:
    register(
        Employee,
        fields=(
            "last_name",
            "first_name", 
            "patronymic",
            "email",
            "phone_number",
        ),
        store=("last_name", "first_name", "patronymic", "email"),
    )

# 3. Отделы (Departments)
Department = get_model_safe("employees", "Department")
if Department:
    register(
        Department,
        fields=("name", "description"),
        store=("name", "description"),
    )

# 4. Заявления (Requests)
Request = get_model_safe("requests_app", "Request")
if Request:
    register(
        Request,
        fields=("title", "comment"),
        store=("title", "status", "created_at"),
    )

# 5. Чаты (Communications)
Chat = get_model_safe("communications", "Chat")
if Chat:
    register(
        Chat,
        fields=("name", "description"),
        store=("name",),
    )

# 6. Сообщения чатов (Communications)
Message = get_model_safe("communications", "Message")
if Message:
    register(
        Message,
        fields=("content",),
        store=("content", "created_at"),
    )

# 7. Календарные события (Calendar)
CalendarEvent = get_model_safe("calendar_app", "CalendarEvent")
if CalendarEvent:
    register(
        CalendarEvent,
        fields=("title", "description"),
        store=("title", "start_date"),
    )
