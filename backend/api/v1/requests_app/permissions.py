# api/v1/requests_app/permissions.py
from __future__ import annotations

from typing import Any, Optional

from api.v1.permissions import AdminOrDeptAllowed
from rest_framework.permissions import BasePermission
from rest_framework.request import Request


class CommentsPermission(BasePermission):
    """Права доступа к экшену `comments`.

    - GET/HEAD: staff или право `requests_app.view_requestcomment`.
    - POST: staff или право `requests_app.add_requestcomment`.
    - Владелец заявки без модельных прав доступа не имеет.

    Raises:
        Ничего не выбрасывает: при отказе возвращает False → DRF вернёт 403.
    """

    message = "Недостаточно прав для доступа к комментариям."

    def has_permission(self, request: Request, view: Any) -> bool:
        """Проверка уровня запроса.

        Args:
            request (Request): Текущий запрос.
            view (Any): Текущий вьюсет.

        Returns:
            bool: True, если пользователь аутентифицирован.
        """
        return bool(getattr(request.user, "is_authenticated", False))

    def has_object_permission(self, request: Request, view: Any, obj: Any) -> bool:
        """Объектная проверка на уровне конкретной заявки.

        Args:
            request (Request): Текущий запрос.
            view (Any): Текущий вьюсет.
            obj (Any): Экземпляр заявки (EmployeeRequest).

        Returns:
            bool: Разрешение/запрет.
        """
        user = request.user
        if getattr(user, "is_staff", False):
            return True

        if request.method in {"GET", "HEAD"}:
            return user.has_perm("requests_app.view_requestcomment")

        if request.method == "POST":
            return user.has_perm("requests_app.add_requestcomment")

        return False


class NotFinalOrStaff(BasePermission):
    """Запрещает удаление финальной заявки для не-админов.

    - Разрешает любые методы, кроме DELETE, без ограничений.
    - Для DELETE: разрешено, если заявка не финальная, либо пользователь — staff.

    Атрибуты:
        message (str): Текст ошибки для 403 Forbidden.

    Notes:
        Пермишены не выбрасывают исключения — они возвращают False,
        что приводит к 403 Forbidden.
    """

    message = "Финальная заявка не может быть удалена."

    def has_object_permission(self, request: Request, view: Any, obj: Any) -> bool:
        """Объектная проверка.

        Args:
            request (Request): Текущий запрос DRF.
            view (Any): Экземпляр вьюсета.
            obj (Any): Экземпляр удаляемого объекта (заявки).

        Returns:
            bool: True, если доступ разрешён; иначе False.
        """
        if request.method != "DELETE":
            return True
        is_final = bool(getattr(obj, "is_final", False))
        is_staff = bool(getattr(request.user, "is_staff", False))
        return (not is_final) or is_staff


class DeptViewRequest(AdminOrDeptAllowed):
    """Чтение заявки: staff ИЛИ право отдела 'view_request'."""

    required_code = "view_request"


class DeptCanProcess(AdminOrDeptAllowed):
    """Обработка заявок: staff ИЛИ право отдела 'can_process_requests'."""

    required_code = "can_process_requests"


class DeptChangeRequest(AdminOrDeptAllowed):
    """Правка заявок: staff ИЛИ право отдела 'change_request'."""

    required_code = "change_request"


class DeptComments(AdminOrDeptAllowed):
    """Комментарии: staff ИЛИ право отдела
    - GET/HEAD: 'view_requestcomment'
    - POST:     'add_requestcomment'
    """

    def _required_code(self, view: Any, request: Request) -> Optional[str]:
        # Метод-чувствительная логика: GET/HEAD → view, POST → add
        if request.method in {"GET", "HEAD"}:
            return "view_requestcomment"
        if request.method == "POST":
            return "add_requestcomment"
        return None  # другие методы не поддерживаем
