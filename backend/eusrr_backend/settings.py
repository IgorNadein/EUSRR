import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# -----------------------------------------------------------------------------
# БАЗОВЫЕ НАСТРОЙКИ
# -----------------------------------------------------------------------------
SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"


def _split_env_list(value: str) -> list[str]:
    return [x.strip() for x in (value or "").split(",") if x.strip()]


ALLOWED_HOSTS = _split_env_list(os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1"))

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
    "realtime.apps.RealtimeConfig",  # WebSocket consumers для real-time
    "communications.apps.CommunicationsConfig",
    "notifications.apps.NotificationsConfig",
    "search.apps.SearchConfig",
    "bots",
    "finance.apps.FinanceConfig",
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
    "api.middleware.JWTRefreshMiddleware",  # Автообновление JWT токенов
    "eusrr_backend.middleware.AuthRequiredMiddleware",
    "eusrr_backend.middleware.EmailVerificationMiddleware",
    "eusrr_backend.middleware.RegistrationIPRestrictionMiddleware",  # IP ограничение для регистрации
    "eusrr_backend.middleware.CacheControlMiddleware",  # Cache-Control headers
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
                "eusrr_backend.context_processors.branding",
            ],
        },
    },
]

WSGI_APPLICATION = "eusrr_backend.wsgi.application"
ASGI_APPLICATION = "eusrr_backend.asgi.application"

# -----------------------------------------------------------------------------
# БАЗА ДАННЫХ
# -----------------------------------------------------------------------------
USE_SQLITE = os.getenv("USE_SQLITE", "false").lower() == "true"

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
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3"),
    }
else:
    DATABASES["default"] = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.getenv("POSTGRES_DB", "django"),
        "USER": os.getenv("POSTGRES_USER", "django"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
    }

# -----------------------------------------------------------------------------
# АВТОРИЗАЦИЯ / ПАРОЛИ
# -----------------------------------------------------------------------------
# AUTH_PASSWORD_VALIDATORS = [
#     {
#         "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
#     },
#     {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
#     {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
#     {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
# ]

LANGUAGE_CODE = "ru"
TIME_ZONE = "Europe/Moscow"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
AUTH_USER_MODEL = "employees.Employee"

API_LOGIN_URL_NAME = "auth_front:login"
# Внутренний URL для API клиента (для запросов view -> API внутри сервера)
# Используем локальный адрес для избежания проблем с SSL
API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:9000/api")
LOGIN_URL = "auth_front:login"
LOGIN_REDIRECT_URL = "/"
REGISTRATION_AUTO_LOGIN = True
PASSWORD_RESET_TIMEOUT = 60 * 60 * 24

PHONE_DEFAULT_REGION = os.getenv("PHONE_DEFAULT_REGION", "RU")
PHONENUMBER_DEFAULT_REGION = "RU"

# -----------------------------------------------------------------------------
# IP ОГРАНИЧЕНИЯ ДЛЯ РЕГИСТРАЦИИ
# -----------------------------------------------------------------------------
# Список разрешенных IP-адресов или сетей для регистрации (формат CIDR)
# Примеры:
#   None - разрешены только локальные IP (по умолчанию)
#   ['*'] - разрешены все IP
#   ['192.168.1.0/24', '10.0.0.0/8'] - конкретные сети
#   ['192.168.1.100', '192.168.1.101'] - конкретные IP
REGISTRATION_ALLOWED_IPS = [
    '127.0.0.0/8',      # localhost
    '10.0.0.0/8',       # приватная сеть класса A
    '172.16.0.0/12',    # приватная сеть класса B (172.16-31.x.x)
    '172.11.0.0/16',    # ваша корпоративная сеть
    '192.168.0.0/16',   # приватная сеть класса C
]

# Медиа файлы
MEDIA_ROOT = os.path.join(BASE_DIR, "media/")
MEDIA_URL = "/media/"

# Лимиты загрузки файлов
# По умолчанию Django ограничивает загрузку до 2.5MB
# Увеличиваем до 10MB для аватаров и документов
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB

# -----------------------------------------------------------------------------
# ЛОГИРОВАНИЕ
# -----------------------------------------------------------------------------
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
        "documents": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "bots": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "communications": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "notifications": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "requests_app": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "employees": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "common": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "aiogram": {"handlers": ["console"], "level": "INFO", "propagate": False},
        # полезно видеть ошибки и отладку ldap3
        "ldap3": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

# -----------------------------------------------------------------------------
# БЕЗОПАСНОСТЬ И ПРОКСИ
# -----------------------------------------------------------------------------
CSRF_TRUSTED_ORIGINS = _split_env_list(
    os.getenv("CSRF_TRUSTED_ORIGINS", "https://*.sytes.net")
)

# Настройки CSRF для AJAX запросов
CSRF_COOKIE_HTTPONLY = False  # Позволяет JavaScript читать cookie
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_USE_SESSIONS = False

# -----------------------------------------------------------------------------
# EMAIL
# -----------------------------------------------------------------------------
EMAIL_BACKEND = os.getenv(
    "EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend"
)
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "465"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_SSL = os.getenv("EMAIL_USE_SSL", "true").lower() == "true"
# Если SSL включён (465), TLS должен быть False
EMAIL_USE_TLS = (
    False if EMAIL_USE_SSL else (os.getenv("EMAIL_USE_TLS", "false").lower() == "true")
)
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "webmaster@localhost"
)

# -----------------------------------------------------------------------------
# NOTIFICATIONS
# -----------------------------------------------------------------------------
# Порог для определения массовой рассылки (количество получателей)
# При массовой рассылке уведомления создаются быстро, а отправка идёт в фоне
NOTIFICATION_BULK_THRESHOLD = int(os.getenv("NOTIFICATION_BULK_THRESHOLD", "10"))

# -----------------------------------------------------------------------------
# CHANNELS & CACHE
# -----------------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": (
            f"redis://{os.getenv('REDIS_HOST', '127.0.0.1')}:"
            f"{os.getenv('REDIS_PORT', '6379')}/1"
        ),
        "OPTIONS": {
            "db": "1",  # Используем отдельную БД для кэша (Channels - 0)
        },
        "KEY_PREFIX": "eusrr_cache",
        "TIMEOUT": 300,  # 5 минут по умолчанию
    }
}

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [
                (
                    os.getenv("REDIS_HOST", "127.0.0.1"),
                    int(os.getenv("REDIS_PORT", "6379")),
                )
            ],
        },
    }
}

# -----------------------------------------------------------------------------
# DRF / JWT
# -----------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework_simplejwt.authentication.JWTAuthentication"
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
        "rest_framework.permissions.DjangoModelPermissions",
    ],
    "DEFAULT_THROTTLE_CLASSES": ["rest_framework.throttling.AnonRateThrottle"],
    "DEFAULT_THROTTLE_RATES": {"anon": "60/min"},
    "DEFAULT_PAGINATION_CLASS": "api.pagination.StandardPagination",
    "PAGE_SIZE": 20,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=int(os.getenv("JWT_ACCESS_MIN", "30"))),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "7"))),
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "LEEWAY": 30,
}

# Автообновление JWT токенов: за сколько минут до истечения обновлять
JWT_REFRESH_THRESHOLD_MINUTES = int(os.getenv("JWT_REFRESH_THRESHOLD_MIN", "5"))


# -----------------------------------------------------------------------------
# АУТЕНТИФИКАЦИОННЫЕ БЭКЕНДЫ
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# AUTHENTICATION_BACKENDS
# -----------------------------------------------------------------------------
# Порядок важен: первый успешный бэкенд останавливает цепочку
AUTHENTICATION_BACKENDS = [
    "eusrr_backend.auth_backends.LDAP3Backend",  # работает только если LDAP_ENABLED=True
    "eusrr_backend.auth_backends.EmailOrPhoneBackend",  # фоллбэк для режима без LDAP
    "eusrr_backend.auth_backends.SuperuserOnlyBackend",  # экстренный доступ для админа
    "eusrr_backend.auth_backends.PositionRoleBackend",  # расчёт прав на основе должностей
    "django.contrib.auth.backends.ModelBackend",  # стандартный Django бэкенд
]

# -----------------------------------------------------------------------------
# LDAP (двусторонний обмен + LWW)
# -----------------------------------------------------------------------------
LDAP_ENABLED = os.getenv("LDAP_ENABLED", "true").lower() == "true"

# Основное подключение
LDAP_URI = os.getenv("LDAP_URI", "ldaps://dcii.robotail.local:636")
LDAP_BIND_DN = os.getenv("LDAP_BIND_DN", "")
LDAP_BIND_PASSWORD = os.getenv("LDAP_BIND_PASSWORD", "")

# TLS/CA
LDAP_CA_CERTS = os.getenv("LDAP_CA_CERTS", "")  # путь к CA bundle/серту (если нужен)
LDAP_TLS_REQUIRED = os.getenv("LDAP_TLS_REQUIRED", "true").lower() == "true"

# Где искать пользователей
LDAP_USER_BASE = os.getenv("LDAP_USER_BASE", "OU=company,DC=robotail,DC=local")
# Где создавать новых пользователей (может отличаться от базы поиска)
LDAP_USERS_BASE = os.getenv("LDAP_USERS_BASE", LDAP_USER_BASE)
# Базовый DN для операций создания (если не указан department_dn)
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", LDAP_USERS_BASE)
# UPN-суффикс для создания пользователей (userPrincipalName) - домен БЕЗ @
LDAP_UPN_SUFFIX = os.getenv("LDAP_USER_UPN_SUFFIX", "robotail.local")

LDAP_USER_FILTER = os.getenv(
    "LDAP_USER_FILTER", "(&(objectCategory=person)(objectClass=user))"
)
# Для AD по умолчанию; для OpenLDAP можно обнулить в .env
LDAP_ACTIVE_FILTER = os.getenv(
    "LDAP_ACTIVE_FILTER",
    "(!(userAccountControl:1.2.840.113556.1.4.803:=2))",  # битовый NOT DISABLED
)


LDAP_ATTR_MAIL = os.getenv("LDAP_ATTR_MAIL", "mail")
LDAP_ATTR_GIVENNAME = os.getenv("LDAP_ATTR_GIVENNAME", "givenName")
LDAP_ATTR_SN = os.getenv("LDAP_ATTR_SN", "sn")
LDAP_ATTR_PHONE = os.getenv("LDAP_ATTR_PHONE", "telephoneNumber")
LDAP_PHONE_ATTRS = tuple(
    _split_env_list(os.getenv("LDAP_PHONE_ATTRS", "mobile,telephoneNumber"))
)

LDAP_DEPT_ATTR = os.getenv("LDAP_DEPT_ATTR", "")  # например, departmentNumber
LDAP_SYNC_GROUPS = os.getenv("LDAP_SYNC_GROUPS", "false").lower() == "true"
LDAP_GROUP_ATTR = os.getenv("LDAP_GROUP_ATTR", "memberOf")
# Пример: {"CN=HR,OU=Groups,DC=...,DC=...": "hr"}
LDAP_GROUP_MAP = {}
LDAP_GROUPS_EXCLUSIVE = os.getenv("LDAP_GROUPS_EXCLUSIVE", "false").lower() == "true"

# WRITE-BACK
LDAP_WRITE_ENABLED = os.getenv("LDAP_WRITE_ENABLED", "false").lower() == "true"
LDAP_WRITE_DN = os.getenv("LDAP_WRITE_DN", LDAP_BIND_DN)
LDAP_WRITE_PASSWORD = os.getenv("LDAP_WRITE_PASSWORD", LDAP_BIND_PASSWORD)
LDAP_WRITE_TIMEOUT = int(os.getenv("LDAP_WRITE_TIMEOUT", "5"))

# UPN суффикс для создания пользователей (домен БЕЗ @, например robotail.local)
LDAP_UPN_SUFFIX = os.getenv("LDAP_USER_UPN_SUFFIX", "robotail.local")

# Белый список: локальные поля -> LDAP-атрибуты
LDAP_WRITE_ATTRS = {
    "first_name": LDAP_ATTR_GIVENNAME,
    "last_name": LDAP_ATTR_SN,
    # фактическое имя локального телефонного поля подставляет код
    "phone": LDAP_ATTR_PHONE,
    # "photo": "jpegPhoto",
}

# LWW (Last Writer Wins) — сравнение меток изменения
# Для AD обычно whenChanged, для OpenLDAP — modifyTimestamp
LDAP_ASSERT_ATTR_AD = "whenChanged"
LDAP_ASSERT_ATTR_OL = "modifyTimestamp"
LDAP_ASSERT_ATTR = os.getenv("LDAP_ASSERT_ATTR", LDAP_ASSERT_ATTR_AD)

# Локальное поле «последнее изменение» (ваше поле модели, напр. updated_at)
LOCAL_ASSERT_FIELD = os.getenv("LOCAL_ASSERT_FIELD", "updated_at")
LDAP_CREATE_EXTRA_ATTRS = {
    "sAMAccountName": "{username20}",
    "userPrincipalName": "{upn}",
    "givenName": "{first_name_or_dot}",
    "sn": "{last_name_or_dot}",
    "displayName": "{cn}",
    "mail": "{email}",
}
LDAP_SYNC_MODE = os.getenv("LDAP_SYNC_MODE", "lww")  # lww|ldap|django
LDAP_PURGE = os.getenv("LDAP_PURGE", "false").lower() == "true"

LDAP_CONNECT_TIMEOUT = int(os.getenv("LDAP_CONNECT_TIMEOUT", "5"))
LDAP_OPERATION_TIMEOUT = int(os.getenv("LDAP_OPERATION_TIMEOUT", "10"))


LDAP_USERS_BASE = os.getenv("LDAP_USERS_BASE")
LDAP_USER_BASE = os.getenv("LDAP_USER_BASE")
LDAP_DEPARTMENTS_BASE = os.getenv(
    "LDAP_DEPARTMENTS_BASE", "OU=Departments,OU=company,DC=robotail,DC=local"
)
LDAP_DISMISSED_BASE = os.getenv(
    "LDAP_DISMISSED_BASE", "OU=Dismissed,OU=company,DC=robotail,DC=local"
)
LDAP_GROUPS_BASE = os.getenv("LDAP_GROUPS_BASE")

LDAP_AUTO_CREATE = os.getenv("LDAP_AUTO_CREATE", "False")

LDAP_RESPECT_IS_ACTIVE = True
LDAP_RESPECT_AD_DISABLED = True
LDAP_REGISTRATION_CREATE = True
LDAP_POSITIONS_BASE = os.getenv("LDAP_POSITIONS_BASE")



BRAND_NAME = os.getenv("BRAND_NAME", "HiRo")
BRAND_LOGO = "img/logo.png"

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "eusrr_bot")

# Web Push Notifications (VAPID)
# Ключи для авторизации push-уведомлений
VAPID_PUBLIC_KEY = os.getenv(
    "VAPID_PUBLIC_KEY",
    "BMTitZy9r4ygYJBgGdaZuCkb7rwR7iHLJv0DkNpaJOLESotONETWtZAQxnJVU_Yo9v-iYo-7dWEeF0VEjMcGMkQ"
)
VAPID_PRIVATE_KEY = os.getenv(
    "VAPID_PRIVATE_KEY",
    "MIGHAgEAMBMGByqGSM49AgEGCCqGSM49AwEHBG0wawIBAQQgCNnpupg3xbtFUiOSUZ6L7s6puxuEjzR73kTL7v8bMvKhRANCAATE4rWcva-MoGCQYBnWmbgpG-68Ee4hyyb9A5DaWiTixEqLTjRE1rWQEMZyVVP2KPb_omKPu3VhHhdFRIzHBjJE"
)
VAPID_ADMIN_EMAIL = os.getenv("VAPID_ADMIN_EMAIL", "robotail-info@yandex.ru")