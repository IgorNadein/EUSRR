# api/v1/requests_app/permissions.py
from __future__ import annotations

from typing import Any, Optional

from api.v1.permissions import AdminOrDeptAllowed
from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from employees.constants import DeptPerm


class CommentsPermission(BasePermission):
    """Доступ к экшену `comments` по *модельным* правам.

    - GET/HEAD: `requests_app.view_requestcomment` ИЛИ staff.
    - POST:     `requests_app.add_requestcomment` ИЛИ staff.
    - Владелец без прав — НЕТ.
    """

    message = "Недостаточно прав для доступа к комментариям."

    def _required_perm(self, request: Request) -> Optional[str]:
        if request.method in {"GET", "HEAD"}:
            return "requests_app.view_requestcomment"
        if request.method == "POST":
            return "requests_app.add_requestcomment"
        return None

    def has_permission(self, request: Request, view: Any) -> bool:
        return bool(getattr(request.user, "is_authenticated", False))

    def has_object_permission(self, request: Request, view: Any, obj: Any) -> bool:
        user = request.user
        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            return True
        code = self._required_perm(request)
        return bool(code and user.has_perm(code))


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
    """Просмотр заявки по департаментным правам.

    Доступ разрешается, если пользователь — staff/superuser ИЛИ имеет
    право отдела ``view_request`` именно для отдела данной заявки.

    Применяется только к detail-экшену `retrieve`.

    Attributes:
        allow_safe_without_code (bool): Запрещает фоллбек пропуска SAFE-методов
            без явного кода права (защита от «случайных 200»).
        required_code_map (dict[str, str]): Ограничиваем право только на `retrieve`.
        required_code (Optional[str]): Явно отключаем общий fallback.
    """

    # SAFE-методы не должны проходить «на шару»
    allow_safe_without_code: bool = False

    # Явно ограничиваем сферу действия права
    required_code_map: dict[str, str] = {
        "retrieve": "view_request",
    }

    # Не даём базовому классу брать «любой экшен = view_request»
    required_code: Optional[str] = None

    def get_required_code(self, request: Request, view: Any) -> Optional[str]:
        """Возвращает код департаментного права только для поддерживаемых action.

        Args:
            request (Request): DRF-запрос.
            view (Any): Вью/вьюсет; важен `view.action`.

        Returns:
            Optional[str]: 'view_request' для `retrieve`, иначе None (запрет).
        """
        return self.required_code_map.get(getattr(view, "action", None))


class DeptCanProcess(AdminOrDeptAllowed):
    """Пермишен для обработки заявок по департаментным правам.

    Доступ разрешается, если пользователь — staff/superuser ИЛИ имеет
    право отдела ``can_process_requests`` для отдела заявки.

    Применяется на детальных экшенах workflow:
      - approve
      - reject

    Атрибуты:
        allow_safe_without_code (bool): Запретить «фоллбек» на SAFE-методы
            без явного кода права (по умолчанию в базовом классе мог быть True).
        required_code_map (dict[str, str]): Маппинг action → код права.
        required_code (str): Резервный код права, если action не сматчился.

    Raises:
        Ничего напрямую не выбрасывает — при отсутствии прав вернёт False,
        DRF ответит 403 Forbidden.
    """

    # SAFE-методы пусть тоже требуют явного кода (на всякий случай)
    allow_safe_without_code: bool = False

    # Явно описываем нужные action-ы workflow
    required_code_map: dict[str, str] = {
        "approve": "can_process_requests",
        "reject": "can_process_requests",
    }

    # Резервный вариант — если вдруг action неизвестен,
    # базовый класс возьмёт этот код.
    required_code: str = "can_process_requests"


class DeptChangeRequest(AdminOrDeptAllowed):
    """Правка заявок по департаментным правам.

    Доступ разрешается, если пользователь — staff/superuser ИЛИ имеет
    право отдела ``change_request`` для отдела конкретной заявки.

    Применяется ТОЛЬКО к экшенам редактирования:
      - update (PUT)
      - partial_update (PATCH)
      - destroy (DELETE)

    ВНИМАНИЕ: для workflow-экшенов (approve/reject) используйте DeptCanProcess.

    Attributes:
        allow_safe_without_code (bool): запрещает фоллбек пропуска SAFE-методов
            без явного кода права (защита от случайных «200»).
    """

    # Не пропускаем SAFE-методы без явного кода (страховка)
    allow_safe_without_code: bool = False

    def get_required_code(self, request: Request, view: Any) -> Optional[str]:
        """Возвращает код департаментного права для экшенов редактирования.

        Args:
            request (Request): DRF-запрос.
            view (Any): Вью/вьюсет (важен view.action).

        Returns:
            Optional[str]: 'change_request' для update/partial_update/destroy, иначе None.

        Notes:
            Возврат None означает «кода нет» → базовый класс вернёт False (403),
            так мы исключаем approve/reject и прочие экшены из этого пермишена.
        """
        if getattr(view, "action", None) in {"update", "partial_update", "destroy"}:
            return "change_request"
        return None


class DeptComments(AdminOrDeptAllowed):
    """Комментарии: staff ИЛИ департаментное право.

    - GET/HEAD → 'view_requestcomment'
    - POST     → 'add_requestcomment'
    """

    # Чтобы SAFE-методы не проходили «без кода» при ошибке конфигурации:
    allow_safe_without_code = False

    def get_required_code(self, request: Request, view: Any) -> Optional[str]:
        """Возвращает код департаментного права для экшена `comments`.

        Args:
            request (Request): Текущий запрос DRF.
            view (Any): Вью/вьюсет (не используется).

        Returns:
            Optional[str]: Код права для текущего HTTP-метода или None для неподдерживаемых методов.

        Raises:
            None: Исключения не выбрасываются — при отсутствии кода доступ будет запрещён базовым классом.
        """
        if request.method in {"GET", "HEAD"}:
            return DeptPerm.VIEW_REQUESTCOMMENT
        if request.method == "POST":
            return DeptPerm.ADD_REQUESTCOMMENT
        return None