# tests/api/v1/employees/test_ldap_optional_register.py
"""
Тесты для RegisterAPIView с опциональной LDAP интеграцией.
Покрывает тест-кейсы R1-R9 из плана тестирования.
"""
import itertools

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from employees.models import Employee
from tests.conftest import _unique_phone

pytestmark = pytest.mark.django_db

_phone_seq = itertools.count(4000)


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def test_user_data():
    """Базовые данные для регистрации"""
    # Минимальный валидный PNG 1x1 пиксель (прозрачный) в base64
    tiny_png_base64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    return {
        "email": f"test{next(_phone_seq)}@example.com",
        "first_name": "Test",
        "last_name": "User",
        "phone_number": _unique_phone(),
        "password": "SecurePass123!",
        "gender": 1,  # Обязательное поле: 1 - Мужской
        "avatar": f"data:image/png;base64,{tiny_png_base64}",  # Обязательное поле
        "whatsapp": _unique_phone(),  # Контактные поля опциональны, но можно указать
        "birth_date": "1990-01-01",
    }

# ---------- Тесты БЕЗ LDAP (LDAP_ENABLED=False) ----------


def test_register_without_ldap_creates_user_only_in_db(
    api_client, test_user_data, settings
):
    """
    R7: Успешная регистрация без LDAP.
    - Создан пользователь только в БД
    - Пароль установлен в БД (set_password)
    - is_active=False
    """
    settings.LDAP_ENABLED = False

    url = reverse("api:v1:register")
    response = api_client.post(url, test_user_data, format="json")

    assert response.status_code == status.HTTP_201_CREATED

    # Проверяем создание в БД
    user = Employee.objects.get(email=test_user_data["email"])
    assert user.is_active is False
    assert user.email_verified is False
    assert user.has_usable_password()  # Пароль в БД
    assert user.check_password(test_user_data["password"])


def test_register_without_ldap_duplicate_email_returns_400(
    api_client, test_user_data, settings
):
    """R9: Дублирование email без LDAP возвращает 400"""
    settings.LDAP_ENABLED = False

    # Создаём существующего пользователя с верифицированным email
    Employee.objects.create(
        email=test_user_data["email"],
        phone_number=_unique_phone(),
        first_name="Existing",
        last_name="User",
        email_verified=True,  # Верифицирован - нельзя регистрировать снова
    )

    url = reverse("api:v1:register")
    response = api_client.post(url, test_user_data, format="json")

    assert response.status_code == status.HTTP_400_BAD_REQUEST

