"""Domain Data Transfer Objects для LDAP-сервисов.

Этот модуль содержит DTOs, используемые для передачи данных
между различными слоями приложения при работе с LDAP каталогом.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from django.conf import settings

from ...models import Employee
from ..utils.ldap_utils import _ldap_pick_phone, _uac_is_active, get_attr_str, get_guid_str
from ..utils.phone_utils import normalize_phone


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


def _extract_ldap_attrs(entry) -> Dict[str, Optional[str]]:
    """Извлекает сырые атрибуты из LDAP entry.

    Args:
        entry: Объект из ldap3 (результат поиска).

    Returns:
        Словарь с извлечёнными атрибутами.
    """
    a = getattr(entry, "entry_attributes_as_dict", {}) or {}
    dn: str = str(getattr(entry, "entry_dn", "")) or get_attr_str(
        a, "distinguishedName"
    )
    return {
        "dn": dn,
        "guid": get_guid_str(a),
        "username": get_attr_str(a, "sAMAccountName"),
        "email": (get_attr_str(a, "mail") or "").lower(),
        "given": get_attr_str(a, "givenName"),
        "sn": get_attr_str(a, "sn"),
        "display": get_attr_str(a, "displayName"),
        "when_changed": get_attr_str(a, "whenChanged"),
        "is_active": _uac_is_active(a.get("userAccountControl")),
        "phone_raw": _ldap_pick_phone(a),
    }


def _resolve_email(email: str, username: str) -> str:
    """Нормализует email с fallback на username@domain.

    Args:
        email: Email из LDAP (может быть пустым).
        username: sAMAccountName для генерации fallback.

    Returns:
        Email в нижнем регистре.
    """
    if email:
        return email
    if username:
        domain = getattr(settings, "DEFAULT_EMAIL_DOMAIN", "robotail.local")
        return f"{username}@{domain}".lower()
    return ""


def _resolve_name(
    given: str, sn: str, display: str, email: str
) -> Tuple[str, str]:
    """Нормализует имя/фамилию с fallback на displayName или email.

    Args:
        given: Имя из LDAP.
        sn: Фамилия из LDAP.
        display: displayName из LDAP.
        email: Email (для последнего fallback).

    Returns:
        Кортеж (given, sn).
    """
    if given or sn:
        return given, sn
    if display:
        parts = display.split(" ", 1)
        return parts[0], parts[1] if len(parts) > 1 else ""
    local = (email or "user").split("@", 1)[0]
    return local, ""


def _entry_to_dto(entry) -> LdapPersonDTO:
    """Преобразует LDAP-объект в DTO с нормализацией e-mail, ФИО и телефона.

    Args:
        entry: Объект из ldap3 (результат поиска).

    Returns:
        LdapPersonDTO: Нормализованные поля для upsert в Django.
    """
    raw = _extract_ldap_attrs(entry)

    email = _resolve_email(raw["email"], raw["username"])
    given, sn = _resolve_name(raw["given"], raw["sn"], raw["display"], email)
    phone_e164 = normalize_phone(raw["phone_raw"])

    return LdapPersonDTO(
        dn=raw["dn"],
        guid=str(raw["guid"]) if raw["guid"] else None,
        username=raw["username"],
        email=email,
        given=given,
        sn=sn,
        display=raw["display"],
        when_changed=raw["when_changed"] or None,
        is_active=raw["is_active"],
        phone_e164=phone_e164,
    )


__all__ = [
    "DirectoryUserDTO",
    "DirectoryDepartmentDTO",
    "LdapPersonDTO",
    "_entry_to_dto",
]
