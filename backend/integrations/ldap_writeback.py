from __future__ import annotations

from typing import Any, Dict, Optional

from django.conf import settings
from django.db import transaction
from django.utils.timezone import now
from ldap3 import ALL, Connection, MODIFY_REPLACE, Server
from ldap3.utils.conv import escape_filter_chars

from employees.models import Employee

try:
    # используем ваш нормалайзер и автоопределение поля телефона
    from eusrr_backend.auth_backends import PHONE_FIELD as DETECTED_PHONE_FIELD  # type: ignore
    from eusrr_backend.auth_backends import _normalize_phone  # type: ignore
except Exception:  # pragma: no cover
    DETECTED_PHONE_FIELD = "phone_number"

    def _normalize_phone(raw: str) -> Optional[str]:
        return str(raw).strip() if raw else None


def _ldap_server() -> Server:
    """Создает объект Server для соединения с LDAP.

    Returns:
        Server: Инициализированный LDAP сервер.

    Raises:
        ValueError: Если URI не указан.
    """
    uri = getattr(settings, "LDAP_URI", None)
    if not uri:
        raise ValueError("LDAP_URI is not configured")
    return Server(uri, get_info=ALL)


def _bind() -> Connection:
    """Устанавливает соединение с LDAP с учётом таймаута записи.

    Returns:
        Connection: Авторизованное соединение.

    Raises:
        ConnectionError: При неудачной авторизации/соединении.
    """
    try:
        return Connection(
            _ldap_server(),
            user=getattr(settings, "LDAP_BIND_DN", ""),
            password=getattr(settings, "LDAP_BIND_PASSWORD", ""),
            auto_bind=True,
            read_only=False,
            receive_timeout=getattr(settings, "LDAP_WRITE_TIMEOUT", 5),
        )
    except Exception as exc:  # pragma: no cover
        raise ConnectionError(f"LDAP bind failed: {exc}") from exc


def _build_changes(attrs: Dict[str, Any]) -> Dict[str, list[tuple]]:
    """Готовит словарь изменений для ldap3.modify().

    Args:
        attrs: Словарь LDAP-атрибутов и значений.

    Returns:
        Dict[str, list[tuple]]: Формат для ldap3.modify().

    Raises:
        ValueError: Если attrs пуст.
    """
    if not attrs:
        raise ValueError("No attributes to modify")
    changes: Dict[str, list[tuple]] = {}
    for attr, value in attrs.items():
        if value is None:
            continue
        if isinstance(value, (list, tuple)):
            changes[attr] = [(MODIFY_REPLACE, list(value))]
        else:
            changes[attr] = [(MODIFY_REPLACE, [str(value)])]
    return changes


def _user_filter_for_search(u: Employee) -> str:
    """Формирует фильтр поиска DN по уникальным ключам.

    Args:
        u: Пользователь.

    Returns:
        str: LDAP фильтр.

    Raises:
        ValueError: Если нет данных для поиска.
    """
    terms: list[str] = []
    if getattr(u, "email", None):
        terms.append(f"(mail={escape_filter_chars(u.email)})")
    phone_field = DETECTED_PHONE_FIELD or "phone_number"
    phone = getattr(u, phone_field, None)
    if phone:
        terms.append(f"(telephoneNumber={escape_filter_chars(str(phone))})")
    if not terms:
        raise ValueError("Insufficient data to search LDAP entry")
    return f"(|{''.join(terms)})"


def _find_dn(conn: Connection, u: Employee) -> str:
    """Определяет DN учётки: по сохранённому DN/guid или поиском.

    Args:
        conn: Подключение LDAP.
        u: Пользователь.

    Returns:
        str: DN найденной записи.

    Raises:
        ValueError: Если база поиска не настроена или запись не найдена.
    """
    if getattr(u, "ldap_dn", None):
        return str(u.ldap_dn)

    guid = getattr(u, "ldap_guid", None)
    if guid:
        filt = f"(|(objectGUID={escape_filter_chars(guid)})(entryUUID={escape_filter_chars(guid)}))"
    else:
        filt = _user_filter_for_search(u)

    base = getattr(settings, "LDAP_USER_BASE", None)
    if not base:
        raise ValueError("LDAP_USER_BASE is not configured")

    if not conn.search(base, filt, attributes=["distinguishedName"]):
        raise ValueError("LDAP entry not found")
    return conn.entries[0].entry_dn


def _read_assert_ts(conn: Connection, dn: str) -> Optional[str]:
    """Читает штамп изменения записи (для optimistic locking).

    Args:
        conn: Подключение LDAP.
        dn: DN записи.

    Returns:
        Optional[str]: Текущее значение whenChanged/modifyTimestamp.
    """
    attr = getattr(settings, "LDAP_ASSERT_ATTR", "whenChanged")
    if not conn.search(dn, "(objectClass=*)", search_scope="BASE", attributes=[attr]):
        return None
    e = conn.entries[0]
    val = getattr(e, attr, None)
    return getattr(val, "value", None)


def update_employee_in_ldap(u: Employee, *, payload: dict[str, Any]) -> None:
    """Пишет изменения профиля в LDAP с optimistic locking и обновляет локальную проекцию.

    Допускаются только поля из белого списка (settings.LDAP_WRITE_ATTRS).
    Для телефона выполняется нормализация в E.164.

    Args:
        u: Пользователь.
        payload: Изменённые локальные поля (например, {'first_name': 'Иван', 'phone_number': '+7999...'}).

    Raises:
        PermissionError: Если write-back отключён или поле вне белого списка.
        ValueError: Если запись не найдена или нечего обновлять.
        RuntimeError: Если сервер отклонил изменение (конфликт/ошибка modify).
        ConnectionError: Ошибка соединения/авторизации с LDAP.
    """
    if not getattr(settings, "LDAP_WRITE_ENABLED", False):
        raise PermissionError("LDAP write-back is disabled")

    # 1) Маппинг локальных -> LDAP атрибутов с белым списком
    allowed_map: dict[str, str] = dict(getattr(settings, "LDAP_WRITE_ATTRS", {}))

    # Нормализуем телефон и подставим фактическое имя локального поля
    phone_field = DETECTED_PHONE_FIELD or "phone_number"
    if "phone" in allowed_map and phone_field in payload:
        raw = payload.get(phone_field)
        norm = _normalize_phone(raw) if raw is not None else None
        payload = dict(payload)
        payload["phone"] = norm

    attrs: dict[str, Any] = {}
    for local_name, ldap_attr in allowed_map.items():
        if local_name in payload and payload[local_name] is not None:
            attrs[ldap_attr] = payload[local_name]

    if not attrs:
        raise ValueError("No allowed changes to write into LDAP")

    # 2) Поиск DN и чтение штампа
    with _bind() as conn:
        dn = _find_dn(conn, u)
        ts = _read_assert_ts(conn, dn)

        # 3) Assertion Control (RFC 4528) — меняем, только если штамп тот же
        assertion_attr = getattr(settings, "LDAP_ASSERT_ATTR", "whenChanged")
        assertion_filter = f"({assertion_attr}={ts})" if ts else "(objectClass=*)"

        ok = conn.modify(dn, _build_changes(attrs), controls=[("1.3.6.1.1.12", True, assertion_filter)])
        if not ok:
            # Конфликт параллельного изменения (коды у серверов разные)
            code = (conn.result or {}).get("result")
            if code in {80, 122, 50}:
                raise RuntimeError("LDAP optimistic lock conflict")
            raise RuntimeError(f"LDAP modify error: {conn.result}")

        # 4) Успех: обновим локальную проекцию без смены источника истины
        upd: dict[str, Any] = {}
        if "givenName" in attrs and hasattr(u, "first_name"):
            u.first_name = attrs["givenName"]; upd["first_name"] = u.first_name
        if "sn" in attrs and hasattr(u, "last_name"):
            u.last_name = attrs["sn"]; upd["last_name"] = u.last_name
        if "telephoneNumber" in attrs and hasattr(u, phone_field):
            setattr(u, phone_field, attrs["telephoneNumber"]); upd[phone_field] = getattr(u, phone_field)

        # Обновим служебные поля, если есть
        if hasattr(u, "last_ldap_sync_at"):
            u.last_ldap_sync_at = now(); upd["last_ldap_sync_at"] = u.last_ldap_sync_at
        if hasattr(u, "last_ldap_modify_ts") and ts:
            u.last_ldap_modify_ts = ts; upd["last_ldap_modify_ts"] = ts
        if hasattr(u, "ldap_dn") and not getattr(u, "ldap_dn", None):
            u.ldap_dn = dn; upd["ldap_dn"] = dn

        if upd:
            with transaction.atomic():
                u.save(update_fields=list(upd.keys()))
