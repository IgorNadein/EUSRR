"""Миксины для API views с LDAP-специфичной логикой."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from django.conf import settings
from employees.ldap.directory_service import DirectoryService, DirectoryUserDTO
from employees.ldap.errors import DirectoryDbError, DirectoryLdapError
from rest_framework.response import Response

if TYPE_CHECKING:
    from employees.models import Employee

logger = logging.getLogger(__name__)


def _is_ldap_enabled() -> bool:
    """Проверяет, включена ли интеграция с LDAP."""
    return getattr(settings, "LDAP_ENABLED", False)


class LdapUserCreationMixin:
    """Миксин для создания пользователей в LDAP при регистрации.
    
    Используется в RegisterAPIView для вынесения LDAP-специфичной логики
    из основного метода регистрации.
    
    Методы:
        create_ldap_user(): Создаёт пользователя в LDAP через DirectoryService
        create_db_user(): Создаёт пользователя напрямую в БД (fallback без LDAP)
    """
    
    def create_ldap_user(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        phone_e164: str,
        password: str,
        avatar_bytes: Optional[bytes] = None,
        is_active: bool = False,
    ) -> tuple[Optional['Employee'], Optional[Response]]:
        """Создаёт disabled пользователя в LDAP с паролем.
        
        Args:
            first_name: Имя
            last_name: Фамилия
            email: Email (нормализованный, lowercase)
            phone_e164: Телефон в E.164 формате
            password: Пароль (идёт только в LDAP, в БД будет unusable)
            avatar_bytes: Байты аватара (опционально)
            is_active: False до верификации email
            
        Returns:
            tuple[Employee | None, Response | None]:
                - (Employee, None) при успехе
                - (None, Response) при ошибке (Response для возврата клиенту)
        """
        svc = DirectoryService()
        dto = DirectoryUserDTO(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_e164=phone_e164,
            department_dn=None,
            group_cns=[],
            initial_password=password,  # пароль идёт только в LDAP
            avatar_bytes=avatar_bytes,
            is_active=is_active,  # disabled до верификации email
        )
        
        try:
            emp = svc.create_user(dto)
            return emp, None
        except DirectoryLdapError as e:
            logger.error(f"LDAP user creation failed: {e}", exc_info=True)
            return None, Response(
                {"ok": False, "error": "ldap_error", "detail": str(e)}, 
                status=502
            )
        except DirectoryDbError as e:
            logger.error(f"DB error during LDAP user creation: {e}", exc_info=True)
            return None, Response(
                {"ok": False, "error": "db_error", "detail": str(e)}, 
                status=500
            )
    
    def create_db_user(
        self,
        *,
        first_name: str,
        last_name: str,
        email: str,
        phone_number: str,
        password: str,
        is_active: bool = False,
    ) -> 'Employee':
        """Создаёт пользователя напрямую в БД (режим без LDAP).
        
        Args:
            first_name: Имя
            last_name: Фамилия
            email: Email (нормализованный, lowercase)
            phone_number: Телефон в E.164 формате
            password: Пароль (устанавливается через set_password)
            is_active: False до верификации email
            
        Returns:
            Employee: Созданный пользователь
        """
        from employees.models import Employee
        
        emp = Employee.objects.create(
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone_number=phone_number,
            is_active=is_active,
            is_ldap_managed=False,
        )
        # Устанавливаем пароль в БД
        emp.set_password(password)
        emp.save(update_fields=['password'])
        
        return emp


class LdapPasswordMixin:
    """Миксин для endpoints, работающих с паролями LDAP пользователей.
    
    Используется в PasswordChangeView, PasswordResetView и других
    endpoints, которым нужно обновлять пароли в LDAP.
    
    Методы:
        update_ldap_password(): Обновляет пароль пользователя в LDAP
    """
    
    def update_ldap_password(
        self,
        employee: 'Employee',
        new_password: str,
    ) -> tuple[bool, Optional[Response]]:
        """Обновляет пароль пользователя в LDAP.
        
        Args:
            employee: Employee instance
            new_password: Новый пароль
            
        Returns:
            tuple[bool, Response | None]:
                - (True, None) при успехе
                - (False, Response) при ошибке (Response для возврата клиенту)
        """
        if not employee.is_ldap_managed:
            # Не LDAP пользователь - устанавливаем пароль в БД
            employee.set_password(new_password)
            employee.save(update_fields=['password'])
            return True, None
        
        # LDAP пользователь - обновляем через DirectoryService
        try:
            svc = DirectoryService()
            svc.update_user(
                emp=employee,
                changes={'password': new_password},
                group_cns=None,
                move_to_department_dn=None,
            )
            return True, None
        except DirectoryLdapError as e:
            logger.error(f"LDAP password update failed for user {employee.id}: {e}", exc_info=True)
            return False, Response(
                {"ok": False, "error": "ldap_error", "detail": str(e)},
                status=502
            )
        except Exception as e:
            logger.error(f"Unexpected error updating LDAP password for user {employee.id}: {e}", exc_info=True)
            return False, Response(
                {"ok": False, "error": "password_update_failed", "detail": str(e)},
                status=500
            )
