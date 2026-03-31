"""Сервис для маппинга атрибутов между Django Employee и LDAP User.

Выделен из UserService для упрощения и следования SRP.
Отвечает за:
- Построение атрибутов для создания пользователя в LDAP
- Маппинг полей Django → LDAP
- Обработку специальных полей (изображения, телефоны)
"""

import logging
from typing import Any, Dict, List, Optional
from django.conf import settings

from .base_service import BaseService
from .constants import UserAccountControl, LdapObjectClass
from ..domain.dtos import DirectoryUserDTO
from ..orm_models import LdapUser
from ..utils.image_utils import normalize_avatar_to_jpeg


logger = logging.getLogger(__name__)


class UserMapperService(BaseService):
    """Сервис для маппинга данных между Django и LDAP."""

    def build_creation_attributes(
        self,
        dto: DirectoryUserDTO,
        sam: str,
        upn: str,
        cn: str,
    ) -> Dict[str, Any]:
        """Собирает атрибуты для создания пользователя в AD.

        Фильтрует пустые значения и форматирует данные согласно требованиям AD.

        Args:
            dto: DTO с данными пользователя
            sam: sAMAccountName
            upn: userPrincipalName
            cn: Common Name (CN)

        Returns:
            Словарь атрибутов для ldap3.Connection.add()

        Raises:
            TypeError: Если параметры неверного типа
        """
        if not all(isinstance(x, str) for x in (sam, upn, cn)):
            raise TypeError("sam, upn и cn должны быть строками")

        self._logger.debug(
            f"Building creation attributes for CN={cn}"
        )

        attrs: Dict[str, Any] = {
            "cn": cn,
            "sAMAccountName": sam,
            "userPrincipalName": upn,
            # Создаем пользователя отключенным.
            "userAccountControl": UserAccountControl.DISABLED,
            "givenName": dto.first_name or None,
            "sn": dto.last_name or ".",  # sn обязателен, минимум точка
            "displayName": cn or None,
            "mail": (dto.email or None),
        }

        # Телефонный атрибут
        phone_attr = self._get_phone_write_attribute()
        if dto.phone_e164:
            attrs[phone_attr] = dto.phone_e164

        # Удаляем пустые значения
        return {k: v for k, v in attrs.items() if v not in (None, "", [])}

    def get_object_classes_for_user(self) -> List[str]:
        """Возвращает список классов объектов для пользователя AD.

        Returns:
            Список objectClass для создания user в AD
        """
        return [
            LdapObjectClass.TOP,
            LdapObjectClass.PERSON,
            LdapObjectClass.ORGANIZATIONAL_PERSON,
            LdapObjectClass.USER,
        ]

    def build_update_attributes(
        self,
        changes: Dict[str, Any],
        *,
        include_uac: bool = True,
    ) -> Dict[str, Any]:
        """Преобразует изменения Django модели в атрибуты LDAP.

        Args:
            changes: Словарь изменений от клиента
            include_uac: Включать ли обработку userAccountControl

        Returns:
            Словарь для обновления LDAP атрибутов
        """
        ldap_attrs = {}

        # Маппинг полей Django -> LDAP
        field_mapping = {
            "first_name": "givenName",
            "last_name": "sn",
            "email": "mail",
            "display_name": "displayName",
        }

        # Телефон - специальная обработка
        phone_attr = self._get_phone_write_attribute()
        if "phone_number" in changes:
            ldap_attrs[phone_attr] = changes["phone_number"]

        # Стандартные поля
        for django_field, ldap_field in field_mapping.items():
            if django_field in changes:
                value = changes[django_field]
                # sn обязателен, ставим точку если пусто
                if ldap_field == "sn" and not value:
                    value = "."
                ldap_attrs[ldap_field] = value

        # UAC (состояние учетки)
        if include_uac and "is_active" in changes:
            is_active = changes["is_active"]
            ldap_attrs["userAccountControl"] = (
                UserAccountControl.ENABLED
                if is_active
                else UserAccountControl.DISABLED
            )

        return ldap_attrs

    def process_avatar(
        self,
        avatar_bytes: bytes,
        *,
        size_px: int = 384,
        max_kb: int = 100,
    ) -> Optional[bytes]:
        """Обрабатывает аватар для записи в LDAP.

        Конвертирует изображение в JPEG, изменяет размер и сжимает.

        Args:
            avatar_bytes: Сырые байты изображения
            size_px: Желаемый размер (ширина и высота)
            max_kb: Максимальный размер в КБ

        Returns:
            Обработанные байты JPEG или None если обработка не удалась
        """
        if not avatar_bytes:
            return None

        try:
            processed = normalize_avatar_to_jpeg(
                avatar_bytes, size_px=size_px, max_kb=max_kb
            )

            if processed:
                size_kb = len(processed) / 1024
                self._logger.debug(
                    f"Avatar processed: {len(avatar_bytes)} bytes -> "
                    f"{len(processed)} bytes ({size_kb:.1f} KB)"
                )

            return processed
        except Exception as e:
            self._logger.warning(f"Failed to process avatar: {e}")
            return None

    def update_ldap_user_attributes(
        self,
        ldap_user: LdapUser,
        attributes: Dict[str, Any],
    ) -> bool:
        """Обновляет атрибуты LDAP пользователя через ORM.

        Args:
            ldap_user: Объект LdapUser (django-ldapdb)
            attributes: Словарь атрибутов для обновления

        Returns:
            True если были изменения, False если ничего не изменилось
        """
        changed = False

        # Маппинг LDAP атрибутов -> поля модели
        ldap_to_model = {
            "givenName": "given_name",
            "sn": "sn",
            "mail": "mail",
            "displayName": "display_name",
            "mobile": "mobile",
            "telephoneNumber": "telephone_number",
            "userAccountControl": "user_account_control",
            "thumbnailPhoto": "thumbnail_photo",
        }

        for ldap_attr, value in attributes.items():
            model_field = ldap_to_model.get(ldap_attr)
            if model_field and hasattr(ldap_user, model_field):
                if getattr(ldap_user, model_field) != value:
                    setattr(ldap_user, model_field, value)
                    changed = True

        if changed:
            ldap_user.save()
            self._logger.debug(
                f"Updated LDAP user attributes for DN={ldap_user.dn}"
            )

        return changed

    def _get_phone_write_attribute(self) -> str:
        """Определяет, в какой атрибут писать номер телефона.

        Returns:
            Имя LDAP атрибута для записи телефона
        """
        # Проверяем настройки
        write_attr = getattr(settings, "LDAP_WRITE_PHONE_ATTR", None)
        if write_attr:
            return write_attr

        # Fallback из списка допустимых атрибутов
        candidates = getattr(
            settings, "LDAP_PHONE_ATTRS", ("mobile", "telephoneNumber")
        )

        return candidates[0] if candidates else "telephoneNumber"


__all__ = ["UserMapperService"]
