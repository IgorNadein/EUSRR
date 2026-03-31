"""
Утилиты для работы с медиа URL
"""
from django.conf import settings


def get_media_base_url(request=None):
    """
    Возвращает базовый URL для медиа-файлов.

    Приоритет:
    1. Если USE_HTTPS=true и DOMAIN установлен → используем его
    2. Если есть request → используем домен из запроса
    3. Fallback → /media/
    """
    # Если в настройках указан предпочтительный домен
    use_https = getattr(settings, 'USE_HTTPS', False)
    domain = getattr(settings, 'DOMAIN', None)

    if domain and domain not in ['127.0.0.1:9000', 'localhost:9000']:
        # Глобальный домен из настроек
        scheme = 'https' if use_https else 'http'
        return f"{scheme}://{domain}/media/"

    # Используем домен из запроса (для локальной разработки)
    if request:
        return request.build_absolute_uri('/media/')

    # Fallback
    return '/media/'


def build_media_url(file_field, request=None):
    """
    Формирует полный URL для медиа-файла.

    Args:
        file_field: ImageField/FileField объект
        request: HTTP запрос (опционально)

    Returns:
        str: Полный URL к файлу
    """
    if not file_field:
        return None

    # Получаем относительный путь
    if hasattr(file_field, 'url'):
        relative_url = file_field.url
    else:
        relative_url = str(file_field)

    # Убираем /media/ если есть
    if relative_url.startswith('/media/'):
        relative_url = relative_url[7:]
    elif relative_url.startswith('/'):
        relative_url = relative_url[1:]

    # Формируем полный URL
    base_url = get_media_base_url(request)
    if not base_url.endswith('/'):
        base_url += '/'

    return f"{base_url}{relative_url}"
