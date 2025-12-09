"""
Настройки для тестов - используют InMemoryChannelLayer вместо Redis.
"""

from .settings import *  # noqa

# Используем InMemoryChannelLayer для тестов
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}
