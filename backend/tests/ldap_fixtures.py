"""
Фикстуры для тестирования с LDAP.

Предоставляет:
- ldap_connection: подключение к тестовому LDAP серверу
- ldap_enabled/ldap_disabled: маркеры для параметризации тестов
- ldap_config: конфигурация LDAP для тестов
"""
import os

import pytest
from django.conf import settings


@pytest.fixture(scope="session")
def ldap_available():
    """
    Проверяет доступность LDAP сервера.

    Returns:
        bool: True если LDAP доступен и настроен
    """
    if not settings.LDAP_ENABLED:
        return False

    try:
        from employees.ldap.infrastructure.connections import _ldap
        with _ldap() as conn:
            # Простая проверка подключения
            return conn.bind()
    except Exception as e:
        print(f"LDAP не доступен: {e}")
        return False


@pytest.fixture
def ldap_config():
    """
    Возвращает конфигурацию LDAP для тестов.
    """
    return {
        'enabled': settings.LDAP_ENABLED,
        'uri': settings.LDAP_URI,
        'base_dn': settings.LDAP_BASE_DN,
        'users_base': settings.LDAP_USERS_BASE,
        'departments_base': getattr(settings, 'LDAP_DEPARTMENTS_BASE', None),
        'groups_base': getattr(settings, 'LDAP_GROUPS_BASE', None),
        'positions_base': getattr(settings, 'LDAP_POSITIONS_BASE', None),
        'dismissed_base': getattr(settings, 'LDAP_DISMISSED_BASE', None),
    }


@pytest.fixture
def ensure_ldap_enabled(settings):
    """
    Гарантирует что LDAP включен для теста.
    Используется для тестов которые требуют LDAP.
    """
    original = settings.LDAP_ENABLED
    settings.LDAP_ENABLED = True
    yield
    settings.LDAP_ENABLED = original


@pytest.fixture
def ensure_ldap_disabled(settings):
    """
    Гарантирует что LDAP выключен для теста.
    Используется для тестов режима без LDAP.
    """
    original = settings.LDAP_ENABLED
    settings.LDAP_ENABLED = False
    yield
    settings.LDAP_ENABLED = original


@pytest.fixture
def ldap_cleanup():
    """
    Cleanup фикстура для удаления тестовых данных из LDAP после теста.

    Usage:
        def test_something(ldap_cleanup):
            # создаем объекты в LDAP
            ldap_cleanup.add_for_deletion(dn)
    """
    cleanup_list = []

    class Cleanup:
        def add_for_deletion(self, dn):
            cleanup_list.append(dn)

    yield Cleanup()

    # Cleanup после теста
    if cleanup_list and settings.LDAP_ENABLED:
        try:
            from employees.ldap.infrastructure.connections import _ldap
            with _ldap() as conn:
                for dn in reversed(cleanup_list):  # удаляем в обратном порядке
                    try:
                        conn.delete(dn)
                    except Exception as e:
                        print(f"Не удалось удалить {dn}: {e}")
        except Exception as e:
            print(f"LDAP cleanup failed: {e}")


def pytest_configure(config):
    """
    Регистрация маркеров для pytest.
    """
    config.addinivalue_line(
        "markers", "ldap_required: тест требует работающий LDAP сервер"
    )
    config.addinivalue_line(
        "markers", "ldap_optional: тест может работать с LDAP и без него (параметризован)"
    )


def pytest_collection_modifyitems(config, items):
    """
    Автоматически скипает тесты требующие LDAP если он недоступен.
    """
    ldap_available = False
    if settings.LDAP_ENABLED:
        try:
            from employees.ldap.infrastructure.connections import _ldap
            with _ldap() as conn:
                ldap_available = conn.bind()
        except:
            pass

    skip_ldap = pytest.mark.skip(reason="LDAP сервер недоступен")

    for item in items:
        if "ldap_required" in item.keywords and not ldap_available:
            item.add_marker(skip_ldap)
