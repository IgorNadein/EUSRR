from __future__ import annotations

from typing import Dict, List, Mapping, Optional, Sequence, Any, Set

from django.conf import settings
from ldap3 import BASE, MODIFY_REPLACE, SUBTREE, Connection

from .utils import esc_filter, esc_rdn, group_type
from ..models import Department


def read_attrs(conn: Connection, dn: str, attrs: List[str]) -> Dict[str, Optional[str]]:
    """Читает значения указанных LDAP-атрибутов у записи по DN."""
    if not isinstance(dn, str) or not dn.strip():
        raise TypeError("dn должен быть непустой строкой")
    if not isinstance(attrs, list) or not all(isinstance(a, str) for a in attrs):
        raise TypeError("attrs должен быть списком строк")

    out: Dict[str, Optional[str]] = {a: None for a in attrs}
    try:
        ok = conn.search(
            search_base=dn,
            search_filter="(objectClass=*)",
            search_scope=BASE,
            attributes=attrs,
        )
        if not ok or not conn.entries:
            return out
        entry = conn.entries[0]
        for a in attrs:
            try:
                raw = getattr(getattr(entry, a, None), "value", None)
                if isinstance(raw, (list, tuple)):
                    raw = raw[0] if raw else None
                out[a] = str(raw).strip() if raw is not None else None
            except Exception:
                out[a] = None
        return out
    except Exception:
        return out


def is_taken(
    conn: Connection,
    *,
    attributes: Mapping[str, Optional[str]],
    object_classes: Sequence[str] = ("user",),
    object_category: str = "person",
    base_dn: Optional[str] = None,
) -> bool:
    """Проверяет занятость атрибутов в домене (LDAP search OR по значениям).

    Args:
        conn (Connection): Активное LDAP-соединение.
        attributes (Mapping[str, Optional[str]]): Пары {атрибут: значение}. Пустые/None игнорируются.
        object_classes (Sequence[str]): Список objectClass для фильтрации (по умолчанию ('user',)).
        object_category (str): Значение objectCategory (по умолчанию 'person').
        base_dn (Optional[str]): База поиска. Если не указана, берётся из settings.LDAP_BASE_DN.

    Returns:
        bool: True, если найден хотя бы один объект с любым из указанных значений.

    Raises:
        RuntimeError: Если не задан base DN.
        TypeError: Если ключи/значения словаря атрибутов имеют неверные типы.
    """
    base = base_dn or getattr(settings, "LDAP_BASE_DN", None)
    if not base:
        raise RuntimeError("LDAP_BASE_DN must be set")

    # Валидация входных данных
    if not isinstance(attributes, Mapping):
        raise TypeError("attributes must be a mapping")
    if not all(isinstance(k, str) and k.strip() for k in attributes.keys()):
        raise TypeError("All attribute names must be non-empty strings")
    if not all((v is None) or isinstance(v, str) for v in attributes.values()):
        raise TypeError("All attribute values must be strings or None")

    # (attr1=val1) OR (attr2=val2) ...
    attr_filters = [
        f"({attr}={esc_filter(value)})" for attr, value in attributes.items() if value
    ]
    if not attr_filters:
        return False  # нечего проверять

    # AND с категорией и классами
    class_filter = "".join(f"(objectClass={esc_filter(cls)})" for cls in object_classes)
    ldap_filter = f"(&(|{''.join(attr_filters)})(objectCategory={esc_filter(object_category)}){class_filter})"

    conn.search(
        search_base=base,
        search_filter=ldap_filter,
        search_scope=SUBTREE,
        attributes=["cn"],
        size_limit=1,
    )
    return bool(conn.entries)


def modify_user_attrs(
    conn, user_dn: str, attrs: dict[str, object], *, do_write: bool
) -> None:
    """MODIFY_REPLACE атрибутов пользователя; None-значения пропускаются."""
    changes = {
        k: [(MODIFY_REPLACE, [v] if not isinstance(v, (list, tuple)) else list(v))]
        for k, v in attrs.items()
        if v is not None
    }
    if not changes or not do_write:
        return
    if not conn.modify(user_dn, changes=changes):
        raise RuntimeError(f"LDAP modify failed for {user_dn}: {conn.result}")


def ensure_container_exists(conn: Connection, base_dn: str) -> None:
    """Проверяет, что контейнер (OU) существует."""
    if not isinstance(base_dn, str) or not base_dn.strip():
        raise TypeError("base_dn должен быть непустой строкой")
    ok = conn.search(
        search_base=base_dn,
        search_filter="(objectClass=organizationalUnit)",
        search_scope=BASE,
        attributes=["distinguishedName"],
    )
    if not ok or not conn.entries:
        raise RuntimeError(f"Контейнер для создания не найден: {base_dn}")


def ldap_modify_or_ignore(
    conn: Connection,
    dn: str,
    changes: Dict[str, Any],
    ignore_descriptions: Set[str] | None = None,
) -> None:
    """Общий modify с белым списком «нефатальных» описаний.

    Args:
        conn (Connection): Подключение LDAP.
        dn (str): DN объекта.
        changes (Dict[str, Any]): Карта изменений для conn.modify.
        ignore_descriptions (Optional[Set[str]]): Список описаний, которые не считаем ошибкой.

    Raises:
        RuntimeError: Если modify вернул ошибку вне разрешённых.
    """
    ok = conn.modify(dn, changes)
    if ok:
        return
    desc = (conn.result or {}).get("description", "")
    if ignore_descriptions and desc in ignore_descriptions:
        return
    raise RuntimeError(f"LDAP modify failed: {conn.result}")
