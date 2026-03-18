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

# Текущие импорты (для обратной совместимости)
from .directory_service import DirectoryService
from .services.sync_service import SyncService

# Конфигурация
from .config import SyncConfig, SyncMode, SyncScope, DISABLED_FLAG

# Ошибки
from .errors import (
    DirectoryServiceError,
    DirectoryLdapError,
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
from .utils.group_utils import sync_user_groups_by_cns
from .utils.group_utils_orm import sync_user_groups_by_cns_orm

# ORM модели и сервисы
from .orm_models import LdapUser, LdapGroup, LdapOrganizationalUnit
from .orm_services import LdapOrmUserService, LdapOrmGroupService, LdapOrmDepartmentService

# Подключения
from .infrastructure.connections import _ldap


# Обратная совместимость: обёртки над SyncService
def import_departments(cfg=None):
    """Обёртка для SyncService().import_departments(cfg)."""
    svc = SyncService()
    return svc.import_departments(cfg or SyncConfig())


def import_users(cfg=None):
    """Обёртка для SyncService().import_users(cfg)."""
    svc = SyncService()
    return svc.import_users(cfg or SyncConfig())


def export_users(cfg=None):
    """Обёртка для SyncService().export_users(cfg)."""
    svc = SyncService()
    return svc.export_users(cfg or SyncConfig())

__all__ = [
    # Сервисы
    "DirectoryService",
    "import_departments",
    "import_users",
    "export_users",

    # Конфигурация
    "SyncConfig",
    "SyncMode",
    "SyncScope",
    "DISABLED_FLAG",

    # Ошибки
    "DirectoryServiceError",
    "DirectoryLdapError",
    "DirectoryDbError",
    "DirectoryGroupError",

    # DTO
    "DirectoryUserDTO",
    "DirectoryDepartmentDTO",
    "LdapPersonDTO",

    # Утилиты
    "sync_user_groups_by_cns",
    "sync_user_groups_by_cns_orm",

    # ORM
    "LdapUser",
    "LdapGroup",
    "LdapOrganizationalUnit",
    "LdapOrmUserService",
    "LdapOrmGroupService",
    "LdapOrmDepartmentService",

    # Подключения
    "_ldap",
]
