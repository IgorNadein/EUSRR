"""Миксин для API endpoint'ов, работающих с паролями в LDAP."""

import logging

from django.conf import settings

from employees.ldap.directory_service import DirectoryService
from employees.ldap.errors import DirectoryDbError, DirectoryLdapError, DirectoryServiceError
from employees.models import LdapSyncState

logger = logging.getLogger(__name__)


def _is_ldap_enabled():
    """Проверяет, включена ли интеграция с LDAP."""
    return getattr(settings, "LDAP_ENABLED", False)


class LdapPasswordMixin:
    """Миксин для endpoint'ов, которые работают с паролями.
    
    Автоматически синхронизирует изменения паролей с LDAP.
    Использование:
    
        class ChangePasswordAPIView(LdapPasswordMixin, APIView):
            def post(self, request):
                user = request.user
                new_password = request.data['new_password']
                
                # Меняем пароль в БД
                user.set_password(new_password)
                user.save()
                
                # Синхронизируем с LDAP (автоматически через миксин)
                self.sync_password_to_ldap(user, new_password)
                
                return Response({'ok': True})
    """
    
    def sync_password_to_ldap(self, employee_instance, new_password):
        """Синхронизирует пароль с LDAP для данного Employee.
        
        Args:
            employee_instance: инстанс Employee
            new_password: новый пароль (plaintext)
            
        Returns:
            tuple: (success: bool, error: str or None)
        """
        if not _is_ldap_enabled():
            return True, None
            
        if not employee_instance.is_ldap_managed:
            return True, None
            
        # Проверяем наличие LDAP пользователя
        sync_state = LdapSyncState.objects.filter(
            model='employee',
            object_pk=str(employee_instance.pk)
        ).first()
        
        if not sync_state or not (sync_state.ldap_dn or sync_state.ldap_guid):
            logger.warning(
                f"Employee {employee_instance.id} has no LDAP sync state, "
                "password not synced to LDAP"
            )
            return False, "no_ldap_user"
            
        try:
            svc = DirectoryService()
            svc.update_user(
                emp=employee_instance,
                changes={'password': new_password},
                group_cns=None,
                move_to_department_dn=None,
            )
            logger.info(f"Password synced to LDAP for Employee {employee_instance.id}")
            return True, None
            
        except DirectoryLdapError as e:
            logger.error(
                f"LDAP error during password sync for Employee {employee_instance.id}: {e}",
                exc_info=True
            )
            return False, f"ldap_error: {str(e)}"
            
        except DirectoryServiceError as e:
            logger.error(
                f"Service error during password sync for Employee {employee_instance.id}: {e}",
                exc_info=True
            )
            return False, f"service_error: {str(e)}"
            
        except DirectoryDbError as e:
            logger.error(
                f"DB error during password sync for Employee {employee_instance.id}: {e}",
                exc_info=True
            )
            return False, f"db_error: {str(e)}"
            
        except Exception as e:
            logger.error(
                f"Unexpected error during password sync for Employee {employee_instance.id}: {e}",
                exc_info=True
            )
            return False, f"unexpected_error: {str(e)}"
