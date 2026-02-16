# tests/api/v1/employees/test_ldap_optional_register.py
"""
Тесты для RegisterAPIView с опциональной LDAP интеграцией.
Покрывает тест-кейсы R1-R9 из плана тестирования.

Использует реальный LDAP контейнер для интеграционного тестирования.
"""
import itertools

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from employees.models import Employee, LdapSyncState
from tests.conftest import _unique_phone

User = get_user_model()
pytestmark = pytest.mark.django_db

_phone_seq = itertools.count(4000)

@pytest.fixture
def api_client():
    return APIClient()

@pytest.fixture
def test_user_data():
    """Базовые данные для регистрации"""
    return {
        "email": f"test{next(_phone_seq)}@example.com",
        "first_name": "TestUser",
        "last_name": "LastName",
        "phone_number": _unique_phone(),
        "password": "SecurePass123!",
        "whatsapp": _unique_phone(),
        "birth_date": "1990-01-01",
    }

# ---------- Тесты С LDAP (LDAP_ENABLED=True) ----------

@pytest.mark.ldap_required
def test_register_with_ldap_creates_user_in_ldap_and_db(
    api_client, test_user_data, ensure_ldap_enabled, ldap_cleanup
):
    """
    R1: Успешная регистрация с LDAP.
    - Пользователь создан в LDAP (disabled)
    - Пароль установлен в LDAP
    - Создана запись в БД (unusable_password)
    - is_active=False
    """
    url = reverse("api:v1:register")
    response = api_client.post(url, test_user_data, format="json")
    
    assert response.status_code == status.HTTP_201_CREATED
    
    # Проверяем создание в БД
    user = Employee.objects.get(email=test_user_data["email"])
    assert user.is_active is False
    assert user.email_verified is False
    assert not user.has_usable_password()  # Пароль в LDAP, не в БД
    
    # Проверяем создание в LDAP
    sync_state = LdapSyncState.objects.filter(
        model="employee",
        object_pk=str(user.pk)
    ).first()
    
    assert sync_state is not None, "Пользователь должен быть синхронизирован с LDAP"
    assert sync_state.ldap_dn is not None
    
    # Добавляем DN в cleanup
    ldap_cleanup.add_for_deletion(sync_state.ldap_dn)

@pytest.mark.ldap_required
def test_register_with_ldap_duplicate_email_returns_400(
    api_client, test_user_data, ensure_ldap_enabled
):
    """R3: Дублирование email возвращает 400"""
    
    # Создаём существующего пользователя
    Employee.objects.create(
        email=test_user_data["email"],
        phone_number=_unique_phone(),
        first_name="Existing",
        last_name="User",
    )
    
    url = reverse("api:v1:register")
    response = api_client.post(url, test_user_data, format="json")
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "email" in str(response.data).lower() or "exists" in str(response.data).lower()

# ---------- Тесты БЕЗ LDAP (LDAP_ENABLED=False) ----------

def test_register_without_ldap_creates_user_only_in_db(
    api_client, test_user_data, ensure_ldap_disabled
):
    """
    R7: Успешная регистрация без LDAP.
    - Создан пользователь только в БД
    - Пароль установлен в БД (set_password)
    - is_active=False
    """
    url = reverse("api:v1:register")
    response = api_client.post(url, test_user_data, format="json")
    
    assert response.status_code == status.HTTP_201_CREATED
    
    # Проверяем создание в БД
    user = Employee.objects.get(email=test_user_data["email"])
    assert user.is_active is False
    assert user.email_verified is False
    assert user.has_usable_password()  # Пароль в БД
    assert user.check_password(test_user_data["password"])
    
    # Проверяем что НЕ создан в LDAP
    sync_state = LdapSyncState.objects.filter(
        model="employee",
        object_pk=str(user.pk)
    ).first()
    assert sync_state is None, "Пользователь не должен быть в LDAP"

def test_register_without_ldap_duplicate_email_returns_400(
    api_client, test_user_data, ensure_ldap_disabled
):
    """R9: Дублирование email без LDAP возвращает 400"""
    
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

# ---------- Параметризованные тесты (оба режима) ----------

@pytest.mark.ldap_optional
@pytest.mark.parametrize(
    "ldap_enabled", [True, False], ids=["with_ldap", "without_ldap"]
)
def test_register_validates_required_fields(
    api_client, ldap_enabled, settings, ensure_ldap_enabled, ensure_ldap_disabled
):
    """Проверка валидации обязательных полей в обоих режимах"""
    # Используем нужную фикстуру в зависимости от параметра
    if ldap_enabled:
        settings.LDAP_ENABLED = True
    else:
        settings.LDAP_ENABLED = False
    
    url = reverse("api:v1:register")
    
    # Отсутствует email
    response = api_client.post(url, {
        "first_name": "Test",
        "last_name": "User",
        "password": "Pass123!",
        "birth_date": "1990-01-01",
    }, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    # Отсутствует password
    response = api_client.post(url, {
        "email": "test@example.com",
        "first_name": "Test",
        "last_name": "User",
        "birth_date": "1990-01-01",
    }, format="json")
    assert response.status_code == status.HTTP_400_BAD_REQUEST
