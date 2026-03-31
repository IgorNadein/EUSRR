"""
Тест реального подключения к LDAP.
"""

import pytest
from employees.ldap.infrastructure.connections import _ldap


@pytest.mark.integration
def test_ldap_connection():
    """Проверка подключения к реальному LDAP серверу."""
    try:
        with _ldap() as conn:
            # Пробуем простой поиск базового DN
            conn.search(
                search_base='DC=robotail,DC=local',
                search_filter='(objectClass=*)',
                search_scope='BASE',
                attributes=['*']
            )
            assert conn.result['description'] == 'success'
            print("\n✓ LDAP подключение успешно")
            print(f"✓ Сервер: {conn.server}")
            print(f"✓ Пользователь: {conn.user}")
    except Exception as e:
        pytest.fail(f"Не удалось подключиться к LDAP: {e}")


if __name__ == '__main__':
    test_ldap_connection()
