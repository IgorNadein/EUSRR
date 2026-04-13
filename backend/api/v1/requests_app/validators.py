from __future__ import annotations

from typing import Any, Mapping

from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

# VACATION/SICK_LEAVE/TRANSFER/DISMISSAL/OTHER
from requests_app.enums import RequestType
from requests_app.enums import RequestStatus


class RequestDatesByTypeValidator:
    """Мягкая проверка дат по типу заявки.

    Правила:
            - Проверяем ТОЛЬКО если в payload присутствуют date_from/date_to
                ИЛИ меняется type.
            - Для VACATION/SICK_LEAVE: если хотя бы одна дата передана,
                требуются обе; date_to >= date_from.
      - Для TRANSFER/DISMISSAL: если даты трогают — обязателен date_from.
      - Для OTHER: дат можно не указывать.
    """

    requires_context = True

    def _is_draft_mode(self, serializer) -> bool:
        request = serializer.context.get("request")
        save_as = (
            (getattr(getattr(request, "query_params", None), "get", lambda *_: "")("save_as") or "")
            .strip()
            .lower()
        )
        if save_as == "draft":
            return True
        if save_as == "submit":
            return False
        instance = getattr(serializer, "instance", None)
        return getattr(instance, "status", None) == RequestStatus.DRAFT

    def __call__(self, attrs: Mapping[str, Any], serializer) -> None:
        if self._is_draft_mode(serializer):
            return

        instance = getattr(serializer, "instance", None)

        # Определяем «эффективные» значения с учётом instance
        type_ = attrs.get("type", getattr(instance, "type", None))
        date_from = attrs.get("date_from", getattr(instance, "date_from", None))
        date_to = attrs.get("date_to", getattr(instance, "date_to", None))

        # Меняем ли мы даты/тип в этом запросе?
        touches_dates = any(k in attrs for k in ("date_from", "date_to"))
        touches_type = "type" in attrs

        # Если ни тип, ни даты не трогают — ничего не проверяем
        if not (touches_dates or touches_type):
            return

        if type_ in (RequestType.VACATION, RequestType.SICK_LEAVE):
            # Если пользователь прислал хотя бы одно из полей даты — должны быть
            # обе
            if touches_dates and (not date_from or not date_to):
                raise ValidationError(
                    {
                        "date_from": _("Требуются обе даты."),
                        "date_to": _("Требуются обе даты."),
                    }
                )
            if date_from and date_to and date_to < date_from:
                raise ValidationError(
                    {"date_to": _("Дата окончания раньше даты начала.")}
                )

        elif type_ in (RequestType.TRANSFER, RequestType.DISMISSAL):
            if touches_dates and not date_from:
                raise ValidationError(
                    {"date_from": _("Требуется дата начала.")}
                )
        # OTHER — ограничений нет


class RequestApproverNotEmployeeValidator:
    """Запрещает совпадение согласующего и автора.

    Учитывает частичное обновление: берёт значения из attrs поверх instance.
    """

    requires_context = True

    def _is_draft_mode(self, serializer) -> bool:
        request = serializer.context.get("request")
        save_as = (
            (getattr(getattr(request, "query_params", None), "get", lambda *_: "")("save_as") or "")
            .strip()
            .lower()
        )
        if save_as == "draft":
            return True
        if save_as == "submit":
            return False
        instance = getattr(serializer, "instance", None)
        return getattr(instance, "status", None) == RequestStatus.DRAFT

    def __call__(self, attrs: Mapping[str, Any], serializer) -> None:
        if self._is_draft_mode(serializer):
            return

        instance = getattr(serializer, "instance", None)

        def eff(name: str) -> Any:
            if name in attrs:
                return attrs[name]
            return (
                getattr(instance, name, None) if instance is not None else None
            )

        employee = eff("employee") or getattr(
            serializer.context.get("request"), "user", None
        )
        approver = eff("approver")

        if employee and approver and employee == approver:
            raise ValidationError(
                {"approver": _("Согласующий не может совпадать с автором.")}
            )
