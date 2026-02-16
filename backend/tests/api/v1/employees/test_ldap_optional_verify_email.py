"""
Тесты для VerifyEmailAPIView с опциональной LDAP интеграцией.

Покрытие:
- V1: Верификация email с LDAP активирует пользователя в LDAP и БД
- V2: Верификация email без LDAP активирует пользователя только в БД
- V3: Неверный код возвращает 400 в обоих режимах
- V4: Повторная верификация уже верифицированного email возвращает 400
- V5: Верификация несуществующего пользователя возвращает 404
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from unittest.mock import patch, MagicMock

Employee = get_user_model()


@pytest.fixture
def unverified_user(db):
    """Создаёт неверифицированного пользователя с кодом активации"""
    user = Employee.objects.create(
        email="unverified@example.com",
        first_name="Test",
        last_name="User",
        phone_number="+79990001111",
        is_active=False,
        email_verified=False,
        email_activation_code="123456",
    )
    user.set_password("TestPass123!")
    user.save()
    return user


@pytest.fixture
def verified_user(db):
    """Создаёт уже верифицированного пользователя"""
    user = Employee.objects.create(
        email="verified@example.com",
        first_name="Verified",
        last_name="User",
        phone_number="+79990002222",
        is_active=True,
        email_verified=True,
        email_activation_code="",
    )
    user.set_password("TestPass123!")
    user.save()
    return user


# ---------- Тесты с LDAP ----------


@pytest.mark.ldap_required
@patch("api.v1.employees.views.auth.DirectoryService")
def test_verify_email_with_ldap_activates_user_in_ldap_and_db(
    mock_ds, api_client, unverified_user, settings
):
    """V1: Верификация email с LDAP активирует пользователя в LDAP и БД"""
    settings.LDAP_ENABLED = True

    mock_svc = MagicMock()
    mock_ds.return_value = mock_svc

    url = reverse("api:v1:verify-email")
    data = {
        "email": unverified_user.email,
        "code": unverified_user.email_activation_code,
    }

    response = api_client.post(url, data, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["ok"] is True

    # Проверяем что пользователь активирован в БД
    unverified_user.refresh_from_db()
    assert unverified_user.is_active is True
    assert unverified_user.email_verified is True
    assert unverified_user.email_activation_code == ""

    # Проверяем что вызван метод активации в LDAP
    mock_svc.enable_user.assert_called_once_with(unverified_user)


# ---------- Тесты без LDAP ----------


@pytest.mark.django_db
def test_verify_email_without_ldap_activates_user_only_in_db(
    api_client, unverified_user, settings
):
    """V2: Верификация email без LDAP активирует пользователя только в БД"""
    settings.LDAP_ENABLED = False

    url = reverse("api:v1:verify-email")
    data = {
        "email": unverified_user.email,
        "code": unverified_user.email_activation_code,
    }

    response = api_client.post(url, data, format="json")

    assert response.status_code == status.HTTP_200_OK
    assert response.data["ok"] is True

    # Проверяем что пользователь активирован в БД
    unverified_user.refresh_from_db()
    assert unverified_user.is_active is True
    assert unverified_user.email_verified is True
    assert unverified_user.email_activation_code is None  # Становится None


@pytest.mark.django_db
def test_verify_email_with_wrong_code_returns_400_without_ldap(
    api_client, unverified_user, settings
):
    """V3: Неверный код возвращает 400"""
    settings.LDAP_ENABLED = False

    url = reverse("api:v1:verify-email")
    data = {
        "email": unverified_user.email,
        "code": "999999",  # Неправильный, но валидный формат (6 цифр)
    }

    response = api_client.post(url, data, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    # API возвращает {"ok": False, "error": "invalid_code"}
    assert "ok" in response.data
    assert response.data["ok"] is False

    # Пользователь остался неактивирован
    unverified_user.refresh_from_db()
    assert unverified_user.is_active is False
    assert unverified_user.email_verified is False


@pytest.mark.django_db
def test_verify_email_already_verified_returns_400_without_ldap(
    api_client, verified_user, settings
):
    """V4: Повторная верификация уже верифицированного email возвращает 400"""
    settings.LDAP_ENABLED = False

    url = reverse("api:v1:verify-email")
    data = {
        "email": verified_user.email,
        "code": "123456",  # Валидный формат, но неправильный код
    }

    response = api_client.post(url, data, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    # API возвращает {"ok": False, "error": "invalid_code"}
    # т.к. верифицированный пользователь не имеет валидного кода
    assert "ok" in response.data
    assert response.data["ok"] is False
@pytest.mark.django_db
def test_verify_email_nonexistent_user_returns_404_without_ldap(
    api_client, settings
):
    """V5: Верификация несуществующего пользователя возвращает 404"""
    settings.LDAP_ENABLED = False

    url = reverse("api:v1:verify-email")
    data = {
        "email": "nonexistent@example.com",
        "code": "123456",
    }

    response = api_client.post(url, data, format="json")

    assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_verify_email_empty_code_returns_400_without_ldap(
    api_client, unverified_user, settings
):
    """V6: Пустой код возвращает 400"""
    settings.LDAP_ENABLED = False

    url = reverse("api:v1:verify-email")
    data = {
        "email": unverified_user.email,
        "code": "",
    }

    response = api_client.post(url, data, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST


# ---------- Тесты LDAP ошибок ----------


@pytest.mark.ldap_required
@patch("api.v1.employees.views.auth.DirectoryService")
def test_verify_email_ldap_error_returns_502(
    mock_ds, api_client, unverified_user, settings
):
    """Ошибка LDAP при активации возвращает 502"""
    settings.LDAP_ENABLED = True

    from bots.services.directory import DirectoryLdapError

    mock_svc = MagicMock()
    mock_svc.enable_user.side_effect = DirectoryLdapError("LDAP connection failed")
    mock_ds.return_value = mock_svc

    url = reverse("api:v1:verify-email")
    data = {
        "email": unverified_user.email,
        "code": unverified_user.email_activation_code,
    }

    response = api_client.post(url, data, format="json")

    assert response.status_code == status.HTTP_502_BAD_GATEWAY
    assert "LDAP" in str(response.data)
