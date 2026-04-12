"""
Настройки для тестов - используют InMemoryChannelLayer вместо Redis.
"""

import os

# Тесты работают без LDAP write-back и на SQLite
os.environ.setdefault("USE_SQLITE", "true")
os.environ.setdefault("LDAP_WRITE_ENABLED", "false")
os.environ.setdefault("LDAP_ENABLED", "false")

from .settings import *  # noqa

# Используем InMemoryChannelLayer для тестов
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer"
    }
}

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "eusrr-test-cache",
    }
}

REST_FRAMEWORK = {
    **REST_FRAMEWORK,
    "DEFAULT_THROTTLE_RATES": {
        **REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {}),
        "anon": "10000/min",
    },
}

# Celery - синхронное выполнение в тестах (без отдельного worker)
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True
CELERY_BROKER_URL = 'memory://'
CELERY_RESULT_BACKEND = 'cache+memory://'
