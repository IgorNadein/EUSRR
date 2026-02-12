# backend/calendar_app/cache.py
"""Утилиты для управления кешем календаря."""

from django.core.cache import cache


def invalidate_calendar_cache(calendar_id=None, user_id=None):
    """Инвалидация кеша календаря.

    Args:
        calendar_id: ID календаря (опционально)
        user_id: ID пользователя (опционально)
    """
    patterns = []

    if calendar_id:
        # Кеш конкретного календаря
        patterns.extend(
            [
                f"calendar:events:{calendar_id}:*",
                f"calendar:detail:{calendar_id}",
                f"calendar:subscriptions:{calendar_id}:*",
            ]
        )
    else:
        # Все события и календари
        patterns.extend(
            [
                "calendar:events:*",
                "calendar:list:*",
                "calendar:subscriptions:*",
            ]
        )

    if user_id:
        # Кеш пользователя
        patterns.extend(
            [
                f"calendar:user:{user_id}:*",
                f"calendar:my_calendars:{user_id}",
            ]
        )

    # Удаляем по паттернам
    for pattern in patterns:
        # Django cache не поддерживает wildcards напрямую,
        # поэтому используем delete с точным ключом
        cache.delete(pattern.replace(":*", ""))


def invalidate_event_cache(event_id=None):
    """Инвалидация кеша событий.

    Args:
        event_id: ID события (опционально)
    """
    if event_id:
        cache.delete(f"calendar:event:{event_id}")
    else:
        # Инвалидация всех событий
        cache.delete("calendar:events")


def invalidate_subscription_cache(user_id=None):
    """Инвалидация кеша подписок.

    Args:
        user_id: ID пользователя (опционально)
    """
    if user_id:
        cache.delete(f"calendar:subscriptions:user:{user_id}")
        cache.delete(f"calendar:my_calendars:{user_id}")
    else:
        cache.delete("calendar:subscriptions")
