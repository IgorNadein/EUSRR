"""Модуль синхронизации с Active Directory / LDAP.

Предоставляет высокоуровневые API для:
- Синхронизации пользователей, отделов и групп между LDAP и Django
- Управления объектами в LDAP (создание, обновление, удаление)
- Экспорта изменений из Django в LDAP

Архитектура (Clean Architecture):
    domain/          - Бизнес-логика и DTO (независимые от инфраструктуры)
    services/        - Бизнес-сервисы (UserService, DepartmentService и др.)
    repositories/    - Слой доступа к данным (LDAP + DB)
    infrastructure/  - Внешние подключения (LDAP)
    utils/           - Вспомогательные функции (DN, группы, текст и др.)

Основное использование:
    from employees.ldap import DirectoryService, DirectoryUserDTO, SyncConfig

    # Создание пользователя через фасад
    service = DirectoryService()
    dto = DirectoryUserDTO(
        first_name="Иван",
        last_name="Иванов",
        email="ivanov@example.com",
        phone_e164="+79991234567",
        department_dn="OU=IT,DC=example,DC=com",
        group_cns=["Domain Users"],
        initial_password="SecurePass123!",
        is_active=True
    )
    employee = service.create_user(dto)

    # Синхронизация из LDAP в Django
    from employees.ldap import import_users
    config = SyncConfig(mode='ldap', scope='users', dry_run=False)
    created, updated, deleted = import_users(cfg=config)

    # Синхронизация групп пользователя
    from employees.ldap import sync_user_groups_by_cns, _ldap
    with _ldap() as conn:
        added, removed = sync_user_groups_by_cns(
            conn, user_dn, target_cns=["IT Support"], do_write=True
        )
"""

from importlib import import_module

# Сервисы (прямой доступ)
from .services.user_service import UserService
from .services.group_service import GroupService
from .services.department_service import DepartmentService
from .services.position_service import PositionService
from .services.sync_service import SyncService

# Конфигурация
from .config import SyncConfig, SyncMode, SyncScope, DISABLED_FLAG

# Ошибки
from .errors import (
    DirectoryServiceError,
    DirectoryLdapError,
    DirectoryConnectionError,
    DirectoryDbError,
    DirectoryGroupError,
)

# DTO (из domain слоя)
from .domain.dtos import (
    DirectoryUserDTO,
    DirectoryDepartmentDTO,
    LdapPersonDTO,
)

# Утилиты работы с группами
from .utils.group_utils_orm import sync_user_groups_by_cns_orm

# ORM модели
from .orm_models import (
    LdapUser,
    LdapGroup,
    LdapOrganizationalUnitGroup,
    LdapOrganizationalUnit,
)

# Подключения
from .infrastructure.connections import LdapConfig, _ldap

# Админка (автоматическая регистрация)
import_module("employees.ldap.admin")


def export_users(cfg=None):
    """Обёртка для SyncService().export_users(cfg)."""
    svc = SyncService()
    return svc.export_users(cfg or SyncConfig())


__all__ = [
    # Сервисы
    "UserService",
    "GroupService",
    "DepartmentService",
    "PositionService",
    "SyncService",
    "export_users",

    # Конфигурация
    "SyncConfig",
    "SyncMode",
    "SyncScope",
    "DISABLED_FLAG",

    # Ошибки
    "DirectoryServiceError",
    "DirectoryLdapError",
    "DirectoryConnectionError",
    "DirectoryDbError",
    "DirectoryGroupError",

    # DTO
    "DirectoryUserDTO",
    "DirectoryDepartmentDTO",
    "LdapPersonDTO",

    # Утилиты
    "sync_user_groups_by_cns_orm",

    # ORM
    "LdapUser",
    "LdapGroup",
    "LdapOrganizationalUnitGroup",
    "LdapOrganizationalUnit",

    # Подключения
    "LdapConfig",
    "_ldap",
]
