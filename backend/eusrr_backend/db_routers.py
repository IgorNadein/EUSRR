"""Database routers для направления запросов к нужным базам данных.

LdapRouter направляет все операции с LDAP моделями (из employees.ldap.orm_models)
в LDAP database, а все остальные модели - в default PostgreSQL database.
"""


class LdapRouter:
    """
    Database router для направления LDAP моделей в LDAP подключение.
    
    LDAP модели (LdapUser, LdapGroup, LdapOrganizationalUnit) используются
    ТОЛЬКО для записи (POST/PUT/DELETE) в LDAP через ORM.
    
    Чтение (GET) происходит из обычных Django моделей (Employee, Department и т.д.)
    которые хранятся в PostgreSQL.
    """

    ldap_models = {
        'ldapuser',
        'ldapgroup',
        'ldaporganizationalunit',
        'ldaporganizationalunitgroup',
    }

    def db_for_read(self, model, **hints):
        """
        Направляет READ операции для LDAP моделей в 'ldap' database.
        """
        if model._meta.model_name.lower() in self.ldap_models:
            return 'ldap'
        return None  # Используем default database

    def db_for_write(self, model, **hints):
        """
        Направляет WRITE операции для LDAP моделей в 'ldap' database.
        """
        if model._meta.model_name.lower() in self.ldap_models:
            return 'ldap'
        return None  # Используем default database

    def allow_relation(self, obj1, obj2, **hints):
        """
        Разрешает отношения между моделями только если они в одной базе.
        LDAP модели не могут иметь ForeignKey к Django моделям.
        """
        db_obj1 = obj1._meta.model_name.lower() in self.ldap_models
        db_obj2 = obj2._meta.model_name.lower() in self.ldap_models
        
        # Оба LDAP или оба Django - разрешаем
        if db_obj1 == db_obj2:
            return True
        
        # Один LDAP, другой Django - запрещаем
        return False

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        """
        Запрещает миграции для LDAP моделей (схема управляется AD/LDAP сервером).
        """
        if model_name and model_name.lower() in self.ldap_models:
            # LDAP модели не мигрируют никуда
            return False
        
        # Обычные Django модели мигрируют только в default
        return db == 'default'
