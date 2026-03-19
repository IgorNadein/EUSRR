"""Доменный слой модуля LDAP.

Содержит бизнес-логику, DTO и доменные модели.
"""

from .dtos import (
    DirectoryUserDTO,
    DirectoryDepartmentDTO,
    LdapPersonDTO,
    _entry_to_dto,
    _extract_ldap_attrs,
    _resolve_email,
    _resolve_name,
)

__all__ = [
    "DirectoryUserDTO",
    "DirectoryDepartmentDTO",
    "LdapPersonDTO",
    "_entry_to_dto",
    "_extract_ldap_attrs",
    "_resolve_email",
    "_resolve_name",
]
