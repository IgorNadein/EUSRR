"""Управление LDAP-соединениями.

Функции для создания и управления подключениями к Active Directory / LDAP серверу.
"""

import ssl
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Generator, Optional

from django.conf import settings
from ldap3 import Connection, Server, Tls
from ldap3.core.exceptions import LDAPBindError, LDAPSocketOpenError

from ..errors import DirectoryConnectionError


@dataclass(frozen=True)
class LdapConfig:
    """Конфигурация подключения к LDAP-серверу.

    Attributes:
        uri: URI сервера (ldap:// или ldaps://).
        bind_dn: Distinguished Name сервисной учётной записи.
        bind_password: Пароль сервисной учётной записи.
        ca_certs: Путь к CA-сертификатам (для TLS).
        timeout: Таймаут операций в секундах.
    """

    uri: str
    bind_dn: str
    bind_password: str
    ca_certs: Optional[str] = None
    timeout: int = 30

    @classmethod
    def from_settings(cls) -> "LdapConfig":
        """Создаёт конфигурацию из Django settings.

        Raises:
            DirectoryConnectionError: Если обязательные настройки не заданы.
        """
        uri = getattr(settings, "LDAP_URI", "")
        bind_dn = getattr(settings, "LDAP_BIND_DN", "")
        bind_pw = getattr(settings, "LDAP_BIND_PASSWORD", "")

        if not uri or not bind_dn or not bind_pw:
            raise DirectoryConnectionError(
                "LDAP_URI, LDAP_BIND_DN и LDAP_BIND_PASSWORD "
                "должны быть заданы в settings"
            )

        return cls(
            uri=uri,
            bind_dn=bind_dn,
            bind_password=bind_pw,
            ca_certs=getattr(settings, "LDAP_CA_CERTS", "") or None,
            timeout=getattr(settings, "LDAP_TIMEOUT", 30),
        )


def _conn(config: Optional[LdapConfig] = None) -> Connection:
    """Возвращает привязанное service-bind соединение LDAP.

    Args:
        config: Конфигурация подключения. Если None — берётся из settings.

    Returns:
        Connection: Готовое соединение с автоматической привязкой.

    Raises:
        DirectoryConnectionError: Если подключение не удалось.
    """
    cfg = config or LdapConfig.from_settings()

    tls = Tls(
        validate=ssl.CERT_REQUIRED if cfg.ca_certs else ssl.CERT_NONE,
        ca_certs_file=cfg.ca_certs,
    )

    # get_info=NONE чтобы избежать recursion error в pyasn1 с Python 3.13
    from ldap3 import NONE
    server = Server(
        cfg.uri,
        use_ssl=cfg.uri.lower().startswith("ldaps://"),
        tls=tls,
        get_info=NONE,
    )

    try:
        return Connection(
            server,
            user=cfg.bind_dn,
            password=cfg.bind_password,
            auto_bind=True,
            receive_timeout=cfg.timeout,
        )
    except LDAPBindError as e:
        raise DirectoryConnectionError(
            f"Ошибка аутентификации LDAP ({cfg.bind_dn}): {e}"
        ) from e
    except LDAPSocketOpenError as e:
        raise DirectoryConnectionError(
            f"Не удалось подключиться к {cfg.uri}: {e}"
        ) from e
    except Exception as e:
        raise DirectoryConnectionError(
            f"Ошибка подключения к LDAP: {e}"
        ) from e


@contextmanager
def _ldap(
    config: Optional[LdapConfig] = None,
) -> Generator[Connection, None, None]:
    """Контекст-менеджер LDAP-соединения с гарантированным закрытием.

    Args:
        config: Конфигурация подключения. Если None — берётся из settings.

    Yields:
        Connection: Подключение ldap3.

    Raises:
        DirectoryConnectionError: Если подключение не удалось.

    Example:
        >>> from employees.ldap.infrastructure import _ldap
        >>> with _ldap() as conn:
        ...     conn.search("dc=example,dc=com", "(objectClass=*)")
    """
    conn = _conn(config)
    try:
        yield conn
    finally:
        try:
            if hasattr(conn, "unbind"):
                conn.unbind()
            elif hasattr(conn, "close"):
                conn.close()
        except Exception:
            pass


# Псевдоним для обратной совместимости
ldap_connection = _ldap


__all__ = [
    "LdapConfig",
    "_conn",
    "_ldap",
    "ldap_connection",
]
