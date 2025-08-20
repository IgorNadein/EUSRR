# eusrr_backend/auth_backends.py
import re
from typing import Optional

from django.contrib.auth.backends import ModelBackend
from django.conf import settings

from employees.models import Employee  # если модель в другом месте — поправь импорт

# phonenumbers — опционально, но очень желательно: pip install phonenumbers
try:
    import phonenumbers
    from phonenumbers import PhoneNumberFormat
except Exception:
    phonenumbers = None
    PhoneNumberFormat = None

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _looks_like_email(s: str) -> bool:
    return bool(EMAIL_RE.match(s or ""))


def _normalize_phone(raw: str) -> Optional[str]:
    """
    Приводим номер к формату E.164 (+79991234567).
    Возвращаем None, если распарсить не удалось или пакет не установлен.
    """
    if not raw:
        return None
    if phonenumbers is None:
        # fallback — без нормализации
        return str(raw).strip()
    region = getattr(settings, "PHONE_DEFAULT_REGION", "RU")
    try:
        pn = phonenumbers.parse(str(raw), region)
        if not phonenumbers.is_valid_number(pn):
            return None
        return phonenumbers.format_number(pn, PhoneNumberFormat.E164)
    except Exception:
        return None


def _detect_phone_field() -> Optional[str]:
    """
    Определяем имя поля телефона в модели Employee.
    Поддерживаем распространённые варианты.
    """
    candidates = ("phone", "phone_number", "mobile", "msisdn", "tel")
    field_names = {f.name for f in Employee._meta.get_fields()}
    for name in candidates:
        if name in field_names:
            return name
    return None


PHONE_FIELD = _detect_phone_field()


class EmailOrPhoneBackend(ModelBackend):
    """
    Аутентификация по email ИЛИ по телефону (E.164) + стандартная проверка пароля.
    Пользователь должен быть активен (is_active=True) — активируйте после verify_email().
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        login = username or kwargs.get("email") or kwargs.get("phone")
        if not login or not password:
            return None

        user: Optional[Employee] = None

        # 1) Email
        if _looks_like_email(login):
            user = Employee.objects.filter(email__iexact=login).first()
        else:
            # 2) Phone
            if PHONE_FIELD:
                normalized = _normalize_phone(login)
                # сначала пробуем нормализованный E.164
                if normalized:
                    user = Employee.objects.filter(**{PHONE_FIELD: normalized}).first()
                # если не нашли — пробуем как ввёл пользователь (на случай старых данных)
                if not user:
                    raw = str(login).strip()
                    user = Employee.objects.filter(**{PHONE_FIELD: raw}).first()

        if not user:
            return None

        # допускаем логин только активных (email подтверждён → is_active=True)
        if not user.is_active:
            return None

        if user.check_password(password):
            return user
        return None
