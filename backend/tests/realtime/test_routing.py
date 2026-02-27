# tests/realtime/test_routing.py
"""
Тесты для WebSocket routing.
Проверяем правильность маршрутизации WebSocket подключений.
"""
import pytest
from channels.routing import URLRouter
from django.urls import re_path

from realtime.routing import websocket_urlpatterns
from realtime.consumers import UserConsumer


def test_websocket_urlpatterns_structure():
    """Проверяем структуру websocket_urlpatterns."""
    assert isinstance(websocket_urlpatterns, list)
    assert len(websocket_urlpatterns) > 0
    
    # Проверяем, что есть паттерн для ws/
    patterns = [str(p.pattern) for p in websocket_urlpatterns]
    assert any("ws" in p for p in patterns), "Должен быть паттерн для /ws/"


def test_websocket_uses_user_consumer():
    """Проверяем, что WebSocket использует UserConsumer."""
    # Проверяем первый паттерн
    first_pattern = websocket_urlpatterns[0]
    
    # Получаем callback (consumer)
    consumer_class = first_pattern.callback.keywords.get('consumer_class')
    
    # Может быть обернут в as_asgi()
    # Проверяем тип или имя
    assert 'UserConsumer' in str(first_pattern.callback)


def test_url_router_accepts_patterns():
    """Проверяем, что URLRouter принимает наши паттерны."""
    try:
        router = URLRouter(websocket_urlpatterns)
        assert router is not None
    except Exception as e:
        pytest.fail(f"URLRouter не принял websocket_urlpatterns: {e}")
