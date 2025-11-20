"""Domain Data Transfer Objects для LDAP-сервисов.

Этот модуль содержит DTOs, используемые для передачи данных
между различными слоями приложения при работе с LDAP каталогом.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from django.conf import settings

from ...models import Employee
from ..utils.ldap_utils import _ldap_pick_phone, _uac_is_active, get_attr_str, get_guid_str
from employees.utils import _normalize_phone


@dataclass(frozen=True)
class DirectoryUserDTO:
    """DTO для создания/обновления пользователя через DirectoryService.

    Attributes:
        first_name (str): Имя пользователя.
        last_name (str): Фамилия пользователя.
        email (str): Email адрес пользователя.
        phone_e164 (Optional[str]): Телефон в формате E.164 или None.
        department_dn (Optional[str]): DN целевого отдела (OU в LDAP).
        group_cns (List[str]): Список CN групп для членства пользователя.
        initial_password (str): Начальный пароль (используется только в LDAP).
        avatar_bytes (Optional[bytes]): Байты изображения аватара.
        is_active (bool): Флаг активности (влияет на userAccountControl в AD).
    """

    first_name: str
    last_name: str
    email: str
    phone_e164: Optional[str]
    department_dn: Optional[str]
    group_cns: List[str]
    initial_password: str
    avatar_bytes: Optional[bytes] = None
    is_active: bool = True


@dataclass(frozen=True)
class DirectoryDepartmentDTO:
    """DTO для создания/обновления отдела (Organizational Unit).

    Attributes:
        name (str): Название отдела.
        description (Optional[str]): Описание отдела.
        head (Optional[Employee]): Руководитель отдела (объект Employee).
    """

    name: str
    description: Optional[str] = None
    head: Optional[Employee] = None


@dataclass(frozen=True)
class LdapPersonDTO:
    """Нормализованные данные пользователя из LDAP для импорта в Django.

    Используется при синхронизации LDAP → Django для представления
    пользователя, прочитанного из Active Directory.

    Attributes:
        dn (str): DN объекта пользователя.
        guid (Optional[str]): Строковое представление GUID пользователя.
        username (str): sAMAccountName (может быть пустым).
        email (str): E-mail (в нижнем регистре; может быть сгенерирован как fallback).
        given (str): Имя (м.б. получено из display/email).
        sn (str): Фамилия (м.б. пустой).
        display (str): displayName из LDAP.
        when_changed (Optional[str]): whenChanged из LDAP (как строка; храним как есть).
        is_active (bool): Флаг активности по userAccountControl.
        phone_e164 (Optional[str]): Нормализованный телефон в E.164, если удалось.
    """

    dn: str
    guid: Optional[str]
    username: str
    email: str
    given: str
    sn: str
    display: str
    when_changed: Optional[str]
    is_active: bool
    phone_e164: Optional[str]


def _entry_to_dto(entry) -> LdapPersonDTO:
    """Преобразует LDAP-объект в DTO с нормализацией e-mail, ФИО и телефона.

    Args:
        entry: Объект из ldap3 (результат поиска).

    Returns:
        LdapPersonDTO: Нормализованные поля для upsert в Django.
    """
    a = getattr(entry, "entry_attributes_as_dict", {}) or {}
    dn: str = str(getattr(entry, "entry_dn", "")) or get_attr_str(
        a, "distinguishedName"
    )
    guid = get_guid_str(a)
    username = get_attr_str(a, "sAMAccountName")
    email = (get_attr_str(a, "mail") or "").lower()
    given = get_attr_str(a, "givenName")
    sn = get_attr_str(a, "sn")
    display = get_attr_str(a, "displayName")
    when_changed = get_attr_str(a, "whenChanged")
    is_active = _uac_is_active(a.get("userAccountControl"))

    # Email fallback
    if not email and username:
        domain = getattr(settings, "DEFAULT_EMAIL_DOMAIN", "robotail.local")
        email = f"{username}@{domain}".lower()

    # Имя/фамилия fallbacks
    if not (given or sn):
        if display:
            parts = display.split(" ", 1)
            given = parts[0]
            sn = parts[1] if len(parts) > 1 else ""
        else:
            local = (email or "user").split("@", 1)[0]
            given = local
            sn = ""

    # Телефон
    phone_raw = _ldap_pick_phone(a)
    phone_e164 = _normalize_phone(phone_raw)

    return LdapPersonDTO(
        dn=dn,
        guid=str(guid) if guid else None,
        username=username,
        email=email,
        given=given,
        sn=sn,
        display=display,
        when_changed=when_changed or None,
        is_active=is_active,
        phone_e164=phone_e164,
    )


__all__ = [
    "DirectoryUserDTO",
    "DirectoryDepartmentDTO",
    "LdapPersonDTO",
    "_entry_to_dto",
]
