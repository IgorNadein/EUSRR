"""Инфраструктурный слой модуля LDAP.

Содержит подключения к внешним системам (LDAP server).
"""

from .connections import LdapConfig, _conn, _ldap, ldap_connection

__all__ = [
    "LdapConfig",
    "_conn",
    "_ldap",
    "ldap_connection",
]
