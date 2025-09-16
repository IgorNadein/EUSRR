import os
from pathlib import Path
from datetime import timedelta

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")


INSTALLED_APPS = [
    "daphne",
    "channels",
    "django.contrib.admin",
    "django_bootstrap5",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "widget_tweaks",
    "simple_history",
    "rest_framework",
    "employees.apps.EmployeesConfig",
    "api.apps.ApiConfig",
    "hikcentral.apps.HikcentralConfig",
    "calendar_app.apps.CalendarAppConfig",
    "documents.apps.DocumentsConfig",
    "requests_app.apps.RequestsAppConfig",
    "feed.apps.FeedConfig",
    "communications.apps.CommunicationsConfig",
    "search.apps.SearchConfig",
    "bots",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "simple_history.middleware.HistoryRequestMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "eusrr_backend.middleware.AuthRequiredMiddleware",
]

ROOT_URLCONF = "eusrr_backend.urls"

TEMPLATES_DIR = BASE_DIR / "templates"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [TEMPLATES_DIR],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "communications.context_processors.chat_unread_total",
            ],
        },
    },
]

WSGI_APPLICATION = "eusrr_backend.wsgi.application"


USE_SQLITE = os.getenv("USE_SQLITE", "False").lower() == "true"

DATABASES = {
    "default": {},
    "hikcentral": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": "cms",
        "USER": "postgres",
        "PASSWORD": None,
        "HOST": "127.0.0.1",
        "PORT": "5432",
        "OPTIONS": {"options": "-c search_path=platform"},
    },
}

if USE_SQLITE:
    # Конфигурация для SQLite
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
    }
else:
    # Конфигурация для PostgreSQL
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "django"),
        "USER": os.getenv("POSTGRES_USER", "django"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", ""),
        "PORT": os.getenv("DB_PORT", "5432"),
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]


LANGUAGE_CODE = "ru"

TIME_ZONE = "Europe/Moscow"

USE_I18N = True

USE_TZ = True


STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

AUTH_USER_MODEL = "employees.Employee"

API_LOGIN_URL_NAME = "auth_front:login"
LOGIN_URL = "auth_front:login"
LOGIN_REDIRECT_URL = "/"
# LOGOUT_REDIRECT_URL = 'login'
REGISTRATION_AUTO_LOGIN = True
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24

PHONE_DEFAULT_REGION = os.getenv("PHONE_DEFAULT_REGION", "RU")

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media/")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name}:{lineno} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG",
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "loggers": {
        # собственные приложения
        "documents": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        "bots": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
        # всё, что делает Django
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        # и библиотека aiogram
        "aiogram": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

PHONENUMBER_DEFAULT_REGION = "RU"

CSRF_TRUSTED_ORIGINS = os.getenv(
    "CSRF_TRUSTED_ORIGINS", default="https://*.sytes.net"
).split(",")

EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "465"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "false").lower() == "true"
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "true").lower() == "true"
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "webmaster@localhost"
)
ASGI_APPLICATION = "eusrr_backend.asgi.application"

AUTHENTICATION_BACKENDS = [
    "eusrr_backend.auth_backends.EmailOrPhoneBackend",
    "eusrr_backend.auth_backends.PositionRoleBackend",
    "django.contrib.auth.backends.ModelBackend",
]

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [("127.0.0.1", 6379)],
        },
    }
}

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication"
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "rest_framework.permissions.DjangoModelPermissions",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MIN", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "7"))),
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "LEEWAY": 30,  # допускаем ±30с рассинхронизации времени
}

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:9000/api")

# LOGGING = {
#     'version': 1,
#     'handlers': {
#         'console': {
#             'class': 'logging.StreamHandler',
#         },
#     },
#     'loggers': {
#         'your_app': {
#             'handlers': ['console'],
#             'level': 'DEBUG',
#         },
#     },
# }