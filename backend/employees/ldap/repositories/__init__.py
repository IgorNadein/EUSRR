"""Слой репозиториев модуля LDAP.

Содержит классы для работы с данными (LDAP и Django ORM).
"""

from .ldap_repository import LdapRepository, read_attrs, is_taken, modify_user_attrs, ensure_container_exists, ldap_modify_or_ignore
from .sync_state_repository import SyncStateRepository, _touch_sync_state
from .employee_repository import EmployeeRepository, _load_existing_users_index, _find_user_for_dto, _bind_user_department, _cleanup_absent_users

__all__ = [
    # Классы репозиториев
    "LdapRepository",
    "SyncStateRepository",
    "EmployeeRepository",
    
    # Обратная совместимость - функции из helpers.py
    "read_attrs",
    "is_taken",
    "modify_user_attrs",
    "ensure_container_exists",
    "ldap_modify_or_ignore",
    
    # Обратная совместимость - функции из repo_db.py
    "_load_existing_users_index",
    "_find_user_for_dto",
    "_bind_user_department",
    "_cleanup_absent_users",
    "_touch_sync_state",
]
