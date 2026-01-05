# 🔍 Анализ: Восстановление пароля не отправляет email

**Дата:** 5 января 2026  
**Статус:** ⚠️ Email не отправляется при восстановлении пароля  
**Тип:** Логика фильтрации пользователей в Django PasswordResetForm

## 📋 Проблема

Пользователи жалуются, что при нажатии кнопки "Забыли пароль?" не приходит письмо на почту.

### Логи системы:

```
[INFO] 08:52:00 HTTP GET /auth/password-reset/ 200           ← Открыта форма
[INFO] 08:52:24 HTTP POST /auth/password-reset/ 302         ← Форма отправлена
[INFO] 08:52:24 HTTP GET /auth/password-reset/done/ 200     ← Показана страница "готово"
```

**Проблема:** Нет записей об отправке email! Ожидалось что-то вроде:
```
[INFO] Email отправлен: password_reset → user@example.com
```

## 🔍 Исследование

### Код восстановления пароля

**Используется:** Django встроенный `PasswordResetView` и `PasswordResetForm`

[employees/views_auth.py](backend/employees/views_auth.py#L217-L222):
```python
class PasswordResetView(DjangoPasswordResetView):
    template_name = "auth/password_reset.html"
    email_template_name = "auth/password_reset_email.txt"
    subject_template_name = "auth/password_reset_subject.txt"
    success_url = "/auth/password-reset/done/"
```

### Django PasswordResetForm.get_users()

Проверил исходный код Django `PasswordResetForm`:

```python
def get_users(self, email):
    """Given an email, return matching user(s) who should receive a reset.
    
    This allows subclasses to more easily customize the default policies
    that prevent inactive users and users with unusable passwords from
    resetting their password.
    """
    email_field_name = UserModel.get_email_field_name()
    active_users = UserModel._default_manager.filter(
        **{
            "%s__iexact" % email_field_name: email,
            "is_active": True,  # ← 🚨 ФИЛЬТР НА АКТИВНЫХ!
        }
    )
    return (
        u
        for u in active_users
        if u.has_usable_password()
        and _unicode_ci_compare(email, getattr(u, email_field_name))
    )
```

**Ключевая строка:** `"is_active": True`

### Логика регистрации в EUSRR

[api/v1/employees/views.py](backend/api/v1/employees/views.py#L473-L477):
```python
# Режим без LDAP: создаём пользователя напрямую в БД
emp = Employee.objects.create(
    first_name=v["first_name"],
    last_name=v["last_name"],
    email=email,
    phone_number=phone_norm,
    is_active=False,  # ← не активен до верификации email
    is_ldap_managed=False,
)
```

Пользователь становится активным только после верификации email:

[api/v1/employees/views.py](backend/api/v1/employees/views.py#L1778-L1788):
```python
# Верификация email
emp = Employee.objects.filter(email__iexact=email).first()
# ... проверка кода ...

# Активируем пользователя
emp.is_active = True  # ← Активируем
emp.email_verified = True
emp.save(update_fields=["is_active", "email_verified", "email_activation_code"])
```

## 🎯 КОРНЕВАЯ ПРИЧИНА

### Сценарий 1: Незаверифицированный пользователь

1. **Пользователь регистрируется** → `is_active=False`, `email_verified=False`
2. **НЕ верифицирует email** (не ввел код из письма)
3. **Пытается восстановить пароль**
4. Django `PasswordResetForm.get_users()` фильтрует: `is_active=True`
5. **Пользователь не найден** → email НЕ отправляется
6. Но форма показывает "done" (чтобы не раскрывать существование аккаунта)

### Сценарий 2: Верифицированный пользователь

1. **Пользователь регистрируется** → `is_active=False`, `email_verified=False`
2. **Верифицирует email** → `is_active=True`, `email_verified=True`
3. **Пытается восстановить пароль**
4. Django `PasswordResetForm.get_users()` находит пользователя
5. **Email отправляется** ✅

## 📊 Диагностика

### Проверка текущего статуса пользователей:

```bash
.venv/Scripts/python manage.py shell
```

```python
from employees.models import Employee

# Незаверифицированные пользователи
unverified = Employee.objects.filter(
    is_active=False,
    email_verified=False
).count()
print(f"Незаверифицированных: {unverified}")

# Заверифицированные пользователи
verified = Employee.objects.filter(
    is_active=True,
    email_verified=True
).count()
print(f"Заверифицированных: {verified}")

# Проблемные: email verified, но is_active=False (не должны существовать)
problem = Employee.objects.filter(
    is_active=False,
    email_verified=True
).count()
print(f"Проблемных: {problem}")
```

### Тест восстановления пароля:

```bash
.venv/Scripts/python manage.py shell
```

```python
from django.contrib.auth.forms import PasswordResetForm
from employees.models import Employee

# Создать тестового неактивного пользователя
test_user = Employee.objects.create(
    email="test@example.com",
    first_name="Test",
    last_name="User",
    phone_number="+79990001234",
    is_active=False,  # НЕ активен
    telegram="@test"
)
test_user.set_password("password123")
test_user.save()

# Попытка сброса пароля
form = PasswordResetForm(data={"email": "test@example.com"})
if form.is_valid():
    users = list(form.get_users(form.cleaned_data["email"]))
    print(f"Найдено пользователей: {len(users)}")  # ← Должно быть 0!
else:
    print("Форма невалидна")

# Очистка
test_user.delete()
```

**Ожидаемый результат:** `Найдено пользователей: 0` для неактивного пользователя.

## ✅ РЕШЕНИЯ

### Вариант 1: Переопределить get_users() (рекомендуется)

Создать кастомную форму, которая позволяет сбрасывать пароль незаверифицированным пользователям:

**Создать:** `backend/employees/forms_auth.py` (дополнение)

```python
from django.contrib.auth.forms import PasswordResetForm as DjangoPasswordResetForm
from django.contrib.auth import get_user_model

class CustomPasswordResetForm(DjangoPasswordResetForm):
    """Форма сброса пароля, разрешающая сброс для неактивных пользователей"""
    
    def get_users(self, email):
        """Находит пользователей по email, включая неактивных.
        
        Отличие от Django: не фильтрует по is_active=True,
        чтобы пользователи могли восстановить пароль до верификации email.
        """
        UserModel = get_user_model()
        email_field_name = UserModel.get_email_field_name()
        
        # Убираем фильтр is_active=True
        users = UserModel._default_manager.filter(
            **{f"{email_field_name}__iexact": email}
        )
        
        return (
            u for u in users
            if u.has_usable_password()
            and u.email.lower() == email.lower()
        )
```

**Обновить:** `backend/employees/views_auth.py`

```python
from .forms_auth import CustomPasswordResetForm

class PasswordResetView(DjangoPasswordResetView):
    template_name = "auth/password_reset.html"
    email_template_name = "auth/password_reset_email.txt"
    subject_template_name = "auth/password_reset_subject.txt"
    success_url = "/auth/password-reset/done/"
    form_class = CustomPasswordResetForm  # ← Использовать кастомную форму
```

**Преимущества:**
- ✅ Пользователи могут восстановить пароль до верификации email
- ✅ Стандартное поведение Django, просто без фильтра `is_active`
- ✅ Безопасно (форма все равно не раскрывает существование аккаунта)

**Недостатки:**
- ⚠️ Пользователи без верификации email могут получить доступ

### Вариант 2: Активировать при регистрации

Изменить логику: `is_active=True` сразу, но блокировать вход через middleware до верификации.

**Изменить:** `backend/api/v1/employees/views.py`

```python
emp = Employee.objects.create(
    # ...
    is_active=True,  # ← Активен сразу
    email_verified=False,  # ← Но email не подтвержден
    is_ldap_managed=False,
)
```

**Создать middleware:** `backend/eusrr_backend/middleware.py` (дополнение)

```python
class EmailVerificationRequiredMiddleware:
    """Блокирует доступ пользователям без верификации email"""
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.user.is_authenticated:
            if not request.user.email_verified:
                # Разрешить только страницы верификации
                allowed = [
                    '/auth/verify-email/',
                    '/auth/resend-email/',
                    '/auth/logout/',
                ]
                if not any(request.path.startswith(p) for p in allowed):
                    return redirect('auth_front:verify_email')
        
        return self.get_response(request)
```

**Преимущества:**
- ✅ Восстановление пароля работает для всех
- ✅ Безопасность через middleware

**Недостатки:**
- ⚠️ Более сложная логика
- ⚠️ Требует тщательного тестирования

### Вариант 3: Разрешить вход без верификации (НЕ рекомендуется)

Просто убрать требование верификации email вообще.

**Недостатки:**
- ❌ Небезопасно (фейковые email)
- ❌ Не соответствует логике системы

## 🧪 Тестирование после фикса

### 1. Тест незаверифицированного пользователя:

```python
# 1. Создать пользователя (is_active=False)
# 2. Попытаться восстановить пароль
# 3. Проверить что email отправлен
# 4. Перейти по ссылке из письма
# 5. Установить новый пароль
# 6. Войти с новым паролем
```

### 2. Тест заверифицированного пользователя:

```python
# 1. Создать пользователя и верифицировать email
# 2. Попытаться восстановить пароль
# 3. Проверить что email отправлен
# 4. Установить новый пароль
# 5. Войти
```

## 📈 Дополнительные проверки

### Настройки EMAIL

Проверить [settings.py](backend/eusrr_backend/settings.py#L233-L246):

```python
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.yandex.ru'
EMAIL_PORT = 465
EMAIL_HOST_USER = 'robotail-info@yandex.ru'
EMAIL_HOST_PASSWORD = '***'  # Проверить что пароль валиден
EMAIL_USE_SSL = True
```

**Тест отправки email:**

```bash
.venv/Scripts/python manage.py shell
```

```python
from django.core.mail import send_mail

send_mail(
    'Test Subject',
    'Test Message',
    'robotail-info@yandex.ru',
    ['recipient@example.com'],
    fail_silently=False,
)
# Если ошибка → проверить настройки SMTP
```

### Шаблоны писем

Проверить существование:
- ✅ `backend/templates/auth/password_reset_email.txt`
- ✅ `backend/templates/auth/password_reset_subject.txt`

## 🎯 Рекомендация

**Использовать Вариант 1** - переопределить `get_users()`:

1. Минимальные изменения кода
2. Решает проблему напрямую
3. Безопасно (не раскрывает существование аккаунтов)
4. Пользователи смогут восстановить пароль в любом статусе

**Дополнительно:** Добавить в письмо восстановления пароля ссылку на верификацию email, если он не подтвержден.

---

**Приоритет:** 🔴 ВЫСОКИЙ - пользователи не могут восстановить доступ  
**Трудозатраты:** ⚡ 10-15 минут на реализацию Варианта 1
