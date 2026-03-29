"""Утилита для нормализации телефонных номеров.

Обёртка над общей функцией _normalize_phone из employees.utils,
чтобы не создавать зависимость domain → employees.utils напрямую.
"""

from __future__ import annotations

from typing import Optional

from employees.utils import _normalize_phone


def normalize_phone(raw: Optional[str]) -> Optional[str]:
    """Нормализует телефонный номер в формат E.164.

    Args:
        raw: Сырой номер телефона из LDAP (может быть None).

    Returns:
        Нормализованный номер в E.164 или None.
    """
    return _normalize_phone(raw)


__all__ = ["normalize_phone"]
