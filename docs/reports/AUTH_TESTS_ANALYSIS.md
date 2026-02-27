# 🔍 Подробный отчет: Проблемы с тестами аутентификации

**Дата:** 5 января 2026
**Файл:** `tests/api/auth/test_auth_and_registration.py`

## 📊 Статистика

```
✅ 8 тестов ПРОШЛИ
❌ 11 тестов ПРОВАЛЕНЫ
━━━━━━━━━━━━━━━━━━━━━
📈 Успешность: 42%
```

## 🔴 ОСНОВНАЯ ПРОБЛЕМА

### 🚨 КРИТИЧЕСКОЕ НЕСООТВЕТСТВИЕ: Модель vs Сериализатор

#### ✅ Модель Employee (models.py:162-165):
```python
gender = models.PositiveSmallIntegerField(
    "Пол", choices=GENDER_CHOICES,
    default=0,      # ✅ Есть дефолт
    blank=True      # ✅ НЕОБЯЗАТЕЛЬНОЕ
)
avatar = models.ImageField(
    "Фото", upload_to="users/avatars",
    blank=True,     # ✅ НЕОБЯЗАТЕЛЬНОЕ
    null=True       # ✅ НЕОБЯЗАТЕЛЬНОЕ
)
```

#### ❌ RegisterSerializer (serializers.py:29-67):
```python
class RegisterSerializer(serializers.Serializer):
    # ... другие поля ...

    avatar = Base64ImageField(required=True)  # ❌ ОБЯЗАТЕЛЬНОЕ (противоречие!)

    gender = serializers.ChoiceField(
        required=True,  # ❌ ОБЯЗАТЕЛЬНОЕ (противоречие!)
        choices=((1, "Мужской"), (2, "Женский")),
        error_messages={
            'required': 'Поле "Пол" обязательно для заполнения.',
        }
    )
```

**⚠️ Проблема:** Сериализатор требует поля, которые в модели **необязательны**. Это создает искусственные требования для API регистрации, не соответствующие структуре БД.

---

### Обязательные поля в RegisterSerializer

**Файл:** `backend/api/v1/employees/serializers.py` (строки 29-67)

```python
class RegisterSerializer(serializers.Serializer):
    # ... другие поля ...

    avatar = Base64ImageField(required=True)  # ❌ ОБЯЗАТЕЛЬНОЕ

    gender = serializers.ChoiceField(
        required=True,  # ❌ ОБЯЗАТЕЛЬНОЕ
        choices=((1, "Мужской"), (2, "Женский")),
        error_messages={
            'required': 'Поле "Пол" обязательно для заполнения.',
        }
    )
```

### Что отправляют тесты

**Файл:** `tests/api/auth/test_auth_and_registration.py` (строка 44)

```python
def register_payload(**overrides):
    data = {
        "first_name": "Иван",
        "last_name": "Иванов",
        "phone_number": "+79990000001",
        "email": "ivan@example.com",
        "password": "Str0ngPass!",
        "birth_date": "1990-01-01",
        "telegram": "@ivan",
        # ❌ НЕТ avatar
        # ❌ НЕТ gender
    }
    return data
```

## 📝 Ошибки валидации

Все 11 проваленных тестов получают одинаковую ошибку:

```python
[REGISTER] Validation errors: {
    'avatar': [ErrorDetail(string='Ни одного файла не было отправлено.', code='required')],
    'gender': [ErrorDetail(string='Поле "Пол" обязательно для заполнения.', code='required')]
}
```

**HTTP статус:** `400 Bad Request` (ожидается `201 Created`)

## 📋 Детальный список проваленных тестов

### 1. ❌ test_register_success_sends_email_and_user_inactive
**Цель:** Проверка успешной регистрации с отправкой email
**Проблема:** Не передает `avatar` и `gender`

### 2. ❌ test_register_duplicate_email_phone
**Цель:** Проверка дубликатов email/phone
**Проблема:** Не может создать первого пользователя (нет `avatar`, `gender`)

### 3. ❌ test_register_accepts_optional_fields
**Цель:** Проверка опциональных полей (patronymic, whatsapp)
**Проблема:** Передает `gender=1`, но **не передает `avatar`**

```python
# Частичное исправление в тесте:
payload = {
    ...
    "patronymic": "Петрович",
    "gender": 1,  # ✅ Есть
    "whatsapp": "+79995550011",
    # ❌ Нет avatar
}
```

### 4-11. ❌ Тесты верификации email и логина
Все зависят от `register()` функции, которая не передает обязательные поля:
- `test_verify_email_success_activates_user`
- `test_verify_email_wrong_code`
- `test_resend_email_sends_new_code_and_old_becomes_invalid`
- `test_verify_expired_more_than_5_minutes_deletes_account`
- `test_login_by_email_denied_before_verify`
- `test_login_by_email_allowed_after_verify`
- `test_login_by_phone_allowed_after_verify`
- `test_login_wrong_password`

## ✅ Успешные тесты (8 штук)

Эти тесты проверяют **валидацию отсутствующих полей**, поэтому они ожидают `400 Bad Request`:

1. ✅ `test_register_missing_required_field[first_name]`
2. ✅ `test_register_missing_required_field[last_name]`
3. ✅ `test_register_missing_required_field[phone_number]`
4. ✅ `test_register_missing_required_field[email]`
5. ✅ `test_register_missing_required_field[password]`
6. ✅ `test_register_missing_required_field[birth_date]`
7. ✅ `test_register_requires_at_least_one_contact`
8. ✅ `test_register_birth_date_must_be_valid_date`

**Почему они проходят?** Они ожидают ошибку валидации и получают её (хоть и по другим причинам).

## 🔍 Анализ причин

### Вопрос 1: Почему `avatar` и `gender` обязательные?

Вероятно, это бизнес-требование:
- **Avatar:** Для корпоративной системы важно иметь фото сотрудника
- **Gender:** Для HR-целей и документооборота

### Вопрос 2: Должны ли они быть обязательными при регистрации?

**Два подхода:**

#### Вариант A: Сделать опциональными для регистрации
```python
avatar = Base64ImageField(required=False, allow_null=True)
gender = serializers.ChoiceField(
    required=False,
    allow_null=True,
    choices=((1, "Мужской"), (2, "Женской")),
)
```

**Плюсы:** Упрощает регистрацию
**Минусы:** Может нарушить бизнес-логику

#### Вариант B: Исправить тесты (добавить поля)
```python
def register_payload(**overrides):
    data = {
        "first_name": "Иван",
        "last_name": "Иванов",
        "phone_number": "+79990000001",
        "email": "ivan@example.com",
        "password": "Str0ngPass!",
        "birth_date": "1990-01-01",
        "telegram": "@ivan",
        "avatar": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",  # 1x1 прозрачный PNG
        "gender": 1,  # Мужской
    }
    return data
```

**Плюсы:** Соответствует текущей бизнес-логике
**Минусы:** Нужно обновить все тесты

## 🎯 Рекомендации

### ✅ РЕКОМЕНДУЕМОЕ РЕШЕНИЕ: Исправить сериализатор

**Причина:** Модель Employee позволяет `avatar` и `gender` быть необязательными. Сериализатор должен соответствовать модели.

**Изменение в `backend/api/v1/employees/serializers.py`:**

```python
class RegisterSerializer(serializers.Serializer):
    # ... другие поля ...

    # Было:
    # avatar = Base64ImageField(required=True)
    # gender = serializers.ChoiceField(required=True, ...)

    # Стало:
    avatar = Base64ImageField(required=False, allow_null=True)  # ✅ Соответствует модели

    gender = serializers.ChoiceField(
        required=False,  # ✅ Соответствует модели
        choices=((1, "Мужской"), (2, "Женский"), (0, "Не указано")),
        default=0,  # ✅ Соответствует модели
        error_messages={
            'invalid_choice': 'Выберите корректное значение пола.',
        }
    )
```

**Преимущества:**
- ✅ Соответствие архитектуре (модель → сериализатор → API)
- ✅ Упрощение регистрации для пользователей
- ✅ Тесты пройдут без изменений
- ✅ Возможность заполнить профиль позже

---

### Альтернатива: Обновить тесты (НЕ рекомендуется)

**Обновить `register_payload()` в тестах:**

```python
def register_payload(**overrides):
    # Минимальное base64 изображение (1x1 пиксель)
    MINIMAL_AVATAR = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )

    data = {
        "first_name": "Иван",
        "last_name": "Иванов",
        "phone_number": "+79990000001",
        "email": "ivan@example.com",
        "password": "Str0ngPass!",
        "birth_date": "1990-01-01",
        "telegram": "@ivan",
        "avatar": MINIMAL_AVATAR,  # ✅ Добавлено
        "gender": 1,  # ✅ Добавлено (1 = Мужской)
    }
    data.update(overrides)
    return data
```

**Недостатки этого подхода:**
- ❌ Не решает архитектурную проблему (несоответствие модели и сериализатора)
- ❌ Усложняет регистрацию в production (требует обязательную загрузку аватара)
- ❌ Требует изменений в тестах вместо исправления кода

---

### Долгосрочное решение (архитектурное)

**Вариант 1:** Разделить регистрацию на этапы
1. **Этап 1:** Email, пароль, базовая информация
2. **Этап 2:** После верификации email → заполнение профиля (avatar, gender)

**Вариант 2:** Сделать поля условно обязательными
- При регистрации: опциональные
- При активации аккаунта: требуется заполнить
- При первом входе: напоминание заполнить

## 📊 Влияние на production

### ⚠️ Текущая ситуация

Если `avatar` и `gender` обязательны:
- Фронтенд **должен** отправлять эти поля при регистрации
- Если фронтенд не отправляет → регистрация не работает
- Пользователи не могут зарегистрироваться

### ✅ Вопросы для проверки

1. **Работает ли регистрация на production?**
   - Если да → значит фронтенд корректно отправляет поля
   - Если нет → критическая ошибка

2. **Как фронтенд отправляет avatar?**
   - Base64 строка
   - File upload
   - URL изображения

3. **Обязателен ли gender в бизнес-логике?**
   - Требование HR
   - Требование законодательства
   - Опционально

## 🚀 Заключение

**Основная проблема:** Рассинхронизация между тестами и сериализатором

- **Сериализатор** требует `avatar` и `gender`
- **Тесты** не передают эти поля

**Решение:** Нужно привести в соответствие:
- ЛИБО сделать поля опциональными в сериализаторе
- ЛИБО добавить поля в тестовые данные

**Рекомендация:** Обновить тесты (добавить `avatar` и `gender`), так как это, вероятно, соответствует реальному поведению фронтенда.
