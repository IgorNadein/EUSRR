"""Idempotent EmployeeAction creation for approved requests."""

from __future__ import annotations

from datetime import date, datetime, time
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from employees.models import EmployeeAction


def as_action_datetime(value: date | datetime | None, *, hour: int = 12) -> datetime:
    """Normalize request dates to aware datetimes for EmployeeAction.date."""
    if value is None:
        return timezone.now()
    if isinstance(value, datetime):
        return value if timezone.is_aware(value) else timezone.make_aware(value)
    return timezone.make_aware(datetime.combine(value, time(hour=hour)))


def build_request_action_comment(request, prefix: str = "Заявление") -> str:
    comment = f"{prefix} #{request.id}"
    if getattr(request, "comment", ""):
        comment += f": {request.comment[:200]}"
    return comment


def get_existing_request_action(request, action_type: str) -> EmployeeAction | None:
    """Find an action by the new FK, falling back to legacy extra.request_id."""
    existing = (
        EmployeeAction.objects.filter(source_request=request, action=action_type)
        .order_by("id")
        .first()
    )
    if existing:
        return existing

    return (
        EmployeeAction.objects.filter(
            source_request__isnull=True,
            extra__request_id=request.id,
            action=action_type,
        )
        .order_by("id")
        .first()
    )


def create_request_action(
    *,
    request,
    action_type: str,
    action_date: date | datetime | None,
    comment: str,
    extra: dict[str, Any] | None = None,
) -> tuple[EmployeeAction, bool]:
    """
    Create one EmployeeAction per request/action pair.

    Returns:
        tuple: (action, created)
    """
    extra_data = dict(extra or {})
    extra_data["request_id"] = request.id

    legacy = get_existing_request_action(request, action_type)
    if legacy:
        updates: list[str] = []
        if legacy.source_request_id is None:
            legacy.source_request = request
            updates.append("source_request")
        if (
            not isinstance(legacy.extra, dict)
            or legacy.extra.get("request_id") is None
        ):
            current_extra = legacy.extra if isinstance(legacy.extra, dict) else {}
            legacy.extra = {**current_extra, "request_id": request.id}
            updates.append("extra")
        if updates:
            try:
                legacy.save(update_fields=updates)
            except IntegrityError:
                existing = EmployeeAction.objects.get(
                    source_request=request,
                    action=action_type,
                )
                return existing, False
        return legacy, False

    defaults = {
        "employee": request.employee,
        "date": as_action_datetime(action_date),
        "comment": comment,
        "extra": extra_data,
    }

    try:
        with transaction.atomic():
            action, created = EmployeeAction.objects.get_or_create(
                source_request=request,
                action=action_type,
                defaults=defaults,
            )
    except IntegrityError:
        action = EmployeeAction.objects.get(
            source_request=request,
            action=action_type,
        )
        created = False

    return action, created
