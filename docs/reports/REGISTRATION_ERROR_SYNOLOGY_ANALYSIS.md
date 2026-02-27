# 🔴 КРИТИЧЕСКАЯ ОШИБКА: Регистрация падает с IntegrityError

**Дата:** 5 января 2026
**Статус:** 🚨 БЛОКИРУЕТ регистрацию пользователей
**Тип:** Синхронизация БД и модели - несоответствие

## 📋 Проблема

```
IntegrityError at /api/v1/auth/register/
NOT NULL constraint failed: employees_employee.synology_username
```

### Что происходит?

1. **Пользователь отправляет данные на** `/api/v1/auth/register/`
2. **Django пытается создать Employee** с помощью `Employee.objects.create()`
3. **SQLite попадает на колонки в БД**, которых НЕТ в модели Django
4. **Результат:** пустые значения для этих колонок
5. **БД отвергает:** поле `synology_username` помечено как `NOT NULL` → ошибка

## 🔍 Диагностика

### В БД (SQLite) существуют колонки:

```sql
PRAGMA table_info(employees_employee);

-- Результат grep:
(25, 'synology_user_id', 'INTEGER', 0, None, 0)
(26, 'synology_username', 'varchar(100)', 1, None, 0)  -- ❌ NOT NULL!
(27, 'synology_session_expires', 'datetime', 0, None, 0)
(28, 'synology_session_id', 'varchar(255)', 1, None, 0) -- ❌ NOT NULL!
```

**Пояснение колонок (слева направо):**
- `0` = порядковый номер
- `'synology_username'` = название колонки
- `'varchar(100)'` = тип данных
- `1` = NOT NULL constraint (1 = есть constraint, 0 = нет)
- `None` = default значение
- `0` = PRIMARY KEY flag

### В модели (employees/models.py):

```python
class Employee(AbstractUser):
    # ... другие поля ...

    # ❌ SYNOLOGY ПОЛЕЙ НЕТ!
    # synology_user_id - не определено
    # synology_username - не определено
    # synology_session_expires - не определено
    # synology_session_id - не определено
```

## 🚨 КОРНЕВАЯ ПРИЧИНА

### Сценарий что произошло:

1. **На ранней стадии разработки** были добавлены Synology поля в БД (миграция была создана)
2. **Позже эти поля были удалены из модели** Employee (вероятно, закомментированы или удалены)
3. **НО соответствующая миграция удаления никогда не была создана** (`RemoveField`)
4. **Результат:** Мисматч между:
   - ✅ Тем, что Django ожидает создать (модель)
   - ⚠️ Тем, что реально в БД (таблица с Synology полями)

### Почему ошибка происходит именно при регистрации?

Когда Django создаёт объект:
```python
emp = Employee.objects.create(
    first_name=v["first_name"],
    last_name=v["last_name"],
    email=email,
    phone_number=phone_norm,
    is_active=False,
    is_ldap_managed=False,
    # ❌ synology_username НЕ УКАЗАН (его нет в модели)
    # ❌ synology_session_id НЕ УКАЗАН (его нет в модели)
)
```

SQLite вставляет `NULL` для недостающих полей, но:
- `synology_username` имеет `NOT NULL` constraint → **ОШИБКА**
- `synology_session_id` имеет `NOT NULL` constraint → **ОШИБКА**

## ✅ РЕШЕНИЕ

### Вариант 1: Удалить поля из БД (рекомендуется)

Создать миграцию удаления:

```bash
.venv/Scripts/python manage.py makemigrations employees --empty --name remove_synology_fields
```

Затем заполнить миграцию:

```python
from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('employees', 'PREV_MIGRATION'),  # последняя миграция
    ]

    operations = [
        migrations.RemoveField(
            model_name='employee',
            name='synology_user_id',
        ),
        migrations.RemoveField(
            model_name='employee',
            name='synology_username',
        ),
        migrations.RemoveField(
            model_name='employee',
            name='synology_session_expires',
        ),
        migrations.RemoveField(
            model_name='employee',
            name='synology_session_id',
        ),
    ]
```

Затем применить:

```bash
.venv/Scripts/python manage.py migrate
```

### Вариант 2: Вернуть поля в модель

Если Synology интеграция ещё нужна, вернуть поля в модель:

```python
class Employee(AbstractUser):
    # ... другие поля ...

    synology_user_id = models.IntegerField(null=True, blank=True)
    synology_username = models.CharField(
        max_length=100,
        blank=True,
        null=True,  # ← Чтобы Django мог вставлять NULL
        verbose_name="Synology Username"
    )
    synology_session_expires = models.DateTimeField(null=True, blank=True)
    synology_session_id = models.CharField(
        max_length=255,
        blank=True,
        null=True,  # ← Чтобы Django мог вставлять NULL
        verbose_name="Synology Session ID"
    )
```

Затем создать миграцию:

```bash
.venv/Scripts/python manage.py makemigrations
```

**Внимание:** Миграция обнаружит уже существующие поля в БД, может показать `AlterField` вместо `AddField`.

### Вариант 3: Очистить и пересоздать БД (только для разработки)

```bash
rm backend/db.sqlite3
.venv/Scripts/python manage.py migrate
```

## 📊 Рекомендация

**Используйте Вариант 1** - удаление полей:

1. Synology поля очевидно не используются (они отсутствуют в коде)
2. Это чистит БД и приводит её в соответствие с моделью
3. Регистрация сразу же начнёт работать
4. Если Synology интеграция понадобится позже, её легко добавить заново

## 🔗 Связанные проблемы

Эта ошибка влияет на:
- ❌ **Регистрация пользователей** (новые пользователи не могут зарегистрироваться)
- ❌ **API endpoint** `/api/v1/auth/register/`
- ❌ **Фронт-end регистрация** (через views_auth.py)
- ✅ Всё остальное (логин, профиль) работает нормально

## 🧪 Тестирование после фикса

После удаления полей:

1. Попробовать регистрацию через API
2. Проверить, что пользователь создан в БД
3. Выполнить `python manage.py check` для валидации схемы
4. Запустить тесты регистрации

```bash
pytest tests/api/auth/test_auth_and_registration.py::test_register_success_sends_email_and_user_inactive -v
```

---

**Приоритет:** 🔴 КРИТИЧЕСКИЙ - блокирует основной функционал
**Трудозатраты:** ⚡ 5-10 минут на реализацию + 2-3 минуты на тестирование
