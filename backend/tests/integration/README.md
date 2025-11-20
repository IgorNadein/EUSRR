# LDAP Integration Tests

## Описание

Интеграционные тесты для проверки работы с реальным LDAP сервером в Docker.

## Быстрый старт

### 1. Запуск LDAP сервера

```bash
cd backend
docker-compose -f docker-compose.test.yml up -d
```

**Сервисы:**
- OpenLDAP: `ldap://localhost:10389`
- phpLDAPadmin (веб-интерфейс): http://localhost:8090

**Учётные данные:**
- Admin DN: `cn=admin,dc=test,dc=local`
- Admin Password: `test_change-me-redacted-secret`

### 2. Проверка работы LDAP

```bash
# Через ldapsearch (если установлен)
ldapsearch -x -H ldap://localhost:10389 -b "dc=test,dc=local" \
  -D "cn=admin,dc=test,dc=local" -w test_change-me-redacted-secret

# Через веб-интерфейс
# Откройте http://localhost:8090
# Login DN: cn=admin,dc=test,dc=local
# Password: test_change-me-redacted-secret
```

### 3. Установка зависимостей для тестов

```bash
pip install python-ldap
```

### 4. Запуск интеграционных тестов

```bash
# Все интеграционные тесты
pytest -m integration tests/integration/ -v

# Конкретный тест
pytest tests/integration/test_ldap_integration.py::test_ldap_server_is_accessible -v

# С остановкой на первой ошибке
pytest -m integration tests/integration/ -v -x

# С подробным выводом
pytest -m integration tests/integration/ -v -s
```

### 5. Остановка LDAP сервера

```bash
# Остановить с сохранением данных
docker-compose -f docker-compose.test.yml stop

# Остановить и удалить (очистить данные)
docker-compose -f docker-compose.test.yml down -v
```

## Структура

```
tests/
├── integration/
│   ├── conftest.py              # Фикстуры для интеграционных тестов
│   └── test_ldap_integration.py # Интеграционные тесты LDAP
└── ldap_fixtures/
    └── 01-base-structure.ldif   # Начальная структура LDAP
```

## Конфигурация тестового LDAP

**База данных:**
- Base DN: `dc=test,dc=local`
- Users OU: `ou=Users,dc=test,dc=local`
- Groups OU: `ou=Groups,dc=test,dc=local`
- Departments OU: `ou=Departments,dc=test,dc=local`

**Тестовые данные:**
- Пользователь: `cn=test.user,ou=Users,dc=test,dc=local`
- Группа: `cn=test-group,ou=Groups,dc=test,dc=local`
- Отдел: `ou=IT,ou=Departments,dc=test,dc=local`

## Созданные тесты

### ✅ test_ldap_server_is_accessible
Проверяет доступность LDAP сервера и базовую структуру.

### 🔧 test_register_user_creates_in_ldap
Тестирует создание пользователя через API с записью в LDAP.
**Статус:** Требует настройки DirectoryService на тестовый LDAP

### 🔧 test_verify_email_activates_in_ldap
Тестирует верификацию email и активацию в LDAP.
**Статус:** Требует настройки DirectoryService на тестовый LDAP

### 🔧 test_create_group_syncs_to_ldap
Тестирует создание группы с синхронизацией в LDAP.
**Статус:** Требует настройки DirectoryService на тестовый LDAP

### 🔧 test_full_user_lifecycle_with_ldap
Тестирует полный жизненный цикл: регистрация → верификация → активация.
**Статус:** Требует настройки DirectoryService на тестовый LDAP

## TODO

### Следующие шаги:

1. **Настроить DirectoryService для тестов**
   ```python
   # В conftest.py или settings_test.py
   LDAP_SERVER_URI = "ldap://localhost:10389"
   LDAP_BASE_DN = "dc=test,dc=local"
   ```

2. **Добавить хелперы для проверки LDAP**
   ```python
   def assert_user_exists_in_ldap(username):
       """Проверяет наличие пользователя в LDAP"""
       conn = ldap.initialize("ldap://localhost:10389")
       # ...
   ```

3. **Расширить тестовое покрытие**
   - Тесты отделов с LDAP
   - Тесты позиций с LDAP
   - Тесты синхронизации изменений
   - Тесты удаления и деактивации

4. **Добавить CI/CD интеграцию**
   ```yaml
   # .github/workflows/tests.yml
   - name: Start LDAP server
     run: docker-compose -f docker-compose.test.yml up -d
   
   - name: Run integration tests
     run: pytest -m integration
   ```

## Отладка

### Просмотр логов LDAP

```bash
docker logs eusrr-test-ldap -f
```

### Подключение к контейнеру

```bash
docker exec -it eusrr-test-ldap bash
```

### Проверка данных в LDAP

```bash
# Список всех пользователей
docker exec eusrr-test-ldap ldapsearch -x -b "ou=Users,dc=test,dc=local" -D "cn=admin,dc=test,dc=local" -w test_change-me-redacted-secret

# Список всех групп
docker exec eusrr-test-ldap ldapsearch -x -b "ou=Groups,dc=test,dc=local" -D "cn=admin,dc=test,dc=local" -w test_change-me-redacted-secret
```

### Сброс данных LDAP

```bash
# Удалить все данные и начать заново
docker-compose -f docker-compose.test.yml down -v
docker-compose -f docker-compose.test.yml up -d
```

## Полезные команды

```bash
# Статус контейнеров
docker-compose -f docker-compose.test.yml ps

# Рестарт LDAP
docker-compose -f docker-compose.test.yml restart test-ldap

# Просмотр использования ресурсов
docker stats eusrr-test-ldap

# Экспорт данных LDAP
docker exec eusrr-test-ldap slapcat > ldap_backup.ldif
```

## Troubleshooting

### Проблема: LDAP сервер не запускается

**Решение:**
```bash
# Проверить логи
docker logs eusrr-test-ldap

# Проверить занят ли порт
netstat -ano | findstr :10389

# Убить процесс если порт занят
taskkill /PID <PID> /F
```

### Проблема: Тесты не могут подключиться к LDAP

**Решение:**
1. Проверить что контейнер запущен: `docker ps`
2. Проверить доступность порта: `telnet localhost 10389`
3. Увеличить время ожидания в `conftest.py`

### Проблема: python-ldap не устанавливается на Windows

**Решение:**
```bash
# Установить готовый wheel
pip install https://download.lfd.uci.edu/pythonlibs/archived/python_ldap-3.4.0-cp313-cp313-win_amd64.whl

# Или использовать ldap3 (альтернатива)
pip install ldap3
```
