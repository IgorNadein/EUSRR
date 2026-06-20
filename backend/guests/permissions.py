from __future__ import annotations


GUEST_ADMIN_PERMS = (
    "guests.view_all_guestvisit",
    "guests.decide_guestvisit",
    "guests.manage_guestaccount",
)


def is_guest_admin(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    return any(user.has_perm(perm) for perm in GUEST_ADMIN_PERMS)


def can_decide_guest_visit(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    return bool(user.has_perm("guests.decide_guestvisit"))


def can_manage_guest_account(user) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    return bool(user.has_perm("guests.manage_guestaccount"))
