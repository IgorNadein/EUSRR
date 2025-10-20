class DirectoryServiceError(Exception):
    """Базовая ошибка сервисного слоя."""


class DirectoryLdapError(DirectoryServiceError):
    """Ошибка на стороне LDAP."""


class DirectoryDbError(DirectoryServiceError):
    """Ошибка фиксации изменений в БД."""


class DirectoryGroupError(DirectoryServiceError):
    """Ошибка операций с LDAP-группами."""
