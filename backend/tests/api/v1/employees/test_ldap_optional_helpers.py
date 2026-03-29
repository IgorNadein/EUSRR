# tests/api/v1/employees/test_ldap_optional_helpers.py
"""
Тесты для вспомогательных функций LDAP интеграции:
- _is_ldap_enabled()
- _ldap_try()
"""
import pytest
from unittest.mock import Mock
from rest_framework.response import Response

from api.v1.employees.views._helpers import _is_ldap_enabled, _ldap_try
from employees.ldap.errors import (
    DirectoryLdapError,
    DirectoryServiceError,
    DirectoryDbError,
)

pytestmark = pytest.mark.django_db


# ---------- Тесты _is_ldap_enabled() ----------


def test_is_ldap_enabled_returns_true_when_enabled(settings):
    """H1: Проверка с LDAP_ENABLED=True"""
    settings.LDAP_ENABLED = True
    assert _is_ldap_enabled() is True


def test_is_ldap_enabled_returns_false_when_disabled(settings):
    """H2: Проверка с LDAP_ENABLED=False"""
    settings.LDAP_ENABLED = False
    assert _is_ldap_enabled() is False


def test_is_ldap_enabled_returns_false_when_not_set(settings):
    """H3: LDAP_ENABLED не задан - должен возвращать False по умолчанию"""
    if hasattr(settings, 'LDAP_ENABLED'):
        delattr(settings, 'LDAP_ENABLED')
    assert _is_ldap_enabled() is False


# ---------- Тесты _ldap_try() ----------


def test_ldap_try_success_with_ldap_enabled(settings):
    """H4: Успешное выполнение функции при LDAP_ENABLED=True"""
    settings.LDAP_ENABLED = True
    
    mock_fn = Mock()
    result = _ldap_try(mock_fn)
    
    assert result is None
    mock_fn.assert_called_once()


def test_ldap_try_ldap_error_returns_502(settings):
    """H5: Ошибка DirectoryLdapError возвращает Response(502)"""
    settings.LDAP_ENABLED = True
    
    def failing_fn():
        raise DirectoryLdapError("LDAP connection failed")
    
    result = _ldap_try(failing_fn)
    
    assert isinstance(result, Response)
    assert result.status_code == 502
    assert "LDAP sync failed" in str(result.data)


def test_ldap_try_skips_when_ldap_disabled(settings):
    """H6: Функция не вызывается при LDAP_ENABLED=False"""
    settings.LDAP_ENABLED = False
    
    mock_fn = Mock()
    result = _ldap_try(mock_fn)
    
    assert result is None
    mock_fn.assert_not_called()


def test_ldap_try_service_error_returns_502(settings):
    """H7: DirectoryServiceError возвращает Response(502)"""
    settings.LDAP_ENABLED = True
    
    def failing_fn():
        raise DirectoryServiceError("Service error")
    
    result = _ldap_try(failing_fn)
    
    assert isinstance(result, Response)
    assert result.status_code == 502


def test_ldap_try_db_error_returns_502(settings):
    """H7: DirectoryDbError возвращает Response(502)"""
    settings.LDAP_ENABLED = True
    
    def failing_fn():
        raise DirectoryDbError("Database error")
    
    result = _ldap_try(failing_fn)
    
    assert isinstance(result, Response)
    assert result.status_code == 502
