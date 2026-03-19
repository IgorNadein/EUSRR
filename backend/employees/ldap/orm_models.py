"""LDAP ORM модели для работы с Active Directory через django-ldapdb.

Эти модели используются ТОЛЬКО для записи (POST/PUT/DELETE) в LDAP.
Для чтения (GET) используются обычные Django модели (Employee, Department).

Преимущества ORM подхода:
- Замена низкоуровневых ldap3 операций на Django ORM
- Автоматическая валидация и типизация
- Унифицированный API для CRUD операций
- Меньше кода, больше удобства

ВАЖНО: Ограничения django-ldapdb
==================================

django-ldapdb (версия 1.5.1) НЕ поддерживает следующие операции LDAP:

1. ModifyDN (rename/move) — перемещение объектов между OU
   - Для перемещения пользователей используется ldap3.Connection.modify_dn()
   - См. utils.dn_utils._move_to_department()
   - При переводе в отдел, увольнении — низкоуровневый ldap3

2. Создание объектов с динамическим DN
   - Создание пользователей: ldap3.Connection.add() с явным DN
   - DN формируется на основе department_dn или LDAP_USERS_BASE
   - См. services.user_service.UserService._create_user_in_ldap()

3. Транзакционное создание с перебором CN (collision handling)
   - При создании пользователя перебираются варианты CN до успеха
   - См. services.user_service.UserService._try_add_with_cn_list()

Что МОЖНО делать через ORM:
- UPDATE: изменение атрибутов существующих объектов (.save())
- READ: поиск объектов для последующего обновления (.objects.get(dn=...))
- BATCH UPDATE: массовое обновление атрибутов (.save() в цикле)

Архитектура использования:
==========================

CREATE пользователя:
  1. ldap3.Connection.add(dn, object_classes, attrs)  # низкоуровневое создание
  2. LdapUser.objects.get(dn=new_dn)                  # загрузка для проверки
  
UPDATE пользователя:
  1. ldap_user = LdapUser.objects.get(dn=dn)          # загрузка через ORM
  2. ldap_user.display_name = "New Name"              # изменение атрибутов
  3. ldap_user.save()                                 # сохранение через ORM

MOVE пользователя (перевод в отдел):
  1. new_dn = conn.modify_dn(dn, new_superior=dept_dn)  # низкоуровневое перемещение
  2. ldap_user = LdapUser.objects.get(dn=new_dn)        # загрузка по новому DN
  3. ldap_user.save()                                   # обновление атрибутов

DELETE пользователя:
  1. conn.delete(dn)                                    # низкоуровневое удаление

Структура DN в Active Directory:
=================================

Пользователи (зависит от статуса):
  - Активные по отделам:
    CN=Иванов Иван,OU=IT,OU=Departments,OU=company,DC=robotail,DC=local
  - Уволенные:
    CN=Иванов Иван,OU=Dismissed,OU=company,DC=robotail,DC=local

Группы (зависит от типа):
  - Глобальные группы:
    CN=Developers,OU=Groups,OU=company,DC=robotail,DC=local
  - Роли отделов:
    CN=ROLE_Manager,OU=Roles,OU=IT,OU=Departments,OU=company,DC=robotail,DC=local

Организационные единицы:
  - Отделы:
    OU=IT,OU=Departments,OU=company,DC=robotail,DC=local
  - Вспомогательные контейнеры:
    OU=Roles,OU=IT,OU=Departments,OU=company,DC=robotail,DC=local

base_dn моделей:
================

base_dn в моделях используется ТОЛЬКО для SUBTREE поиска через .objects.filter()
и НЕ определяет местоположение создаваемых/перемещаемых объектов.

- LdapUser.base_dn = "OU=company,DC=..." — покрывает все отделы и Dismissed
- LdapGroup.base_dn = "DC=..." — покрывает Groups и роли отделов
- LdapOrganizationalUnit.base_dn = "DC=..." — покрывает все OU
"""

import datetime as _dt

from django.conf import settings
from django.utils import timezone as _dj_tz

# Compatibility: django-ldapdb 1.5.1 uses timezone.utc removed in Django 5.x
if not hasattr(_dj_tz, 'utc'):
    class _UtcCompat:
        """pytz-compatible UTC stub for django-ldapdb."""
        def localize(self, dt):
            return dt.replace(tzinfo=_dt.timezone.utc)
    _dj_tz.utc = _UtcCompat()

from ldapdb.models import Model as LdapModel
from ldapdb.models.fields import (
    CharField,
    DateTimeField,
    ImageField,
    IntegerField,
    ListField,
)

# Миксины для расширения функциональности LDAP моделей
from .mixins import ModifyDnMixin, LdapSyncStateMixin


def get_users_base():
    """Получает base DN для пользователей из settings.
    
    Возвращает корневой DN, который покрывает все возможные местоположения
    пользователей для SUBTREE search:
    - OU=Departments (активные сотрудники по отделам)
    - OU=Dismissed (уволенные)
    - Любые другие OU под OU=company
    
    Приоритет:
    1. LDAP_USER_BASE или LDAP_USERS_BASE (если задан в settings)
    2. Fallback: OU=company,DC=robotail,DC=local
    """
    return getattr(settings, 'LDAP_USER_BASE', 
                   getattr(settings, 'LDAP_USERS_BASE', 
                          'OU=company,DC=robotail,DC=local'))


def get_base_dn():
    """Получает корневой base DN из settings.
    
    Используется для групп и OU. Должен покрывать:
    - OU=Groups (глобальные группы)
    - OU=Departments (отделы и их роли)
    - Любые другие контейнеры
    
    Приоритет:
    1. LDAP_BASE_DN (если задан)
    2. Fallback: корневой DN домена (DC=robotail,DC=local)
       или LDAP_USERS_BASE если нет LDAP_BASE_DN
    """
    return getattr(settings, 'LDAP_BASE_DN',
                   getattr(settings, 'LDAP_USERS_BASE',
                          'DC=robotail,DC=local'))


class LdapUser(LdapSyncStateMixin, ModifyDnMixin, LdapModel):
    """LDAP модель для пользователя Active Directory.
    
    Использует objectClass: top, person, organizationalPerson, user.
    Только для WRITE операций (POST/PUT/DELETE).
    
    Миксины:
    - LdapSyncStateMixin: автоматически обновляет LdapSyncState при save/delete
    - ModifyDnMixin: поддержка перемещения между OU через base_dn изменение
    
    ВАЖНО О base_dn:
    - base_dn используется только для SUBTREE поиска через .objects.filter()
    - НЕ определяет местоположение создаваемых/перемещаемых объектов
    - Реально пользователи находятся в разных OU:
      • CN=User,OU=<Dept>,OU=Departments,OU=company,... (активные)
      • CN=User,OU=Dismissed,OU=company,... (уволенные)
    - При изменении base_dn ModifyDnMixin автоматически выполнит modify_dn!
    
    Операции через ORM:
    - CREATE: используйте UserService.create_user() (создание + sync state)
    - UPDATE: изменение атрибутов через .save() (автообновление sync state)
    - MOVE: user.base_dn = new_dn; user.save() (автоматический modify_dn!)
    - DELETE: .delete() (автоматическое удаление sync state)
    
    Модель используется для:
    - UPDATE: изменение атрибутов существующих объектов через .save()
    - READ: поиск через .objects.get(dn=...) для последующего обновления
    """
    
    # Конфигурация LdapSyncStateMixin
    _sync_model_name = 'employee'
    _sync_pk_field = 'employee_number'
    
    # Базовая конфигурация
    # base_dn покрывает все возможные местоположения пользователей для SUBTREE search
    base_dn = get_users_base()
    object_classes = ['top', 'person', 'organizationalPerson', 'user']
    
    # Основные атрибуты
    # dn наследуется от ldapdb.models.Model как primary_key (Distinguished Name)
    cn = CharField(db_column='cn')
    
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


class LdapGroup(ModifyDnMixin, LdapModel):
    """LDAP модель для группы Active Directory.
    
    Использует objectClass: top, group.
    Только для WRITE операций (POST/PUT/DELETE).
    
    Миксины:
    - ModifyDnMixin: поддержка перемещения между OU через base_dn изменение
    
    ВАЖНО О base_dn:
    - base_dn используется только для SUBTREE поиска через .objects.filter()
    - Группы могут находиться в разных OU:
      • CN=Group,OU=Groups,DC=... (глобальные группы)
      • CN=ROLE_*,OU=Roles,OU=<Dept>,OU=Departments,... (роли отделов)
    - При изменении base_dn ModifyDnMixin автоматически выполнит modify_dn!
    
    Операции через django-ldapdb:
    - CREATE: создание через GroupService.create() (ldap3.Connection.add)
    - UPDATE: изменение атрибутов через .save()
    - MOVE: group.base_dn = new_dn; group.save() (автоматический modify_dn!)
    - DELETE: удаление через ldap3.Connection.delete()
    
    При создании ролей отделов DN формируется как:
    CN=ROLE_{name},OU=Roles,OU={dept},OU=Departments,...
    """
    
    # Базовая конфигурация
    base_dn = get_base_dn()
    object_classes = ['top', 'group']
    
    # Основные атрибуты
    # dn наследуется от ldapdb.models.Model как primary_key (Distinguished Name)
    cn = CharField(db_column='cn')
    
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


class LdapOrganizationalUnit(ModifyDnMixin, LdapModel):
    """LDAP модель для Organizational Unit (отдел).
    
    Использует objectClass: top, organizationalUnit.
    Только для WRITE операций (POST/PUT/DELETE).
    
    Миксины:
    - ModifyDnMixin: поддержка перемещения между контейнерами через base_dn
    
    ВАЖНО О base_dn:
    - base_dn используется только для SUBTREE поиска
    - OU отделов располагаются под LDAP_DEPARTMENTS_BASE:
      OU=<DeptName>,OU=Departments,OU=company,...
    - При изменении base_dn ModifyDnMixin автоматически выполнит modify_dn!
    
    Операции через django-ldapdb:
    - CREATE: создание через .save() — работает с ORM
    - UPDATE: изменение через .save() (например, managedBy)
    - MOVE: ou.base_dn = new_dn; ou.save() (автоматический modify_dn!)
    - DELETE: удаление через ldap3.Connection.delete()
    
    При создании отдела DN формируется как:
    OU={dept_name},{LDAP_DEPARTMENTS_BASE}
    """
    
    # Базовая конфигурация
    base_dn = get_base_dn()
    object_classes = ['top', 'organizationalUnit']
    
    # RDN атрибут для построения Distinguished Name
    # Пример: ou=IT → dn=OU=IT,OU=Departments,DC=...
    rdn_attributes = ['ou']
    
    # Основные атрибуты
    # dn наследуется от ldapdb.models.Model как primary_key (Distinguished Name)
    ou = CharField(db_column='ou')
    
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
