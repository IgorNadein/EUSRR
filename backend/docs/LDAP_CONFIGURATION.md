# Конфигурация LDAP в системе EUSRR

## Обзор

Система EUSRR поддерживает два режима работы:
1. **С интеграцией LDAP/Active Directory** (по умолчанию)
2. **Без LDAP** (автономный режим с аутентификацией через БД)

Переключение между режимами осуществляется через переменную окружения `LDAP_ENABLED`.

## Режимы работы

### Режим с LDAP (LDAP_ENABLED=true)

**Аутентификация:**
- Пользователи аутентифицируются через Active Directory/LDAP
- Пароли проверяются в LDAP, не хранятся в БД
- Автоматическая синхронизация профилей при входе

**Создание пользователей:**
- Пользователи создаются сначала в LDAP, затем в БД
- Устанавливается флаг `is_ldap_managed=True`
- DN и GUID пользователя сохраняются в `LdapSyncState`

**Обновление пользователей:**
- Изменения применяются сначала к LDAP, затем к БД
- Поддерживается двусторонняя синхронизация (LWW - Last Writer Wins)

**Бэкенды аутентификации (в порядке приоритета):**
1. `LDAP3Backend` - основной LDAP-бэкенд
2. `EmailOrPhoneBackend` - пропускается (так как LDAP активен)
3. `SuperuserOnlyBackend` - экстренный доступ для суперюзера
4. `PositionRoleBackend` - расчёт прав
5. `ModelBackend` - стандартный Django (как фоллбэк)

**Требуемые настройки в .env:**
```env
LDAP_ENABLED=true
LDAP_URI=ldaps://dcii.robotail.local:636
LDAP_BIND_DN=corp@robotail.local
LDAP_BIND_PASSWORD=your_password
LDAP_USER_BASE="OU=company,DC=robotail,DC=local"
LDAP_USERS_BASE="OU=Users,OU=company,DC=robotail,DC=local"
LDAP_USER_UPN_SUFFIX=@robotail.local
LDAP_WRITE_ENABLED=true
```

### Режим без LDAP (LDAP_ENABLED=false)

**Аутентификация:**
- Пользователи аутентифицируются через БД Django
- Пароли хешируются и хранятся в таблице `employees_employee`
- Используется стандартная система паролей Django

**Создание пользователей:**
- Пользователи создаются напрямую в БД
- Флаг `is_ldap_managed=False`
- Пароль устанавливается через `user.set_password()`

**Обновление пользователей:**
- Все изменения применяются только к БД
- Синхронизация с LDAP не выполняется

**Бэкенды аутентификации (в порядке приоритета):**
1. `LDAP3Backend` - пропускает запрос (LDAP_ENABLED=false)
2. `EmailOrPhoneBackend` - **основной бэкенд** в этом режиме
3. `SuperuserOnlyBackend` - экстренный доступ для суперюзера
4. `PositionRoleBackend` - расчёт прав
5. `ModelBackend` - стандартный Django

**Требуемые настройки в .env:**
```env
LDAP_ENABLED=false
```

## Переключение между режимами

### Включение LDAP

1. В `.env` установите:
   ```env
   LDAP_ENABLED=true
   ```

2. Настройте параметры подключения к LDAP (см. выше)

3. Перезапустите Django:
   ```bash
   python manage.py runserver
   ```

4. **Важно:** Существующие пользователи с `is_ldap_managed=False` продолжат работать через БД до тех пор, пока не будут мигрированы в LDAP

### Отключение LDAP

1. В `.env` установите:
   ```env
   LDAP_ENABLED=false
   ```

2. Перезапустите Django

3. **Важно:** Пользователи с `is_ldap_managed=True` НЕ СМОГУТ войти в систему, так как их пароли хранятся в LDAP. Для восстановления доступа необходимо:
   - Установить пароль вручную: `user.set_password('new_password')`
   - Изменить флаг: `user.is_ldap_managed = False`
   - Сохранить: `user.save()`

## Миграция пользователей

### Из БД в LDAP

```python
from employees.ldap.directory_service import DirectoryService
from employees.ldap.domain.dtos import DirectoryUserDTO

# Для каждого пользователя
dto = DirectoryUserDTO(
    first_name=user.first_name,
    last_name=user.last_name,
    email=user.email,
    phone_e164=user.phone_number,
    initial_password="temporary_password",
    is_active=user.is_active,
)

service = DirectoryService()
service.create_user(dto)
# Пользователь будет создан в LDAP и помечен как is_ldap_managed=True
```

### Из LDAP в БД

```python
# Для каждого LDAP-пользователя
user.set_password('new_password')  # Устанавливаем пароль в БД
user.is_ldap_managed = False
user.save()
```

## Проверка текущего режима

В коде Django:
```python
from django.conf import settings

if settings.LDAP_ENABLED:
    print("Режим: с LDAP")
else:
    print("Режим: без LDAP")
```

В Django shell:
```bash
python manage.py shell
>>> from django.conf import settings
>>> settings.LDAP_ENABLED
True  # или False
```

## Рекомендации по безопасности

1. **Для продакшена с LDAP:**
   - Используйте LDAPS (порт 636)
   - Проверяйте сертификат CA
   - Используйте отдельную сервисную учётку с минимальными правами
   - Включите `LDAP_WRITE_ENABLED` только если нужна запись в LDAP

2. **Для продакшена без LDAP:**
   - Настройте строгие требования к паролям в Django
   - Включите двухфакторную аутентификацию
   - Регулярно аудитируйте доступы
   - Используйте `PASSWORD_HASHERS` с современными алгоритмами

3. **Для разработки:**
   - Можно отключить LDAP для упрощения разработки
   - Создавайте тестовых пользователей напрямую в БД
   - Не храните реальные LDAP-креды в репозитории

## Поддерживаемые операции

| Операция | С LDAP | Без LDAP |
|----------|--------|----------|
| Создание пользователя | LDAP → БД | БД |
| Аутентификация | LDAP | БД (Django) |
| Обновление профиля | LDAP → БД | БД |
| Смена пароля | LDAP | БД |
| Удаление пользователя | LDAP → БД | БД |
| Синхронизация групп | Да | Нет |
| Синхронизация отделов | Да | Нет |

## Устранение неполадок

### Ошибка: "LDAP_BASE_DN must be set"

**Причина:** Не настроены переменные LDAP в settings.py или .env

**Решение:**
1. Проверьте наличие в `.env`:
   ```env
   LDAP_USERS_BASE="OU=Users,OU=company,DC=robotail,DC=local"
   ```
2. Или отключите LDAP:
   ```env
   LDAP_ENABLED=false
   ```

### Ошибка: "LDAP create failed: ..."

**Причина:** Проблема подключения или прав в LDAP

**Решение:**
1. Проверьте сетевое подключение к LDAP-серверу
2. Проверьте права сервисной учётки
3. Временно отключите LDAP для продолжения работы

### Пользователи не могут войти после отключения LDAP

**Причина:** У пользователей установлен `is_ldap_managed=True`, но LDAP недоступен

**Решение:**
```python
# В Django shell
from employees.models import Employee

# Для конкретного пользователя
user = Employee.objects.get(email='user@example.com')
user.set_password('new_password')
user.is_ldap_managed = False
user.save()

# Или массово
Employee.objects.filter(is_ldap_managed=True).update(is_ldap_managed=False)
# Затем установить пароли вручную каждому
```

## Контакты

При возникновении проблем с интеграцией LDAP обращайтесь к системному администратору.
