"""Общие хелперы и миксины для employees views."""

from __future__ import annotations

import logging

from django.contrib.auth import get_user_model
from django.db.models import Q
from employees.utils import _detect_phone_field
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

logger = logging.getLogger(__name__)

Employee = get_user_model()

PHONE_FIELD = _detect_phone_field()


class HistoryActionMixin:
    """
    Добавляет GET /{basename}/{pk}/history/
    Параметры (необяз.): ?from=ISO ?to=ISO ?user=<id|email> ?type=+|~|-
    """

    history_diff_fields = None  # список полей для diff; если None — попытаемся угадать

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def history(self, request, pk=None):
        obj = self.get_object()
        qs = obj.history.select_related("history_user").order_by(
            "-history_date", "-history_id"
        )

        q_from = request.query_params.get("from")
        q_to = request.query_params.get("to")
        q_user = request.query_params.get("user")
        q_type = request.query_params.get("type")

        if q_from:
            try:
                qs = qs.filter(history_date__gte=q_from)
            except Exception:
                pass
        if q_to:
            try:
                qs = qs.filter(history_date__lte=q_to)
            except Exception:
                pass
        if q_user:
            qs = qs.filter(
                Q(history_user__id__iexact=q_user)
                | Q(history_user__email__iexact=q_user)
            )
        if q_type in {"+", "~", "-"}:
            qs = qs.filter(history_type=q_type)

        items = list(qs)
        results = []
        for i, cur in enumerate(items):
            prev = items[i + 1] if i + 1 < len(items) else None
            changes = {}
            # какие поля сравнивать
            if self.history_diff_fields is not None:
                fields = self.history_diff_fields
            else:
                # берём только реальные field.name модели (без M2M)
                fields = [f.name for f in obj._meta.fields]

            for name in fields:
                new = getattr(cur, name, None)
                old = getattr(prev, name, None) if prev else None
                if old != new:
                    changes[name] = {"old": old, "new": new}

            results.append(
                {
                    "history_id": cur.history_id,
                    "history_date": cur.history_date,
                    "history_type": cur.history_type,  # "+", "~", "-"
                    "history_user": getattr(cur.history_user, "email", None),
                    "changes": changes,
                }
            )
        return Response({"count": len(results), "results": results})
