"""Database routers для направления запросов к нужным базам данных.

LdapRouter направляет все операции с LDAP моделями
(из employees.ldap.orm_models)
в LDAP database, а все остальные модели - в default PostgreSQL database.

Когда LDAP_WRITE_ENABLED=False, DATABASES["ldap"] не существует.
Router возвращает None для LDAP моделей (Django не будет выполнять запросы),
но по-прежнему запрещает миграции для них.
"""

from django.conf import settings


class LdapRouter:
    """
    Database router для направления LDAP моделей в LDAP подключение.

    LDAP модели (LdapUser, LdapGroup, LdapOrganizationalUnit) используются
    ТОЛЬКО для записи (POST/PUT/DELETE) в LDAP через ORM.

    Чтение (GET) происходит из обычных Django моделей
    (Employee, Department и т.д.)
    которые хранятся в PostgreSQL.
    """

    ldap_models = {
        "ldapuser",
        "ldapgroup",
        "ldaporganizationalunit",
        "ldaporganizationalunitgroup",
    }

    @property
    def _ldap_db_available(self):
        return "ldap" in settings.DATABASES

    def db_for_read(self, model, **hints):
        if model._meta.model_name.lower() in self.ldap_models:
            return "ldap" if self._ldap_db_available else None
        return None

    def db_for_write(self, model, **hints):
        if model._meta.model_name.lower() in self.ldap_models:
            return "ldap" if self._ldap_db_available else None
        return None

    def allow_relation(self, obj1, obj2, **hints):
        db_obj1 = obj1._meta.model_name.lower() in self.ldap_models
        db_obj2 = obj2._meta.model_name.lower() in self.ldap_models
        if db_obj1 == db_obj2:
            return True
        return False

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        if model_name and model_name.lower() in self.ldap_models:
            return False
        return db == "default"
