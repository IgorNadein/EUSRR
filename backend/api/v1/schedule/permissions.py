# backend/api/v1/schedule/permissions.py
"""
Права доступа для django-scheduler API.
"""

from rest_framework import permissions

from scheduling.services import (
    user_can_create_event,
    user_can_edit_calendar,
    user_can_edit_event,
    user_can_view_calendar,
)


class IsOwnerOfCalendar(permissions.BasePermission):
    """
    Только owner календаря может изменять/удалять календарь.
    Viewer и editor могут только читать календарь.
    """

    def has_object_permission(self, request, view, obj):
        """Проверка прав на календарь."""
        # SAFE_METHODS (GET, HEAD, OPTIONS) доступны всем участникам
        if request.method in permissions.SAFE_METHODS:
            return user_can_view_calendar(request.user, obj)

        # Только owner может изменять/удалять календарь
        return user_can_edit_calendar(request.user, obj)


class CanEditCalendar(permissions.BasePermission):
    """
    Права для событий в календаре:
    - owner: полный доступ (create, read, update, delete)
        - editor: может создавать, изменять и удалять события
            (create, read, update, delete)
    - viewer: только чтение (read)
    """

    def has_permission(self, request, view):
        """Проверка прав на создание события."""
        # Для создания события нужно быть owner или editor календаря
        if view.action == "create":
            calendar_id = request.data.get("calendar")
            if not calendar_id:
                return False

            from schedule.models import Calendar

            try:
                calendar = Calendar.objects.get(id=calendar_id)
            except Calendar.DoesNotExist:
                return False

            return user_can_create_event(request.user, calendar)

        return True

    def has_object_permission(self, request, view, obj):
        """Проверка прав на событие."""
        # Event object
        event = obj
        calendar = event.calendar

        # SAFE_METHODS (GET, HEAD, OPTIONS) доступны всем участникам
        if request.method in permissions.SAFE_METHODS:
            return user_can_view_calendar(request.user, calendar)

        # Для изменения/удаления нужны права editor или owner
        return user_can_edit_event(request.user, event)
