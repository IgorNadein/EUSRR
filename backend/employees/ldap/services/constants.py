"""Константы для работы с LDAP/Active Directory.

Централизованное хранение всех магических чисел,
строк и конфигурационных значений, используемых в сервисах LDAP.
"""

from enum import IntEnum, Enum


# ==================== UAC Constants ==================== #


class UserAccountControl(IntEnum):
    """Флаги User Account Control для Active Directory.

    См. документацию Microsoft по UserAccountControl:
    https://docs.microsoft.com/en-us/troubleshoot/windows-server/
    identity/useraccountcontrol-manipulate-account-properties
    """

    # Основные состояния
    ENABLED = 512  # ADS_UF_NORMAL_ACCOUNT
    DISABLED = 514  # ADS_UF_NORMAL_ACCOUNT | ADS_UF_ACCOUNTDISABLE

    # Дополнительные флаги
    ACCOUNTDISABLE = 0x0002  # Учетная запись отключена
    PASSWD_NOTREQD = 0x0020  # Пароль не требуется
    PASSWD_CANT_CHANGE = 0x0040  # Пользователь не может менять пароль
    NORMAL_ACCOUNT = 0x0200  # Обычная учетная запись
    DONT_EXPIRE_PASSWORD = 0x10000  # Пароль не истекает
    PASSWORD_EXPIRED = 0x800000  # Пароль истек

    # Комбинированные состояния
    DISABLED_PASSWORD_EXPIRED = 0x0202  # Отключен + пароль истек


# ==================== Group Type Constants ==================== #


class GroupType(IntEnum):
    """Типы групп Active Directory.

    groupType - это битовая маска, определяющая тип и область группы.
    """

    # Базовые типы
    GLOBAL_GROUP = 0x00000002  # -2147483646
    DOMAIN_LOCAL_GROUP = 0x00000004  # -2147483644
    UNIVERSAL_GROUP = 0x00000008  # -2147483640

    # Флаг безопасности
    SECURITY_ENABLED = 0x80000000  # -2147483648

    # Комбинированные типы (наиболее частые)
    GLOBAL_SECURITY = -2147483646  # GLOBAL_GROUP | SECURITY_ENABLED
    DOMAIN_LOCAL_SECURITY = -2147483644  # DOMAIN_LOCAL_GROUP | SECURITY_ENABLED
    UNIVERSAL_SECURITY = -2147483640  # UNIVERSAL_GROUP | SECURITY_ENABLED

    GLOBAL_DISTRIBUTION = 2  # GLOBAL_GROUP (без SECURITY_ENABLED)
    DOMAIN_LOCAL_DISTRIBUTION = 4  # DOMAIN_LOCAL_GROUP
    UNIVERSAL_DISTRIBUTION = 8  # UNIVERSAL_GROUP


# ==================== LDAP Object Classes ==================== #


class LdapObjectClass(str, Enum):
    """Классы объектов LDAP."""

    # Пользователи
    TOP = "top"
    PERSON = "person"
    ORGANIZATIONAL_PERSON = "organizationalPerson"
    USER = "user"

    # Группы
    GROUP = "group"

    # Организационные единицы
    ORGANIZATIONAL_UNIT = "organizationalUnit"

    # Контейнеры
    CONTAINER = "container"


# ==================== LDAP Filters ==================== #


class LdapFilter(str, Enum):
    """Часто используемые LDAP фильтры."""

    # Базовые фильтры
    ALL_USERS = "(&(objectCategory=person)(objectClass=user))"
    ALL_GROUPS = "(objectClass=group)"
    ALL_OUS = "(objectClass=organizationalUnit)"

    # Фильтры по состоянию
    ENABLED_USERS = (
        "(&(objectCategory=person)(objectClass=user)"
        "(!(userAccountControl:1.2.840.113556.1.4.803:=2)))"
    )
    DISABLED_USERS = (
        "(&(objectCategory=person)(objectClass=user)"
        "(userAccountControl:1.2.840.113556.1.4.803:=2))"
    )

    # Фильтры групп
    SECURITY_GROUPS = (
        "(&(objectClass=group)(groupType:1.2.840.113556.1.4.803:=2147483648))"
    )
    DISTRIBUTION_GROUPS = (
        "(&(objectClass=group)"
        "(!(groupType:1.2.840.113556.1.4.803:=2147483648)))"
    )


# ==================== LDAP Attributes ==================== #


class LdapAttribute(str, Enum):
    """Стандартные атрибуты LDAP/AD."""

    # Идентификаторы
    DN = "distinguishedName"
    CN = "cn"
    OBJECT_GUID = "objectGUID"
    OBJECT_SID = "objectSid"

    # Пользовательские атрибуты
    SAM_ACCOUNT_NAME = "sAMAccountName"
    USER_PRINCIPAL_NAME = "userPrincipalName"
    DISPLAY_NAME = "displayName"
    GIVEN_NAME = "givenName"
    SN = "sn"
    MAIL = "mail"
    EMPLOYEE_NUMBER = "employeeNumber"

    # Телефонные атрибуты
    MOBILE = "mobile"
    TELEPHONE_NUMBER = "telephoneNumber"

    # Группы и членство
    MEMBER = "member"
    MEMBER_OF = "memberOf"

    # Организационные атрибуты
    OU = "ou"
    DESCRIPTION = "description"
    MANAGED_BY = "managedBy"

    # Технические атрибуты
    USER_ACCOUNT_CONTROL = "userAccountControl"
    GROUP_TYPE = "groupType"
    WHEN_CHANGED = "whenChanged"
    WHEN_CREATED = "whenCreated"

    # Изображения
    THUMBNAIL_PHOTO = "thumbnailPhoto"
    JPEG_PHOTO = "jpegPhoto"


# ==================== LDAP Search Scopes ==================== #


class SearchScope(str, Enum):
    """Области поиска LDAP."""

    BASE = "BASE"  # Только базовый объект
    LEVEL = "LEVEL"  # Один уровень (дети)
    SUBTREE = "SUBTREE"  # Всё поддерево


# ==================== Error Messages ==================== #


class LdapErrorCode(str, Enum):
    """Коды ошибок LDAP."""

    NO_SUCH_OBJECT = "noSuchObject"
    ENTRY_ALREADY_EXISTS = "entryAlreadyExists"
    UNWILLING_TO_PERFORM = "unwillingToPerform"
    CONSTRAINT_VIOLATION = "constraintViolation"
    INVALID_CREDENTIALS = "invalidCredentials"
    INSUFFICIENT_ACCESS = "insufficientAccessRights"


# ==================== Password Policy ==================== #


class PasswordError(str, Enum):
    """Коды ошибок паролей AD."""

    COMPLEXITY_VIOLATION = (
        "0000052D"  # Пароль не соответствует политике сложности
    )
    PASSWORD_TOO_SHORT = "00000523"  # Пароль слишком короткий
    PASSWORD_IN_HISTORY = "0000052C"  # Пароль уже использовался


# ==================== Sync Direction ==================== #


class SyncDirection(str, Enum):
    """Направления синхронизации в LdapSyncState."""

    LDAP = "ldap"  # Синхронизация из LDAP в Django
    DJANGO = "django"  # Синхронизация из Django в LDAP
    AUTO = "auto"  # Автоматическая синхронизация
    MANUAL = "manual"  # Ручная синхронизация


# ==================== Helper Functions ==================== #


def group_type_value(
    scope: str = "global", security_enabled: bool = True
) -> int:
    """Вычисляет значение groupType для создания группы.

    Args:
        scope: Область группы ('global', 'domain_local', 'universal')
        security_enabled: Является ли группа группой безопасности

    Returns:
        Числовое значение для атрибута groupType

    Raises:
        ValueError: Если указан неверный scope
    """
    scope_map = {
        "global": GroupType.GLOBAL_GROUP,
        "domain_local": GroupType.DOMAIN_LOCAL_GROUP,
        "universal": GroupType.UNIVERSAL_GROUP,
    }

    if scope not in scope_map:
        raise ValueError(
            f"Неверный scope: {scope}. Допустимы: {list(scope_map.keys())}"
        )

    value = scope_map[scope]
    if security_enabled:
        value |= GroupType.SECURITY_ENABLED

    return int(value)


__all__ = [
    "UserAccountControl",
    "GroupType",
    "LdapObjectClass",
    "LdapFilter",
    "LdapAttribute",
    "SearchScope",
    "LdapErrorCode",
    "PasswordError",
    "SyncDirection",
    "group_type_value",
]
