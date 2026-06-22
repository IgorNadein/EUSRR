from django.core.cache import cache
from django.db.models import Count
from django.db.models import Q


UNREAD_SUMMARY_TIMEOUT = 60


def unread_summary_cache_key(user_id):
    return f"notifications:unread_summary:user:{user_id}"


def _coerce_positive_int(value):
    try:
        integer_value = int(value)
    except (TypeError, ValueError):
        return None
    return integer_value if integer_value > 0 else None


def _build_procurement_request_counts(user_id):
    from django.contrib.contenttypes.models import ContentType
    from procurement.models import ProcurementRequest
    from .models import Notification

    request_content_type = ContentType.objects.get_for_model(
        ProcurementRequest,
    )
    request_content_type_id = request_content_type.id
    counts = {}
    notifications = (
        Notification.objects.filter(
            recipient_id=user_id,
            unread=True,
            deleted=False,
        )
        .filter(
            Q(verb__startswith="procurement_")
            | Q(verb__startswith="equipment_")
        )
        .only(
            "data",
            "target_content_type_id",
            "target_object_id",
            "action_object_content_type_id",
            "action_object_object_id",
        )
    )

    for notification in notifications:
        data = notification.data if isinstance(notification.data, dict) else {}
        request_id = _coerce_positive_int(data.get("request_id"))

        if request_id is None and (
            notification.target_content_type_id == request_content_type_id
        ):
            request_id = _coerce_positive_int(notification.target_object_id)

        if request_id is None and (
            notification.action_object_content_type_id == request_content_type_id
        ):
            request_id = _coerce_positive_int(
                notification.action_object_object_id,
            )

        if request_id is not None:
            counts[request_id] = counts.get(request_id, 0) + 1

    return [
        {"request_id": request_id, "unread": unread}
        for request_id, unread in sorted(counts.items())
    ]


def build_unread_summary(user_id):
    from .models import Notification

    rows = (
        Notification.objects.filter(
            recipient_id=user_id,
            unread=True,
            deleted=False,
        )
        .values("verb")
        .annotate(unread=Count("id"))
        .order_by()
    )
    verbs = [
        {"verb": row["verb"], "unread": row["unread"]}
        for row in rows
    ]
    return {
        "total": sum(item["unread"] for item in verbs),
        "verbs": verbs,
        "procurement_requests": _build_procurement_request_counts(user_id),
    }


def get_unread_summary(user_id):
    key = unread_summary_cache_key(user_id)

    try:
        cached = cache.get(key)
    except Exception:
        cached = None

    if cached is not None:
        return cached

    summary = build_unread_summary(user_id)
    try:
        cache.set(key, summary, UNREAD_SUMMARY_TIMEOUT)
    except Exception:
        pass
    return summary


def get_unread_count(user_id):
    return get_unread_summary(user_id)["total"]


def invalidate_unread_summary(user_id):
    if not user_id:
        return

    try:
        cache.delete(unread_summary_cache_key(user_id))
    except Exception:
        pass
