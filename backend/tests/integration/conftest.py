"""
Pytest fixtures для интеграционных тестов с LDAP.

ВАЖНО: Перед запуском тестов запустите LDAP сервер:
    cd backend
    ./ldap-test.sh start

Запуск тестов:
    pytest tests/integration/ -v
"""

import pytest
from ldap3 import Server, Connection, ALL, SUBTREE
from django.conf import settings


@pytest.fixture(scope="session")
def ldap_connection():
    """
    Возвращает параметры подключения к тестовому LDAP серверу.
    
    LDAP сервер должен быть запущен заранее: ./ldap-test.sh start
    """
    return {
        "uri": "ldap://localhost:10389",
        "base_dn": "dc=test,dc=local",
        "admin_dn": "cn=admin,dc=test,dc=local",
        "change-me-redacted-secret": "test_change-me-redacted-secret",
        "users_ou": "ou=Users,dc=test,dc=local",
        "groups_ou": "ou=Groups,dc=test,dc=local",
        "departments_ou": "ou=Departments,dc=test,dc=local",
    }


@pytest.fixture
def ldap_test_settings(ldap_connection):
    """
    Временно переключает Django настройки на тестовый LDAP сервер.
    """
    original_settings = {
        "LDAP_ENABLED": settings.LDAP_ENABLED,
        "LDAP_URI": getattr(settings, "LDAP_URI", ""),
        "LDAP_HOST": getattr(settings, "LDAP_HOST", ""),
        "LDAP_PORT": getattr(settings, "LDAP_PORT", 389),
        "LDAP_BASE_DN": getattr(settings, "LDAP_BASE_DN", ""),
        "LDAP_BIND_DN": getattr(settings, "LDAP_BIND_DN", ""),
        "LDAP_BIND_PASSWORD": getattr(settings, "LDAP_BIND_PASSWORD", ""),
        "LDAP_GROUPS_BASE": getattr(settings, "LDAP_GROUPS_BASE", ""),
        "LDAP_POSITIONS_BASE": getattr(settings, "LDAP_POSITIONS_BASE", ""),
        "LDAP_UPN_SUFFIX": getattr(settings, "LDAP_UPN_SUFFIX", ""),
    }
    
    # Устанавливаем тестовые настройки
    settings.LDAP_ENABLED = True
    settings.LDAP_URI = ldap_connection["uri"]
    settings.LDAP_HOST = "localhost"
    settings.LDAP_PORT = 10389
    settings.LDAP_BASE_DN = ldap_connection["base_dn"]
    settings.LDAP_BIND_DN = ldap_connection["admin_dn"]
    settings.LDAP_BIND_PASSWORD = ldap_connection["change-me-redacted-secret"]
    settings.LDAP_USERS_BASE = ldap_connection["users_ou"]
    settings.LDAP_GROUPS_BASE = ldap_connection["groups_ou"]
    settings.LDAP_DEPARTMENTS_BASE = ldap_connection["departments_ou"]
    settings.LDAP_POSITIONS_BASE = "ou=Positions,dc=test,dc=local"
    settings.LDAP_UPN_SUFFIX = "@test.local"
    
    yield ldap_connection
    
    # Восстанавливаем оригинальные настройки
    for key, value in original_settings.items():
        setattr(settings, key, value)


# ============================================================================
# Helper функции для работы с LDAP
# ============================================================================

def get_ldap_connection(ldap_connection):
    """
    Создает подключение к LDAP серверу.
    
    Returns:
        ldap3.Connection: Готовое подключение
    """
    server = Server(ldap_connection["uri"], get_info=ALL)
    conn = Connection(
        server,
        user=ldap_connection["admin_dn"],
        password=ldap_connection["change-me-redacted-secret"],
        auto_bind=True
    )
    return conn


def ldap_search_user(ldap_connection, username):
    """
    Ищет пользователя в LDAP по username.
    
    Args:
        ldap_connection: Параметры подключения из фикстуры
        username: Username для поиска
    
    Returns:
        dict или None: Найденный пользователь или None
    """
    conn = get_ldap_connection(ldap_connection)
    try:
        conn.search(
            ldap_connection["users_ou"],
            f"(uid={username})",
            search_scope=SUBTREE
        )
        if conn.entries:
            entry = conn.entries[0]
            return (entry.entry_dn, entry.entry_attributes_as_dict)
        return None
    finally:
        conn.unbind()


def ldap_delete_user(ldap_connection, username):
    """
    Удаляет пользователя из LDAP.
    
    Args:
        ldap_connection: Параметры подключения из фикстуры
        username: Username для удаления
    """
    user = ldap_search_user(ldap_connection, username)
    if user:
        dn, attrs = user
        conn = get_ldap_connection(ldap_connection)
        try:
            conn.delete(dn)
        finally:
            conn.unbind()


def ldap_cleanup_test_users(ldap_connection, prefix="test_"):
    """
    Удаляет всех тестовых пользователей (по префиксу).
    
    Args:
        ldap_connection: Параметры подключения из фикстуры
        prefix: Префикс username для удаления (по умолчанию "test_")
    """
    conn = get_ldap_connection(ldap_connection)
    try:
        conn.search(
            ldap_connection["users_ou"],
            f"(uid={prefix}*)",
            search_scope=SUBTREE
        )
        for entry in conn.entries:
            try:
                conn.delete(entry.entry_dn)
            except Exception:
                pass  # Игнорируем ошибки при удалении
    finally:
        conn.unbind()


@pytest.fixture
def cleanup_test_data(ldap_connection):
    """
    Очищает тестовые данные после каждого теста.
    
    Удаляет всех пользователей с префиксом "test_" из LDAP.
    Используйте явно в тестах где нужна очистка.
    """
    yield
    
    # После теста удаляем тестовых пользователей
    try:
        ldap_cleanup_test_users(ldap_connection, prefix="test_")
    except Exception as e:
        print(f"⚠️  Не удалось очистить тестовые данные: {e}")
