"""LDAP ORM модели для работы с Active Directory через django-ldapdb.

Эти модели используются ТОЛЬКО для записи (POST/PUT/DELETE) в LDAP.
Для чтения (GET) используются обычные Django модели (Employee, Department).

Преимущества ORM подхода:
- Замена низкоуровневых ldap3 операций на Django ORM
- Автоматическая валидация и типизация
- Унифицированный API для CRUD операций
- Меньше кода, больше удобства

ВАЖНО: Миксины расширяют django-ldapdb
=======================================

django-ldapdb (версия 1.5.1) изначально НЕ поддерживает некоторые операции,
но мы добавили их через кастомные миксины:

✅ ModifyDN (rename/move) — перемещение объектов между OU
   - РЕШЕНО: ModifyDnMixin выполняет modify_dn
     при изменении base_dn
   - Использование: user.base_dn = new_dn; user.save()
   - См. employees.ldap.mixins.ModifyDnMixin

✅ Автоматическое управление LdapSyncState
   - РЕШЕНО: LdapSyncStateMixin автоматически
     создает/обновляет/удаляет sync state
   - Работает на save() и delete()
   - См. employees.ldap.mixins.LdapSyncStateMixin

Что требует низкоуровневого ldap3:

1. Создание объектов с динамическим DN
   - Создание пользователей: ldap3.Connection.add() с явным DN
   - DN формируется на основе department_dn или LDAP_USERS_BASE
   - См. services.user_service.UserService._create_user_in_ldap()

2. Транзакционное создание с перебором CN (collision handling)
   - При создании пользователя перебираются варианты CN до успеха
   - См. services.user_service.UserService._try_add_with_cn_list()

Что МОЖНО делать через ORM с миксинами:
- CREATE: через сервисы (UserService.create_user)
- READ: поиск объектов (.objects.get(dn=...))
- UPDATE: изменение атрибутов (.save())
- MOVE: изменение base_dn + save() — автоматический modify_dn! 🎉
- DELETE: .delete() — автоматическое удаление sync state
- BATCH UPDATE: массовое обновление атрибутов (.save() в цикле)

Архитектура использования (с миксинами):
========================================

CREATE пользователя:
  from employees.ldap.services import UserService
  service = UserService()
  employee = service.create_user(employee)  # создание + LdapSyncState

UPDATE пользователя:
  ldap_user = LdapUser.objects.get(dn=dn)
  ldap_user.display_name = "New Name"
  ldap_user.save()  # автообновление LdapSyncState через миксин

MOVE пользователя (перевод в отдел) — НОВОЕ С МИКСИНОМ:
  ldap_user = LdapUser.objects.get(dn=old_dn)
  ldap_user.base_dn = "OU=NewDept,OU=Departments,DC=..."
  ldap_user.save()  # ModifyDnMixin автоматически выполнит modify_dn!

DELETE пользователя:
  ldap_user = LdapUser.objects.get(dn=dn)
  ldap_user.delete()  # автоудаление LdapSyncState через миксин

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
  - Группы OU (внутри OU):
    CN=DEP_IT,OU=IT,OU=Departments,OU=company,DC=robotail,DC=local
  - Роли отделов:
    CN=ROLE_Manager,OU=IT,OU=Departments,OU=company,DC=robotail,DC=local

Организационные единицы:
  - Отделы:
    OU=IT,OU=Departments,OU=company,DC=robotail,DC=local
  - Вспомогательные контейнеры:
    OU=Roles,OU=IT,OU=Departments,OU=company,DC=robotail,DC=local

base_dn моделей:
================

base_dn используется ТОЛЬКО для SUBTREE поиска
через .objects.filter()
и НЕ определяет местоположение создаваемых/перемещаемых объектов.

- LdapUser.base_dn = "OU=company,DC=..." — покрывает все отделы и Dismissed
- LdapGroup.base_dn = "OU=Groups,..." — покрывает только глобальные группы
- LdapOrganizationalUnit.base_dn = "OU=Departments,..." — покрывает OU отделов
"""

import datetime as _dt

from django.conf import settings
from django.utils import timezone as _dj_tz


class _UtcCompat(_dt.tzinfo):
    """pytz-compatible UTC wrapper for django-ldapdb.

    django-ldapdb still expects timezone.utc to provide pytz-like
    `localize()` and `normalize()` methods. Some Django/Python combinations
    expose `timezone.utc`, but without these methods. In that case ORM
    save/update paths for LDAP models crash deep inside field preparation.
    """

    def localize(self, dt):
        """pytz-style localize method."""
        return dt.replace(tzinfo=_dt.timezone.utc)

    def normalize(self, dt):
        """pytz-style normalize method - same as localize for UTC."""
        return dt.replace(tzinfo=_dt.timezone.utc)

    def utcoffset(self, dt):
        return _dt.timedelta(0)

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return _dt.timedelta(0)

    def __repr__(self):
        return "UTC"


# Compatibility: django-ldapdb 1.5.1 expects timezone.utc with pytz methods.
if not hasattr(_dj_tz, "utc") or not all(
    hasattr(_dj_tz.utc, attr) for attr in ("localize", "normalize")
):
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
    return getattr(
        settings,
        "LDAP_USER_BASE",
        getattr(settings, "LDAP_USERS_BASE", "OU=company,DC=robotail,DC=local"),
    )


def get_base_dn():
    """Получает корневой base DN из settings.

    Используется для операций, которым нужен охват всего домена.

    Приоритет:
    1. LDAP_BASE_DN (если задан)
    2. Fallback: LDAP_USERS_BASE или DC=robotail,DC=local
    """
    return getattr(
        settings,
        "LDAP_BASE_DN",
        getattr(settings, "LDAP_USERS_BASE", "DC=robotail,DC=local"),
    )


def get_groups_base():
    """Получает base DN для глобальных групп из settings.

    Глобальные группы располагаются в:
      CN=<GroupName>,OU=Groups,OU=company,DC=robotail,DC=local

    Приоритет:
    1. LDAP_GROUPS_BASE (если задан)
    2. Fallback: OU=Groups,DC=robotail,DC=local
    """
    return getattr(
        settings,
        "LDAP_GROUPS_BASE",
        "OU=Groups,DC=robotail,DC=local",
    )


def get_departments_base():
    """Получает base DN для отделов (OU) из settings.

    Отделы располагаются в фиксированном контейнере:
      OU=<DeptName>,OU=Departments,OU=company,DC=robotail,DC=local

    Приоритет:
    1. LDAP_DEPARTMENTS_BASE (если задан)
    2. Fallback: OU=Departments,DC=robotail,DC=local
    """
    return getattr(
        settings,
        "LDAP_DEPARTMENTS_BASE",
        "OU=Departments,DC=robotail,DC=local",
    )


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
    _sync_model_name = "employee"
    _sync_pk_field = "employee_number"

    # Базовая конфигурация
    # base_dn покрывает все местоположения
    # пользователей для SUBTREE search
    base_dn = get_users_base()
    object_classes = ["top", "person", "organizationalPerson", "user"]

    # RDN атрибут для построения Distinguished Name
    # Пример: cn=Ivan Ivanov → dn=CN=Ivan Ivanov,OU=...,DC=...
    rdn_attributes = ["cn"]

    # Основные атрибуты
    # dn: ldapdb.models.Model primary_key (DN)
    cn = CharField(db_column="cn")

    # Идентификация
    sam_account_name = CharField(db_column="sAMAccountName")
    user_principal_name = CharField(db_column="userPrincipalName")

    # Персональные данные
    given_name = CharField(db_column="givenName")
    sn = CharField(db_column="sn")  # surname (фамилия)
    display_name = CharField(db_column="displayName")
    mail = CharField(db_column="mail")

    # Контакты
    telephone_number = CharField(db_column="telephoneNumber", blank=True)
    mobile = CharField(db_column="mobile", blank=True)

    # Управление учетной записью
    user_account_control = IntegerField(db_column="userAccountControl")

    # Пароль (write-only атрибут AD)
    # ВАЖНО: unicodePwd - специальный атрибут Active Directory
    # - Write-only: можно записать, но нельзя прочитать
    # - Требует SSL/TLS соединения
    # - Требует специальной кодировки: UTF-16-LE с кавычками
    # - Используйте метод set_password() вместо прямой записи
    unicode_pwd = CharField(db_column="unicodePwd", blank=True)

    # Дополнительная информация
    description = CharField(db_column="description", blank=True)
    thumbnail_photo = ImageField(db_column="thumbnailPhoto", blank=True)

    # ID сотрудника (для связи с Django Employee.pk)
    employee_number = CharField(db_column="employeeNumber", blank=True)

    # Членство в группах
    member_of = ListField(db_column="memberOf", blank=True)

    # Временные метки
    when_created = DateTimeField(db_column="whenCreated")
    when_changed = DateTimeField(db_column="whenChanged")

    class Meta:
        managed = False  # Django не управляет схемой LDAP

    def __str__(self):
        return f"{self.display_name} ({self.sam_account_name})"

    def __repr__(self):
        return f"<LdapUser: {self.sam_account_name}>"

    def set_password(self, new_password: str) -> None:
        """Устанавливает новый пароль для пользователя.

        Через AD extended operation.

        Использует Microsoft-специфичное расширение modify_password
        для корректной работы с политиками паролей AD.
        Это более надежный способ, чем прямая
        запись в unicodePwd.

        Args:
            new_password: Новый пароль (plaintext)

        Raises:
            ValueError: Если пароль пустой или не соответствует политике
            DirectoryLdapError: Если операция не удалась

        Example:
            >>> ldap_user = LdapUser.objects.get(dn='CN=...')
            >>> ldap_user.set_password('NewSecurePass123!')
            >>> # Пароль изменён в AD, НЕ требуется .save()
        """
        from .infrastructure.connections import _ldap
        from .services.user_password_service import UserPasswordService

        service = UserPasswordService()
        with _ldap() as conn:
            service.set_password(conn, self.dn, new_password)

    def change_password(self, old_password: str, new_password: str) -> None:
        """Меняет пароль пользователя (требует знания старого пароля).

        Используется для самостоятельной смены пароля пользователем.

        Args:
            old_password: Текущий пароль
            new_password: Новый пароль

        Raises:
            ValueError: Если новый пароль не соответствует политике
            DirectoryLdapError: Если старый пароль неверен
                или операция не удалась

        Example:
            >>> ldap_user = LdapUser.objects.get(dn='CN=...')
            >>> ldap_user.change_password('OldPass123', 'NewSecurePass123!')
            >>> # Пароль изменён в AD, НЕ требуется .save()
        """
        from .infrastructure.connections import _ldap
        from .services.user_password_service import UserPasswordService

        service = UserPasswordService()
        with _ldap() as conn:
            service.change_password(conn, self.dn, old_password, new_password)


class LdapGroup(ModifyDnMixin, LdapModel):
    """LDAP модель для глобальных групп Active Directory.

    Использует objectClass: top, group.
    Только для WRITE операций (POST/PUT/DELETE).

    Миксины:
    - ModifyDnMixin: поддержка перемещения между OU через base_dn изменение

    ВАЖНО О base_dn:
    - base_dn = LDAP_GROUPS_BASE — сканирует ТОЛЬКО OU=Groups
    - Для групп отделов (DEP_*): используйте LdapOrganizationalUnitGroup
    - Для должностей (POS_*): используйте PositionService
    - При изменении base_dn ModifyDnMixin автоматически выполнит modify_dn!

    Операции через django-ldapdb:
    - CREATE: создание через GroupService.create() (ORM)
    - UPDATE: изменение атрибутов через .save()
        - MOVE: group.base_dn = new_dn; group.save()
            (автоматический modify_dn!)
    - RENAME: переименование через GroupService.rename() (low-level ldap3)
    - DELETE: удаление через .delete() (ORM)

    Расположение групп по типам:
        - Глобальные:  CN=<Name>,OU=Groups,...
            ← эта модель
        - Отделы:      CN=DEP_*,OU=<Dept>,OU=Departments
            ← LdapOrganizationalUnitGroup
        - Должности:   CN=POS_*,OU=Positions,...
            ← PositionService
        - Роли:        CN=ROLE_*,OU=<Dept>,OU=Departments
            ← через GroupService
    """

    # Базовая конфигурация: только OU=Groups
    base_dn = get_groups_base()
    object_classes = ["top", "group"]

    # RDN атрибут для построения Distinguished Name
    # Пример: cn=Developers → dn=CN=Developers,OU=Groups,DC=...
    rdn_attributes = ["cn"]

    # Основные атрибуты
    # dn: ldapdb.models.Model primary_key (DN)
    cn = CharField(db_column="cn")

    # Идентификация
    # objectGUID исключен (проблемы с бинарными данными)
    sam_account_name = CharField(db_column="sAMAccountName")

    # Описание
    description = CharField(db_column="description", blank=True)

    # Члены группы
    member = ListField(db_column="member", blank=True)
    member_of = ListField(db_column="memberOf", blank=True)

    # Временные метки
    when_created = DateTimeField(db_column="whenCreated")
    when_changed = DateTimeField(db_column="whenChanged")

    class Meta:
        managed = False

    def __str__(self):
        return f"Group: {self.cn}"

    def __repr__(self):
        return f"<LdapGroup: {self.cn}>"

    # ==================== Membership Methods ==================== #

    def list_members(self) -> list[str]:
        """Возвращает список DN участников группы."""
        return list(self.member or [])

    def add_member(self, member_dn: str) -> None:
        """Добавляет участника в глобальную группу."""
        current = self.member or []
        if member_dn in current:
            return

        from ldap3 import MODIFY_ADD

        from .infrastructure.connections import _ldap

        with _ldap() as conn:
            ok = conn.modify(self.dn, {"member": [(MODIFY_ADD, [member_dn])]})
            if not ok:
                result_str = str(conn.result)
                if "attributeOrValueExists" not in result_str:
                    raise RuntimeError(f"add_member failed: {conn.result}")

    def remove_member(self, member_dn: str) -> None:
        """Удаляет участника из глобальной группы."""
        from ldap3 import MODIFY_DELETE

        from .infrastructure.connections import _ldap

        with _ldap() as conn:
            ok = conn.modify(
                self.dn, {"member": [(MODIFY_DELETE, [member_dn])]}
            )
            if not ok:
                result_str = str(conn.result)
                if "noSuchAttribute" not in result_str:
                    raise RuntimeError(f"remove_member failed: {conn.result}")

    def sync_members(self, desired_dns: list[str]) -> dict:
        """Синхронизирует состав группы к точному списку."""
        current = set(self.member or [])
        desired = set(desired_dns)

        to_add = desired - current
        to_remove = current - desired

        from ldap3 import MODIFY_ADD, MODIFY_DELETE

        from .infrastructure.connections import _ldap

        with _ldap() as conn:
            if to_remove:
                conn.modify(
                    self.dn, {"member": [(MODIFY_DELETE, list(to_remove))]}
                )
            if to_add:
                conn.modify(self.dn, {"member": [(MODIFY_ADD, list(to_add))]})

        return {
            "added": len(to_add),
            "removed": len(to_remove),
        }


class LdapOrganizationalUnitGroup(ModifyDnMixin, LdapModel):
    """LDAP модель группы организационной единицы (DEP_*).

    Каждая OU в LDAP имеет агрегаторную группу,
    содержащую всех активных сотрудников этой OU:
      CN=DEP_IT,OU=IT,OU=Departments,OU=company,DC=robotail,DC=local

    Миксины:
    - ModifyDnMixin: перемещение при переименовании OU

    ВАЖНО О base_dn:
    - base_dn = LDAP_DEPARTMENTS_BASE — SUBTREE поиск найдёт
      все DEP_* группы внутри всех OU
    - objectClass фильтрация: ищет только group (не OU)

    Операции:
    - READ: .objects.filter(cn__startswith='DEP_')
    - UPDATE: изменение description/member через .save()
    - MOVE: group.base_dn = new_ou_dn; group.save()
    - DELETE: .delete()
    - CREATE: ensure() на LdapOrganizationalUnit (low-level ldap3)

    Управление членством:
    - add_member(user_dn) → добавить пользователя
    - remove_member(user_dn) → удалить пользователя
    - sync_members(user_dns) → привести к точному списку
    - list_members() → текущий список DN участников
    """

    # Базовая конфигурация: ищем группы внутри OU отделов
    base_dn = get_departments_base()
    object_classes = ["top", "group"]

    rdn_attributes = ["cn"]

    # Основные атрибуты
    cn = CharField(db_column="cn")
    sam_account_name = CharField(db_column="sAMAccountName")
    description = CharField(db_column="description", blank=True)

    # Члены группы
    member = ListField(db_column="member", blank=True)
    member_of = ListField(db_column="memberOf", blank=True)

    # Временные метки
    when_created = DateTimeField(db_column="whenCreated")
    when_changed = DateTimeField(db_column="whenChanged")

    class Meta:
        managed = False

    def __str__(self):
        return f"OUGroup: {self.cn}"

    def __repr__(self):
        return f"<LdapOrganizationalUnitGroup: {self.cn}>"

    # ==================== Membership Methods ==================== #

    def list_members(self) -> list[str]:
        """Возвращает список DN участников группы."""
        return list(self.member or [])

    def add_member(self, member_dn: str) -> None:
        """Добавляет участника в группу отдела.

        Args:
            member_dn: DN пользователя.

        Raises:
            RuntimeError: Если операция не удалась.
        """
        current = self.member or []
        if member_dn in current:
            return

        from .infrastructure.connections import _ldap
        from ldap3 import MODIFY_ADD

        with _ldap() as conn:
            ok = conn.modify(self.dn, {"member": [(MODIFY_ADD, [member_dn])]})
            if not ok:
                result_str = str(conn.result)
                if "attributeOrValueExists" not in result_str:
                    raise RuntimeError(f"add_member failed: {conn.result}")

    def remove_member(self, member_dn: str) -> None:
        """Удаляет участника из группы отдела.

        Args:
            member_dn: DN пользователя.

        Raises:
            RuntimeError: Если операция не удалась.
        """
        from .infrastructure.connections import _ldap
        from ldap3 import MODIFY_DELETE

        with _ldap() as conn:
            ok = conn.modify(
                self.dn, {"member": [(MODIFY_DELETE, [member_dn])]}
            )
            if not ok:
                result_str = str(conn.result)
                if "noSuchAttribute" not in result_str:
                    raise RuntimeError(f"remove_member failed: {conn.result}")

    def sync_members(self, desired_dns: list[str]) -> dict:
        """Синхронизирует состав группы к точному списку.

        Добавляет недостающих, удаляет лишних.

        Args:
            desired_dns: Целевой список DN участников.

        Returns:
            dict: {'added': int, 'removed': int}
        """
        current = set(self.member or [])
        desired = set(desired_dns)

        to_add = desired - current
        to_remove = current - desired

        from .infrastructure.connections import _ldap
        from ldap3 import MODIFY_ADD, MODIFY_DELETE

        with _ldap() as conn:
            if to_remove:
                conn.modify(
                    self.dn, {"member": [(MODIFY_DELETE, list(to_remove))]}
                )
            if to_add:
                conn.modify(self.dn, {"member": [(MODIFY_ADD, list(to_add))]})

        return {
            "added": len(to_add),
            "removed": len(to_remove),
        }


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

    Структура отдела в LDAP:
    OU=<DeptName>,OU=Departments,...  ← LdapOrganizationalUnit
      ├─ CN=DEP_<DeptName>            ← LdapOrganizationalUnitGroup (все члены)
      ├─ CN=ROLE_Manager              ← LdapGroup (роль)
      └─ CN=User1, CN=User2, ...      ← LdapUser (пользователи)

    Методы работы с группой OU (DEP_*):
    - get_department_group_dn() → DN группы OU
    - get_department_group() → LdapOrganizationalUnitGroup или None
    - ensure_department_group() →
      создаёт/возвращает LdapOrganizationalUnitGroup
    """

    # Базовая конфигурация
    base_dn = get_departments_base()
    object_classes = ["top", "organizationalUnit"]

    # RDN атрибут для построения Distinguished Name
    # Пример: ou=IT → dn=OU=IT,OU=Departments,DC=...
    rdn_attributes = ["ou"]

    # Основные атрибуты
    # dn: ldapdb.models.Model primary_key (DN)
    ou = CharField(db_column="ou")

    # Идентификация
    # objectGUID исключен из-за проблем с декодированием бинарных данных

    # Описание
    description = CharField(db_column="description", blank=True)

    # Управление (managedBy - DN руководителя)
    managed_by = CharField(db_column="managedBy", blank=True)

    # Временные метки
    when_created = DateTimeField(db_column="whenCreated")
    when_changed = DateTimeField(db_column="whenChanged")

    class Meta:
        managed = False

    def __str__(self):
        return f"OU: {self.ou}"

    def __repr__(self):
        return f"<LdapOrganizationalUnit: {self.ou}>"

    # ==================== Department Group Methods ==================== #

    def get_department_group_dn(self) -> str:
        """Возвращает ожидаемый DN группы отдела DEP_*.

        Группа отдела находится внутри OU отдела:
        CN=DEP_<DeptName>,OU=<DeptName>,OU=Departments,...

        Returns:
            str: DN группы отдела.
        """
        return f"CN=DEP_{self.ou},{self.dn}"

    def get_department_group(self):
        """Возвращает группу OU (DEP_*), если существует.

        Returns:
            LdapOrganizationalUnitGroup | None
        """
        try:
            return LdapOrganizationalUnitGroup.objects.get(
                dn=self.get_department_group_dn()
            )
        except LdapOrganizationalUnitGroup.DoesNotExist:
            return None

    def ensure_department_group(self):
        """Создаёт или возвращает группу OU (DEP_*).

        Если группа существует — возвращает её.
        Если нет — создаёт через low-level ldap3.

        Returns:
            LdapOrganizationalUnitGroup: Группа OU.

        Raises:
            RuntimeError: Если создание группы не удалось.
        """
        group = self.get_department_group()
        if group:
            return group

        from .infrastructure.connections import _ldap
        from .utils.ldap_utils import group_type
        from .utils.text_utils import esc_rdn

        cn = f"DEP_{self.ou}"
        group_dn = f"CN={esc_rdn(cn)},{self.dn}"

        with _ldap() as conn:
            attrs = {
                "sAMAccountName": cn[:20],
                "description": f"{self.ou} department members",
                "groupType": group_type("global", security_enabled=True),
            }
            ok = conn.add(group_dn, ["top", "group"], attrs)
            if not ok:
                res = str(conn.result)
                if "entryAlreadyExists" not in res:
                    raise RuntimeError(
                        f"Failed to create dept group: {conn.result}"
                    )

        return LdapOrganizationalUnitGroup.objects.get(dn=group_dn)


__all__ = [
    "LdapUser",
    "LdapGroup",
    "LdapOrganizationalUnitGroup",
    "LdapOrganizationalUnit",
]
