"""Temporary host access policy for payroll administration.

The deterministic payroll core is intentionally unaware of portal roles.  This
adapter keeps the current pilot simple without deleting the granular permission
model that will be needed after the workflow has been tested in production.
"""

from __future__ import annotations

from .config import simple_admin_access_enabled

SELF_APPROVAL_OVERRIDE_PERMISSION = "finance.override_payroll_approval"


def has_simple_admin_access(user) -> bool:
    """Grant temporary full payroll access to authenticated portal admins."""

    return bool(
        simple_admin_access_enabled()
        and user is not None
        and getattr(user, "is_authenticated", False)
        and getattr(user, "is_active", False)
        and (getattr(user, "is_staff", False) or getattr(user, "is_superuser", False))
    )


def has_payroll_permission(user, permission: str) -> bool:
    """Check the temporary admin bypass, then the preserved granular policy."""

    if user is None or not getattr(user, "is_authenticated", False):
        return False
    if has_simple_admin_access(user):
        return True
    return user.has_perm(permission)


def can_self_approve_payroll(user) -> bool:
    """Allow admins to approve directly while retaining the old override role."""

    # TODO(payroll-access-hardening): disable SIMPLE_ADMIN_ACCESS and require the
    # maker-checker/override policy again after roles and approval flows have
    # passed a full pilot with finance administrators.
    return has_simple_admin_access(user) or has_payroll_permission(
        user,
        SELF_APPROVAL_OVERRIDE_PERMISSION,
    )
