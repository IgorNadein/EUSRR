from rest_framework.permissions import BasePermission, SAFE_METHODS

from guests.constants import EDITABLE_BY_AUTHOR_STATUSES
from guests.constants import GuestVisitStatus
from guests.permissions import (
    can_decide_guest_visit,
    can_manage_guest_account,
    is_guest_admin,
)


class GuestVisitPermission(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        user = request.user
        action = getattr(view, "action", "")

        if is_guest_admin(user):
            return True

        if request.method in SAFE_METHODS:
            return obj.inviter_id == user.id

        if action in {
            "submit",
            "provide_info",
            "cancel",
            "return_to_work",
            "destroy",
        }:
            return obj.inviter_id == user.id

        if action in {"approve", "reject", "request_info", "revoke", "sync_ldap"}:
            return False

        if action in {"update", "partial_update"}:
            return (
                obj.inviter_id == user.id
                and obj.status in EDITABLE_BY_AUTHOR_STATUSES
            )

        if action in {"comments", "delete_comment"}:
            return obj.inviter_id == user.id

        if action in {"attach_document", "remove_document"}:
            return (
                obj.inviter_id == user.id
                and obj.status
                in {
                    *EDITABLE_BY_AUTHOR_STATUSES,
                    GuestVisitStatus.PENDING,
                }
            )

        return False


class GuestAdminPermission(BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        if request.method in SAFE_METHODS:
            return True
        action = getattr(view, "action", "")
        if action in {"comments", "delete_comment", "documents"}:
            return True
        if action in {"sync_ldap", "blacklist", "unblacklist"}:
            return can_manage_guest_account(request.user)
        return is_guest_admin(request.user)


class GuestDecisionPermission(BasePermission):
    def has_permission(self, request, view):
        return can_decide_guest_visit(request.user)
