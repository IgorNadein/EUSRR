"""Сервис для генерации и управления логинами пользователей.

Поддерживает sAMAccountName и UPN.

Выделен из UserService для упрощения и следования SRP.
Отвечает за:
- Генерацию уникальных sAMAccountName
- Генерацию UPN (User Principal Name)
- Проверку доступности логинов
"""

import logging
from typing import Optional, Tuple
from django.conf import settings

from .base_service import BaseService
from ..orm_models import LdapUser
from ..utils.ldap_utils import build_logins_for_user


logger = logging.getLogger(__name__)


class UserLoginService(BaseService):
    """Сервис для генерации уникальных логинов пользователей."""

    def generate_unique_logins(
        self,
        first_name: str,
        last_name: str,
        email: str,
        *,
        upn_suffix: Optional[str] = None,
        ldap_guid: Optional[str] = None,
    ) -> Tuple[str, str]:
        """Генерирует уникальные sAMAccountName и UPN для нового пользователя.

        Использует различные стратегии для создания логина:
        1. Первая буква имени + фамилия (iivanov)
        2. Имя + первая буква фамилии (igori)
        3. Часть email до @ (если доступна)
        4. С добавлением цифр, если есть коллизии

        Args:
            first_name: Имя пользователя
            last_name: Фамилия пользователя
            email: Email пользователя
            upn_suffix: UPN suffix (domain), если None - берется из настроек
            ldap_guid: GUID пользователя (для генерации fallback логина)

        Returns:
            Tuple (sAMAccountName, userPrincipalName)

        Raises:
            ValueError: Если не удалось сгенерировать уникальные логины
        """
        # Определяем UPN suffix
        if not upn_suffix:
            upn_suffix = getattr(settings, "LDAP_UPN_SUFFIX", None)
            if not upn_suffix and email and "@" in email:
                upn_suffix = email.split("@", 1)[1]

        if not upn_suffix:
            raise ValueError(
                "Не задан UPN-суффикс (LDAP_UPN_SUFFIX) "
                "и его нельзя вывести из email"
            )

        self._logger.debug(
            f"Generating logins for {first_name} {last_name} ({email})"
        )

        # Используем существующую логику из utils
        sam, upn = build_logins_for_user(
            first_name=first_name,
            last_name=last_name,
            email=email,
            upn_suffix=upn_suffix,
            is_taken_sam=self._is_sam_taken,
            is_taken_upn=self._is_upn_taken,
            guid=ldap_guid,
        )

        if not sam or not upn:
            raise ValueError(
                "Не удалось сгенерировать уникальные sAMAccountName/UPN"
            )

        self._logger.info(f"Generated logins: sAMAccountName={sam}, UPN={upn}")

        return sam, upn

    def _is_sam_taken(self, sam_account_name: str) -> bool:
        """Проверяет, занят ли sAMAccountName в AD.

        Args:
            sam_account_name: sAMAccountName для проверки

        Returns:
            True если логин уже используется, False если свободен
        """
        return LdapUser.objects.filter(
            sam_account_name=sam_account_name
        ).exists()

    def _is_upn_taken(self, upn: str) -> bool:
        """Проверяет, занят ли userPrincipalName в AD.

        Args:
            upn: UPN для проверки

        Returns:
            True если UPN уже используется, False если свободен
        """
        return LdapUser.objects.filter(user_principal_name=upn).exists()

    def validate_sam_account_name(self, sam: str) -> Tuple[bool, Optional[str]]:
        """Проверяет корректность sAMAccountName по правилам AD.

        AD ограничения:
        - Максимум 20 символов
        - Допустимы: буквы, цифры, точка, дефис, подчеркивание
        - Не может начинаться/заканчиваться точкой

        Args:
            sam: sAMAccountName для проверки

        Returns:
            Tuple (is_valid, error_message)
        """
        if not sam:
            return False, "sAMAccountName не может быть пустым"

        if len(sam) > 20:
            return False, "sAMAccountName не может быть длиннее 20 символов"

        if sam.startswith(".") or sam.endswith("."):
            return (
                False,
                "sAMAccountName не может начинаться или заканчиваться точкой",
            )

        # Проверка допустимых символов
        allowed_chars = set(
            "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-_"
        )
        if not all(c in allowed_chars for c in sam):
            return False, (
                "sAMAccountName может содержать только буквы, цифры, "
                "точку, дефис и подчеркивание"
            )

        return True, None

    def validate_upn(self, upn: str) -> Tuple[bool, Optional[str]]:
        """Проверяет корректность UPN.

        Args:
            upn: UPN для проверки

        Returns:
            Tuple (is_valid, error_message)
        """
        if not upn:
            return False, "UPN не может быть пустым"

        if "@" not in upn:
            return False, "UPN должен содержать символ @"

        parts = upn.split("@")
        if len(parts) != 2:
            return False, "UPN должен иметь формат user@domain"

        username, domain = parts

        if not username:
            return False, "Часть username в UPN не может быть пустой"

        if not domain:
            return False, "Часть domain в UPN не может быть пустой"

        return True, None


__all__ = ["UserLoginService"]
