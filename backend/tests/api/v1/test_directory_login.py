from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

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


@pytest.mark.django_db
def test_employees_me_returns_cached_username():
    client = APIClient()
    user = make_user(username="cached.login", is_ldap_managed=True)
    client.force_authenticate(user=user)

    response = client.get("/api/v1/employees/me/")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["username"] == "cached.login"


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
