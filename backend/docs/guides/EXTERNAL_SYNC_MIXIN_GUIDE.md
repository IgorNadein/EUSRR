# External System Sync Mixin - Руководство

Универсальное решение для синхронизации Django ViewSet операций с внешними системами (LDAP, Active Directory, внешние API).

## Проблема

При работе с внешними системами возникает классическая проблема распределенных транзакций:
1. Создаем/обновляем объект в БД
2. Синхронизируем с внешней системой (LDAP, AD, API)
3. Если внешняя система недоступна - нужно откатить БД
4. Нужно обрабатывать ошибки и логировать

## Решение

`ExternalSystemSyncMixin` - миксин для ViewSet, который автоматически оборачивает операции CRUD в транзакции и синхронизирует с внешней системой.

## Установка

```python
# settings.py
INSTALLED_APPS = [
    ...
    'common',  # где лежит external_sync_mixin.py
]
```

## Быстрый старт

### Вариант 1: Использование миксина (рекомендуется)

```python
from common.external_sync_mixin import ExternalSystemSyncMixin
from rest_framework import viewsets
from employees.ldap.directory_service import DirectoryService

class EmployeeViewSet(ExternalSystemSyncMixin, viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer

    # Сервис для работы с внешней системой
    external_sync_service = DirectoryService()

    # Включить/выключить синхронизацию
    external_sync_enabled = True

    def get_external_sync_method(self, action):
        """Маппинг: action ViewSet -> метод внешнего сервиса"""
        return {
            'create': 'create_user_ldap',           # POST /employees/
            'update': 'update_user_ldap',           # PUT /employees/{id}/
            'partial_update': 'update_user_ldap',   # PATCH /employees/{id}/
            'destroy': 'delete_user_ldap',          # DELETE /employees/{id}/
        }.get(action)

    def prepare_external_data(self, instance, action):
        """Подготовка данных для передачи в LDAP"""
        if action == 'create':
            return {
                'user': instance,
                'password': self.request.data.get('password')  # из request
            }
        elif action in ['update', 'partial_update']:
            return {
                'user': instance,
                'changes': self.request.data
            }
        elif action == 'destroy':
            return {'user_dn': instance.ldap_dn}
        return {}

    def handle_external_sync_error(self, error, instance, action):
        """Кастомная обработка ошибок LDAP"""
        from employees.ldap.errors import LDAPConnectionError, LDAPOperationError

        if isinstance(error, LDAPConnectionError):
            return Response(
                {'detail': 'LDAP сервер недоступен. Попробуйте позже.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        elif isinstance(error, LDAPOperationError):
            return Response(
                {'detail': f'Ошибка LDAP операции: {error.message}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Для остальных ошибок - стандартная обработка
        return super().handle_external_sync_error(error, instance, action)
```

### Вариант 2: Использование декоратора

```python
from common.external_sync_mixin import with_external_sync

class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all()
    serializer_class = EmployeeSerializer
    external_sync_service = DirectoryService()

    @with_external_sync(method_map={
        'create': 'create_user_ldap',
        'update': 'update_user_ldap',
        'destroy': 'delete_user_ldap'
    })
    def create(self, request, *args, **kwargs):
        return super().create(request, *args, **kwargs)
```

## Архитектура

### Порядок выполнения операций

```
1. ViewSet.create() вызывается
   ↓
2. ExternalSystemSyncMixin.perform_create() перехватывает
   ↓
3. Открывается transaction.atomic()
   ↓
4. Выполняется super().perform_create(serializer)
   - Валидация serializer
   - Сохранение в БД: instance = serializer.save()
   ↓
5. Вызывается prepare_external_data(instance, 'create')
   - Подготовка данных для LDAP
   ↓
6. Вызывается external_sync_service.create_user_ldap(**data)
   - Создание в LDAP
   - Если успех: commit транзакции
   - Если ошибка: rollback транзакции
   ↓
7. Возврат Response с данными
```

### Обработка ошибок

```python
try:
    with transaction.atomic():
        # 1. Сохраняем в БД
        db_operation(serializer)
        instance = serializer.instance

        # 2. Синхронизируем с LDAP
        ldap_service.create_user_ldap(user=instance)

        # Если все ОК - commit
except LDAPError as e:
    # При ошибке LDAP - автоматический rollback БД
    return Response({'detail': 'LDAP error'}, status=500)
```

## Примеры использования

### Пример 1: Простой CRUD

```python
class DepartmentViewSet(ExternalSystemSyncMixin, viewsets.ModelViewSet):
    external_sync_service = DirectoryService()

    def get_external_sync_method(self, action):
        return {
            'create': 'create_department_ldap',
            'update': 'update_department_ldap',
            'destroy': 'delete_department_ldap',
        }.get(action)

    def prepare_external_data(self, instance, action):
        return {'department': instance}
```

### Пример 2: С обновлением БД после LDAP

Если LDAP возвращает данные, которые нужно сохранить в БД (например, DN):

```python
# В DirectoryService
def create_user_ldap(self, user):
    """Создает пользователя в LDAP и возвращает DN."""
    dn = self._user_service.create_in_ldap(user)

    # Возвращаем данные для обновления БД
    return {
        'update_db': {
            'ldap_dn': dn,
            'ldap_synced_at': timezone.now()
        }
    }

# Миксин автоматически обновит БД:
# instance.ldap_dn = dn
# instance.ldap_synced_at = timezone.now()
# instance.save(update_fields=['ldap_dn', 'ldap_synced_at'])
```

### Пример 3: Условная синхронизация

```python
class EmployeeViewSet(ExternalSystemSyncMixin, viewsets.ModelViewSet):
    def get_external_sync_method(self, action):
        # Синхронизируем только если LDAP включен в настройках
        if not settings.LDAP_ENABLED:
            return None

        # Синхронизируем только активных пользователей
        if action == 'create' and not self.request.data.get('is_active'):
            return None

        return {
            'create': 'create_user_ldap',
            'update': 'update_user_ldap',
        }.get(action)
```

### Пример 4: Кастомные действия (actions)

```python
class EmployeeViewSet(ExternalSystemSyncMixin, viewsets.ModelViewSet):
    @action(detail=True, methods=['post'])
    def activate(self, request, pk=None):
        """Активация пользователя."""
        instance = self.get_object()

        with transaction.atomic():
            instance.is_active = True
            instance.save()

            # Синхронизируем с LDAP
            try:
                self.external_sync_service.activate_user_ldap(user=instance)
            except LDAPError:
                transaction.set_rollback(True)
                raise

        return Response({'status': 'activated'})
```

## Сравнение подходов

### ❌ Старый подход (до миксина)

```python
class EmployeeViewSet(viewsets.ModelViewSet):
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                # Создаем в БД
                self.perform_create(serializer)
                instance = serializer.instance

                # Синхронизируем с LDAP
                svc = DirectoryService()
                try:
                    svc.create_user(instance)  # <- LDAP внутри тоже делает БД!
                except LDAPError as e:
                    # Откат
                    raise ValidationError({'ldap': str(e)})

            return Response(serializer.data, status=201)
        except Exception as e:
            return Response({'detail': str(e)}, status=500)

    # Аналогично для update, partial_update, destroy...
    # Дублирование кода в каждом методе!
```

**Проблемы:**
- ❌ Дублирование кода в каждом методе ViewSet
- ❌ LDAP сервис делает БД операции (`transaction.atomic` внутри LDAP)
- ❌ Сложная обработка ошибок
- ❌ Логика размазана между view и service

### ✅ Новый подход (с миксином)

```python
class EmployeeViewSet(ExternalSystemSyncMixin, viewsets.ModelViewSet):
    external_sync_service = DirectoryService()

    def get_external_sync_method(self, action):
        return {
            'create': 'create_user_ldap',
            'update': 'update_user_ldap',
            'destroy': 'delete_user_ldap',
        }.get(action)

    def prepare_external_data(self, instance, action):
        return {'user': instance}
```

**Преимущества:**
- ✅ Минимум кода (3 метода вместо переопределения всего ViewSet)
- ✅ Четкое разделение: View делает БД, LDAP делает только LDAP
- ✅ Единая обработка ошибок
- ✅ Легко переиспользовать для других ViewSet
- ✅ Легко отключить синхронизацию (`external_sync_enabled = False`)

## Тестирование

### Отключение синхронизации в тестах

```python
@pytest.fixture
def no_ldap_sync(monkeypatch):
    """Отключает LDAP синхронизацию для тестов."""
    from api.v1.employees.views import EmployeeViewSet
    monkeypatch.setattr(EmployeeViewSet, 'external_sync_enabled', False)

def test_create_employee_without_ldap(api_client, no_ldap_sync):
    """Тест создания без LDAP."""
    response = api_client.post('/api/v1/employees/', {...})
    assert response.status_code == 201
    # LDAP не вызывался
```

### Мокирование внешнего сервиса

```python
@pytest.fixture
def mock_ldap_service(monkeypatch):
    """Мокает DirectoryService."""
    mock = Mock()
    mock.create_user_ldap = Mock(return_value={'update_db': {'ldap_dn': 'cn=test'}})

    from api.v1.employees.views import EmployeeViewSet
    monkeypatch.setattr(EmployeeViewSet, 'external_sync_service', mock)

    return mock

def test_create_employee_with_mock_ldap(api_client, mock_ldap_service):
    """Тест с моком LDAP."""
    response = api_client.post('/api/v1/employees/', {...})
    assert response.status_code == 201

    # Проверяем что LDAP вызвался
    mock_ldap_service.create_user_ldap.assert_called_once()
```

## Миграция существующего кода

### Шаг 1: Создать LDAP-only методы

```python
# employees/ldap/directory_service.py
class DirectoryService:
    def create_user_ldap(self, user, password=None):
        """ТОЛЬКО LDAP операция, БД не трогает."""
        dn = self._user_service.create_in_ldap(user, password)
        return {'update_db': {'ldap_dn': dn}}

    # Старый метод для обратной совместимости
    def create_user(self, dto):
        """DEPRECATED: Использует create_user_ldap."""
        with transaction.atomic():
            user = Employee.objects.create(...)
            self.create_user_ldap(user=user)
```

### Шаг 2: Добавить миксин в ViewSet

```python
# До
class EmployeeViewSet(viewsets.ModelViewSet):
    ...

# После
class EmployeeViewSet(ExternalSystemSyncMixin, viewsets.ModelViewSet):
    external_sync_service = DirectoryService()

    def get_external_sync_method(self, action):
        return {'create': 'create_user_ldap'}.get(action)

    def prepare_external_data(self, instance, action):
        return {'user': instance, 'password': self.request.data.get('password')}
```

### Шаг 3: Удалить старый код из ViewSet

```python
# Было
def create(self, request, *args, **kwargs):
    # 50 строк кода с транзакциями и LDAP
    ...

# Стало
# Метод create() вообще не нужен! Используется стандартный из ModelViewSet
```

## Troubleshooting

### Проблема: Транзакция не откатывается

**Решение:** Убедитесь что LDAP метод не перехватывает исключения:

```python
# ❌ Плохо
def create_user_ldap(self, user):
    try:
        self._ldap_connection.add(...)
    except LDAPError:
        return {'error': 'failed'}  # <- Исключение проглочено!

# ✅ Хорошо
def create_user_ldap(self, user):
    try:
        self._ldap_connection.add(...)
    except LDAPError as e:
        raise LDAPOperationError(str(e))  # <- Пробрасываем наверх
```

### Проблема: LDAP метод изменяет БД

**Решение:** LDAP методы не должны трогать БД. Только чтение и LDAP операции:

```python
# ❌ Плохо
def create_user_ldap(self, user):
    dn = self._ldap.add(...)
    user.ldap_dn = dn
    user.save()  # <- БД операция в LDAP методе!

# ✅ Хорошо
def create_user_ldap(self, user):
    dn = self._ldap.add(...)
    return {'update_db': {'ldap_dn': dn}}  # <- Возвращаем для обновления
```

### Проблема: Нужен доступ к request в LDAP методе

**Решение:** Передавайте нужные данные через `prepare_external_data`:

```python
def prepare_external_data(self, instance, action):
    return {
        'user': instance,
        'password': self.request.data.get('password'),
        'request_user': self.request.user,  # Кто делает операцию
        'ip_address': self.request.META.get('REMOTE_ADDR'),
    }
```

## Альтернативы

### 1. Django Signals + on_commit

```python
from django.db.models.signals import post_save
from django.db.transaction import on_commit

@receiver(post_save, sender=Employee)
def sync_employee_to_ldap(sender, instance, created, **kwargs):
    if created:
        on_commit(lambda: DirectoryService().create_user_ldap(instance))
```

**Минусы:**
- Не откатывает БД при ошибке LDAP
- Сложно передать данные из request (password)
- Сигналы выполняются для всех создан��й, не только через API

### 2. Celery tasks

```python
@shared_task
def sync_user_to_ldap(user_id):
    user = Employee.objects.get(id=user_id)
    DirectoryService().create_user_ldap(user)

# В ViewSet
def perform_create(self, serializer):
    super().perform_create(serializer)
    sync_user_to_ldap.delay(serializer.instance.id)
```

**Минусы:**
- Асинхронность: пользователь создан в БД, но LDAP может упасть позже
- Нужен Celery + Redis/RabbitMQ
- Сложнее отладка

**Когда использовать:** Если LDAP может быть медленным и не критичен

### 3. Saga Pattern (django-fsm)

Для сложных multi-step операций с откатом.

## Заключение

`ExternalSystemSyncMixin` - это универсальное решение для синхронизации Django ViewSet с внешними системами:

- ✅ Минимум кода
- ✅ Атомарность (БД + внешняя система)
- ✅ Обработка ошибок
- ✅ Легко тестировать
- ✅ Переиспользуется для любых ViewSet

Подходит для: LDAP, Active Directory, внешние API, системы очередей, файловые хранилища.
