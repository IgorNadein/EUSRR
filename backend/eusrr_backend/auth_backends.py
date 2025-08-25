# eusrr_backend/auth_backends.py
import re
from typing import Optional

from django.conf import settings
from django.contrib.auth.backends import ModelBackend
from django.db.models import Q
from django.utils import timezone
from employees.models import Employee

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


class PositionRoleBackend(ModelBackend):
    """
    Добавляет:
      - Глобальные права от активных EmployeePosition → PositionRole.permissions
      - Объектные права на Department из DepartmentRole.permissions (через EmployeeDepartment.role_fk)
    """

    def _active_positions(self, user):
        today = timezone.now().date()
        return (
            user.positions.select_related("position_role")
            .prefetch_related("position_role__permissions")
            .filter(date_from__lte=today)
            .filter(Q(date_to__isnull=True) | Q(date_to__gte=today))
        )

    def get_user_permissions(self, user, obj=None):
        # только глобальные (obj=None): соберём из активных должностей
        if not user.is_authenticated or obj is not None:
            return set()
        perms = set()
        for ep in self._active_positions(user):
            pr = ep.position_role
            if not pr:
                continue
            for p in pr.permissions.all():
                perms.add(f"{p.content_type.app_label}.{p.codename}")
        return perms

    def has_perm(self, user, perm, obj=None):
        # 1) Сначала стандартные механики Django (user.user_permissions, groups, superuser)
        if super().has_perm(user, perm, obj=obj):
            return True
        if not user.is_authenticated:
            return False

        # 2) Глобальные должности (obj=None)
        if obj is None:
            return perm in self.get_user_permissions(user)

        # 3) Объектные права на Department — смотрим роль в ЭТОМ отделе
        from employees.models import Department, EmployeeDepartment

        if isinstance(obj, Department):
            # начальнику отдела — всё
            if obj.head_id == user.id:
                return True
            link = (
                EmployeeDepartment.objects.select_related("role_fk")
                .filter(employee=user, department=obj, is_active=True)
                .first()
            )
            if not link or not link.role_fk:
                return False

            try:
                app_label, codename = perm.split(".", 1)
            except ValueError:
                return False

            return link.role_fk.permissions.filter(
                content_type__app_label=app_label, codename=codename
            ).exists()

        # для других obj вернёмся к базовой логике
        return False
