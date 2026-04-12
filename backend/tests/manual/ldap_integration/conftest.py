from __future__ import annotations

import uuid
from collections.abc import Callable, Generator

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from ldap3 import SUBTREE
from rest_framework.test import APIClient

from employees.ldap import UserService, _ldap
from employees.ldap.domain.dtos import DirectoryUserDTO
from employees.models import LdapSyncState

pytestmark = [
    pytest.mark.manual,
    pytest.mark.integration,
    pytest.mark.django_db(transaction=True, databases=["default", "ldap"]),
]

User = get_user_model()


def _uuid_suffix() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture
def ldap_runtime(settings) -> None:
    settings.LDAP_ENABLED = True
    settings.LDAP_WRITE_ENABLED = True


@pytest.fixture
def ensure_live_ldap(ldap_runtime) -> None:
    with _ldap() as conn:
        assert conn.bound is True


@pytest.fixture
def unique_name() -> Callable[[str], str]:
    def _make(prefix: str) -> str:
        return f"{prefix}-{_uuid_suffix()}"

    return _make


@pytest.fixture
def ldap_cleanup() -> Generator[Callable[[str], None], None, None]:
    tracked_dns: set[str] = set()

    def _track(dn: str) -> None:
        if dn:
            tracked_dns.add(dn)

    yield _track

    if not tracked_dns:
        return

    with _ldap() as conn:
        for root_dn in sorted(tracked_dns, key=lambda value: value.count(","), reverse=True):
            try:
                ok = conn.search(
                    root_dn,
                    "(objectClass=*)",
                    search_scope=SUBTREE,
                    attributes=["distinguishedName"],
                )
                dns = (
                    {str(entry.entry_dn) for entry in conn.entries}
                    if ok and conn.entries
                    else {root_dn}
                )
            except Exception:
                dns = {root_dn}

            for entry_dn in sorted(dns, key=lambda value: value.count(","), reverse=True):
                try:
                    conn.delete(entry_dn)
                except Exception:
                    continue


@pytest.fixture
def superuser_client(user_factory) -> APIClient:
    user = user_factory(
        email=f"ldap-admin-{_uuid_suffix()}@example.com",
        phone_number=f"+79991{uuid.uuid4().int % 10**6:06d}",
        staff=True,
        superuser=True,
        verified=True,
        active=True,
    )
    client = APIClient()
    client.force_authenticate(user=user)
    return client


@pytest.fixture
def create_ldap_user(
    ensure_live_ldap, ldap_cleanup, unique_name
) -> Callable[..., User]:
    def _make(
        *,
        first_name: str = "Ldap",
        last_name: str = "User",
        email_prefix: str = "ldap-user",
        password: str = "TestPass123!",
        is_active: bool = True,
    ) -> User:
        suffix = _uuid_suffix()
        dto = DirectoryUserDTO(
            first_name=first_name,
            last_name=f"{last_name}{suffix}",
            email=f"{email_prefix}-{suffix}@example.com",
            phone_e164=f"+7999{uuid.uuid4().int % 10**7:07d}",
            department_dn=None,
            group_cns=[],
            initial_password=password,
            is_active=is_active,
        )
        employee = UserService().create_user(dto)
        employee.email_verified = True
        employee.is_active = is_active
        employee._skip_ldap_sync = True
        employee.save(update_fields=["email_verified", "is_active"])
        employee = User.objects.get(pk=employee.pk)

        sync_state = LdapSyncState.objects.get(
            model="employee", object_pk=str(employee.pk)
        )
        ldap_cleanup(sync_state.ldap_dn)
        return employee

    return _make


@pytest.fixture
def disable_ldap_for_cleanup() -> Generator[None, None, None]:
    with override_settings(LDAP_ENABLED=False, LDAP_WRITE_ENABLED=False):
        yield
