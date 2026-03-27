"""Утилиты для безопасной обработки данных запросов."""
from typing import Any, Optional, Union


def safe_int(value: Any, default: int = 0) -> int:
    """Безопасно конвертирует значение в int.
    
    Args:
        value: Значение для конверсии (может быть str, int, None, ...)
        default: Значение по умолчанию при ошибке конверсии
    
    Returns:
        int: Сконвертированное значение или default
    
    Examples:
        >>> safe_int('123')
        123
        >>> safe_int('abc', default=1)
        1
        >>> safe_int(None, default=10)
        10
        >>> safe_int('', default=5)
        5
    """
    if value is None or value == '':
        return default
    
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def safe_bool(value: Any, default: bool = False) -> bool:
    """Безопасно конвертирует значение в bool.
    
    Поддерживает строки: 'true', 'false', '1', '0', 'yes', 'no'
    
    Args:
        value: Значение для конверсии
        default: Значение по умолчанию при ошибке
    
    Returns:
        bool: Сконвертированное значение или default
    """
    if value is None:
        return default
    
    if isinstance(value, bool):
        return value
    
    if isinstance(value, (int, float)):
        return bool(value)
    
    if isinstance(value, str):
        value_lower = value.lower().strip()
        if value_lower in ('true', '1', 'yes', 'on'):
            return True
        if value_lower in ('false', '0', 'no', 'off', ''):
            return False
    
    return default


def safe_float(value: Any, default: float = 0.0) -> float:
    """Безопасно конвертирует значение в float.
    
    Args:
        value: Значение для конверсии
        default: Значение по умолчанию при ошибке
    
    Returns:
        float: Сконвертированное значение или default
    """
    if value is None or value == '':
        return default
    
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def safe_get_data(
    data: Union[dict, 'QueryDict'],
    key: str,
    default: Any = None,
    required: bool = False,
) -> Any:
    """Безопасно извлекает значение из request.data.
    
    Args:
        data: request.data (может быть dict или QueryDict)
        key: Ключ для извлечения
        default: Значение по умолчанию
        required: Если True, вызовет KeyError при отсутствии ключа
    
    Returns:
        Значение или default
    
    Raises:
        KeyError: Если required=True и ключа нет
    
    Examples:
        >>> safe_get_data({'name': 'John'}, 'name')
        'John'
        >>> safe_get_data({}, 'age', default=18)
        18
        >>> safe_get_data({}, 'email', required=True)
        KeyError: 'email'
    """
    if required and key not in data:
        raise KeyError(f"Required field '{key}' is missing")
    
    return data.get(key, default)
