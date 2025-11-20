"""
Интеграционные тесты для проверки что код работает с LDAP включенным.

ВАЖНО: Перед запуском запустите LDAP сервер:
    cd backend
    ./ldap-test.sh start

Эти тесты проверяют что:
1. Код не падает когда LDAP включен
2. Ошибки LDAP обрабатываются корректно
3. Fallback на БД работает когда LDAP недоступен

Запуск тестов:
    pytest tests/integration/test_ldap_enabled.py -v
"""

import pytest
from rest_framework.test import APIClient

from employees.models import Employee


@pytest.mark.django_db
def test_register_with_ldap_enabled_handles_errors(ldap_test_settings):
    """
    Регистрация с включенным LDAP корректно обрабатывает ошибки.
    
    OpenLDAP не поддерживает AD атрибуты, поэтому ожидаем 502,
    но важно что код не падает с 500.
    """
    client = APIClient()
    
    email = "test_error@test.local"
    user_data = {
        "email": email,
        "password": "TestPassword123!",
        "password_confirmation": "TestPassword123!",
        "first_name": "Test",
        "last_name": "Error",
        "telegram": "@test_error",
        "birth_date": "1990-01-01",
        "phone_number": "+79001234567",
    }
    
    response = client.post("/api/v1/auth/register/", user_data)
    
    # Ожидаем 502 (LDAP ошибка) или 201 (успех)
    # но НЕ 500 (необработанное исключение)
    assert response.status_code in [201, 502], \
        f"Expected 201 or 502, got {response.status_code}: {response.data}"
    
    if response.status_code == 502:
        # Проверяем что ошибка понятная
        assert "ldap" in str(response.data).lower()
        print(f"✅ LDAP error handled correctly: {response.data}")
    else:
        # Если регистрация прошла - проверяем БД
        assert Employee.objects.filter(email=email).exists()
        print("✅ User registered successfully")


@pytest.mark.django_db
def test_register_without_ldap_works(ldap_connection):
    """
    Регистрация работает когда LDAP отключен.
    
    Это базовый тест что Django часть работает независимо от LDAP.
    """
    from django.conf import settings
    
    # Временно отключаем LDAP
    original_enabled = settings.LDAP_ENABLED
    settings.LDAP_ENABLED = False
    
    try:
        client = APIClient()
        
        email = "test_noldap@test.local"
        user_data = {
            "email": email,
            "password": "TestPassword123!",
            "password_confirmation": "TestPassword123!",
            "first_name": "Test",
            "last_name": "NoLDAP",
            "telegram": "@test_noldap",
            "birth_date": "1990-01-01",
            "phone_number": "+79001234568",
        }
        
        response = client.post("/api/v1/auth/register/", user_data)
        
        # Без LDAP должно работать
        assert response.status_code == 201, \
            f"Expected 201, got {response.status_code}: {response.data}"
        
        # Проверяем что пользователь создан в БД
        employee = Employee.objects.get(email=email)
        assert employee.email == user_data["email"]
        assert employee.first_name == user_data["first_name"]
        print(f"✅ User created without LDAP: {employee.email}")
        
    finally:
        # Восстанавливаем настройку
        settings.LDAP_ENABLED = original_enabled


@pytest.mark.django_db
def test_verify_email_works_without_ldap(ldap_connection):
    """
    Верификация email работает когда LDAP отключен.
    """
    from django.conf import settings
    
    # Временно отключаем LDAP
    original_enabled = settings.LDAP_ENABLED
    settings.LDAP_ENABLED = False
    
    try:
        client = APIClient()
        
        email = "test_verify@test.local"
        user_data = {
            "email": email,
            "password": "TestPassword123!",
            "password_confirmation": "TestPassword123!",
            "first_name": "Test",
            "last_name": "Verify",
            "telegram": "@test_verify",
            "birth_date": "1990-01-01",
            "phone_number": "+79001234569",
        }
        
        # Регистрируемся
        response = client.post("/api/v1/auth/register/", user_data)
        assert response.status_code == 201
        
        # Получаем код активации
        employee = Employee.objects.get(email=email)
        code = employee.email_activation_code
        assert code is not None
        
        # Верифицируем email
        verify_response = client.post(
            "/api/v1/auth/verify-email/",
            {"email": email, "code": code}
        )
        
        assert verify_response.status_code == 200
        
        employee.refresh_from_db()
        assert employee.email_verified is True
        assert employee.is_active is True
        print(f"✅ Email verified: {employee.email}")
        
    finally:
        settings.LDAP_ENABLED = original_enabled


@pytest.mark.django_db
def test_ldap_settings_are_properly_configured(
    ldap_test_settings, ldap_connection
):
    """
    Проверяет что тестовые LDAP параметры установлены правильно.
    
    Это базовая проверка что фикстура ldap_test_settings работает.
    """
    from django.conf import settings
    
    assert settings.LDAP_ENABLED is True
    assert settings.LDAP_URI == ldap_connection["uri"]
    assert settings.LDAP_BASE_DN == ldap_connection["base_dn"]
    assert settings.LDAP_BIND_DN == ldap_connection["admin_dn"]
    assert settings.LDAP_BIND_PASSWORD == ldap_connection["change-me-redacted-secret"]
    assert settings.LDAP_USERS_BASE == ldap_connection["users_ou"]
    
    print("✅ LDAP settings configured correctly:")
    print(f"   URI: {settings.LDAP_URI}")
    print(f"   Base DN: {settings.LDAP_BASE_DN}")
    print(f"   Users Base: {settings.LDAP_USERS_BASE}")


