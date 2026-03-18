"""LDAP ORM модели для работы с Active Directory через django-ldapdb.

Эти модели используются ТОЛЬКО для записи (POST/PUT/DELETE) в LDAP.
Для чтения (GET) используются обычные Django модели (Employee, Department).

Преимущества ORM подхода:
- Замена низкоуровневых ldap3 операций на Django ORM
- Автоматическая валидация и типизация
- Унифицированный API для CRUD операций
- Меньше кода, больше удобства
"""

from django.conf import settings
from ldapdb.models import Model as LdapModel
from ldapdb.models.fields import (
    CharField,
    DateTimeField,
    ImageField,
    IntegerField,
    ListField,
)


def get_users_base():
    """Получает base DN для пользователей из settings."""
    return getattr(settings, 'LDAP_USERS_BASE', 
                   getattr(settings, 'LDAP_USER_BASE', 
                          'OU=company,DC=robotail,DC=local'))


def get_base_dn():
    """Получает корневой base DN из settings."""
    return getattr(settings, 'LDAP_BASE_DN',
                   getattr(settings, 'LDAP_USER_BASE',
                          'DC=robotail,DC=local'))


class LdapUser(LdapModel):
    """LDAP модель для пользователя Active Directory.
    
    Использует objectClass: top, person, organizationalPerson, user.
    Только для WRITE операций (POST/PUT/DELETE).
    """
    
    # Базовая конфигурация
    base_dn = get_users_base()
    object_classes = ['top', 'person', 'organizationalPerson', 'user']
    
    # Основные атрибуты
    cn = CharField(db_column='cn', primary_key=True)
    distinguished_name = CharField(db_column='distinguishedName')
    
    # Идентификация
    object_guid = CharField(db_column='objectGUID')
    sam_account_name = CharField(db_column='sAMAccountName')
    user_principal_name = CharField(db_column='userPrincipalName')
    
    # Персональные данные
    given_name = CharField(db_column='givenName')
    sn = CharField(db_column='sn')  # surname (фамилия)
    display_name = CharField(db_column='displayName')
    mail = CharField(db_column='mail')
    
    # Контакты
    telephone_number = CharField(db_column='telephoneNumber', blank=True)
    mobile = CharField(db_column='mobile', blank=True)
    
    # Управление учетной записью
    user_account_control = IntegerField(db_column='userAccountControl')
    
    # Дополнительная информация
    description = CharField(db_column='description', blank=True)
    thumbnail_photo = ImageField(db_column='thumbnailPhoto', blank=True)
    
    # ID сотрудника (для связи с Django Employee.pk)
    employee_number = CharField(db_column='employeeNumber', blank=True)
    
    # Членство в группах
    member_of = ListField(db_column='memberOf', blank=True)
    
    # Временные метки
    when_created = DateTimeField(db_column='whenCreated')
    when_changed = DateTimeField(db_column='whenChanged')
    
    class Meta:
        managed = False  # Django не управляет схемой LDAP
    
    def __str__(self):
        return f"{self.display_name} ({self.sam_account_name})"
    
    def __repr__(self):
        return f"<LdapUser: {self.sam_account_name}>"


class LdapGroup(LdapModel):
    """LDAP модель для группы Active Directory.
    
    Использует objectClass: top, group.
    Только для WRITE операций (POST/PUT/DELETE).
    """
    
    # Базовая конфигурация
    base_dn = get_base_dn()
    object_classes = ['top', 'group']
    
    # Основные атрибуты
    cn = CharField(db_column='cn', primary_key=True)
    distinguished_name = CharField(db_column='distinguishedName')
    
    # Идентификация
    object_guid = CharField(db_column='objectGUID')
    sam_account_name = CharField(db_column='sAMAccountName')
    
    # Описание
    description = CharField(db_column='description', blank=True)
    
    # Члены группы
    member = ListField(db_column='member', blank=True)
    member_of = ListField(db_column='memberOf', blank=True)
    
    # Временные метки
    when_created = DateTimeField(db_column='whenCreated')
    when_changed = DateTimeField(db_column='whenChanged')
    
    class Meta:
        managed = False
    
    def __str__(self):
        return f"Group: {self.cn}"
    
    def __repr__(self):
        return f"<LdapGroup: {self.cn}>"


class LdapOrganizationalUnit(LdapModel):
    """LDAP модель для Organizational Unit (отдел).
    
    Использует objectClass: top, organizationalUnit.
    Только для WRITE операций (POST/PUT/DELETE).
    """
    
    # Базовая конфигурация
    base_dn = get_base_dn()
    object_classes = ['top', 'organizationalUnit']
    
    # Основные атрибуты
    ou = CharField(db_column='ou', primary_key=True)
    distinguished_name = CharField(db_column='distinguishedName')
    
    # Идентификация
    object_guid = CharField(db_column='objectGUID')
    
    # Описание
    description = CharField(db_column='description', blank=True)
    
    # Управление (managedBy - DN руководителя)
    managed_by = CharField(db_column='managedBy', blank=True)
    
    # Временные метки
    when_created = DateTimeField(db_column='whenCreated')
    when_changed = DateTimeField(db_column='whenChanged')
    
    class Meta:
        managed = False
    
    def __str__(self):
        return f"OU: {self.ou}"
    
    def __repr__(self):
        return f"<LdapOrganizationalUnit: {self.ou}>"


__all__ = [
    'LdapUser',
    'LdapGroup',
    'LdapOrganizationalUnit',
]
