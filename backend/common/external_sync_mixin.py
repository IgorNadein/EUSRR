"""
Универсальный миксин для синхронизации DB операций с внешними системами (LDAP, AD, etc).

Использование:
    class EmployeeViewSet(ExternalSystemSyncMixin, viewsets.ModelViewSet):
        external_sync_service = DirectoryService()
        
        def get_external_sync_method(self, action):
            return {
                'create': 'create_user_ldap',
                'update': 'update_user_ldap',
                'destroy': 'delete_user_ldap',
            }.get(action)
        
        def prepare_external_data(self, instance, action):
            if action == 'create':
                return {'user': instance}
            return {'user_id': instance.id}
"""
from django.db import transaction
from rest_framework import status
from rest_framework.response import Response
from functools import wraps
import logging

logger = logging.getLogger(__name__)


class ExternalSystemSyncMixin:
    """
    Миксин для автоматической синхронизации операций ViewSet с внешними системами.
    
    Паттерн:
    1. Выполняет DB операцию в транзакции
    2. При успехе - вызывает метод внешней системы
    3. При ошибке внешней системы - откатывает DB транзакцию
    
    Attributes:
        external_sync_service: Сервис для работы с внешней системой (например, DirectoryService)
        external_sync_enabled: Флаг включения синхронизации (по умолчанию True)
        external_sync_async: Использовать асинхронную синхронизацию через Celery
    """
    external_sync_service = None
    external_sync_enabled = True
    external_sync_async = False
    
    def get_external_sync_method(self, action):
        """
        Возвращает имя метода внешнего сервиса для данного action.
        
        Args:
            action: 'create', 'update', 'partial_update', 'destroy'
        
        Returns:
            str: имя метода сервиса или None если синхронизация не нужна
        """
        raise NotImplementedError("Переопределите get_external_sync_method()")
    
    def prepare_external_data(self, instance, action):
        """
        Подготавливает данные для передачи во внешний сервис.
        
        Args:
            instance: Инстанс модели Django
            action: Тип операции
        
        Returns:
            dict: данные для метода внешнего сервиса
        """
        return {'instance': instance}
    
    def handle_external_sync_error(self, error, instance, action):
        """
        Обработка ошибки синхронизации с внешней системой.
        
        Args:
            error: Exception от внешней системы
            instance: Инстанс модели
            action: Тип операции
        
        Returns:
            Response или None (если None - будет поднята ошибка)
        """
        logger.error(f"External sync failed for {action} on {instance}: {error}")
        return Response(
            {'detail': f'Ошибка синхронизации с внешней системой: {str(error)}'},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    def perform_create(self, serializer):
        """Переопределение create с синхронизацией."""
        return self._perform_with_sync(serializer, 'create', super().perform_create)
    
    def perform_update(self, serializer):
        """Переопределение update с синхронизацией."""
        action = 'partial_update' if self.request.method == 'PATCH' else 'update'
        return self._perform_with_sync(serializer, action, super().perform_update)
    
    def perform_destroy(self, instance):
        """Переопределение destroy с синхронизацией."""
        return self._perform_with_sync_instance(instance, 'destroy', super().perform_destroy)
    
    def _perform_with_sync(self, serializer, action, db_operation):
        """
        Выполняет DB операцию и синхронизацию с внешней системой.
        
        Args:
            serializer: DRF serializer с валидированными данными
            action: Тип операции
            db_operation: Функция для выполнения DB операции
        """
        if not self.external_sync_enabled:
            return db_operation(serializer)
        
        sync_method_name = self.get_external_sync_method(action)
        if not sync_method_name or not self.external_sync_service:
            return db_operation(serializer)
        
        # Атомарная транзакция: сохраняем в БД
        with transaction.atomic():
            db_operation(serializer)
            instance = serializer.instance
            
            # Подготавливаем данные для внешней системы
            external_data = self.prepare_external_data(instance, action)
            
            try:
                # Вызываем метод внешней системы
                sync_method = getattr(self.external_sync_service, sync_method_name)
                result = sync_method(**external_data)
                
                # Если внешняя система вернула данные для обновления БД
                if isinstance(result, dict) and result.get('update_db'):
                    for field, value in result['update_db'].items():
                        setattr(instance, field, value)
                    instance.save(update_fields=list(result['update_db'].keys()))
                
                logger.info(f"External sync success for {action} on {instance}")
                
            except Exception as e:
                # При ошибке внешней системы - откатываем транзакцию
                logger.error(f"External sync failed, rolling back: {e}")
                transaction.set_rollback(True)
                
                # Вызываем обработчик ошибок
                error_response = self.handle_external_sync_error(e, instance, action)
                if error_response:
                    raise ExternalSyncError(error_response)
                raise
    
    def _perform_with_sync_instance(self, instance, action, db_operation):
        """
        Выполняет DB операцию на инстансе с синхронизацией.
        
        Args:
            instance: Инстанс модели
            action: Тип операции
            db_operation: Функция для выполнения DB операции
        """
        if not self.external_sync_enabled:
            return db_operation(instance)
        
        sync_method_name = self.get_external_sync_method(action)
        if not sync_method_name or not self.external_sync_service:
            return db_operation(instance)
        
        # Сохраняем данные перед удалением
        external_data = self.prepare_external_data(instance, action)
        
        # Атомарная транзакция: удаляем из БД
        with transaction.atomic():
            db_operation(instance)
            
            try:
                # Вызываем метод внешней системы
                sync_method = getattr(self.external_sync_service, sync_method_name)
                sync_method(**external_data)
                
                logger.info(f"External sync success for {action} on {instance}")
                
            except Exception as e:
                # При ошибке внешней системы - откатываем транзакцию
                logger.error(f"External sync failed, rolling back: {e}")
                transaction.set_rollback(True)
                
                error_response = self.handle_external_sync_error(e, instance, action)
                if error_response:
                    raise ExternalSyncError(error_response)
                raise


class ExternalSyncError(Exception):
    """Исключение с Response для возврата клиенту."""
    def __init__(self, response):
        self.response = response
        super().__init__()


def with_external_sync(external_service_attr='external_sync_service', method_map=None):
    """
    Декоратор для методов ViewSet, добавляющий синхронизацию с внешней системой.
    
    Usage:
        @with_external_sync(method_map={'create': 'create_user_ldap'})
        def create(self, request, *args, **kwargs):
            return super().create(request, *args, **kwargs)
    
    Args:
        external_service_attr: Имя атрибута ViewSet с сервисом
        method_map: Маппинг action -> метод внешнего сервиса
    """
    def decorator(func):
        @wraps(func)
        def wrapper(self, request, *args, **kwargs):
            # Выполняем оригинальный метод
            with transaction.atomic():
                response = func(self, request, *args, **kwargs)
                
                # Получаем сервис и метод для синхронизации
                service = getattr(self, external_service_attr, None)
                if not service or not method_map:
                    return response
                
                action = self.action
                sync_method_name = method_map.get(action)
                if not sync_method_name:
                    return response
                
                try:
                    # Получаем созданный/обновленный инстанс
                    instance = getattr(response, 'data', {}).get('id')
                    if isinstance(response.data, dict):
                        instance = self.get_queryset().get(id=response.data['id'])
                    
                    # Вызываем метод внешней системы
                    sync_method = getattr(service, sync_method_name)
                    sync_method(instance=instance)
                    
                except Exception as e:
                    transaction.set_rollback(True)
                    logger.error(f"External sync failed: {e}")
                    raise
                
                return response
        return wrapper
    return decorator
