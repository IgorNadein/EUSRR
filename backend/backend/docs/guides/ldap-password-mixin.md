# LDAP Password Mixin - Руководство

## Обзор

`LdapPasswordMixin` - миксин для API endpoint'ов, которые работают с паролями пользователей.

Автоматически синхронизирует изменения паролей с LDAP после обновления в БД.

## Расположение

`backend/common/ldap_password_mixin.py`

## Использование

### Пример 1: Endpoint смены пароля

```python
from common.ldap_password_mixin import LdapPasswordMixin
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status


class ChangePasswordAPIView(LdapPasswordMixin, APIView):
    """Смена пароля текущего пользователя."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        user = request.user
        old_password = request.data.get('old_password')
        new_password = request.data.get('new_password')
        
        # Проверяем старый пароль
        if not user.check_password(old_password):
            return Response(
                {'error': 'invalid_old_password'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Меняем пароль в БД
        user.set_password(new_password)
        user.save(update_fields=['password'])
        
        # Синхронизируем с LDAP
        success, error = self.sync_password_to_ldap(user, new_password)
        
        if not success:
            return Response(
                {
                    'ok': True,
                    'warning': f'Password changed in DB, but LDAP sync failed: {error}'
                },
                status=status.HTTP_200_OK
            )
        
        return Response({'ok': True}, status=status.HTTP_200_OK)
```

### Пример 2: Сброс пароля администратором

```python
from common.ldap_password_mixin import LdapPasswordMixin
from rest_framework.decorators import action
from rest_framework.response import Response
from employees.models import Employee


class EmployeeViewSet(LdapPasswordMixin, viewsets.ModelViewSet):
    """ViewSet для управления сотрудниками."""
    
    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def reset_password(self, request, pk=None):
        """Сброс пароля администратором."""
        employee = self.get_object()
        new_password = request.data.get('new_password')
        
        if not new_password:
            return Response(
                {'error': 'new_password is required'},
                status=400
            )
        
        # Меняем пароль в БД
        employee.set_password(new_password)
        employee.save(update_fields=['password'])
        
        # Синхронизируем с LDAP
        success, error = self.sync_password_to_ldap(employee, new_password)
        
        return Response({
            'ok': True,
            'ldap_synced': success,
            'ldap_error': error
        })
```

## Метод `sync_password_to_ldap`

### Сигнатура

```python
def sync_password_to_ldap(self, employee_instance, new_password):
    """Синхронизирует пароль с LDAP для данного Employee.
    
    Args:
        employee_instance: инстанс Employee
        new_password: новый пароль (plaintext)
        
    Returns:
        tuple: (success: bool, error: str or None)
    """
```

### Возвращаемые значения

- `(True, None)` - успешная синхронизация
- `(True, None)` - LDAP отключен (ок, синхронизация не нужна)
- `(False, "no_ldap_user")` - Employee не имеет LDAP пользователя
- `(False, "ldap_error: ...")` - ошибка LDAP
- `(False, "service_error: ...")` - ошибка DirectoryService
- `(False, "db_error: ...")` - ошибка БД

### Логика работы

1. Проверяет `LDAP_ENABLED` в settings
2. Проверяет `employee_instance.is_ldap_managed`
3. Проверяет наличие `LdapSyncState` для пользователя
4. Вызывает `DirectoryService.update_user()` с изменениями пароля
5. Логирует успех/ошибки

## Когда ИСПОЛЬЗОВАТЬ миксин

✅ **Используйте** для endpoint'ов:
- Смена пароля пользователем
- Сброс пароля администратором
- Первичная установка пароля
- Восстановление пароля

## Когда НЕ использовать миксин

❌ **НЕ используйте** для:
- Регистрации новых пользователей (используйте `RegisterAPIView` напрямую с `DirectoryService.create_user`)
- CRUD операций через `EmployeeViewSet` (сигналы автоматически синхронизируют)
- Административного создания Employee без LDAP (просто создавайте в БД)

## Текущая архитектура паролей

### Регистрация (RegisterAPIView)
```python
# Создает Employee + LDAP user с паролем
svc = DirectoryService()
dto = DirectoryUserDTO(
    ...
    initial_password=password,  # пароль только в LDAP
    is_active=False,
)
emp = svc.create_user(dto)
```

### Обычное создание через API (EmployeeViewSet.perform_create)
```python
# Создает только Employee в БД (без пароля, без LDAP)
instance = serializer.save(is_ldap_managed=ldap_enabled)
instance.set_unusable_password()
instance.save()
```

### Обновление через API (EmployeeViewSet.perform_update)
```python
# Обновляет Employee в БД
# Сигналы автоматически синхронизируют с LDAP (если пользователь существует)
instance._ldap_changes = dict(self.request.data)
serializer.save()
```

### Смена пароля (используйте LdapPasswordMixin)
```python
# Меняем в БД
user.set_password(new_password)
user.save()

# Синхронизируем с LDAP через миксин
success, error = self.sync_password_to_ldap(user, new_password)
```

## Файлы

- `backend/common/ldap_password_mixin.py` - миксин
- `backend/api/v1/employees/views/auth.py` - примеры RegisterAPIView, VerifyEmailAPIView
- `backend/employees/signals_ldap.py` - сигналы для автоматической синхронизации

## Связанные коммиты

- `f43761fd` - Создание LdapPasswordMixin
- `9764eb1a` - Переход на сигналы
- `0192c590` - Удаление ExternalSystemSyncMixin
