"""Базовый класс для всех LDAP сервисов.

Содержит общую логику, которая используется во всех сервисах:
- Управление состоянием синхронизации (LdapSyncState)
- Логирование операций
- Обработка ошибок
"""

import logging
from typing import Any, Optional
from django.utils import timezone

from ...models import LdapSyncState
from .constants import SyncDirection


class BaseService:
    """Базовый класс для всех LDAP сервисов.
    
    Предоставляет общую функциональность:
    - _touch_state() - обновление LdapSyncState
    - _log_operation() - логирование операций
    - _get_logger() - получение логгера для сервиса
    """
    
    def __init__(self):
        """Инициализация базового сервиса."""
        self._logger = self._get_logger()
    
    def _get_logger(self) -> logging.Logger:
        """Получает логгер для сервиса.
        
        Returns:
            Logger с именем модуля сервиса.
        """
        return logging.getLogger(self.__class__.__module__)
    
    def _touch_state(
        self,
        *,
        model: str,
        object_pk: int | str,
        ldap_dn: Optional[str] = None,
        ldap_guid: Optional[str] = None,
        last_ldap_modify_ts: Optional[Any] = None,
        last_django_modify_ts: Optional[Any] = None,
        sync_dir: Optional[str] = None,
    ) -> LdapSyncState:
        """Обновляет или создает запись состояния синхронизации.
        
        Единая точка входа для всех сервисов для обновления LdapSyncState.
        Автоматически логирует изменения при изменении DN.
        
        Args:
            model: Тип модели ('employee', 'department', 'group', 'position')
            object_pk: Primary key объекта в Django
            ldap_dn: Distinguished Name в LDAP
            ldap_guid: GUID объекта в LDAP
            last_ldap_modify_ts: Время последнего изменения в LDAP
            last_django_modify_ts: Время последнего изменения в Django
            sync_dir: Направление синхронизации (из SyncDirection)
            
        Returns:
            Обновленная запись LdapSyncState
        """
        state, created = LdapSyncState.objects.get_or_create(
            model=model, 
            object_pk=str(object_pk)
        )
        
        # Логируем изменение DN
        old_dn = state.ldap_dn if not created else None
        if ldap_dn is not None and ldap_dn != old_dn:
            self._logger.info(
                f"DN changed for {model}#{object_pk}: {old_dn} -> {ldap_dn}"
            )
        
        # Обновляем поля
        if ldap_dn is not None:
            state.ldap_dn = ldap_dn
        if ldap_guid is not None:
            state.ldap_guid = ldap_guid
        if last_ldap_modify_ts is not None:
            state.last_ldap_modify_ts = last_ldap_modify_ts
        if last_django_modify_ts is not None:
            state.last_django_modify_ts = last_django_modify_ts
        if sync_dir is not None:
            state.sync_dir = sync_dir
        
        state.save()
        
        if created:
            self._logger.debug(
                f"Created LdapSyncState for {model}#{object_pk} with DN={ldap_dn}"
            )
        
        return state
    
    def _get_object_dn(self, model: str, object_pk: int | str) -> str:
        """Получает DN объекта из LdapSyncState.
        
        Args:
            model: Тип модели
            object_pk: Primary key объекта
            
        Returns:
            Distinguished Name объекта
            
        Raises:
            ValueError: Если DN не найден или пустой
        """
        dn = (
            LdapSyncState.objects.filter(
                model=model, 
                object_pk=str(object_pk)
            )
            .values_list("ldap_dn", flat=True)
            .first()
        )
        
        if not dn:
            raise ValueError(
                f"DN not found for {model}#{object_pk} in LdapSyncState"
            )
        
        return dn
    
    def _log_operation(
        self,
        operation: str,
        *,
        model: str,
        object_id: Optional[int | str] = None,
        dn: Optional[str] = None,
        success: bool = True,
        error: Optional[Exception] = None,
        extra: Optional[dict] = None,
    ) -> None:
        """Логирует операцию LDAP.
        
        Args:
            operation: Название операции (create, update, delete, move, etc.)
            model: Тип модели
            object_id: ID объекта (если есть)
            dn: Distinguished Name (если есть)
            success: Успешность операции
            error: Ошибка (если была)
            extra: Дополнительные данные для логирования
        """
        level = logging.INFO if success else logging.ERROR
        
        parts = [f"{operation.upper()}", model]
        if object_id:
            parts.append(f"#{object_id}")
        if dn:
            parts.append(f"DN={dn}")
        
        message = " ".join(parts)
        
        if error:
            message += f" - ERROR: {error}"
        
        if extra:
            message += f" - {extra}"
        
        self._logger.log(level, message)
    
    def _safe_execute(
        self,
        operation: callable,
        operation_name: str,
        *,
        model: str = "unknown",
        object_id: Optional[int | str] = None,
        dn: Optional[str] = None,
        reraise: bool = True,
    ) -> Any:
        """Безопасно выполняет операцию с логированием.
        
        Args:
            operation: Функция для выполнения
            operation_name: Название операции для логов
            model: Тип модели
            object_id: ID объекта
            dn: Distinguished Name
            reraise: Пробрасывать ли исключение дальше
            
        Returns:
            Результат выполнения operation
            
        Raises:
            Exception: Если reraise=True и operation вызвала исключение
        """
        try:
            result = operation()
            self._log_operation(
                operation_name,
                model=model,
                object_id=object_id,
                dn=dn,
                success=True,
            )
            return result
        except Exception as e:
            self._log_operation(
                operation_name,
                model=model,
                object_id=object_id,
                dn=dn,
                success=False,
                error=e,
            )
            if reraise:
                raise
            return None


__all__ = ["BaseService"]
