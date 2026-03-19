"""Слой репозиториев модуля LDAP.

Содержит классы и функции для работы с данными (LDAP и Django ORM).
"""

from .ldap_repository import LdapRepository
from .sync_state_repository import (
    get_or_create,
    get_state,
    touch,
    get_employees_with_dn,
    delete_for_employee,
    bulk_delete_for_employees,
)
from .employee_repository import (
    load_users_index,
    find_user_for_dto,
    bind_user_department,
    get_stale_employee_ids,
)

__all__ = [
    # LDAP
    "LdapRepository",
    # Sync state
    "get_or_create",
    "get_state",
    "touch",
    "get_employees_with_dn",
    "delete_for_employee",
    "bulk_delete_for_employees",
    # Employee
    "load_users_index",
    "find_user_for_dto",
    "bind_user_department",
    "get_stale_employee_ids",
]
