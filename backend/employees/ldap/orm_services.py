"""ORM сервисы для работы с LDAP через django-ldapdb.

Упрощенная альтернатива низкоуровневым ldap3 операциям.
Использует LDAP модели (LdapUser, LdapGroup, LdapOrganizationalUnit) для CRUD.

Преимущества:
- Чистый Django ORM вместо ldap3 костылей
- Автоматическая валидация
- Унифицированный API
- Меньше кода

Использование:
- Только для WRITE операций (POST/PUT/DELETE)
- Чтение идет из обычных Django моделей (Employee, Department)
"""

import logging
from typing import Optional

from django.conf import settings

from .orm_models import LdapUser, LdapGroup, LdapOrganizationalUnit
from .utils.text_utils import esc_rdn

logger = logging.getLogger(__name__)

# User Account Control values для Active Directory
UAC_ENABLED = 512
UAC_DISABLED = 514


class LdapOrmUserService:
    """Сервис для управления пользователями в LDAP через ORM."""

    def create_user(
        self,
        *,
        sam_account_name: str,
        first_name: str,
        last_name: str,
        email: str,
        employee_pk: Optional[int] = None,
        phone: Optional[str] = None,
        is_active: bool = True,
        ou_dn: Optional[str] = None,
    ) -> LdapUser:
        """
        Создает пользователя в LDAP используя django-ldapdb ORM.
        
        Args:
            sam_account_name: sAMAccountName (логин без домена)
            first_name: Имя
            last_name: Фамилия
            email: Email адрес
            employee_pk: ID сотрудника в Django (для employeeNumber)
            phone: Телефон (опционально)
            is_active: Активен ли пользователь
            ou_dn: DN organizational unit для размещения
            
        Returns:
            Созданный LdapUser объект
        """
        # Генерация CN и UPN
        cn = f"{first_name} {last_name}".strip() or sam_account_name
        cn_safe = esc_rdn(cn)
        
        upn_suffix = getattr(settings, 'LDAP_UPN_SUFFIX', 'robotail.local')
        upn = f"{sam_account_name}@{upn_suffix}"
        
        # Определение OU для размещения
        if ou_dn is None:
            ou_dn = getattr(settings, 'LDAP_USERS_BASE',
                          getattr(settings, 'LDAP_USER_BASE',
                                 'OU=company,DC=robotail,DC=local'))
        
        # DN нового пользователя
        dn = f"CN={cn_safe},{ou_dn}"
        
        # Создание через ORM
        user = LdapUser()
        user.dn = dn
        user.cn = cn
        user.sam_account_name = sam_account_name
        user.user_principal_name = upn
        user.given_name = first_name
        user.sn = last_name or "."  # AD требует sn
        user.display_name = cn
        user.mail = email
        
        if phone:
            user.mobile = phone
        
        if employee_pk:
            user.employee_number = str(employee_pk)
        
        # UserAccountControl
        user.user_account_control = UAC_ENABLED if is_active else UAC_DISABLED
        
        # Сохранение в LDAP
        user.save()
        
        logger.info(f"Created LDAP user: {dn} (sAMAccountName={sam_account_name})")
        
        return user

    def update_user(
        self,
        user_dn: str,
        *,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        is_active: Optional[bool] = None,
    ) -> LdapUser:
        """
        Обновляет пользователя в LDAP через ORM.
        
        Args:
            user_dn: DN пользователя для обновления
            first_name: Новое имя (если нужно изменить)
            last_name: Новая фамилия
            email: Новый email
            phone: Новый телефон
            is_active: Новый статус активности
            
        Returns:
            Обновленный LdapUser объект
        """
        # Получаем пользователя по DN
        try:
            user = LdapUser.objects.get(dn=user_dn)
        except LdapUser.DoesNotExist:
            raise ValueError(f"LDAP user not found: {user_dn}")
        
        # Обновляем поля
        updated = False
        
        if first_name is not None and user.given_name != first_name:
            user.given_name = first_name
            updated = True
            
        if last_name is not None and user.sn != last_name:
            user.sn = last_name or "."
            updated = True
            
        if email is not None and user.mail != email:
            user.mail = email
            updated = True
            
        if phone is not None and user.mobile != phone:
            user.mobile = phone
            updated = True
            
        if is_active is not None:
            new_uac = UAC_ENABLED if is_active else UAC_DISABLED
            if user.user_account_control != new_uac:
                user.user_account_control = new_uac
                updated = True
        
        # Обновление displayName если изменились имя/фамилия
        if first_name is not None or last_name is not None:
            new_display = f"{user.given_name} {user.sn}".strip()
            if new_display and user.display_name != new_display:
                user.display_name = new_display
                updated = True
        
        if updated:
            user.save()
            logger.info(f"Updated LDAP user: {user_dn}")
        
        return user

    def delete_user(self, user_dn: str, *, soft: bool = True) -> None:
        """
        Удаляет пользователя из LDAP.
        
        Args:
            user_dn: DN пользователя для удаления
            soft: Если True, только деактивирует (userAccountControl=DISABLED)
                  Если False, полностью удаляет из LDAP
        """
        try:
            user = LdapUser.objects.get(dn=user_dn)
        except LdapUser.DoesNotExist:
            logger.warning(f"LDAP user not found for deletion: {user_dn}")
            return
        
        if soft:
            # Soft delete - деактивация
            user.user_account_control = UAC_DISABLED
            user.save()
            logger.info(f"Soft deleted (disabled) LDAP user: {user_dn}")
        else:
            # Hard delete - удаление из LDAP
            user.delete()
            logger.info(f"Deleted LDAP user: {user_dn}")

    def get_user_by_dn(self, dn: str) -> Optional[LdapUser]:
        """Получает пользователя из LDAP по DN."""
        try:
            return LdapUser.objects.get(dn=dn)
        except LdapUser.DoesNotExist:
            return None

    def get_user_by_employee_pk(self, employee_pk: int) -> Optional[LdapUser]:
        """Получает пользователя из LDAP по Employee.pk."""
        try:
            return LdapUser.objects.get(employee_number=str(employee_pk))
        except LdapUser.DoesNotExist:
            return None


class LdapOrmGroupService:
    """Сервис для управления группами в LDAP через ORM."""

    def create_group(
        self,
        cn: str,
        description: Optional[str] = None,
        ou_dn: Optional[str] = None,
    ) -> LdapGroup:
        """
        Создает группу в LDAP.
        
        Args:
            cn: Common Name группы
            description: Описание группы
            ou_dn: DN organizational unit для размещения
            
        Returns:
            Созданный LdapGroup объект
        """
        if ou_dn is None:
            ou_dn = getattr(settings, 'LDAP_BASE_DN', 'DC=robotail,DC=local')
        
        cn_safe = esc_rdn(cn)
        dn = f"CN={cn_safe},{ou_dn}"
        
        group = LdapGroup()
        group.dn = dn
        group.cn = cn
        group.sam_account_name = cn
        
        if description:
            group.description = description
        
        group.save()
        
        logger.info(f"Created LDAP group: {dn}")
        
        return group

    def add_member(self, group_dn: str, member_dn: str) -> None:
        """Добавляет члена в группу."""
        try:
            group = LdapGroup.objects.get(dn=group_dn)
        except LdapGroup.DoesNotExist:
            raise ValueError(f"LDAP group not found: {group_dn}")
        
        # Добавляем DN члена в список member
        if member_dn not in (group.member or []):
            members = list(group.member or [])
            members.append(member_dn)
            group.member = members
            group.save()
            logger.info(f"Added {member_dn} to group {group_dn}")

    def remove_member(self, group_dn: str, member_dn: str) -> None:
        """Удаляет члена из группы."""
        try:
            group = LdapGroup.objects.get(dn=group_dn)
        except LdapGroup.DoesNotExist:
            raise ValueError(f"LDAP group not found: {group_dn}")
        
        # Удаляем DN члена из списка member
        if member_dn in (group.member or []):
            members = list(group.member or [])
            members.remove(member_dn)
            group.member = members
            group.save()
            logger.info(f"Removed {member_dn} from group {group_dn}")

    def delete_group(self, group_dn: str) -> None:
        """Удаляет группу из LDAP."""
        try:
            group = LdapGroup.objects.get(dn=group_dn)
            group.delete()
            logger.info(f"Deleted LDAP group: {group_dn}")
        except LdapGroup.DoesNotExist:
            logger.warning(f"LDAP group not found for deletion: {group_dn}")


class LdapOrmDepartmentService:
    """Сервис для управления Organizational Units (отделами) в LDAP через ORM."""

    def create_ou(
        self,
        ou_name: str,
        description: Optional[str] = None,
        parent_dn: Optional[str] = None,
    ) -> LdapOrganizationalUnit:
        """
        Создает Organizational Unit в LDAP.
        
        Args:
            ou_name: Название OU
            description: Описание
            parent_dn: DN родительского контейнера
            
        Returns:
            Созданный LdapOrganizationalUnit объект
        """
        if parent_dn is None:
            parent_dn = getattr(settings, 'LDAP_BASE_DN', 'DC=robotail,DC=local')
        
        ou_safe = esc_rdn(ou_name)
        dn = f"OU={ou_safe},{parent_dn}"
        
        ou = LdapOrganizationalUnit()
        ou.dn = dn
        ou.ou = ou_name
        
        if description:
            ou.description = description
        
        ou.save()
        
        logger.info(f"Created LDAP OU: {dn}")
        
        return ou

    def delete_ou(self, ou_dn: str) -> None:
        """Удаляет OU из LDAP (должна быть пустой)."""
        try:
            ou = LdapOrganizationalUnit.objects.get(dn=ou_dn)
            ou.delete()
            logger.info(f"Deleted LDAP OU: {ou_dn}")
        except LdapOrganizationalUnit.DoesNotExist:
            logger.warning(f"LDAP OU not found for deletion: {ou_dn}")


__all__ = [
    'LdapOrmUserService',
    'LdapOrmGroupService',
    'LdapOrmDepartmentService',
]
