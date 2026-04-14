from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APIClient

from api.auth.models import UserAuthSession

User = get_user_model()


def make_user(**overrides):
    email = overrides.pop("email", "dir@example.com")
    phone = overrides.pop("phone_number", "+79990000077")
    user = User.objects.create_user(
        email=email,
        password="TestPass123!",
        first_name=overrides.pop("first_name", "Dir"),
        last_name=overrides.pop("last_name", "User"),
        phone_number=phone,
        send_activation_email=False,
        **overrides,
    )
    user.email_verified = True
    user.is_active = True
    user.save(update_fields=["email_verified", "is_active"])
    return user


def make_ldap_user(**overrides):
    return SimpleNamespace(
        dn=overrides.pop(
            "dn", "CN=User,OU=Users,OU=company,DC=robotail,DC=local"
        ),
        sam_account_name=overrides.pop("sam_account_name", "ldap.login"),
        mail=overrides.pop("mail", "dir@example.com"),
        user_principal_name=overrides.pop(
            "user_principal_name", "dir@example.com"
        ),
        **overrides,
    )


@pytest.mark.django_db
def test_employees_me_returns_cached_username():
    client = APIClient()
    user = make_user(username="cached.login", is_ldap_managed=True)
    client.force_authenticate(user=user)

    response = client.get("/api/v1/employees/me/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["username"] == "cached.login"


@pytest.mark.django_db
def test_employees_me_returns_last_activity_from_active_sessions():
    client = APIClient()
    user = make_user(username="cached.login", is_ldap_managed=True)
    client.force_authenticate(user=user)

    older = timezone.now() - timezone.timedelta(hours=3)
    newer = timezone.now() - timezone.timedelta(minutes=7)

    older_session = UserAuthSession.objects.create(
        user=user,
        device_name="Firefox on Linux",
    )
    UserAuthSession.objects.filter(pk=older_session.pk).update(last_seen_at=older)

    newer_session = UserAuthSession.objects.create(
        user=user,
        device_name="Chrome on Linux",
    )
    UserAuthSession.objects.filter(pk=newer_session.pk).update(last_seen_at=newer)

    revoked = UserAuthSession.objects.create(
        user=user,
        device_name="Safari on macOS",
    )
    UserAuthSession.objects.filter(pk=revoked.pk).update(last_seen_at=timezone.now())
    revoked.revoke(commit=True)

    response = client.get("/api/v1/employees/me/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["last_activity_at"] is not None
    assert parse_datetime(response.json()["last_activity_at"]) == newer


@pytest.mark.django_db
def test_directory_login_returns_cached_username_without_ldap_lookup(settings):
    settings.LDAP_ENABLED = True
    client = APIClient()
    user = make_user(username="cached.login", is_ldap_managed=True)
    client.force_authenticate(user=user)

    with patch("api.v1.directory.services._find_ldap_user") as find_ldap_user:
        response = client.get("/api/v1/directory/me/login/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "username": "cached.login",
        "source": "db",
        "is_cached": True,
        "is_ldap_managed": True,
    }
    find_ldap_user.assert_not_called()


@pytest.mark.django_db
def test_directory_login_uses_ldap_fallback_and_caches_result(settings):
    settings.LDAP_ENABLED = True
    client = APIClient()
    user = make_user(username="", is_ldap_managed=True)
    client.force_authenticate(user=user)

    ldap_user = SimpleNamespace(sam_account_name="ldap.login")
    with patch(
        "api.v1.directory.services._find_ldap_user", return_value=ldap_user
    ) as find_ldap_user:
        response = client.get("/api/v1/directory/me/login/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "username": "ldap.login",
        "source": "ldap",
        "is_cached": False,
        "is_ldap_managed": True,
    }
    find_ldap_user.assert_called_once()

    user.refresh_from_db()
    assert user.username == "ldap.login"


@pytest.mark.django_db
def test_directory_login_returns_empty_when_ldap_not_found(settings):
    settings.LDAP_ENABLED = True
    client = APIClient()
    user = make_user(username="", is_ldap_managed=True)
    client.force_authenticate(user=user)

    with patch("api.v1.directory.services._find_ldap_user", return_value=None):
        response = client.get("/api/v1/directory/me/login/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "username": None,
        "source": "ldap_not_found",
        "is_cached": False,
        "is_ldap_managed": True,
    }


@pytest.mark.django_db
def test_directory_login_returns_empty_when_ldap_disabled(settings):
    settings.LDAP_ENABLED = False
    client = APIClient()
    user = make_user(username="", is_ldap_managed=True)
    client.force_authenticate(user=user)

    with patch("api.v1.directory.services._find_ldap_user") as find_ldap_user:
        response = client.get("/api/v1/directory/me/login/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "username": None,
        "source": "none",
        "is_cached": False,
        "is_ldap_managed": True,
    }
    find_ldap_user.assert_not_called()


@pytest.mark.django_db
def test_directory_login_refresh_forces_ldap_lookup(settings):
    settings.LDAP_ENABLED = True
    client = APIClient()
    user = make_user(username="old.login", is_ldap_managed=True)
    client.force_authenticate(user=user)

    ldap_user = SimpleNamespace(sam_account_name="new.login")
    with patch(
        "api.v1.directory.services._find_ldap_user", return_value=ldap_user
    ) as find_ldap_user:
        response = client.post("/api/v1/directory/me/login/refresh/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {
        "username": "new.login",
        "source": "ldap",
        "is_cached": False,
        "is_ldap_managed": True,
    }
    find_ldap_user.assert_called_once()

    user.refresh_from_db()
    assert user.username == "new.login"


@pytest.mark.django_db
def test_find_ldap_user_prefers_sync_state_dn(settings):
    settings.LDAP_ENABLED = True
    user = make_user(username="", is_ldap_managed=True)

    from employees.models import LdapSyncState

    preferred = make_ldap_user(
        dn="CN=Preferred,OU=Users,OU=company,DC=robotail,DC=local",
        sam_account_name="preferred.login",
    )
    other = make_ldap_user(
        dn="CN=Other,OU=Users,OU=company,DC=robotail,DC=local",
        sam_account_name="other.login",
    )

    LdapSyncState.objects.create(
        model="employee",
        object_pk=str(user.pk),
        ldap_dn=preferred.dn,
    )

    with patch("employees.ldap.orm_models.LdapUser.objects.get") as get_mock, patch(
        "employees.ldap.orm_models.LdapUser.objects.filter"
    ) as filter_mock:
        get_mock.return_value = preferred
        filter_mock.return_value = [other]

        from api.v1.directory.services import _find_ldap_user

        resolved = _find_ldap_user(user)

    assert resolved is preferred
    get_mock.assert_called_once_with(dn=preferred.dn)


@pytest.mark.django_db
def test_find_ldap_user_prefers_email_match_among_multiple_candidates(settings):
    settings.LDAP_ENABLED = True
    user = make_user(
        username="",
        is_ldap_managed=True,
        email="match@example.com",
    )

    preferred = make_ldap_user(
        dn="CN=Preferred,OU=Users,OU=company,DC=robotail,DC=local",
        sam_account_name="preferred.login",
        mail="match@example.com",
        user_principal_name="preferred@robotail.local",
    )
    other = make_ldap_user(
        dn="CN=Other,OU=Users,OU=company,DC=robotail,DC=local",
        sam_account_name="other.login",
        mail="other@example.com",
        user_principal_name="other@robotail.local",
    )

    with patch(
        "employees.ldap.orm_models.LdapUser.objects.filter"
    ) as filter_mock:
        filter_mock.return_value = [other, preferred]

        from api.v1.directory.services import _find_ldap_user

        resolved = _find_ldap_user(user)

    assert resolved is preferred
