from .models import ProcurementRequestActivity


def create_procurement_activity(
    procurement_request,
    actor,
    action,
    *,
    object_kind="",
    object_id=None,
    metadata=None,
):
    """Write one immutable entry to the procurement request audit trail."""
    return ProcurementRequestActivity.objects.create(
        request=procurement_request,
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        object_kind=object_kind or "",
        object_id=object_id,
        metadata=metadata or {},
    )
