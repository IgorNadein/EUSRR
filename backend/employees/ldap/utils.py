# backend\employees\ldap\utils.py
from __future__ import annotations

import io
import uuid
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

from ldap3 import ALL_ATTRIBUTES, BASE, SUBTREE, Connection
from ldap3.utils.conv import escape_filter_chars
from PIL import Image

from .config import DISABLED_FLAG


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
    """Постраничный поиск с возвратом всех entries."""
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


# --- DN parsing -------------------------------------------------------


def extract_department_from_dn(
    dn: str, *, departments_anchor: str = "OU=Departments"
) -> Optional[str]:
    """Возвращает имя отдела из DN при контейнерной модели.

    Ищет сегмент OU=Departments и берёт OU слева от него как название отдела.

    Args:
        dn (str): Distinguished Name пользователя.
        departments_anchor (str): Маркер корневого OU отделов.

    Returns:
        Optional[str]: Имя отдела или None, если пользователь не под OU=Departments.

    Raises:
        TypeError: Если dn не строка.
        ValueError: Если dn пустой.
    """
    if not isinstance(dn, str):
        raise TypeError("dn должен быть строкой")
    dn = dn.strip()
    if not dn:
        raise ValueError("пустой DN")

    parts: Sequence[str] = [p.strip() for p in dn.split(",") if p.strip()]
    # точное совпадение полного сегмента
    try:
        idx = parts.index(departments_anchor)
    except ValueError:
        # fallback: искать просто 'OU=Departments' без хвоста
        try:
            idx = next(
                i for i, p in enumerate(parts) if p.strip().lower() == "ou=departments"
            )
        except StopIteration:
            return None

    dept_idx = idx - 1
    if dept_idx < 0 or not parts[dept_idx].startswith("OU="):
        return None
    value = parts[dept_idx][3:].strip()
    return value or None


# --- Avatar normalization --------------------------------------------


def normalize_avatar_to_jpeg(
    data: bytes, *, size_px: int = 120, max_kb: int = 100
) -> bytes:
    """Нормализует аватар в JPEG нужного размера и лимита.

    Args:
        data (bytes): Входной образ (PNG/JPEG/...).
        size_px (int): Квадратный размер целевого изображения.
        max_kb (int): Максимальный размер файла в килобайтах (ограничение AD ~100 KB).

    Returns:
        bytes: JPEG-данные, соответствующие ограничениям.

    Raises:
        RuntimeError: Если Pillow недоступен или не удалось обработать изображение.
        ValueError: Если вход пустой.
    """
    if not data:
        raise ValueError("avatar: пустые данные")
    if Image is None:
        raise RuntimeError(
            "Pillow не установлен. Установите 'Pillow' для обработки аватаров."
        )

    try:
        img = Image.open(io.BytesIO(data))
        img = img.convert("RGB")
        img = img.resize((size_px, size_px))
        # бинарный поиск по качеству для соблюдения max_kb
        lo, hi = 50, 95
        best = None
        while lo <= hi:
            mid = (lo + hi) // 2
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=mid, optimize=True)
            kb = len(buf.getvalue()) // 1024
            if kb <= max_kb:
                best = buf.getvalue()
                lo = mid + 1
            else:
                hi = mid - 1
        if best is None:
            # минимально возможное
            buf = io.BytesIO()
            img.save(buf, format="JPEG", quality=50, optimize=True)
            best = buf.getvalue()
        return best
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(f"avatar: ошибка нормализации: {exc}") from exc


# --- Login/UPN generation --------------------------------------------

_RU2LAT = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "i",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "shch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
}
_RESERVED = {"admin", "administrator", "guest", "krbtgt"}


def translit_to_ascii(text: str) -> str:
    """Транслитерирует строку в ascii: [a-z0-9], нижний регистр.

    Args:
        text (str): Входная строка.

    Returns:
        str: Нормализованная ASCII-строка.
    """
    if not isinstance(text, str):
        raise TypeError("text должен быть строкой")
    s = (text or "").strip().lower()
    out: list[str] = []
    for ch in s:
        if "a" <= ch <= "z" or "0" <= ch <= "9":
            out.append(ch)
            continue
        if ch in (" ", ".", "_", "-"):
            continue
        if ch in _RU2LAT:
            out.append(_RU2LAT[ch])
            continue
    return "".join(out)


def make_base_login(first_name: str, last_name: str) -> str:
    """Строит базовый логин: last + first_initial (ASCII).

    Args:
        first_name (str): Имя.
        last_name (str): Фамилия.

    Returns:
        str: Логин (может быть пустым, если нет данных).
    """
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
    """
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


# --- Attribute normalization (ldap3 returns lists/bytes) -------------


def _first(val: Any) -> Any:
    """Возвращает первый элемент для list/tuple, иначе исходное значение."""
    if isinstance(val, (list, tuple)):
        return val[0] if val else None
    return val


def get_attr_str(attrs: Dict[str, Any], key: str, default: str = "") -> str:
    """Строковое значение атрибута (учитывает list/bytes), trimmed."""
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
    """objectGUID → UUID-строка (учитывает bytes/list/str)."""
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


def esc_filter(value: Optional[str]) -> str:
    """Экранирует строку для подстановки в LDAP-фильтры (RFC4515).

    Args:
        value (Optional[str]): Исходная строка.

    Returns:
        str: Экранированная строка.
    """
    s = (value or "").strip()
    try:
        return escape_filter_chars(s)
    except Exception:
        return (
            s.replace("\\", r"\5c")
            .replace("*", r"\2a")
            .replace("(", r"\28")
            .replace(")", r"\29")
            .replace("\x00", r"\00")
        )


def esc_rdn(text: str) -> str:
    """Экранирует RDN-компонент."""
    return (
        text.replace("\\", "\\\\")
        .replace(",", "\\,")
        .replace("+", "\\+")
        .replace(";", "\\;")
        .replace("=", "\\=")
        .replace("<", "\\<")
        .replace(">", "\\>")
        .replace("#", "\\#")
        .replace('"', '\\"')
    )


def group_type(scope: str, security_enabled: bool) -> int:
    """Возвращает числовой тип группы AD с учётом флага безопасности."""
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
    """Формирует список возможных CN: красивый + постфиксы, затем безопасный + постфиксы."""
    seq: List[str] = [pretty] + [f"{pretty} {i}" for i in range(2, 30)]
    seq += [safe] + [f"{safe} {i}" for i in range(2, 30)]
    return seq


def rewrite_dn_suffix(dn: str, old_suffix: str, new_suffix: str) -> str:
    """Заменяет хвост DN c old_suffix на new_suffix."""
    if not dn or not dn.lower().endswith(old_suffix.lower()):
        return dn
    return dn[: -len(old_suffix)] + new_suffix
