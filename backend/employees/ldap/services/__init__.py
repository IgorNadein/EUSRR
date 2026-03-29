"""Слой сервисов модуля LDAP.

Содержит бизнес-логику синхронизации и управления объектами LDAP.

Архитектура:
- BaseService - базовый класс для всех сервисов (логирование, _touch_state)
- Константы - вынесены в constants.py (UAC, GroupType, LDAP фильтры)
- Подсервисы - разбиение больших сервисов на компоненты

Основные сервисы:
- UserService - управление пользователями
- DepartmentService - управление отделами/OU
- GroupService - управление группами AD
- PositionService - управление должностями (POS-группы)
- SyncService - координация массовых операций синхронизации

Подсервисы (для UserService):
- UserPasswordService - работа с паролями
- UserLoginService - генерация логинов/UPN
- UserMapperService - маппинг атрибутов Django ↔ LDAP
"""

# Базовый класс и константы
from .base_service import BaseService
from .constants import (
    UserAccountControl,
    GroupType,
    LdapFilter,
    LdapAttribute,
    LdapObjectClass,
    LdapErrorCode,
    SyncDirection,
    group_type_value,
)

# Основные сервисы (существующие - для обратной совместимости)
from .department_service import DepartmentService
from .user_service import UserService
from .group_service import GroupService
from .position_service import PositionService
from .sync_service import SyncService

# Подсервисы для UserService
from .user_password_service import UserPasswordService
from .user_login_service import UserLoginService
from .user_mapper_service import UserMapperService


__all__ = [
    # Базовые компоненты
    "BaseService",
    
    # Константы
    "UserAccountControl",
    "GroupType",
    "LdapFilter",
    "LdapAttribute",
    "LdapObjectClass",
    "LdapErrorCode",
    "SyncDirection",
    "group_type_value",
    
    # Основные сервисы
    "DepartmentService",
    "UserService",
    "GroupService",
    "PositionService",
    "SyncService",
    
    # Подсервисы
    "UserPasswordService",
    "UserLoginService",
    "UserMapperService",
]
