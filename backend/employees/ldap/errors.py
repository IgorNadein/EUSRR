class DirectoryServiceError(Exception):
    """Базовая ошибка сервисного слоя."""


class DirectoryLdapError(DirectoryServiceError):
    """Ошибка на стороне LDAP."""


class DirectoryConnectionError(DirectoryLdapError):
    """Ошибка подключения к LDAP-серверу.

    Включает ошибки конфигурации, сети и аутентификации.
    """


class DirectoryDbError(DirectoryServiceError):
    """Ошибка фиксации изменений в БД."""


class DirectoryGroupError(DirectoryServiceError):
    """Ошибка операций с LDAP-группами."""
