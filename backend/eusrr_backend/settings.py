import os
import tempfile
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


ALLOWED_HOSTS = _split_env_list(
    os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1"))

INSTALLED_APPS = [
    "daphne",
    "channels",
    "corsheaders",  # django-cors-headers для CORS
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
    "rules",  # django-rules для декларативных permissions
    # django-filer и зависимости
    "easy_thumbnails",
    "filer",
    "mptt",  # зависимость filer
    "reversion",  # django-reversion для версионирования
    # Celery приложения
    "django_celery_beat",  # Периодические задачи
    "django_celery_results",  # Хранение результатов
    # Основные приложения
    "employees.apps.EmployeesConfig",
    "api.apps.ApiConfig",
    "schedule",  # django-scheduler (проверенная библиотека для календаря)
    "scheduling.apps.SchedulingConfig",  # Интеграция и расширения для django-scheduler
    "documents.apps.DocumentsConfig",
    "requests_app.apps.RequestsAppConfig",
    "feed.apps.FeedConfig",
    "realtime.apps.RealtimeConfig",  # WebSocket consumers для real-time
    "communications.apps.CommunicationsConfig",
    "notifications.apps.NotificationsConfig",
    "watson",  # django-watson для полнотекстового поиска
    "search.apps.SearchConfig",
    "finance.apps.FinanceConfig",
    "procurement.apps.ProcurementConfig",
    "push_notifications",  # django-push-notifications для Web Push
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",  # Нужен для Django Admin
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "reversion.middleware.RevisionMiddleware",  # django-reversion для версионирования
    "simple_history.middleware.HistoryRequestMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "api.middleware.JWTRefreshMiddleware",  # Автообновление JWT токенов
    "eusrr_backend.middleware.AuthRequiredMiddleware",
    "eusrr_backend.middleware.EmailVerificationMiddleware",
    # IP ограничение для регистрации
    "eusrr_backend.middleware.RegistrationIPRestrictionMiddleware",
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

# LDAP database для django-ldapdb (используется только для WRITE операций)
# Конфигурация берется из переменных окружения LDAP_URI, LDAP_BIND_DN и т.д.
# которые определены ниже в разделе LDAP
DATABASES["ldap"] = {
    "ENGINE": "ldapdb.backends.ldap",
    "NAME": os.getenv("LDAP_URI", "ldap://localhost:389"),
    "USER": os.getenv("LDAP_BIND_DN", "cn=admin,dc=eusrr,dc=local"),
    "PASSWORD": os.getenv("LDAP_BIND_PASSWORD", "AdminPassword123!"),
}

# Database router для направления LDAP моделей в LDAP database
DATABASE_ROUTERS = ["eusrr_backend.db_routers.LdapRouter"]

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
REGISTRATION_ALLOWED_IPS = [ "*",
    # '127.0.0.0/8',      # localhost
    # '10.0.0.0/8',       # приватная сеть класса A
    # '172.16.0.0/12',    # приватная сеть класса B (172.16-31.x.x)
    # '172.11.0.0/16',    # ваша корпоративная сеть
    # '192.168.0.0/16',   # приватная сеть класса C
]

# Медиа файлы
MEDIA_ROOT = os.path.join(BASE_DIR, "media/")
MEDIA_URL = "/media/"

# Структура медиа папки:
# media/
#   ├── documents/          ← Документы (читаемая структура по годам/месяцам)
#   ├── avatars/            ← Аватары пользователей
#   ├── chat_attachments/   ← Вложения в чате
#   └── temp/              ← Временные файлы

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
        "communications": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "api.v1.communications": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "notifications": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "requests_app": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "employees": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "common": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        # полезно видеть ошибки и отладку ldap3
        "ldap3": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

# -----------------------------------------------------------------------------
# БЕЗОПАСНОСТЬ И ПРОКСИ
# -----------------------------------------------------------------------------
# CSRF защита (для Django Admin и form-based views)
CSRF_TRUSTED_ORIGINS = _split_env_list(
    os.getenv("CSRF_TRUSTED_ORIGINS", "https://*.sytes.net")
)
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = 'Lax'
CSRF_USE_SESSIONS = False
# Примечание: API endpoints с JWT используют authentication_classes = []
# что отключает SessionAuthentication и автоматически bypass CSRF

# -----------------------------------------------------------------------------
# EMAIL
# -----------------------------------------------------------------------------
# В DEBUG режиме используем console backend (выводит письма в терминал)
# В production - SMTP
if DEBUG:
    EMAIL_BACKEND = os.getenv(
        "EMAIL_BACKEND", "django.core.mail.backends.console.EmailBackend"
    )
else:
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
    False if EMAIL_USE_SSL else (
        os.getenv("EMAIL_USE_TLS", "false").lower() == "true")
)
DEFAULT_FROM_EMAIL = os.getenv(
    "DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "webmaster@localhost"
)

# -----------------------------------------------------------------------------
# SITE SETTINGS
# -----------------------------------------------------------------------------
# Название сайта для email уведомлений и UI
SITE_NAME = os.getenv("SITE_NAME", "CORP HiRo")
SITE_URL = os.getenv("SITE_URL", "https://corp.robotail.pro")

# -----------------------------------------------------------------------------
# NOTIFICATIONS
# -----------------------------------------------------------------------------
# Порог для определения массовой рассылки (количество получателей)
# При массовой рассылке уведомления создаются быстро, а отправка идёт в фоне
NOTIFICATION_BULK_THRESHOLD = int(
    os.getenv("NOTIFICATION_BULK_THRESHOLD", "10"))

# Конфигурация модуля уведомлений
NOTIFICATIONS_CONFIG = {
    'SITE_NAME': SITE_NAME,
    'DEFAULT_FROM_EMAIL': DEFAULT_FROM_EMAIL,
}

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
    "REFRESH_TOKEN_LIFETIME": timedelta(days=int(os.getenv("JWT_REFRESH_DAYS", "90"))),
    "ALGORITHM": "HS256",
    "AUTH_HEADER_TYPES": ("Bearer",),
    "LEEWAY": 30,
}

# Автообновление JWT токенов: за сколько минут до истечения обновлять
JWT_REFRESH_THRESHOLD_MINUTES = int(
    os.getenv("JWT_REFRESH_THRESHOLD_MIN", "5"))


# -----------------------------------------------------------------------------
# АУТЕНТИФИКАЦИОННЫЕ БЭКЕНДЫ
# -----------------------------------------------------------------------------
# -----------------------------------------------------------------------------
# AUTHENTICATION_BACKENDS
# -----------------------------------------------------------------------------
# Порядок важен: первый успешный бэкенд останавливает цепочку
AUTHENTICATION_BACKENDS = [
    # работает только если LDAP_ENABLED=True
    "eusrr_backend.auth_backends.LDAP3Backend",
    "eusrr_backend.auth_backends.EmailOrPhoneBackend",  # фоллбэк для режима без LDAP
    "eusrr_backend.auth_backends.SuperuserOnlyBackend",  # экстренный доступ для админа
    # расчёт прав на основе должностей
    "eusrr_backend.auth_backends.PositionRoleBackend",
    "rules.permissions.ObjectPermissionBackend",  # django-rules для object-level permissions
    "django.contrib.auth.backends.ModelBackend",  # стандартный Django бэкенд
]

# -----------------------------------------------------------------------------
# LDAP / Active Directory
# -----------------------------------------------------------------------------
LDAP_ENABLED = os.getenv("LDAP_ENABLED", "true").lower() == "true"

# Основное подключение
LDAP_URI = os.getenv("LDAP_URI", "ldap://localhost:389")
LDAP_BIND_DN = os.getenv("LDAP_BIND_DN", "cn=admin,dc=eusrr,dc=local")
LDAP_BIND_PASSWORD = os.getenv("LDAP_BIND_PASSWORD", "AdminPassword123!")

# TLS/CA
# путь к CA bundle/серту (если нужен)
LDAP_CA_CERTS = os.getenv("LDAP_CA_CERTS", "")

# Где искать пользователей
LDAP_USER_BASE = os.getenv("LDAP_USER_BASE", "OU=Users,DC=eusrr,DC=local")
# Где создавать новых пользователей (может отличаться от базы поиска)
LDAP_USERS_BASE = os.getenv("LDAP_USERS_BASE", LDAP_USER_BASE)
# Базовый DN для операций создания (если не указан department_dn)
LDAP_BASE_DN = os.getenv("LDAP_BASE_DN", LDAP_USERS_BASE)
# UPN-суффикс для создания пользователей (userPrincipalName) - домен БЕЗ @
LDAP_UPN_SUFFIX = os.getenv("LDAP_UPN_SUFFIX", "eusrr.local")

LDAP_USER_FILTER = os.getenv(
    "LDAP_USER_FILTER", "(&(objectCategory=person)(objectClass=user))"
)

LDAP_ATTR_MAIL = os.getenv("LDAP_ATTR_MAIL", "mail")
LDAP_ATTR_GIVENNAME = os.getenv("LDAP_ATTR_GIVENNAME", "givenName")
LDAP_ATTR_SN = os.getenv("LDAP_ATTR_SN", "sn")
LDAP_ATTR_PHONE = os.getenv("LDAP_ATTR_PHONE", "telephoneNumber")
# Атрибут LDAP для хранения Django pk сотрудника (employeeNumber по RFC 2798, employeeID для AD)
LDAP_EMPLOYEE_ID_ATTR = os.getenv("LDAP_EMPLOYEE_ID_ATTR", "employeeNumber")
LDAP_PHONE_ATTRS = tuple(
    _split_env_list(os.getenv("LDAP_PHONE_ATTRS", "mobile,telephoneNumber"))
)

# WRITE-BACK
LDAP_WRITE_ENABLED = os.getenv("LDAP_WRITE_ENABLED", "false").lower() == "true"
LDAP_WRITE_DN = os.getenv("LDAP_WRITE_DN", LDAP_BIND_DN)
LDAP_WRITE_PASSWORD = os.getenv("LDAP_WRITE_PASSWORD", LDAP_BIND_PASSWORD)
LDAP_WRITE_TIMEOUT = int(os.getenv("LDAP_WRITE_TIMEOUT", "5"))

# Белый список: локальные поля -> LDAP-атрибуты
LDAP_WRITE_ATTRS = {
    "first_name": LDAP_ATTR_GIVENNAME,
    "last_name": LDAP_ATTR_SN,
    # фактическое имя локального телефонного поля подставляет код
    "phone": LDAP_ATTR_PHONE,
}

LDAP_CONNECT_TIMEOUT = int(os.getenv("LDAP_CONNECT_TIMEOUT", "5"))
LDAP_OPERATION_TIMEOUT = int(os.getenv("LDAP_OPERATION_TIMEOUT", "10"))

LDAP_DEPARTMENTS_BASE = os.getenv(
    "LDAP_DEPARTMENTS_BASE", "OU=Departments,DC=eusrr,DC=local"
)
LDAP_DISMISSED_BASE = os.getenv(
    "LDAP_DISMISSED_BASE", "OU=Dismissed,DC=eusrr,DC=local"
)
LDAP_GROUPS_BASE = os.getenv("LDAP_GROUPS_BASE", "OU=Groups,DC=eusrr,DC=local")
LDAP_POSITIONS_BASE = os.getenv("LDAP_POSITIONS_BASE", "OU=Positions,DC=eusrr,DC=local")

BRAND_NAME = os.getenv("BRAND_NAME", "HiRo")
BRAND_LOGO = "img/logo.png"

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

# django-push-notifications settings
PUSH_NOTIFICATIONS_SETTINGS = {
    "WP_PRIVATE_KEY": VAPID_PRIVATE_KEY,
    "WP_CLAIMS": {"sub": f"mailto:{VAPID_ADMIN_EMAIL}"},
    "UPDATE_ON_DUPLICATE_REG_ID": True,
    "UNIQUE_REG_ID": True,
}

# -----------------------------------------------------------------------------
# CELERY CONFIGURATION
# -----------------------------------------------------------------------------
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv(
    'CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

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

# Приоритеты очередей (закомментировано для упрощения в development)
# В production можно раскомментировать для масштабирования
# CELERY_TASK_ROUTES = {
#     'notifications.*': {'queue': 'notifications'},
#     'documents.tasks.*': {'queue': 'default'},
#     'employees.tasks.*': {'queue': 'default'},
# }

# Настройки для периодических задач (Celery Beat)
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

# PID файлы для Celery (используем /tmp чтобы не требовать root прав)
CELERY_BEAT_PIDFILE = os.path.join(tempfile.gettempdir(), 'celery-beat.pid')
CELERYD_PIDFILE = os.path.join(tempfile.gettempdir(), 'celery-worker.pid')

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

# -----------------------------------------------------------------------------
# DJANGO-FILER CONFIGURATION
# -----------------------------------------------------------------------------
FILER_ENABLE_PERMISSIONS = True  # Включаем ACL для файлов
FILER_IS_PUBLIC_DEFAULT = False  # По умолчанию файлы приватные
FILER_CANONICAL_URL = 'canonical/'  # URL для канонических ссылок

# Настройка хранилищ для разных типов файлов
FILER_STORAGES = {
    'public': {
        'main': {
            'ENGINE': 'filer.storage.PublicFileSystemStorage',
            'OPTIONS': {
                'location': os.path.join(MEDIA_ROOT, 'documents/public/'),
                'base_url': '/media/documents/public/',
            },
            'UPLOAD_TO': 'filer.utils.generate_filename.by_date',  # Структура: 2026/03/14/filename.pdf
        },
        'thumbnails': {
            'ENGINE': 'filer.storage.PublicFileSystemStorage',
            'OPTIONS': {
                'location': os.path.join(MEDIA_ROOT, 'documents/public_thumbnails/'),
                'base_url': '/media/documents/public_thumbnails/',
            },
        },
    },
    'private': {
        'main': {
            'ENGINE': 'filer.storage.PrivateFileSystemStorage',
            'OPTIONS': {
                'location': os.path.join(MEDIA_ROOT, 'documents/private/'),
                'base_url': '/smedia/documents/private/',
            },
            'UPLOAD_TO': 'filer.utils.generate_filename.by_date',  # Структура: 2026/03/14/filename.pdf
        },
        'thumbnails': {
            'ENGINE': 'filer.storage.PrivateFileSystemStorage',
            'OPTIONS': {
                'location': os.path.join(MEDIA_ROOT, 'documents/private_thumbnails/'),
                'base_url': '/smedia/documents/private_thumbnails/',
            },
        },
    },
}

# easy-thumbnails настройки для filer
THUMBNAIL_PROCESSORS = (
    'easy_thumbnails.processors.colorspace',
    'easy_thumbnails.processors.autocrop',
    'filer.thumbnail_processors.scale_and_crop_with_subject_location',
    'easy_thumbnails.processors.filters',
)

THUMBNAIL_HIGH_RESOLUTION = True  # Поддержка retina-дисплеев
THUMBNAIL_PRESERVE_EXTENSIONS = ('png', 'gif')  # Сохранять расширения

# Размеры thumbnails по умолчанию
THUMBNAIL_ALIASES = {
    '': {
        'admin_thumbnail': {'size': (100, 100), 'crop': True},
        'small': {'size': (200, 200), 'crop': False},
        'medium': {'size': (400, 400), 'crop': False},
        'large': {'size': (800, 800), 'crop': False},
    },
}

# CORS Configuration for Next.js frontend
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
CORS_ALLOW_CREDENTIALS = True

# ===== Communications App Settings =====
# Функция для разрешения участников чата (callback)
# Позволяет подключить бизнес-специфичную логику (EUSRR: Department, EmployeeDepartment)
COMMUNICATIONS_PARTICIPANT_RESOLVER = 'employees.utils.resolve_chat_participants'
