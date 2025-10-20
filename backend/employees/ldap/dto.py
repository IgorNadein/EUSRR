from dataclasses import dataclass
from typing import Optional

from django.conf import settings

from ..utils import _normalize_phone
from .utils import _ldap_pick_phone, _uac_is_active, get_attr_str, get_guid_str


@dataclass(frozen=True)
class LdapPersonDTO:
    """Нормализованные данные пользователя из LDAP для upsert в Django.

    Attributes:
        dn (str): DN объекта пользователя.
        guid (str | None): Строковое представление GUID пользователя.
        username (str): sAMAccountName (может быть пустым).
        email (str): E-mail (в нижнем регистре; может быть сгенерирован как fallback).
        given (str): Имя (м.б. получено из display/email).
        sn (str): Фамилия (м.б. пустой).
        display (str): displayName из LDAP.
        when_changed (str): whenChanged из LDAP (как строка; храним как есть).
        is_active (bool): Флаг активности по userAccountControl.
        phone_e164 (str | None): Нормализованный телефон в E.164, если удалось.
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
        entry: Объект из ldap3.

    Returns:
        LdapPersonDTO: Нормализованные поля для upsert.
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
        email = f"{username}@{getattr(settings, 'DEFAULT_EMAIL_DOMAIN', 'robotail.local')}".lower()

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
