# 🧪 Интеграционные тесты с LDAP

Простые интеграционные тесты с реальным LDAP сервером.

## 🎯 Подход

**Держите LDAP сервер запущенным постоянно во время разработки.**

Не нужны сложные фикстуры для управления Docker - просто запустите LDAP один раз и пишите обычные pytest тесты.

## 🚀 Быстрый старт

### 1. Запустите LDAP сервер (один раз)

```bash
cd backend
./ldap-test.sh start
```

LDAP сервер запустится в Docker и будет работать в фоне.

### 2. Запустите тесты

```bash
# Все интеграционные тесты
pytest tests/integration/ -v

# Конкретный тест
pytest tests/integration/test_ldap_simple.py::TestLDAPIntegration::test_register_user_creates_in_ldap -v

# С подробным выводом
pytest tests/integration/ -v -s
```

### 3. Пишите новые тесты

Используйте простые фикстуры из `conftest.py`:

```python
@pytest.mark.django_db
def test_my_feature(self, ldap_test_settings, ldap_connection):
    """Мой тест с LDAP"""
    # Arrange
    username = "test_myfeature"
    
    # Act
    # ... ваш код ...
    
    # Assert - проверка в LDAP
    from .conftest import ldap_search_user
    ldap_user = ldap_search_user(ldap_connection, username)
    assert ldap_user is not None
```

## 📋 Доступные helper функции

В `conftest.py` есть готовые функции для работы с LDAP:

- **`ldap_search_user(ldap_connection, username)`** - найти пользователя в LDAP
- **`ldap_delete_user(ldap_connection, username)`** - удалить пользователя из LDAP
- **`ldap_cleanup_test_users(ldap_connection, prefix="test_")`** - очистить всех тестовых пользователей
- **`get_ldap_connection(ldap_connection)`** - получить прямое подключение к LDAP

### Фикстуры

- **`ldap_connection`** (session) - параметры подключения к LDAP
- **`ldap_test_settings`** - временно переключает Django на тестовый LDAP
- **`cleanup_test_data`** (autouse) - автоматически очищает тестовые данные после каждого теста

## 🔧 Управление LDAP сервером

```bash
# Запустить
./ldap-test.sh start

# Остановить (но не удалять данные)
./ldap-test.sh stop

# Перезапустить
./ldap-test.sh restart

# Посмотреть логи
./ldap-test.sh logs

# Проверить что LDAP работает
./ldap-test.sh check

# Полная очистка (удалит все данные)
./ldap-test.sh clean
```

## 🌐 Веб-интерфейс phpLDAPadmin

Для визуального просмотра данных в LDAP:

```bash
start http://localhost:8090
```

**Вход:**
- Login DN: `cn=admin,dc=test,dc=local`
- Password: `test_change-me-redacted-secret`

Здесь можно посмотреть структуру LDAP, созданных пользователей, группы и т.д.

## 📝 Структура тестов

```
tests/integration/
├── conftest.py              # Фикстуры и helper функции
├── test_ldap_simple.py      # Простые интеграционные тесты
└── README.md                # Эта инструкция
```

## 🎨 Пример теста

```python
import pytest
from django.test import TestCase
from .conftest import ldap_search_user

class TestMyFeature(TestCase):
    
    @pytest.mark.django_db
    def test_user_creation(self, ldap_test_settings, ldap_connection):
        """Создание пользователя синхронизируется с LDAP"""
        # Arrange
        user_data = {
            "username": "test_newuser",
            "email": "newuser@test.local",
            "password": "Password123!",
            # ... другие поля
        }
        
        # Act
        response = self.client.post("/api/v1/employees/register/", user_data)
        
        # Assert - проверяем Django
        assert response.status_code == 201
        
        # Assert - проверяем LDAP
        ldap_user = ldap_search_user(ldap_connection, "test_newuser")
        assert ldap_user is not None
        
        dn, attrs = ldap_user
        assert b"newuser@test.local" in attrs.get("mail", [])
```

## 🐛 Отладка

### Проверить что LDAP запущен

```bash
docker ps | grep ldap
# Должен показать: eusrr-test-ldap
```

### Посмотреть логи LDAP

```bash
./ldap-test.sh logs
```

### Проверить подключение к LDAP

```bash
./ldap-test.sh check
```

### Очистить тестовые данные вручную

```python
from tests.integration.conftest import ldap_cleanup_test_users

ldap_connection = {
    "uri": "ldap://localhost:10389",
    "base_dn": "dc=test,dc=local",
    "admin_dn": "cn=admin,dc=test,dc=local",
    "change-me-redacted-secret": "test_change-me-redacted-secret",
    "users_ou": "ou=Users,dc=test,dc=local",
}

ldap_cleanup_test_users(ldap_connection, prefix="test_")
```

## ✅ Преимущества этого подхода

1. **Простота** - обычные pytest тесты, никаких сложных фикстур
2. **Скорость** - LDAP запускается один раз, не перезапускается между тестами
3. **Удобство** - веб-интерфейс для визуального контроля
4. **Изоляция** - автоматическая очистка тестовых данных после каждого теста
5. **Реалистичность** - тесты работают с настоящим LDAP

## 🔄 Workflow разработки

1. **Утром** - запускаете LDAP сервер:
   ```bash
   ./ldap-test.sh start
   ```

2. **В течение дня** - пишете и запускаете тесты:
   ```bash
   pytest tests/integration/ -v
   ```

3. **Вечером** - останавливаете сервер (опционально):
   ```bash
   ./ldap-test.sh stop
   ```

4. **При необходимости** - чистите данные:
   ```bash
   ./ldap-test.sh clean && ./ldap-test.sh start
   ```

## 📚 Следующие шаги

- [ ] Дописать проверки для полей в LDAP (accountStatus, etc)
- [ ] Добавить тесты для групп и департаментов
- [ ] Добавить тесты для обновления пользователей
- [ ] Протестировать синхронизацию при изменении данных
