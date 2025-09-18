# eusrr_backend/auth_backends.py
from __future__ import annotations

import re
from typing import Optional, Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission
from employees.models import Department, Employee, EmployeeDepartment
from django.http import HttpRequest

from ldap3 import ALL, SUBTREE, Connection, Server

UserModel = get_user_model()

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


class LDAP3Backend(ModelBackend):
    """LDAP-аутентификация через ldap3, поддержка логина по email или телефону.

    Правила сопоставления:
      • Входная строка (identifier) может быть email или телефоном.
      • LDAP-фильтр ищет по uid/mail и, при наличии E.164, по mobile/telephoneNumber.
      • В БД ищем пользователя прежде всего по email из LDAP (USERNAME_FIELD='email').
        Если email отсутствует — ищем по телефону (E.164) в поле PHONE_FIELD.
      • Автосоздание выключено по умолчанию (LDAP_AUTO_CREATE=False), чтобы не плодить записи.
        Включайте только если уверены, что сможете заполнить обязательные поля модели.

    Безопасность:
      • Если локальный пользователь найден, но is_active=False и LDAP_RESPECT_IS_ACTIVE=True — не пускаем.
      • Пароль в БД не используем/не трогаем — проверка идёт через LDAP bind.
    """

    def authenticate(
        self,
        request,
        username: str | None = None,
        password: str | None = None,
        **kwargs,
    ) -> Optional[UserModel]:
        """Аутентифицирует по identifier (email/телефон) и паролю.

        Args:
            request: HttpRequest или None.
            username: Идентификатор (email/телефон/uid — что передал фронт).
            password: Пароль.

        Returns:
            Optional[UserModel]: Пользователь при успехе, иначе None.

        Raises:
            Ничего не бросает — при ошибке/несовпадении возвращает None.
        """
        identifier = (
            username
            or kwargs.get("email")
            or kwargs.get("login")
            or kwargs.get(getattr(UserModel, "USERNAME_FIELD", "email"))
        )
        if (
            not identifier
            or not password
            or not getattr(settings, "LDAP_ENABLED", False)
        ):
            return None
        if Connection is None or Server is None:
            return None

        # Подготовим данные для фильтра: email/сырой телефон/E.164
        raw = str(identifier).strip()
        is_email = _looks_like_email(raw)
        e164 = _normalize_phone(raw)  # ваша утилита; может вернуть None

        uri = getattr(settings, "LDAP_URI", None)
        user_base = getattr(settings, "LDAP_USER_BASE", None)
        bind_dn = getattr(settings, "LDAP_BIND_DN", "")
        bind_pw = getattr(settings, "LDAP_BIND_PASSWORD", "")
        tpl = getattr(
            settings, "LDAP_USER_FILTER", "(|(uid={username})(mail={username}))"
        )
        phone_attrs: tuple[str, ...] = tuple(
            getattr(settings, "LDAP_PHONE_ATTRS", ("mobile", "telephoneNumber"))
        )
        if not uri or not user_base:
            return None

        def _esc(v: str) -> str:
            # Простейший экранизатор для LDAP фильтра
            return (
                v.replace("\\", "\\5c")
                .replace("*", "\\2a")
                .replace("(", "\\28")
                .replace(")", "\\29")
                .replace("\x00", "")
            )

        server = Server(uri, get_info=ALL)
        try:
            conn = (
                Connection(server, user=bind_dn, password=bind_pw, auto_bind=True)
                if (bind_dn or bind_pw)
                else Connection(server, auto_bind=True)
            )
        except Exception:
            return None

        # Собираем расширенный фильтр:
        #   из шаблона (uid/mail) + по телефону (если есть e164)
        base_filter = tpl.format(username=_esc(raw))
        phone_filter = ""
        if e164:
            pf = "".join(f"({attr}={_esc(e164)})" for attr in phone_attrs)
            phone_filter = f"(|{pf})"
        ldap_filter = f"(|{base_filter}{phone_filter})" if phone_filter else base_filter

        try:
            ok = conn.search(
                search_base=user_base,
                search_filter=ldap_filter,
                search_scope=SUBTREE,
                attributes=["*"],
                size_limit=1,
            )
            if not ok or not conn.entries:
                conn.unbind()
                return None
            entry = conn.entries[0]
            user_dn = entry.entry_dn
        except Exception:
            conn.unbind()
            return None

        # Проверяем пароль bind'ом пользователя
        try:
            check = Connection(server, user=user_dn, password=password, auto_bind=True)
            check.unbind()
        except Exception:
            conn.unbind()
            return None

        # Достаём атрибуты
        get = self._attr
        first_name = (
            get(entry, getattr(settings, "LDAP_ATTR_GIVENNAME", "givenName")) or ""
        )
        last_name = get(entry, getattr(settings, "LDAP_ATTR_SN", "sn")) or ""
        email = (get(entry, getattr(settings, "LDAP_ATTR_MAIL", "mail")) or "").lower()
        phone_val = get(entry, getattr(settings, "LDAP_ATTR_PHONE", "telephoneNumber"))
        phone_e164 = _normalize_phone(phone_val) if phone_val else None

        # 1) Ищем локального пользователя — сначала по email
        user = None
        if email:
            user = UserModel.objects.filter(email__iexact=email).first()

        # 2) Если не нашли и есть телефон — ищем по телефону
        if user is None and PHONE_FIELD and phone_e164:
            user = UserModel.objects.filter(**{PHONE_FIELD: phone_e164}).first()

        # Уважать локальную блокировку
        if user and getattr(settings, "LDAP_RESPECT_IS_ACTIVE", True):
            if hasattr(user, "is_active") and not user.is_active:
                conn.unbind()
                return None

        # Авто-создание — только если явно разрешено И хватает полей
        if user is None and getattr(settings, "LDAP_AUTO_CREATE", False):
            payload: dict[str, Any] = {}
            if hasattr(UserModel, "email") and email:
                payload["email"] = email
            if PHONE_FIELD and phone_e164:
                payload[PHONE_FIELD] = phone_e164
            if hasattr(UserModel, "first_name"):
                payload["first_name"] = first_name
            if hasattr(UserModel, "last_name"):
                payload["last_name"] = last_name

            # Проверим, что заполняем ключевые поля модели
            key_field = getattr(UserModel, "USERNAME_FIELD", "email")
            key_ok = (key_field != "email") or bool(payload.get("email"))
            phone_ok = (not PHONE_FIELD) or (PHONE_FIELD in payload)
            if key_ok and phone_ok:
                user = UserModel.objects.create(**payload)
                if hasattr(user, "is_active") and user.is_active is False:
                    user.is_active = True
                    user.save(update_fields=["is_active"])
            else:
                conn.unbind()
                return None  # не рискуем плодить «пустышки»

        # Лёгкий апдейт профиля (без пароля)
        if user:
            changed, updates = False, []
            if hasattr(user, "first_name") and user.first_name != first_name:
                user.first_name = first_name
                changed = True
                updates.append("first_name")
            if hasattr(user, "last_name") and user.last_name != last_name:
                user.last_name = last_name
                changed = True
                updates.append("last_name")
            if email and hasattr(user, "email") and (user.email or "").lower() != email:
                user.email = email
                changed = True
                updates.append("email")
            if (
                PHONE_FIELD
                and phone_e164
                and getattr(user, PHONE_FIELD, None) != phone_e164
            ):
                setattr(user, PHONE_FIELD, phone_e164)
                changed = True
                updates.append(PHONE_FIELD)
            if changed:
                user.save(update_fields=list(set(updates)) or None)

        conn.unbind()
        return user

    @staticmethod
    def _attr(entry, name: str) -> Optional[str]:
        """Возвращает первое строковое значение атрибута LDAP.

        Args:
            entry: ldap3 Entry.
            name (str): Имя атрибута.

        Returns:
            Optional[str]: Значение или None.

        Raises:
            None
        """
        try:
            val = getattr(entry, name, None)
            raw = getattr(val, "value", None)
            if raw is None:
                return None
            if isinstance(raw, (list, tuple)):
                return str(raw[0]).strip() if raw else None
            return str(raw).strip()
        except Exception:
            return None


class SuperuserOnlyBackend(ModelBackend):
    """Локальный фолбэк-бэкенд: пускает только суперюзера.

    Используется как «break-glass» при отказе LDAP. Любые не-суперюзеры
    не проходят локальную аутентификацию, даже при корректном пароле.

    Это устраняет локальный фолбэк для рядовых сотрудников (все они идут через LDAP),
    не ломая админ-доступ на случай недоступности каталога.
    """

    def authenticate(
        self,
        request: HttpRequest | None,
        username: str | None = None,
        password: str | None = None,
        **kwargs,
    ) -> Optional[UserModel]:
        """Аутентифицирует только суперюзера через локальную БД.

        Args:
            request: HttpRequest или None.
            username: Идентификатор (для вашей модели это email).
            password: Пароль.

        Returns:
            Optional[UserModel]: Пользователь, если это суперюзер и пароль верен; иначе None.

        Raises:
            Ничего не выбрасывает наружу — при неуспехе возвращает None.
        """
        user = super().authenticate(
            request, username=username, password=password, **kwargs
        )
        if user and getattr(user, "is_superuser", False):
            return user
        return None


# class EmailOrPhoneBackend(ModelBackend):
#     """
#     Аутентификация по email ИЛИ по телефону (E.164) + стандартная проверка пароля.
#     Пользователь должен быть активен (is_active=True) — активируйте после verify_email().
#     """

#     def authenticate(self, request, username=None, password=None, **kwargs):
#         login = username or kwargs.get("email") or kwargs.get("phone")
#         if not login or not password:
#             return None

#         user: Optional[Employee] = None

#         # 1) Email
#         if _looks_like_email(login):
#             user = Employee.objects.filter(email__iexact=login).first()
#         else:
#             # 2) Phone
#             if PHONE_FIELD:
#                 normalized = _normalize_phone(login)
#                 # сначала пробуем нормализованный E.164
#                 if normalized:
#                     user = Employee.objects.filter(**{PHONE_FIELD: normalized}).first()
#                 # если не нашли — пробуем как ввёл пользователь (на случай старых данных)
#                 if not user:
#                     raw = str(login).strip()
#                     user = Employee.objects.filter(**{PHONE_FIELD: raw}).first()

#         if not user:
#             return None

#         # допускаем логин только активных (email подтверждён → is_active=True)
#         if not user.is_active:
#             return None

#         if user.check_password(password):
#             return user
#         return None


class PositionRoleBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        """Этот бэкенд не участвует в аутентификации, только в расчёте прав."""
        return None

    def get_all_permissions(self, user_obj, obj=None):
        perms = super().get_all_permissions(user_obj, obj)
        if not getattr(user_obj, "is_authenticated", False) or obj is not None:
            return perms

        # 1) Глобальные права от должности — оставить
        pos = getattr(user_obj, "position", None)
        if pos:
            pos_perms = (
                Permission.objects.filter(group__positions=pos)
                .select_related("content_type")
                .distinct()
            )
            perms |= {f"{p.content_type.app_label}.{p.codename}" for p in pos_perms}

        # 2) ⚠️ НЕ добавляем сюда пермишены из DepartmentRole.
        # Они должны проверяться только на уровне конкретного Department в has_perm(..., obj=dept)

        return perms

    def has_perm(self, user_obj, perm, obj=None):
        # стандартная ветка + суперюзер/группы/пользовательские
        if super().has_perm(user_obj, perm, obj=obj):
            return True
        if not getattr(user_obj, "is_authenticated", False):
            return False

        if obj is None:
            # добавить глобальные (от должности)
            return perm in self.get_all_permissions(user_obj)

        # Объектные права на Department — как у вас
        if isinstance(obj, Department):
            if obj.head_id == user_obj.id:
                return True
            link = (
                EmployeeDepartment.objects.select_related("role")
                .filter(employee=user_obj, department=obj, is_active=True)
                .first()
            )
            if not (link and link.role_id):
                return False
            app_label, sep, codename = perm.partition(".")
            if not sep:
                return False
            return link.role.scoped_permissions.filter(
                content_type__app_label=app_label,
                codename=codename,
            ).exists()

        return False
