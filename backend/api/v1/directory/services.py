"""Сервисы для directory identity lookup."""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings
from employees.models import LdapSyncState


@dataclass(frozen=True)
class DirectoryLoginResult:
    username: str | None
    source: str
    is_cached: bool
    is_ldap_managed: bool


def _find_ldap_user(employee):
    from employees.ldap.orm_models import LdapUser

    employee_number = str(employee.pk)
    employee_email = (employee.email or "").strip().lower()

    def find_by_email():
        if not employee_email:
            return None

        email_candidates = list(
            LdapUser.objects.filter(mail=employee_email)
        )
        if len(email_candidates) == 1:
            return email_candidates[0]

        upn_candidates = list(
            LdapUser.objects.filter(user_principal_name=employee_email)
        )
        if len(upn_candidates) == 1:
            return upn_candidates[0]

        return None

    sync_state = LdapSyncState.objects.filter(
        model="employee", object_pk=employee_number
    ).first()
    if sync_state and sync_state.ldap_dn:
        try:
            return LdapUser.objects.get(dn=sync_state.ldap_dn)
        except LdapUser.DoesNotExist:
            pass

    if not employee.is_ldap_managed:
        email_match = find_by_email()
        if email_match is not None:
            return email_match

    candidates = list(
        LdapUser.objects.filter(employee_number=employee_number)
    )
    if not candidates:
        return find_by_email()
    if len(candidates) == 1:
        return candidates[0]

    if employee_email:
        for candidate in candidates:
            if (getattr(candidate, "mail", "") or "").strip().lower() == employee_email:
                return candidate
            if (
                getattr(candidate, "user_principal_name", "") or ""
            ).strip().lower() == employee_email:
                return candidate

    candidates.sort(
        key=lambda item: (
            0 if (getattr(item, "mail", "") or "").strip().lower() == employee_email else 1,
            0 if (getattr(item, "user_principal_name", "") or "").strip().lower() == employee_email else 1,
            str(getattr(item, "dn", "")).lower(),
        )
    )
    return candidates[0]


def resolve_directory_login(employee, *, force_refresh: bool = False):
    cached_username = (employee.username or "").strip()
    if cached_username and not force_refresh:
        return DirectoryLoginResult(
            username=cached_username,
            source="db",
            is_cached=True,
            is_ldap_managed=employee.is_ldap_managed,
        )

    if not employee.is_ldap_managed:
        return DirectoryLoginResult(
            username=cached_username or None,
            source="db" if cached_username else "none",
            is_cached=bool(cached_username),
            is_ldap_managed=False,
        )

    if not getattr(settings, "LDAP_ENABLED", False):
        return DirectoryLoginResult(
            username=cached_username or None,
            source="db" if cached_username else "none",
            is_cached=bool(cached_username),
            is_ldap_managed=True,
        )

    ldap_user = _find_ldap_user(employee)
    if not ldap_user or not (ldap_user.sam_account_name or "").strip():
        return DirectoryLoginResult(
            username=None,
            source="ldap_not_found",
            is_cached=False,
            is_ldap_managed=True,
        )

    username = ldap_user.sam_account_name.strip()
    if employee.username != username:
        employee.username = username
        employee.save(update_fields=["username"])

    return DirectoryLoginResult(
        username=username,
        source="ldap",
        is_cached=False,
        is_ldap_managed=True,
    )
