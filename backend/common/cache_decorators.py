"""
Декораторы для кэширования Django views с умной инвалидацией
"""
from functools import wraps
from django.core.cache import cache
from django.http import HttpResponse


def cache_page_per_user(timeout=300, cache_prefix="view"):
    """
    Кэширует страницу для каждого пользователя отдельно

    Args:
        timeout: Время жизни кэша в секундах (по умолчанию 5 минут)
        cache_prefix: Префикс для ключа кэша
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            # Создаем уникальный ключ для пользователя и URL
            user_id = (
                request.user.id if request.user.is_authenticated else 'anon'
            )
            cache_key = (
                f"{cache_prefix}:user_{user_id}:"
                f"{request.path}:{request.GET.urlencode()}"
            )

            # Проверяем кэш
            cached_response = cache.get(cache_key)
            if cached_response is not None:
                # Добавляем заголовки для отладки и браузерного кэша
                cached_response['X-Cache'] = 'HIT'
                cached_response['Cache-Control'] = (
                    f'private, max-age={timeout}'
                )
                return cached_response

            # Генерируем ответ
            response = view_func(request, *args, **kwargs)

            # Кэшируем только успешные GET-запросы
            if (
                request.method == 'GET'
                and isinstance(response, HttpResponse)
                and response.status_code == 200
            ):
                response['X-Cache'] = 'MISS'
                response['Cache-Control'] = (
                    f'private, max-age={timeout}'
                )
                cache.set(cache_key, response, timeout)

            return response

        return wrapper
    return decorator


def invalidate_cache_pattern(pattern):
    """
    Инвалидирует все ключи кэша, соответствующие паттерну

    Args:
        pattern: Паттерн для поиска ключей (например, "view:user_*:feed")
    """
    # Redis-специфичная реализация
    try:
        from django.core.cache.backends.redis import RedisCache
        cache_backend = cache._cache  # noqa: SLF001

        if isinstance(cache_backend, RedisCache):
            client = cache_backend._client  # noqa: SLF001
            # Используем SCAN для безопасного поиска ключей
            full_pattern = f"{cache.key_prefix}:{pattern}"
            keys = []
            for key in client.scan_iter(match=full_pattern, count=100):
                keys.append(key)

            if keys:
                client.delete(*keys)
                return len(keys)
    except Exception as e:
        print(f"Cache invalidation error: {e}")

    return 0


def cache_api_response(timeout=60, key_prefix="api"):
    """
    Кэширует API-ответы (для использования в ApiClient)

    Args:
        timeout: Время жизни кэша в секундах
        key_prefix: Префикс для ключа кэша
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Строим ключ из URL и параметров
            method = kwargs.get('method', 'GET')
            url = kwargs.get('url', '')
            params = kwargs.get('params', {})

            if method != 'GET':
                # Кэшируем только GET-запросы
                return func(*args, **kwargs)

            # Создаем детерминированный ключ
            import json
            params_str = json.dumps(params, sort_keys=True)
            cache_key = f"{key_prefix}:{method}:{url}:{params_str}"

            # Проверяем кэш
            cached = cache.get(cache_key)
            if cached is not None:
                return cached

            # Выполняем запрос
            result = func(*args, **kwargs)

            # Кэшируем успешные ответы
            if result and getattr(result, 'ok', False):
                cache.set(cache_key, result, timeout)

            return result

        return wrapper
    return decorator
