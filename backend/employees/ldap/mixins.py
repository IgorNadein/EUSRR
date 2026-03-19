"""Миксины для расширения функциональности django-ldapdb ORM моделей.

Этот модуль предоставляет дополнительные возможности для LDAP моделей,
которые не поддерживаются django-ldapdb из коробки.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class ModifyDnMixin:
    """Миксин для поддержки перемещения LDAP объектов между OU через modify_dn.
    
    django-ldapdb не поддерживает перемещение объектов между OU из-за того,
    что метод connection.rename_s() не передаёт параметр newsuperior.
    
    Этот миксин добавляет эту функциональность, отслеживая изменения base_dn
    и выполняя low-level modify_dn операцию перед стандартным save().
    
    Usage:
        class LdapUser(ModifyDnMixin, LdapModel):
            # ... поля модели
            pass
        
        # Использование:
        user = LdapUser.objects.get(cn="User")
        user.base_dn = "OU=Dismissed,OU=company,DC=robotail,DC=local"
        user.save()  # Автоматически выполнит modify_dn!
    
    Attributes:
        _original_base_dn (str): Оригинальный base_dn при загрузке объекта.
            Используется для определения, нужно ли перемещение.
    """
    
    def __init__(self, *args, **kwargs):
        """Инициализация миксина с сохранением оригинального base_dn."""
        super().__init__(*args, **kwargs)
        # Сохраняем оригинальный base_dn для отслеживания изменений
        self._original_base_dn = getattr(self, 'base_dn', None)
    
    def build_rdn(self):
        """Build RDN — исправление бага ldapdb 1.5.1.
        
        ldapdb's build_rdn() проверяет field.primary_key AND field.db_column,
        но поле 'dn' имеет primary_key=True и db_column=None,
        а 'cn'/'ou' — наоборот. Ни одно поле не подходит → всегда Exception.
        
        Исправление: для существующих объектов извлекаем RDN из текущего DN,
        для новых — строим из rdn_attributes.
        """
        # Существующий объект — извлекаем RDN из DN (сохраняет регистр CN/OU)
        if self.dn and ',' in self.dn:
            return self.dn.split(',', 1)[0]
        
        # Новый объект — строим из rdn_attributes
        rdn_attrs = getattr(self, 'rdn_attributes', [])
        for field in self._meta.fields:
            if field.db_column and field.db_column in rdn_attrs:
                value = getattr(self, field.name)
                if value:
                    return "%s=%s" % (field.db_column, value)
        raise Exception("Could not build Distinguished Name")
    
    def save(self, *args, **kwargs):
        """Переопределённый save с поддержкой modify_dn при изменении base_dn.
        
        Логика:
        1. Проверяем, изменился ли base_dn
        2. Если да - выполняем LDAP modify_dn для перемещения объекта
        3. Обновляем _saved_dn для корректной работы стандартного save()
        4. Вызываем родительский save() для обновления атрибутов
        
        Args:
            *args: Позиционные аргументы для Model.save()
            **kwargs: Именованные аргументы для Model.save()
            
        Raises:
            RuntimeError: Если modify_dn операция не удалась
        """
        # Проверяем, нужно ли перемещение
        current_base_dn = getattr(self, 'base_dn', None)
        needs_move = (
            hasattr(self, '_saved_dn') and  # Объект уже существует в LDAP
            self._saved_dn and  # DN не пустой
            self._original_base_dn and  # Был оригинальный base_dn
            current_base_dn and  # Есть новый base_dn
            current_base_dn != self._original_base_dn  # И он изменился
        )
        
        if needs_move:
            # Выполняем перемещение через низкоуровневый modify_dn
            from .infrastructure.connections import _ldap
            
            old_dn = self._saved_dn
            new_rdn = self.build_rdn()
            new_superior = current_base_dn
            new_dn = f"{new_rdn},{new_superior}"
            
            logger.debug(
                f"ModifyDnMixin: Moving LDAP object\n"
                f"  Old DN: {old_dn}\n"
                f"  New RDN: {new_rdn}\n"
                f"  New superior: {new_superior}\n"
                f"  New DN: {new_dn}"
            )
            
            with _ldap() as conn:
                # LDAP modify_dn операция с newsuperior
                success = conn.modify_dn(
                    old_dn,
                    new_rdn,
                    new_superior=new_superior
                )
                
                if not success:
                    error_msg = f"Failed to move LDAP object: {conn.result}"
                    logger.error(f"ModifyDnMixin: {error_msg}")
                    raise RuntimeError(error_msg)
                
                logger.info(
                    f"ModifyDnMixin: Successfully moved {old_dn} → {new_dn}"
                )
            
            # Обновляем _saved_dn для корректной работы последующего save()
            # Это важно, чтобы стандартный _save_table() знал новый DN
            self._saved_dn = new_dn
            self.dn = new_dn
            
            # Обновляем _original_base_dn для следующих операций
            self._original_base_dn = current_base_dn
        
        # Вызываем родительский save() для обновления атрибутов
        return super().save(*args, **kwargs)
    
    @classmethod
    def from_db(cls, db, field_names, values):
        """Переопределяем from_db для сохранения оригинального base_dn при загрузке.
        
        Этот метод вызывается Django ORM при загрузке объекта из БД (или LDAP).
        """
        instance = super().from_db(db, field_names, values)
        # Сохраняем base_dn при загрузке из LDAP
        instance._original_base_dn = getattr(instance, 'base_dn', None)
        return instance


class LdapSyncStateMixin:
    """Миксин для автоматического управления LdapSyncState при операциях с LDAP.
    
    Автоматически обновляет LdapSyncState при создании/обновлении/удалении
    LDAP объектов, отслеживая изменения DN и другие метаданные.
    
    Usage:
        class LdapUser(LdapSyncStateMixin, ModifyDnMixin, LdapModel):
            # Указываем, какая Django модель соответствует этой LDAP модели
            _sync_model_name = 'employee'
            _sync_pk_field = 'employee_number'  # Поле LDAP с Django PK
            
            employee_number = CharField(db_column='employeeNumber')
            # ... остальные поля
    
    Attributes:
        _sync_model_name (str): Имя модели для LdapSyncState.model
        _sync_pk_field (str): Имя поля, содержащего Django PK
    """
    
    _sync_model_name: Optional[str] = None
    _sync_pk_field: Optional[str] = None
    
    def save(self, *args, **kwargs):
        """Save с автоматическим обновлением LdapSyncState."""
        result = super().save(*args, **kwargs)
        
        # Обновляем LdapSyncState если настроен
        if self._sync_model_name and self._sync_pk_field:
            self._update_sync_state()
        
        return result
    
    def delete(self, *args, **kwargs):
        """Delete с автоматическим удалением LdapSyncState."""
        result = super().delete(*args, **kwargs)
        
        # Удаляем LdapSyncState если настроен
        if self._sync_model_name and self._sync_pk_field:
            self._delete_sync_state()
        
        return result
    
    def _update_sync_state(self):
        """Обновляет или создаёт запись LdapSyncState для этого объекта."""
        from employees.models import LdapSyncState
        from django.utils import timezone
        
        # Получаем Django PK из LDAP атрибута
        django_pk = getattr(self, self._sync_pk_field, None)
        if not django_pk:
            logger.warning(
                f"LdapSyncStateMixin: No {self._sync_pk_field} set, "
                f"skipping sync state update for {self.dn}"
            )
            return
        
        # Обновляем состояние
        state, created = LdapSyncState.objects.get_or_create(
            model=self._sync_model_name,
            object_pk=str(django_pk)
        )
        
        state.touch(
            ldap_dn=str(self.dn),
            sync_dir='ldap',
            last_ldap_modify_ts=timezone.now(),
        )
        
        action = "Created" if created else "Updated"
        logger.debug(
            f"LdapSyncStateMixin: {action} sync state for "
            f"{self._sync_model_name}#{django_pk} DN={self.dn}"
        )
    
    def _delete_sync_state(self):
        """Удаляет запись LdapSyncState для этого объекта."""
        from employees.models import LdapSyncState
        
        django_pk = getattr(self, self._sync_pk_field, None)
        if not django_pk:
            return
        
        deleted_count, _ = LdapSyncState.objects.filter(
            model=self._sync_model_name,
            object_pk=str(django_pk)
        ).delete()
        
        if deleted_count:
            logger.debug(
                f"LdapSyncStateMixin: Deleted sync state for "
                f"{self._sync_model_name}#{django_pk}"
            )


__all__ = [
    'ModifyDnMixin',
    'LdapSyncStateMixin',
]
