"""LDAP репозиторий - низкоуровневые операции с LDAP.

Предоставляет методы для работы с LDAP: чтение, поиск, модификация атрибутов.
Это слой доступа к данным, который изолирует бизнес-логику от деталей LDAP API.
"""

from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Set

from django.conf import settings
from ldap3 import BASE, MODIFY_REPLACE, SUBTREE, Connection

from ..utils.text_utils import esc_filter


class LdapRepository:
    """Репозиторий для работы с LDAP.
    
    Инкапсулирует низкоуровневые операции с LDAP, предоставляя
    чистый интерфейс для бизнес-логики.
    """

    def __init__(self, conn: Connection):
        """
        Args:
            conn: Активное LDAP-соединение.
        """
        self.conn = conn

    def read_attrs(
        self, dn: str, attrs: List[str]
    ) -> Dict[str, Optional[str]]:
        """Читает значения указанных LDAP-атрибутов у записи по DN.

        Args:
            dn: Distinguished Name записи.
            attrs: Список атрибутов для чтения.

        Returns:
            Словарь {атрибут: значение}, где значение может быть None.

        Raises:
            TypeError: Если параметры неверного типа.
        """
        if not isinstance(dn, str) or not dn.strip():
            raise TypeError("dn должен быть непустой строкой")
        if not isinstance(attrs, list) or not all(
            isinstance(a, str) for a in attrs
        ):
            raise TypeError("attrs должен быть списком строк")

        out: Dict[str, Optional[str]] = {a: None for a in attrs}
        try:
            ok = self.conn.search(
                search_base=dn,
                search_filter="(objectClass=*)",
                search_scope=BASE,
                attributes=attrs,
            )
            if not ok or not self.conn.entries:
                return out
            entry = self.conn.entries[0]
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
        self,
        *,
        attributes: Mapping[str, Optional[str]],
        object_classes: Sequence[str] = ("user",),
        object_category: str = "person",
        base_dn: Optional[str] = None,
    ) -> bool:
        """Проверяет занятость атрибутов в домене (LDAP search OR).

        Args:
            attributes: Пары {атрибут: значение}. Пустые/None игнорируются.
            object_classes: Список objectClass для фильтрации.
            object_category: Значение objectCategory.
            base_dn: База поиска. Если не указана, берётся из settings.

        Returns:
            True, если найден хотя бы один объект с любым из указанных
                значений.

        Raises:
            RuntimeError: Если не задан base DN.
            TypeError: Если параметры неверного типа.
        """
        base = base_dn or getattr(settings, "LDAP_BASE_DN", None)
        if not base:
            raise RuntimeError("LDAP_BASE_DN must be set")

        # Валидация входных данных
        if not isinstance(attributes, Mapping):
            raise TypeError("attributes must be a mapping")
        if not all(isinstance(k, str) and k.strip() for k in attributes.keys()):
            raise TypeError("All attribute names must be non-empty strings")
        if not all(
            (v is None) or isinstance(v, str) for v in attributes.values()
        ):
            raise TypeError("All attribute values must be strings or None")

        # (attr1=val1) OR (attr2=val2) ...
        attr_filters = [
            f"({attr}={esc_filter(value)})"
            for attr, value in attributes.items()
            if value
        ]
        if not attr_filters:
            return False  # нечего проверять

        # AND с категорией и классами
        class_filter = "".join(
            f"(objectClass={esc_filter(cls)})" for cls in object_classes
        )
        ldap_filter = (
            f"(&(|{''.join(attr_filters)})"
            f"(objectCategory={esc_filter(object_category)}){class_filter})"
        )

        self.conn.search(
            search_base=base,
            search_filter=ldap_filter,
            search_scope=SUBTREE,
            attributes=["cn"],
            size_limit=1,
        )
        return bool(self.conn.entries)

    def modify_attrs(
        self, dn: str, attrs: dict[str, object], *, do_write: bool = True
    ) -> None:
        """MODIFY_REPLACE атрибутов объекта; None-значения пропускаются.

        Args:
            dn: Distinguished Name объекта.
            attrs: Словарь {атрибут: значение}.
            do_write: Выполнить изменения (False = dry-run).

        Raises:
            RuntimeError: Если операция завершилась ошибкой.
        """
        changes = {
            k: [
                (
                    MODIFY_REPLACE,
                    [v] if not isinstance(v, (list, tuple)) else list(v),
                )
            ]
            for k, v in attrs.items()
            if v is not None
        }
        if not changes or not do_write:
            return
        if not self.conn.modify(dn, changes=changes):
            raise RuntimeError(
                f"LDAP modify failed for {dn}: {self.conn.result}"
            )

    def ensure_container_exists(self, base_dn: str) -> None:
        """Проверяет, что контейнер (OU) существует.

        Args:
            base_dn: Distinguished Name контейнера.

        Raises:
            TypeError: Если base_dn неверного типа.
            RuntimeError: Если контейнер не найден.
        """
        if not isinstance(base_dn, str) or not base_dn.strip():
            raise TypeError("base_dn должен быть непустой строкой")
        ok = self.conn.search(
            search_base=base_dn,
            search_filter="(objectClass=organizationalUnit)",
            search_scope=BASE,
            attributes=["distinguishedName"],
        )
        if not ok or not self.conn.entries:
            raise RuntimeError(f"Контейнер для создания не найден: {base_dn}")

    def modify_or_ignore(
        self,
        dn: str,
        changes: Dict[str, Any],
        ignore_descriptions: Set[str] | None = None,
    ) -> None:
        """Общий modify с белым списком «нефатальных» описаний.

        Args:
            dn: DN объекта.
            changes: Карта изменений для conn.modify.
            ignore_descriptions: Список описаний, которые не считаем ошибкой.

        Raises:
            RuntimeError: Если modify вернул ошибку вне разрешённых.
        """
        ok = self.conn.modify(dn, changes)
        if ok:
            return
        desc = (self.conn.result or {}).get("description", "")
        if ignore_descriptions and desc in ignore_descriptions:
            return
        raise RuntimeError(f"LDAP modify failed: {self.conn.result}")


def ensure_container_exists(conn: Connection, base_dn: str) -> None:
    """Standalone-обёртка: проверяет что контейнер (OU) существует.
    
    Args:
        conn: LDAP соединение.
        base_dn: Distinguished Name контейнера.
        
    Raises:
        TypeError: Если base_dn неверного типа.
        RuntimeError: Если контейнер не найден.
    """
    LdapRepository(conn).ensure_container_exists(base_dn)


__all__ = [
    "LdapRepository",
    "ensure_container_exists",
]
