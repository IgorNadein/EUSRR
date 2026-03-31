# backend/api/v1/schedule/permissions.py
"""
Права доступа для django-scheduler API.
"""
from rest_framework import permissions
from django.contrib.contenttypes.models import ContentType
from schedule.models import CalendarRelation


class IsOwnerOfCalendar(permissions.BasePermission):
    """
    Только owner календаря может изменять/удалять календарь.
    Viewer и editor могут только читать календарь.
    """

    def has_object_permission(self, request, view, obj):
        """Проверка прав на календарь."""
        # SAFE_METHODS (GET, HEAD, OPTIONS) доступны всем участникам
        if request.method in permissions.SAFE_METHODS:
            return True

        # Только owner может изменять/удалять календарь
        return self._is_owner(obj, request.user)

    @staticmethod
    def _is_owner(calendar, user):
        """Проверка, является ли пользователь владельцем календаря."""
        if user.is_staff or user.is_superuser:
            return True

        from django.contrib.auth import get_user_model
        User = get_user_model()
        ct = ContentType.objects.get_for_model(User)

        return CalendarRelation.objects.filter(
            calendar=calendar,
            content_type=ct,
            object_id=user.id,
            distinction='owner'
        ).exists()


class CanEditCalendar(permissions.BasePermission):
    """
    Права для событий в календаре:
    - owner: полный доступ (create, read, update, delete)
    - editor: может создавать/изменять/удалять события (create, read, update, delete)
    - viewer: только чтение (read)
    """

    def has_permission(self, request, view):
        """Проверка прав на создание события."""
        # Для создания события нужно быть owner или editor календаря
        if view.action == 'create':
            calendar_id = request.data.get('calendar')
            if not calendar_id:
                return False

            from schedule.models import Calendar
            try:
                calendar = Calendar.objects.get(id=calendar_id)
            except Calendar.DoesNotExist:
                return False

            return self._can_edit(calendar, request.user)

        return True

    def has_object_permission(self, request, view, obj):
        """Проверка прав на событие."""
        # Event object
        event = obj
        calendar = event.calendar

        # SAFE_METHODS (GET, HEAD, OPTIONS) доступны всем участникам
        if request.method in permissions.SAFE_METHODS:
            return True

        # Для изменения/удаления нужны права editor или owner
        return self._can_edit(calendar, request.user)

    @staticmethod
    def _can_edit(calendar, user):
        """Проверка, может ли пользователь редактировать события в календаре."""
        if user.is_staff or user.is_superuser:
            return True

        from django.contrib.auth import get_user_model
        User = get_user_model()
        ct = ContentType.objects.get_for_model(User)

        # Проверяем роль пользователя в календаре
        try:
            relation = CalendarRelation.objects.get(
                calendar=calendar,
                content_type=ct,
                object_id=user.id
            )
            # Owner и editor могут редактировать, viewer - нет
            return relation.distinction in ['owner', 'editor']
        except CalendarRelation.DoesNotExist:
            return False
