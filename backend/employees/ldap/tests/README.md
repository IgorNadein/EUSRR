# Тесты LDAP модуля

Комплексный набор тестов для проверки функциональности LDAP модуля после рефакторинга.

## Структура тестов

```
tests/
├── conftest.py              # Общие фикстуры и конфигурация pytest
├── unit/                    # Unit-тесты отдельных сервисов
│   ├── test_user_service.py
│   ├── test_department_service.py
│   ├── test_group_service.py
│   └── test_position_service.py
├── integration/             # Интеграционные тесты
│   └── test_integration.py
└── fixtures/                # Тестовые данные и фикстуры
```

## Запуск тестов

### Все тесты
```bash
pytest backend/employees/ldap/tests/
```

### Только unit-тесты
```bash
pytest backend/employees/ldap/tests/unit/
```

### Только интеграционные тесты
```bash
pytest backend/employees/ldap/tests/integration/
```

### Конкретный файл
```bash
pytest backend/employees/ldap/tests/unit/test_user_service.py
```

### С покрытием кода
```bash
pytest backend/employees/ldap/tests/ --cov=employees.ldap --cov-report=html
```

### В verbose режиме
```bash
pytest backend/employees/ldap/tests/ -v
```

## Покрытие тестами

### UserService (test_user_service.py)
- ✅ Создание пользователей
- ✅ Обновление базовых полей
- ✅ Обновление пароля
- ✅ Обновление отдела
- ✅ Мягкое удаление (деактивация)
- ✅ Жесткое удаление
- ✅ Генерация уникальных логинов
- ✅ Конвертация ID → DN
- ✅ Перемещение между OU
- ✅ Синхронизация из AD

### DepartmentService (test_department_service.py)
- ✅ Создание отделов
- ✅ Создание вложенных отделов
- ✅ Создание с руководителем
- ✅ Переименование отдела
- ✅ Изменение руководителя
- ✅ Удаление с перемещением сотрудников
- ✅ Удаление без сотрудников
- ✅ Добавление членов
- ✅ Удаление членов
- ✅ Назначение руководителя
- ✅ Получение DN отдела
- ✅ Поиск отдела по DN
- ✅ Синхронизация группы отдела

### GroupService (test_group_service.py)
- ✅ Создание групп
- ✅ Создание с описанием
- ✅ Удаление групп
- ✅ Переименование групп
- ✅ Изменение описания
- ✅ Добавление членов
- ✅ Удаление членов
- ✅ Замена всех членов
- ✅ Получение списка членов
- ✅ Поиск DN по имени
- ✅ Поиск групп с пользователем
- ✅ Синхронизация каталога

### PositionService (test_position_service.py)
- ✅ Синхронизация должностей
- ✅ Синхронизация вложенности
- ✅ Назначение должности
- ✅ Снятие должности
- ✅ Удаление группы должности
- ✅ Получение базового DN
- ✅ Создание базового OU
- ✅ Создание/получение группы должности

### Интеграционные тесты (test_integration.py)
- ✅ Полный жизненный цикл пользователя
- ✅ Пользователь с отделом
- ✅ Отдел с членами и руководителем
- ✅ Реструктуризация отделов
- ✅ Назначение должностей
- ✅ Иерархия должностей
- ✅ Массовый импорт пользователей
- ✅ Реструктуризация организации

## Фикстуры (conftest.py)

### Mock LDAP соединения
- `mock_ldap_connection` - Mock LDAP connection
- `mock_ldap_context` - Mock контекстного менеджера _ldap()

### Django модели
- `sample_employee` - Тестовый сотрудник
- `sample_department` - Тестовый отдел
- `sample_position` - Тестовая должность
- `sample_django_group` - Тестовая Django группа
- `sample_ldap_sync_state` - Тестовая запись синхронизации

### DTO объекты
- `sample_user_dto` - Тестовый DirectoryUserDTO
- `sample_department_dto` - Тестовый DirectoryDepartmentDTO

### Mock репозитории
- `mock_ldap_repository` - Mock LdapRepository
- `mock_employee_repository` - Mock EmployeeRepository
- `mock_sync_state_repository` - Mock SyncStateRepository

### Mock сервисы
- `mock_user_service` - Mock UserService
- `mock_group_service` - Mock GroupService
- `mock_department_service` - Mock DepartmentService
- `mock_position_service` - Mock PositionService

### LDAP объекты
- `mock_ldap_entry` - Mock LDAP entry с атрибутами

### Настройки
- `ldap_test_settings` - Тестовые LDAP настройки

## Стратегия тестирования

### Unit-тесты
- **Изоляция**: Каждый сервис тестируется изолированно
- **Mocking**: Все зависимости (LDAP, ORM, другие сервисы) мокируются
- **Фокус**: Проверка логики конкретного сервиса
- **Скорость**: Быстрые тесты без внешних зависимостей

### Интеграционные тесты
- **Взаимодействие**: Тестируется работа нескольких сервисов вместе
- **Сценарии**: Полные бизнес-процессы (создание → изменение → удаление)
- **Mock LDAP**: LDAP соединение мокируется, Django ORM работает с тестовой БД
- **Реальность**: Приближены к реальным сценариям использования

## Добавление новых тестов

### Unit-тест для нового метода
```python
@pytest.mark.django_db
def test_new_method(
    self,
    mock_ldap_context,
    mock_ldap_connection,
    mock_ldap_repository
):
    """Тест нового метода."""
    # Arrange
    service = YourService(mock_ldap_repository)
    
    # Act
    result = service.new_method()
    
    # Assert
    assert result is not None
    assert mock_ldap_connection.some_operation.called
```

### Интеграционный тест
```python
@pytest.mark.django_db
def test_new_workflow(
    self,
    mock_ldap_context,
    mock_ldap_connection,
    all_services
):
    """Тест нового workflow."""
    service1 = all_services['service1']
    service2 = all_services['service2']
    
    # Act: выполняем последовательность операций
    service1.operation1()
    service2.operation2()
    
    # Assert: проверяем результат
    assert mock_ldap_connection.add.call_count == 2
```

## CI/CD интеграция

Тесты можно интегрировать в CI/CD pipeline:

```yaml
# .github/workflows/tests.yml
- name: Run LDAP tests
  run: |
    pytest backend/employees/ldap/tests/ \
      --cov=employees.ldap \
      --cov-report=xml \
      --junitxml=junit.xml
```

## Покрытие кода

Целевое покрытие: **>80%**

Проверка текущего покрытия:
```bash
pytest backend/employees/ldap/tests/ \
  --cov=employees.ldap \
  --cov-report=term-missing
```

## Troubleshooting

### Тесты не находят модули
```bash
# Убедитесь, что PYTHONPATH настроен правильно
export PYTHONPATH="${PYTHONPATH}:/path/to/backend"
```

### Ошибки базы данных
```bash
# Используйте тестовую БД
pytest --ds=eusrr_backend.settings_test
```

### Mock не работает
```python
# Проверьте правильность пути в patch
# Неправильно:
with patch('ldap.Repository'):
    ...

# Правильно:
with patch('employees.ldap.infrastructure.repositories.ldap_repository.LdapRepository'):
    ...
```

## Дополнительные ресурсы

- [pytest документация](https://docs.pytest.org/)
- [unittest.mock документация](https://docs.python.org/3/library/unittest.mock.html)
- [pytest-django документация](https://pytest-django.readthedocs.io/)
- [Архитектура LDAP модуля](../ARCHITECTURE.md)
- [Руководство по миграции](../MIGRATION_GUIDE.md)
