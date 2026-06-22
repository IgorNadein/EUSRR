# api/v1/requests_app/permissions.py
from __future__ import annotations

from typing import Any

from rest_framework.permissions import BasePermission
from rest_framework.request import Request


class IsRecipientOfRequest(BasePermission):
    """Проверяет, что пользователь является получателем заявки.

    Доступ разрешается только если пользователь указан в recipients
    данной заявки. Люди в копии и сотрудники с отдельными правами
    не могут принимать решение, если заявка им не адресована напрямую.
    """

    message = "Вы не являетесь получателем этой заявки."

    def has_permission(self, request: Request, view: Any) -> bool:
        return bool(getattr(request.user, "is_authenticated", False))

    def has_object_permission(
        self, request: Request, view: Any, obj: Any
    ) -> bool:
        # Решение можно принимать только по заявке в статусе pending
        # и только прямому получателю (не cc_users).
        return (
            getattr(obj, "status", None) == "pending"
            and obj.recipients.filter(id=request.user.id).exists()
        )


class CanViewRequest(BasePermission):
    """Проверяет, может ли пользователь просматривать заявку."""

    message = "У вас нет доступа к этой заявке."

    def has_permission(self, request: Request, view: Any) -> bool:
        return bool(getattr(request.user, "is_authenticated", False))

    def has_object_permission(
        self, request: Request, view: Any, obj: Any
    ) -> bool:
        user = request.user

        # Черновик - только авторское состояние.
        if getattr(obj, "status", None) == "draft":
            return getattr(obj, "employee_id", None) == user.id

        # Автор заявки
        if getattr(obj, "employee_id", None) == user.id:
            return True

        # Получатель заявки (recipients)
        if obj.recipients.filter(id=user.id).exists():
            return True

        # В копии заявки (cc_users)
        if obj.cc_users.filter(id=user.id).exists():
            return True

        return False


class IsRequestAuthor(BasePermission):
    """Разрешает доступ только автору заявки."""

    message = "Доступ разрешён только автору заявки."

    def has_permission(self, request: Request, view: Any) -> bool:
        return bool(getattr(request.user, "is_authenticated", False))

    def has_object_permission(
        self, request: Request, view: Any, obj: Any
    ) -> bool:
        return getattr(obj, "employee_id", None) == request.user.id


class CommentsPermission(BasePermission):
    """Комментарии доступны только участникам заявки."""

    message = "Недостаточно прав для доступа к комментариям."

    def has_permission(self, request: Request, view: Any) -> bool:
        return bool(getattr(request.user, "is_authenticated", False))

    def _is_participant(self, user, obj) -> bool:
        """Проверяет, является ли пользователь участником заявки."""
        # Владелец заявки
        if getattr(obj, "employee_id", None) == user.id:
            return True
        # Получатель заявки
        if (
            hasattr(obj, "recipients")
            and obj.recipients.filter(id=user.id).exists()
        ):
            return True
        # В копии
        if (
            hasattr(obj, "cc_users")
            and obj.cc_users.filter(id=user.id).exists()
        ):
            return True
        return False

    def has_object_permission(
        self, request: Request, view: Any, obj: Any
    ) -> bool:
        if getattr(obj, "status", None) == "draft":
            return False
        return self._is_participant(request.user, obj)


class NotFinalOrStaff(BasePermission):
    """Запрещает удаление финальной заявки."""

    message = "Финальная заявка не может быть удалена."

    def has_object_permission(
        self, request: Request, view: Any, obj: Any
    ) -> bool:
        if request.method != "DELETE":
            return True
        return not bool(getattr(obj, "is_final", False))

