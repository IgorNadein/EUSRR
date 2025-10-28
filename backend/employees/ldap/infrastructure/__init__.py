"""Инфраструктурный слой модуля LDAP.

Содержит подключения к внешним системам (LDAP server).
"""

from .connections import _conn, _ldap, ldap_connection

__all__ = [
    "_conn",
    "_ldap",
    "ldap_connection",
]
