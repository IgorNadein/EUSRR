# eusrr_backend/auth_backends.py
from __future__ import annotations

import logging
import re
from typing import Any, List, Optional, Tuple

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend
from django.contrib.auth.models import Permission
from django.http import HttpRequest
from django.utils import timezone
from employees.ldap.utils.text_utils import esc_filter
from employees.models import Department, Employee, EmployeeDepartment
from employees.utils import _normalize_phone
from ldap3 import SUBTREE, Connection, Server
from ldap3.core.exceptions import LDAPBindError, LDAPSocketOpenError

logger = logging.getLogger(__name__)

UserModel = get_user_model()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _looks_like_email(s: str) -> bool:
    return bool(EMAIL_RE.match(s or ""))


def _model_has_field(model, field_name: str) -> bool:
    """Проверяет наличие поля модели по имени (по _meta)."""
    return any(getattr(f, "name", None) == field_name for f in model._meta.get_fields())


_DEFAULT_PHONE_FIELD = getattr(settings, "AUTH_PHONE_FIELD", "phone_number")
PHONE_FIELD: Optional[str] = (
    _DEFAULT_PHONE_FIELD if _model_has_field(UserModel, _DEFAULT_PHONE_FIELD) else None
)


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


class LDAP3Backend(ModelBackend):
    """LDAP-аутентификация через ldap3 с логином по email/телефону/uid.

    Особенности:
        * Поиск DN сервисной учёткой (service bind), затем проверка пароля user bind.
        * Автосоздание локального пользователя (опционально).
        * Лёгкая синхронизация профиля (имя/фамилия/email/телефон/DN/GUID).

    Безопасность:
        * Пароли не логируются.
        * Рекомендуется LDAPS/StartTLS с проверкой сертификата.

    """

    def authenticate(
        self,
        request,
        username: Optional[str] = None,
        password: Optional[str] = None,
        **kwargs: Any,
    ):
        """Аутентифицирует пользователя через LDAP/AD.

        Логика:
            1) Валидирует входные данные и настройки.
            2) Service bind -> поиск записи пользователя (DN) по идентификатору/телефону.
            3) User bind -> проверка пароля.
            4) Поиск/создание локального пользователя и лёгкая синхронизация профиля.

        Args:
            request: Django HttpRequest или None.
            username: Идентификатор (может быть email/телефон/uid).
            password: Пароль пользователя.
            **kwargs: Могут содержать email/login/USERNAME_FIELD.

        Returns:
            User | None: Аутентифицированный пользователь или None при неудаче.

        Raises:
            None: Метод перехватывает ошибки LDAP/сети и возвращает None при сбое.
        """
        identifier = (
            (username or "")
            or (kwargs.get("email") or "")
            or (kwargs.get("login") or "")
            or (kwargs.get(getattr(UserModel, "USERNAME_FIELD", "email")) or "")
        ).strip()

        logger.debug(
            "LDAP3Backend.authenticate called: identifier_provided=%s, password_provided=%s, LDAP_ENABLED=%s",
            bool(identifier),
            bool(password),
            getattr(settings, "LDAP_ENABLED", False),
        )

        if (
            not identifier
            or not password
            or not getattr(settings, "LDAP_ENABLED", False)
        ):
            logger.debug("Fast-exit: identifier/password missing or LDAP disabled")
            return None

        uri = getattr(settings, "LDAP_URI", "")
        user_base = getattr(settings, "LDAP_USERS_AUTH", None) or getattr(
            settings, "LDAP_USER_BASE", None
        )
        bind_dn = getattr(settings, "LDAP_BIND_DN", "")
        bind_pw = getattr(settings, "LDAP_BIND_PASSWORD", "")

        base_tpl = getattr(
            settings,
            "LDAP_USER_FILTER",
            "(|(uid={username})(mail={username}))",
        )
        phone_attrs: Tuple[str, ...] = tuple(
            getattr(settings, "LDAP_PHONE_ATTRS", ("mobile", "telephoneNumber"))
        )

        if not uri or not user_base:
            logger.warning("Fast-exit: LDAP_URI or LDAP_USERS_AUTH not configured")
            return None

        raw = identifier
        is_email = _looks_like_email(raw)
        e164 = _normalize_phone(raw)
        logger.debug(
            "Identifier parse: is_email=%s, normalized_phone=%s", is_email, e164
        )

        # --- Service bind & search ---
        # Важно: используем get_info=NONE для скорости/минимума утечек.
        server = Server(uri)  # get_info=NONE по умолчанию
        svc_conn: Optional[Connection] = None
        try:
            logger.debug("Service bind: connecting...")
            if bind_dn and bind_pw:
                svc_conn = Connection(
                    server,
                    user=bind_dn,
                    password=bind_pw,
                    auto_bind=True,
                    receive_timeout=30,
                )
                logger.debug("Service bind OK (bind_dn)")
            else:
                svc_conn = Connection(server, auto_bind=True, receive_timeout=30)
                logger.debug("Service bind OK (anonymous/simple)")

            # Базовый объектный фильтр (по умолчанию — пользователи AD)
            base_object_filter = getattr(
                settings,
                "LDAP_OBJECT_FILTER",
                "(&(objectCategory=person)(objectClass=user))",
            )

            # Фильтр по идентификатору
            if "{username}" in base_tpl:
                id_filter = base_tpl.format(username=esc_filter(raw))
                logger.debug("Using configured ID filter: %s", id_filter)
            else:
                base_object_filter = base_tpl  # админ дал базовый объектный фильтр
                if is_email:
                    id_attrs = getattr(
                        settings,
                        "LDAP_LOGIN_MAIL_ATTRS",
                        ("mail", "userPrincipalName"),
                    )
                else:
                    id_attrs = getattr(
                        settings,
                        "LDAP_LOGIN_UID_ATTRS",
                        ("uid", "sAMAccountName"),
                    )
                id_filter = (
                    "(|" + "".join(f"({a}={esc_filter(raw)})" for a in id_attrs) + ")"
                )
                logger.debug("Built default ID filter: %s", id_filter)

            phone_filter = ""
            if e164:
                phone_filter = (
                    "(|"
                    + "".join(f"({attr}={esc_filter(e164)})" for attr in phone_attrs)
                    + ")"
                )
                logger.debug("Built phone filter: %s", phone_filter)

            # (& base_object (| id_filter phone_filter?))
            if phone_filter:
                ldap_filter = f"(&{base_object_filter}(|{id_filter}{phone_filter}))"
            else:
                ldap_filter = f"(&{base_object_filter}{id_filter})"
            logger.debug("FINAL LDAP search filter=%s", ldap_filter)

            ok = svc_conn.search(
                search_base=user_base,
                search_filter=ldap_filter,
                search_scope=SUBTREE,
                attributes=[
                    getattr(settings, "LDAP_ATTR_GIVENNAME", "givenName"),
                    getattr(settings, "LDAP_ATTR_SN", "sn"),
                    getattr(settings, "LDAP_ATTR_MAIL", "mail"),
                    "telephoneNumber",
                    "mobile",
                    "userAccountControl",
                    "objectGUID",
                    "userPrincipalName",
                ],
                size_limit=1,
            )
            entries_count = len(svc_conn.entries) if svc_conn else 0
            logger.debug("Search ok=%s entries=%s", ok, entries_count)
            if not ok or not svc_conn.entries:
                logger.info("No entries found -> auth failed")
                return None

            entry = svc_conn.entries[0]
            user_dn: str = str(entry.entry_dn)
            logger.debug("Found DN: %s", user_dn)

        except (LDAPSocketOpenError, LDAPBindError) as e:
            logger.error("Service bind/search LDAP error: %s: %s", type(e).__name__, e)
            return None
        except Exception as e:
            logger.exception("Service bind/search unexpected error: %s", e)
            return None
        finally:
            try:
                if svc_conn is not None:
                    svc_conn.unbind()
                    logger.debug("Service connection unbound")
            except Exception as e:
                logger.warning("Service unbind error: %s", e)

        # --- User bind (password check) ---
        try:
            logger.debug("User bind check for DN=%s ...", user_dn)
            user_conn = Connection(
                server,
                user=user_dn,
                password=password,
                auto_bind=True,
                receive_timeout=30,
            )
            user_conn.unbind()
            logger.debug("User bind OK (password valid)")
        except LDAPBindError as e:
            logger.info("User bind FAILED (invalid credentials): %s", e)
            return None
        except Exception as e:
            logger.error("User bind FAILED: %s: %s", type(e).__name__, e)
            return None

        # --- Read attributes ---
        get = self._attr
        first_name = (
            get(entry, getattr(settings, "LDAP_ATTR_GIVENNAME", "givenName")) or ""
        )
        last_name = get(entry, getattr(settings, "LDAP_ATTR_SN", "sn")) or ""
        email = (get(entry, getattr(settings, "LDAP_ATTR_MAIL", "mail")) or "").lower()
        logger.debug(
            "Attrs: first_name=%r last_name=%r email=%r", first_name, last_name, email
        )

        phone_e164: Optional[str] = None
        for attr in list(phone_attrs) + [
            getattr(settings, "LDAP_ATTR_PHONE", "telephoneNumber")
        ]:
            val = get(entry, attr)
            if val:
                phone_e164 = _normalize_phone(val)
                logger.debug(
                    "Phone candidate attr=%s raw=%r -> norm=%r", attr, val, phone_e164
                )
                if phone_e164:
                    break

        # --- AD disabled flag ---
        if getattr(settings, "LDAP_RESPECT_AD_DISABLED", False):
            uac_raw = get(entry, "userAccountControl")
            try:
                uac_int = int(str(uac_raw).strip())
                if (uac_int & 0x0002) != 0:
                    logger.info("AD says account is DISABLED -> auth denied")
                    return None
            except Exception as e:
                logger.debug("UAC parse error: %s (ignored)", e)

        # --- Find or create local user ---
        user = None
        if email and _model_has_field(UserModel, "email"):
            logger.debug("Lookup local user by email=%r", email)
            user = UserModel.objects.filter(email__iexact=email).first()
        if user is None and PHONE_FIELD and phone_e164:
            logger.debug("Lookup local user by %s=%r", PHONE_FIELD, phone_e164)
            user = UserModel.objects.filter(**{PHONE_FIELD: phone_e164}).first()

        if user and getattr(settings, "LDAP_RESPECT_IS_ACTIVE", True):
            if not self.user_can_authenticate(user):
                logger.info("user_can_authenticate=False -> auth denied")
                return None

        auto_create = bool(
            getattr(settings, "LDAP_AUTO_CREATE", False)
            or getattr(settings, "LDAP_REGISTRATION_CREATE", False)
        )
        logger.debug("auto_create=%s", auto_create)

        if user is None and auto_create:
            payload: dict[str, Any] = {}
            if _model_has_field(UserModel, "email") and email:
                payload["email"] = email
            if PHONE_FIELD and phone_e164:
                payload[PHONE_FIELD] = phone_e164
            if _model_has_field(UserModel, "first_name"):
                payload["first_name"] = first_name
            if _model_has_field(UserModel, "last_name"):
                payload["last_name"] = last_name

            key_field = getattr(UserModel, "USERNAME_FIELD", "email")
            key_ok = (key_field != "email") or bool(payload.get("email"))
            phone_ok = (not PHONE_FIELD) or (PHONE_FIELD in payload)
            logger.debug(
                "Auto-create checks: key_field=%r key_ok=%s phone_ok=%s payload_keys=%s",
                key_field,
                key_ok,
                phone_ok,
                list(payload.keys()),
            )

            if key_ok and phone_ok:
                user = UserModel.objects.create(**payload)
                logger.info("Local user CREATED: id=%s", getattr(user, "id", None))
                if self.user_can_authenticate(user) is False and hasattr(
                    user, "is_active"
                ):
                    user.is_active = True
                    user.save(update_fields=["is_active"])
                    logger.debug("Local user activated (is_active=True)")
            else:
                logger.info("Auto-create refused (insufficient key data)")
                return None

        # --- Light profile sync ---
        if user:
            changed: List[str] = []

            if (
                _model_has_field(UserModel, "first_name")
                and user.first_name != first_name
            ):
                user.first_name = first_name
                changed.append("first_name")
            if _model_has_field(UserModel, "last_name") and user.last_name != last_name:
                user.last_name = last_name
                changed.append("last_name")
            if (
                email
                and _model_has_field(UserModel, "email")
                and (user.email or "").lower() != email
            ):
                user.email = email
                changed.append("email")
            if (
                PHONE_FIELD
                and phone_e164
                and getattr(user, PHONE_FIELD, None) != phone_e164
            ):
                setattr(user, PHONE_FIELD, phone_e164)
                changed.append(PHONE_FIELD)

            if hasattr(user, "ldap_dn") and getattr(user, "ldap_dn") != user_dn:
                setattr(user, "ldap_dn", user_dn)
                changed.append("ldap_dn")

            guid = get(entry, "objectGUID")
            if (
                hasattr(user, "ldap_guid")
                and guid
                and getattr(user, "ldap_guid") != str(guid)
            ):
                # При необходимости замените str(guid) на корректную конверсию GUID.
                setattr(user, "ldap_guid", str(guid))
                changed.append("ldap_guid")

            if hasattr(user, "is_ldap_managed") and not getattr(
                user, "is_ldap_managed", False
            ):
                setattr(user, "is_ldap_managed", True)
                changed.append("is_ldap_managed")

            if hasattr(user, "last_ldap_sync_at"):
                setattr(user, "last_ldap_sync_at", timezone.now())
                changed.append("last_ldap_sync_at")

            if changed:
                user.save(update_fields=list(set(changed)))
                logger.debug("Local user updated fields: %s", sorted(set(changed)))
            else:
                logger.debug("Local user has no changes to save")

            if not self.user_can_authenticate(user):
                logger.info("user_can_authenticate=False after sync -> auth denied")
                return None

            logger.info(
                "AUTH SUCCESS: user_id=%s email=%s",
                getattr(user, "id", None),
                getattr(user, "email", None),
            )
            return user

        logger.info(
            "AUTH FAILED: no local user (auto_create disabled or constraints not met)"
        )
        return None

    @staticmethod
    def _attr(entry: Any, name: str) -> Optional[str]:
        """Возвращает первое строковое значение LDAP-атрибута.

        Args:
            entry: ldap3 Entry.
            name: Имя атрибута (например, 'mail').

        Returns:
            str | None: Нормализованное строковое значение или None.

        Raises:
            None: Ошибки приводят к возврату None и логируются на debug.
        """
        try:
            val = getattr(entry, name, None)
            raw = getattr(val, "value", None)
            if raw is None:
                return None
            if isinstance(raw, (list, tuple)):
                return str(raw[0]).strip() if raw else None
            return str(raw).strip()
        except Exception as e:
            logger.debug("LDAP3Backend._attr('%s') error: %s", name, e)
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


class PositionRoleBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        """Этот бэкенд не участвует в аутентификации, только в расчёте прав."""
        return None

    def get_all_permissions(self, user_obj, obj=None):
        perms = super().get_all_permissions(user_obj, obj)
        
        # Проверяем, что пользователь authenticated и active
        if not getattr(user_obj, "is_authenticated", False) or obj is not None:
            return perms
        if not getattr(user_obj, "is_active", True):
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
