"""Утилиты для обработки текста и экранирования.

Функции для транслитерации, экранирования LDAP-значений и нормализации текста.
"""

from typing import Optional

from ldap3.utils.conv import escape_filter_chars


# Словарь для транслитерации русских символов в латиницу
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


def translit_to_ascii(text: str) -> str:
    """Транслитерирует строку в ascii: [a-z0-9], нижний регистр.

    Args:
        text (str): Входная строка.

    Returns:
        str: Нормализованная ASCII-строка.

    Raises:
        TypeError: Если text не строка.
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
        # Fallback если ldap3 не сработал
        return (
            s.replace("\\", r"\5c")
            .replace("*", r"\2a")
            .replace("(", r"\28")
            .replace(")", r"\29")
            .replace("\x00", r"\00")
        )


def esc_rdn(text: str) -> str:
    """Экранирует RDN-компонент Distinguished Name.

    Args:
        text (str): RDN-значение (например, "John, Doe").

    Returns:
        str: Экранированная строка (например, "John\\, Doe").
    """
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


__all__ = [
    "translit_to_ascii",
    "esc_filter",
    "esc_rdn",
]
