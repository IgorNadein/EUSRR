"""Сервис для работы с паролями пользователей в Active Directory.

Выделен из UserService для упрощения и следования SRP.
Отвечает за:
- Установку паролей через AD extended operation
- Валидацию паролей
- Обработку ошибок политики паролей AD
"""

import logging
from typing import Optional
from ldap3 import Connection

from .base_service import BaseService
from .constants import PasswordError
from ..errors import DirectoryLdapError


logger = logging.getLogger(__name__)


class UserPasswordService(BaseService):
    """Сервис для управления паролями пользователей в AD."""
    
    def set_password(self, conn: Connection, dn: str, new_password: str) -> None:
        """Устанавливает новый пароль для пользователя через AD extended operation.
        
        Использует Microsoft-специфичное расширение modify_password для корректной
        работы с политиками паролей AD.
        
        Args:
            conn: Активное LDAP соединение
            dn: Distinguished Name пользователя
            new_password: Новый пароль
            
        Raises:
            DirectoryLdapError: Если операция не удалась
            ValueError: Если пароль не соответствует политике сложности
        """
        if not new_password:
            raise ValueError("Пароль не может быть пустым")
        
        self._logger.info(f"Setting password for user DN={dn}")
        
        ok = conn.extend.microsoft.modify_password(dn, new_password)
        
        if not ok:
            msg = conn.result or {}
            raw_message = (msg.get("message") or "").upper()
            
            # Проверка на ошибку политики сложности
            if PasswordError.COMPLEXITY_VIOLATION in raw_message:
                raise ValueError(
                    "Пароль не соответствует политике сложности Active Directory. "
                    "Требования: минимальная длина, использование прописных/строчных букв, "
                    "цифр и специальных символов."
                )
            
            # Проверка на слишком короткий пароль
            if PasswordError.PASSWORD_TOO_SHORT in raw_message:
                raise ValueError(
                    "Пароль слишком короткий. Проверьте минимальную длину пароля "
                    "в политике домена."
                )
            
            # Проверка на пароль в истории
            if PasswordError.PASSWORD_IN_HISTORY in raw_message:
                raise ValueError(
                    "Этот пароль уже использовался ранее. Выберите другой пароль."
                )
            
            # Общая ошибка
            raise DirectoryLdapError(
                f"Не удалось установить пароль: {msg}. "
                f"Проверьте требования политики паролей домена."
            )
        
        self._logger.info(f"Password successfully set for DN={dn}")
    
    def validate_password_strength(self, password: str) -> tuple[bool, Optional[str]]:
        """Проверяет базовую надёжность пароля перед отправкой в AD.
        
        Это НЕ заменяет проверку AD, а лишь помогает отловить очевидные проблемы.
        
        Args:
            password: Пароль для проверки
            
        Returns:
            Tuple (is_valid, error_message):
                - is_valid: True если пароль базово корректен
                - error_message: Описание ошибки или None
        """
        if not password:
            return False, "Пароль не может быть пустым"
        
        if len(password) < 7:
            return False, "Пароль должен содержать минимум 7 символов"
        
        # Проверки на наличие разных типов символов
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(not c.isalnum() for c in password)
        
        complexity_count = sum([has_upper, has_lower, has_digit, has_special])
        
        if complexity_count < 3:
            return False, (
                "Пароль должен содержать минимум 3 из 4 типов символов: "
                "прописные буквы, строчные буквы, цифры, специальные символы"
            )
        
        return True, None
    
    def change_password(
        self,
        conn: Connection,
        dn: str,
        old_password: str,
        new_password: str
    ) -> None:
        """Меняет пароль пользователя (требует знания старого пароля).
        
        Args:
            conn: Активное LDAP соединение
            dn: Distinguished Name пользователя
            old_password: Текущий пароль
            new_password: Новый пароль
            
        Raises:
            DirectoryLdapError: Если операция не удалась
            ValueError: Если новый пароль не соответствует политике
        """
        # Валидация перед отправкой
        is_valid, error_msg = self.validate_password_strength(new_password)
        if not is_valid:
            raise ValueError(error_msg)
        
        self._logger.info(f"Changing password for user DN={dn}")
        
        ok = conn.extend.microsoft.modify_password(dn, new_password, old_password)
        
        if not ok:
            msg = conn.result or {}
            raise DirectoryLdapError(f"Не удалось сменить пароль: {msg}")
        
        self._logger.info(f"Password successfully changed for DN={dn}")


__all__ = ["UserPasswordService"]
