"""
Context processors для глобальных переменных в шаблонах
"""


def media_domain(request):
    """
    Динамически определяет MEDIA_URL на основе текущего домена запроса.
    
    Это позволяет правильно формировать ссылки на медиа как для локального,
    так и для глобального домена без перезапуска сервера.
    """
    host = request.get_host()
    scheme = request.scheme
    
    # Формируем базовый URL для текущего домена
    base_url = f"{scheme}://{host}"
    
    # Динамический MEDIA_URL
    dynamic_media_url = f"{base_url}/media/"
    
    return {
        'MEDIA_URL_DYNAMIC': dynamic_media_url,
        'CURRENT_DOMAIN': host,
        'CURRENT_SCHEME': scheme,
    }
