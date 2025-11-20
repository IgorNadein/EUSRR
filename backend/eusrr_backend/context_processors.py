from typing import Dict
from django.conf import settings

def branding(_request) -> Dict[str, str]:
    """Пробрасывает параметры бренда в шаблоны.

    Args:
        _request: Объект запроса (не используется).

    Returns:
        Dict[str, str]: Словарь с ключами BRAND_NAME и BRAND_LOGO для {% static %}.

    Raises:
        AttributeError: Если в settings отсутствуют BRAND_NAME или BRAND_LOGO.
    """
    # Значения по умолчанию оставлены безопасными — но явно валидируем наличие.
    name = getattr(settings, "BRAND_NAME", None)
    logo = getattr(settings, "BRAND_LOGO", None)
    if not name or not logo:
        raise AttributeError("BRAND_NAME/BRAND_LOGO must be set in settings.py")
    return {"BRAND_NAME": name, "BRAND_LOGO": logo}
