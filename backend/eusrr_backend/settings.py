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
    # Celery приложения
    "django_celery_beat",  # Периодические задачи
    "django_celery_results",  # Хранение результатов
    # Основные приложения
    "employees.apps.EmployeesConfig",
    "api.apps.ApiConfig",

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
    "default": {
        "ENGINE": "django.db.backends.sqlite3" if USE_SQLITE else "django.db.backends.postgresql",
        "NAME": os.path.join(BASE_DIR, "db.sqlite3") if USE_SQLITE else os.getenv("POSTGRES_DB", "django"),
    }
}

if not USE_SQLITE:
    DATABASES["default"].update({
        "USER": os.getenv("POSTGRES_USER", "django"),
        "PASSWORD": os.getenv("POSTGRES_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", "127.0.0.1"),
        "PORT": os.getenv("DB_PORT", "5432"),
    })

# -----------------------------------------------------------------------------
# АВТОРИЗАЦИЯ / ПАРОЛИ
# -----------------------------------------------------------------------------

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
# Создаем директорию для логов
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        #Detalized format for development
        "verbose": {
            "format": "[{levelname:8s}] {asctime} | {name:30s} | {funcName:20s}:{lineno:4d} | {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        # Simple format for production console
        "simple": {
            "format": "[{levelname:8s}] {asctime} | {name} | {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        # Structured format for parsing
        "json_style": {
            "format": "%(asctime)s | %(levelname)s | %(name)s | %(funcName)s:%(lineno)d | %(message)s",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
    },
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "handlers": {
        # Console output
        "console": {
            "level": "DEBUG" if DEBUG else "INFO",
            "class": "logging.StreamHandler",
            "formatter": "verbose" if DEBUG else "simple",
        },
        # All logs (INFO+) with rotation
        "file_all": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "all.log",
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 5,
            "formatter": "json_style",
            "encoding": "utf-8",
        },
        # Error logs (ERROR+) with rotation
        "file_error": {
            "level": "ERROR",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "error.log",
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 10,
            "formatter": "verbose",
            "encoding": "utf-8",
        },
        # Debug logs (only in DEBUG mode)
        "file_debug": {
            "level": "DEBUG",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "debug.log",
            "maxBytes": 20 * 1024 * 1024,  # 20 MB
            "backupCount": 3,
            "formatter": "verbose",
            "encoding": "utf-8",
            "filters": ["require_debug_true"],
        },
        # Security logs (authentication, permissions, etc)
        "file_security": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "security.log",
            "maxBytes": 10 * 1024 * 1024,  # 10 MB
            "backupCount": 20,
            "formatter": "json_style",
            "encoding": "utf-8",
        },
        # Django request logs
        "file_requests": {
            "level": "INFO",
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOGS_DIR / "requests.log",
            "maxBytes": 20 * 1024 * 1024,  # 20 MB
            "backupCount": 5,
            "formatter": "json_style",
            "encoding": "utf-8",
        },
        # Mail admins on errors (production only)
        "mail_admins": {
            "level": "ERROR",
            "class": "django.utils.log.AdminEmailHandler",
            "filters": ["require_debug_false"],
            "formatter": "verbose",
        },
    },
    "loggers": {
        # Root logger
        "": {
            "handlers": ["console", "file_all", "file_error"],
            "level": "DEBUG" if DEBUG else "INFO",
        },
        # Django core
        "django": {
            "handlers": ["console", "file_all", "file_error"],
            "level": "INFO",
            "propagate": False,
        },
        "django.request": {
            "handlers": ["console", "file_requests", "file_error", "mail_admins"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.server": {
            "handlers": ["console", "file_requests"],
            "level": "INFO",
            "propagate": False,
        },
        # SQL queries (only in DEBUG mode)
        "django.db.backends": {
            "handlers": ["console", "file_debug"] if DEBUG else [],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        # Security events
        "django.security": {
            "handlers": ["console", "file_security", "mail_admins"],
            "level": "WARNING",
            "propagate": False,
        },
        # Application loggers
        "employees": {
            "handlers": ["console", "file_all", "file_debug", "file_error"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "employees.ldap": {
            "handlers": ["console", "file_all", "file_security", "file_error"],
            "level": "INFO",
            "propagate": False,
        },
        "documents": {
            "handlers": ["console", "file_all", "file_debug", "file_error"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "communications": {
            "handlers": ["console", "file_all", "file_debug", "file_error"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "api.v1.communications": {
            "handlers": ["console", "file_all", "file_debug", "file_error"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "notifications": {
            "handlers": ["console", "file_all", "file_error"],
            "level": "INFO",
            "propagate": False,
        },
        "requests_app": {
            "handlers": ["console", "file_all", "file_debug", "file_error"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "bots": {
            "handlers": ["console", "file_all", "file_debug", "file_error"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
        "feed": {
            "handlers": ["console", "file_all", "file_error"],
            "level": "INFO",
            "propagate": False,
        },
        "calendar_app": {
            "handlers": ["console", "file_all", "file_error"],
            "level": "INFO",
            "propagate": False,
        },
        "finance": {
            "handlers": ["console", "file_all", "file_error"],
            "level": "INFO",
            "propagate": False,
        },
        "common": {
            "handlers": ["console", "file_all", "file_error"],
            "level": "INFO",
            "propagate": False,
        },
        # Third-party integrations
        "ldap3": {
            "handlers": ["console", "file_security", "file_error"],
            "level": "WARNING",
            "propagate": False,
        },
        "aiogram": {
            "handlers": ["console", "file_all", "file_error"],
            "level": "INFO",
            "propagate": False,
        },
        "celery": {
            "handlers": ["console", "file_all", "file_error"],
            "level": "INFO",
            "propagate": False,
        },
        "channels": {
            "handlers": ["console", "file_all", "file_error"],
            "level": "INFO",
            "propagate": False,
        },
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
        "rest_framework_simplejwt.authentication.JWTAuthentication",
        "rest_framework.authentication.SessionAuthentication",
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
LDAP_ENABLED = os.getenv("LDAP_ENABLED", "false").lower() == "true"

# Основное подключение
LDAP_URI = os.getenv("LDAP_URI", "ldap://127.0.0.1:389")
LDAP_BIND_DN = os.getenv("LDAP_BIND_DN", "")
LDAP_BIND_PASSWORD = os.getenv("LDAP_BIND_PASSWORD", "")

# TLS/CA
LDAP_CA_CERTS = os.getenv("LDAP_CA_CERTS", "")
LDAP_TLS_REQUIRED = os.getenv("LDAP_TLS_REQUIRED", "false").lower() == "true"

# DN базы пользователей
LDAP_USER_BASE = os.getenv("LDAP_USER_BASE", "ou=users,dc=eusrr,dc=local")
LDAP_USERS_BASE = os.getenv("LDAP_USERS_BASE", LDAP_USER_BASE)
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", LDAP_USERS_BASE)

# UPN суффикс (домен БЕЗ @)
LDAP_UPN_SUFFIX = os.getenv("LDAP_USER_UPN_SUFFIX", "eusrr.local")

# Фильтры поиска (для OpenLDAP по умолчанию)
LDAP_USER_FILTER = os.getenv(
    "LDAP_USER_FILTER", "(&(objectClass=inetOrgPerson))"
)
LDAP_ACTIVE_FILTER = os.getenv("LDAP_ACTIVE_FILTER", "")


# Атрибуты LDAP
LDAP_ATTR_MAIL = os.getenv("LDAP_ATTR_MAIL", "mail")
LDAP_ATTR_GIVENNAME = os.getenv("LDAP_ATTR_GIVENNAME", "givenName")
LDAP_ATTR_SN = os.getenv("LDAP_ATTR_SN", "sn")
LDAP_ATTR_PHONE = os.getenv("LDAP_ATTR_PHONE", "telephoneNumber")
LDAP_EMPLOYEE_ID_ATTR = os.getenv("LDAP_EMPLOYEE_ID_ATTR", "employeeNumber")
LDAP_PHONE_ATTRS = tuple(
    _split_env_list(os.getenv("LDAP_PHONE_ATTRS", "mobile,telephoneNumber"))
)

# Отделы и группы
LDAP_DEPT_ATTR = os.getenv("LDAP_DEPT_ATTR", "")
LDAP_DEPARTMENTS_BASE = os.getenv(
    "LDAP_DEPARTMENTS_BASE", "OU=Departments,OU=company,DC=eusrr,DC=local"
)
LDAP_DISMISSED_BASE = os.getenv(
    "LDAP_DISMISSED_BASE", "OU=Dismissed,OU=company,DC=eusrr,DC=local"
)
LDAP_POSITIONS_BASE = os.getenv(
    "LDAP_POSITIONS_BASE", "OU=Positions,OU=company,DC=eusrr,DC=local"
)
LDAP_GROUPS_BASE = os.getenv("LDAP_GROUPS_BASE", "")

LDAP_SYNC_GROUPS = os.getenv("LDAP_SYNC_GROUPS", "false").lower() == "true"
LDAP_GROUP_ATTR = os.getenv("LDAP_GROUP_ATTR", "memberOf")
LDAP_GROUP_MAP = {}
LDAP_GROUPS_EXCLUSIVE = os.getenv("LDAP_GROUPS_EXCLUSIVE", "false").lower() == "true"

# WRITE-BACK (двусторонняя синхронизация)
LDAP_WRITE_ENABLED = os.getenv("LDAP_WRITE_ENABLED", "false").lower() == "true"
LDAP_WRITE_DN = os.getenv("LDAP_WRITE_DN", LDAP_BIND_DN)
LDAP_WRITE_PASSWORD = os.getenv("LDAP_WRITE_PASSWORD", LDAP_BIND_PASSWORD)
LDAP_WRITE_TIMEOUT = int(os.getenv("LDAP_WRITE_TIMEOUT", "5"))

# Маппинг локальных полей на LDAP атрибуты
LDAP_WRITE_ATTRS = {
    "first_name": LDAP_ATTR_GIVENNAME,
    "last_name": LDAP_ATTR_SN,
    "phone": LDAP_ATTR_PHONE,
}

# LWW (Last Writer Wins) для разрешения конфликтов синхронизации
LDAP_ASSERT_ATTR = os.getenv("LDAP_ASSERT_ATTR", "modifyTimestamp")  # modifyTimestamp (OpenLDAP) или whenChanged (AD)
LOCAL_ASSERT_FIELD = os.getenv("LOCAL_ASSERT_FIELD", "updated_at")

# Дополнительные атрибуты при создании пользователя в LDAP
LDAP_CREATE_EXTRA_ATTRS = {
    "sAMAccountName": "{username20}",
    "userPrincipalName": "{upn}",
    "givenName": "{first_name_or_dot}",
    "sn": "{last_name_or_dot}",
    "displayName": "{cn}",
    "mail": "{email}",
}

# Режим синхронизации и таймауты
LDAP_SYNC_MODE = os.getenv("LDAP_SYNC_MODE", "lww")  # lww|ldap|django
LDAP_PURGE = os.getenv("LDAP_PURGE", "false").lower() == "true"
LDAP_CONNECT_TIMEOUT = int(os.getenv("LDAP_CONNECT_TIMEOUT", "5"))
LDAP_OPERATION_TIMEOUT = int(os.getenv("LDAP_OPERATION_TIMEOUT", "10"))

# Флаги поведения
LDAP_AUTO_CREATE = os.getenv("LDAP_AUTO_CREATE", "False").lower() == "true"
LDAP_RESPECT_IS_ACTIVE = True
LDAP_RESPECT_AD_DISABLED = True
LDAP_REGISTRATION_CREATE = True



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

# -----------------------------------------------------------------------------
# CELERY CONFIGURATION
# -----------------------------------------------------------------------------
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

# Сериализация
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'

# Таймзона
CELERY_TIMEZONE = 'Europe/Moscow'
CELERY_ENABLE_UTC = True

# Мониторинг и отладка
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 минут максимум на задачу
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # Мягкий лимит - 25 минут

# Приоритеты очередей
CELERY_TASK_ROUTES = {
    'notifications.tasks.*': {'queue': 'notifications'},
    'documents.tasks.*': {'queue': 'default'},
    'employees.tasks.*': {'queue': 'default'},
}

# Настройки для периодических задач (Celery Beat)
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# Расписание периодических задач
CELERY_BEAT_SCHEDULE = {
    'cleanup-orphaned-attachments': {
        'task': 'communications.tasks.cleanup_orphaned_attachments',
        'schedule': 3600.0,  # Каждый час
    },
}

# Опции по умолчанию для всех задач
CELERY_TASK_ACKS_LATE = True  # Подтверждаем выполнение после завершения
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Берем по 1 задаче за раз
CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000  # Перезапуск worker после 1000 задач
