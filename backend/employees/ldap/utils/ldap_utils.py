"""LDAP-специфичные утилиты.

Функции для работы с LDAP-атрибутами, поиска, парсинга значений и работы с группами.
"""

import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from ldap3 import ALL_ATTRIBUTES, BASE, SUBTREE, Connection

from ..config import DISABLED_FLAG


def _first(val: Any) -> Any:
    """Возвращает первый элемент для list/tuple, иначе исходное значение.

    Args:
        val (Any): Значение (может быть list, tuple или скаляр).

    Returns:
        Any: Первый элемент или сам объект.
    """
    if isinstance(val, (list, tuple)):
        return val[0] if val else None
    return val


def _uac_is_active(uac_value: Any) -> bool:
    """Определяет активность учётной записи по userAccountControl.

    Args:
        uac_value (Any): Значение UAC (возможны list/bytes/str/int).

    Returns:
        bool: True если учётка активна (бит DISABLED не установлен).

    Raises:
        ValueError: Если значение невозможно привести к int.
    """
    val = _first(uac_value)
    if val is None or val == "":
        return True
    if isinstance(val, bytes):
        try:
            val = val.decode("utf-8")
        except Exception:
            val = val.decode("latin-1", "ignore")
    try:
        num = int(str(val).strip(), 0)  # поддержка '0x...' и десятичного
    except Exception as exc:
        raise ValueError("Некорректный userAccountControl") from exc
    return (num & DISABLED_FLAG) == 0


def _paged_search(
    conn: Connection, base: str, flt: str, *, page_size: int = 500
) -> list:
    """Постраничный поиск с возвратом всех entries.

    Args:
        conn (Connection): LDAP-соединение.
        base (str): Базовый DN для поиска.
        flt (str): LDAP-фильтр.
        page_size (int): Размер страницы (по умолчанию 500).

    Returns:
        list: Список всех найденных entries.
    """
    results: list = []
    cookie = None
    while True:
        conn.search(
            search_base=base,
            search_filter=flt,
            search_scope=SUBTREE,
            attributes=ALL_ATTRIBUTES,
            paged_size=page_size,
            paged_cookie=cookie,
        )
        results.extend(conn.entries or [])
        cookie = (
            conn.result.get("controls", {})
            .get("1.2.840.113556.1.4.319", {})
            .get("value", {})
            .get("cookie")
        )
        if not cookie:
            break
    return results


def get_attr_str(attrs: Dict[str, Any], key: str, default: str = "") -> str:
    """Строковое значение атрибута (учитывает list/bytes), trimmed.

    Args:
        attrs (Dict[str, Any]): Словарь атрибутов LDAP.
        key (str): Ключ атрибута.
        default (str): Значение по умолчанию.

    Returns:
        str: Строковое значение атрибута или default.
    """
    val = _first(attrs.get(key))
    if val is None:
        return default
    if isinstance(val, bytes):
        try:
            val = val.decode("utf-8")
        except Exception:
            val = val.decode("latin-1", "ignore")
    return str(val).strip()


def get_guid_str(attrs: Dict[str, Any]) -> Optional[str]:
    """objectGUID → UUID-строка (учитывает bytes/list/str).

    Args:
        attrs (Dict[str, Any]): Словарь атрибутов LDAP.

    Returns:
        Optional[str]: Строковое представление GUID или None.
    """
    raw = _first(attrs.get("objectGUID"))
    if raw is None:
        return None
    if isinstance(raw, bytes):
        try:
            return str(uuid.UUID(bytes_le=raw))
        except Exception:
            return None
    return str(raw)


def _ldap_pick_phone(attrs: Dict[str, Any]) -> Optional[str]:
    """Извлекает «лучший» телефон из LDAP-атрибутов.

    Ищет по стандартным полям AD: mobile, telephoneNumber (в таком порядке).

    Args:
        attrs (Dict[str, Any]): Словарь атрибутов записи LDAP
            (как `entry_attributes_as_dict`).

    Returns:
        Optional[str]: Сырая строка телефона или None, если ничего не найдено.
    """
    for key in ("mobile", "telephoneNumber"):
        v = attrs.get(key)
        if isinstance(v, list):
            v = v[0] if v else None
        if v:
            s = str(v).strip()
            if s:
                return s
    return None


def group_type(scope: str, security_enabled: bool) -> int:
    """Возвращает числовой тип группы AD с учётом флага безопасности.

    Args:
        scope (str): Область группы ('global', 'domain_local', 'universal').
        security_enabled (bool): Является ли группа группой безопасности.

    Returns:
        int: Числовое значение для атрибута groupType.
    """
    SCOPE = {
        "global": 0x00000002,
        "domain_local": 0x00000004,
        "universal": 0x00000008,
    }
    val = SCOPE.get(scope, 0x00000002)
    val |= 0x80000000 if security_enabled else 0
    if val & 0x80000000:
        return val - (1 << 32)
    return val


def cn_candidates(pretty: str, safe: str) -> List[str]:
    """Формирует список возможных CN: красивый + постфиксы, затем безопасный + постфиксы.

    Args:
        pretty (str): "Красивый" вариант CN (например, с кириллицей).
        safe (str): "Безопасный" вариант CN (только ASCII).

    Returns:
        List[str]: Список кандидатов CN в порядке приоритета.
    """
    seq: List[str] = [pretty] + [f"{pretty} {i}" for i in range(2, 30)]
    seq += [safe] + [f"{safe} {i}" for i in range(2, 30)]
    return seq


# --- Login/UPN generation (используется в directory_service и sync_service) ---

_RESERVED = {"admin", "administrator", "guest", "krbtgt"}


def make_base_login(first_name: str, last_name: str) -> str:
    """Строит базовый логин: last + first_initial (ASCII).

    Args:
        first_name (str): Имя.
        last_name (str): Фамилия.

    Returns:
        str: Логин (может быть пустым, если нет данных).
    """
    from .text_utils import translit_to_ascii

    ln = translit_to_ascii(last_name)
    fi = translit_to_ascii(first_name[:1]) if first_name else ""
    return ln + fi


def fallback_login_from_email(
    email: str, default_seed: Optional[uuid.UUID] = None
) -> str:
    """Фолбэк-логин из локальной части email, обрезанной до 10 символов.

    Args:
        email (str): Email.
        default_seed (Optional[uuid.UUID]): Seed, если локальная часть пуста.

    Returns:
        str: Логин.

    Raises:
        TypeError: Если email не строка.
    """
    from .text_utils import translit_to_ascii

    if not isinstance(email, str):
        raise TypeError("email должен быть строкой")
    local = (email or "").split("@", 1)[0]
    local = translit_to_ascii(local)[:10]
    if local:
        return local
    seed = (default_seed or uuid.uuid4()).hex[:6]
    return f"user{seed}"


def ensure_unique_login(
    base: str,
    is_taken_sam: Callable[[str], bool],
    is_taken_upn: Callable[[str], bool],
    upn_suffix: str,
    *,
    max_sam_len: int = 20,
    max_attempts: int = 100,
) -> Tuple[str, str]:
    """Подбирает уникальные sAMAccountName и UPN (<sam>@<suffix>) c суффиксами цифр.

    Args:
        base (str): Базовый логин (ASCII).
        is_taken_sam (Callable[[str], bool]): Проверка занятости sAM в LDAP.
        is_taken_upn (Callable[[str], bool]): Проверка занятости UPN в LDAP.
        upn_suffix (str): Домен UPN, например 'robotail.local'.
        max_sam_len (int): Лимит длины sAM (обычно 20).
        max_attempts (int): Число попыток (включая без суффикса).

    Returns:
        Tuple[str, str]: (sam, upn).

    Raises:
        ValueError: Если base пуст или не найдено уникального значения.
    """
    from .text_utils import translit_to_ascii

    base = translit_to_ascii(base)
    if not base:
        raise ValueError("пустой base для логина")
    if base in _RESERVED:
        base = f"{base}1"

    def fit(b: str, suf: str) -> str:
        return b[: max_sam_len - len(suf)] + suf

    for i in range(max_attempts):
        suf = "" if i == 0 else str(i)
        sam = fit(base, suf)
        upn = f"{sam}@{upn_suffix}"
        if not is_taken_sam(sam) and not is_taken_upn(upn):
            return sam, upn
    raise ValueError("не удалось подобрать уникальные sAM/UPN")


def build_logins_for_user(
    first_name: str,
    last_name: str,
    email: str,
    upn_suffix: str,
    is_taken_sam: Callable[[str], bool],
    is_taken_upn: Callable[[str], bool],
    guid: Optional[uuid.UUID] = None,
) -> Tuple[str, str]:
    """Генерирует уникальные sAM и UPN согласно правилам проекта.

    Args:
        first_name (str): Имя.
        last_name (str): Фамилия.
        email (str): Email.
        upn_suffix (str): Домен UPN.
        is_taken_sam (Callable[[str], bool]): Проверка sAM в LDAP.
        is_taken_upn (Callable[[str], bool]): Проверка UPN в LDAP.
        guid (Optional[uuid.UUID]): Seed для детерминированного фолбэка.

    Returns:
        Tuple[str, str]: (sam, upn).
    """
    base = make_base_login(first_name, last_name) or fallback_login_from_email(
        email, default_seed=guid
    )
    try:
        return ensure_unique_login(base, is_taken_sam, is_taken_upn, upn_suffix)
    except ValueError:
        fb = fallback_login_from_email(email, default_seed=guid)
        return ensure_unique_login(fb, is_taken_sam, is_taken_upn, upn_suffix)


def get_base_dn_for_employee(employee) -> str:
    """Определяет целевую OU для сотрудника в зависимости от статуса активности.
    
    Args:
        employee: Экземпляр модели Employee.
        
    Returns:
        str: DN базовой OU (LDAP_DISMISSED_BASE если is_active=False, иначе LDAP_USERS_BASE).
        
    Raises:
        RuntimeError: Если настройка не сконфигурирована в settings.
    """
    from django.conf import settings
    
    if not employee.is_active:
        dismissed_base = getattr(settings, "LDAP_DISMISSED_BASE", None)
        if not dismissed_base:
            raise RuntimeError("LDAP_DISMISSED_BASE is not configured")
        return dismissed_base
    
    users_base = getattr(settings, "LDAP_USERS_BASE", None) or getattr(
        settings, "LDAP_USER_BASE", None
    )
    if not users_base:
        raise RuntimeError("LDAP_USERS_BASE is not configured")
    return users_base


__all__ = [
    "_first",
    "_uac_is_active",
    "_paged_search",
    "get_attr_str",
    "get_guid_str",
    "_ldap_pick_phone",
    "group_type",
    "cn_candidates",
    "make_base_login",
    "fallback_login_from_email",
    "ensure_unique_login",
    "build_logins_for_user",
    "get_base_dn_for_employee",
]
