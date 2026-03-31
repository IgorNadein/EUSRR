from dataclasses import dataclass
from typing import Literal

SyncMode = Literal["ldap", "django", "auto"]
SyncScope = Literal["all", "users", "departments", "groups"]

DISABLED_FLAG = 0x0002


@dataclass(frozen=True)
class SyncConfig:
    """Конфигурация синхронизации каталога.

    Attributes:
        mode (SyncMode): Направление ('ldap'|'django'|'auto').
        scope (SyncScope): Область ('all'|'users'|'departments'|'groups').
        dry_run (bool): Сухой прогон — изменения считаются/
            валидируются, но не применяются.
        max_changes (int): Лимит изменений за прогон (зарезервировано).
        users_base_dn (str): DN контейнера пользователей (OU=Users,...).
        departments_base_dn (str): DN контейнера отделов (OU=Departments,...).
        groups_base_dn (str): DN контейнера глобальных групп (OU=Groups,...).
    """

    mode: SyncMode = "ldap"
    scope: SyncScope = "all"
    dry_run: bool = True
    max_changes: int = 1000
    users_base_dn: str = ""
    departments_base_dn: str = ""
    groups_base_dn: str = ""
    show_changes: bool = False
