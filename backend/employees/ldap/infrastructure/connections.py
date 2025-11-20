"""Управление LDAP-соединениями.

Функции для создания и управления подключениями к Active Directory / LDAP серверу.
"""

import ssl
from contextlib import contextmanager
from typing import Generator

from django.conf import settings
from ldap3 import Connection, Server, Tls


def _conn() -> Connection:
    """Возвращает привязанное service-bind соединение LDAP.

    Returns:
        Connection: Готовое соединение с автоматической привязкой.

    Raises:
        RuntimeError: Если настройки подключения не заданы или неверны.
    """
    uri = getattr(settings, "LDAP_URI", "")
    bind_dn = getattr(settings, "LDAP_BIND_DN", "")
    bind_pw = getattr(settings, "LDAP_BIND_PASSWORD", "")

    if not uri or not bind_dn or not bind_pw:
        raise RuntimeError(
            "LDAP_URI/LDAP_BIND_DN/LDAP_BIND_PASSWORD must be set in settings"
        )

    ca_file = getattr(settings, "LDAP_CA_CERTS", "") or None
    tls = Tls(
        validate=ssl.CERT_REQUIRED if ca_file else ssl.CERT_NONE,
        ca_certs_file=ca_file,
    )

    server = Server(uri, use_ssl=uri.lower().startswith("ldaps://"), tls=tls)

    return Connection(
        server,
        user=bind_dn,
        password=bind_pw,
        auto_bind=True,
        receive_timeout=30,
    )


@contextmanager
def _ldap() -> Generator[Connection, None, None]:
    """Контекст-менеджер LDAP-соединения с гарантированным закрытием.

    Yields:
        Connection: Подключение ldap3.

    Notes:
        Любые ошибки закрытия соединения глушатся, чтобы не маскировать
        основной результат операций.

    Example:
        >>> from employees.ldap.infrastructure import _ldap
        >>> with _ldap() as conn:
        ...     conn.search("dc=example,dc=com", "(objectClass=*)")
    """
    conn = _conn()
    try:
        yield conn
    finally:
        try:
            if hasattr(conn, "unbind"):
                conn.unbind()
            elif hasattr(conn, "close"):
                conn.close()
        except Exception:
            # Игнорируем ошибки закрытия соединения
            pass


# Псевдоним для обратной совместимости
ldap_connection = _ldap


__all__ = [
    "_conn",
    "_ldap",
    "ldap_connection",
]
