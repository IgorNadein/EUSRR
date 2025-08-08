from pathlib import Path
import os
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


SECRET_KEY = 'django-insecure--kftc-d47!6m2ib6jof3^d%n1&4k%mdf33brejsyg*@il#$-52'

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']


INSTALLED_APPS = [
    'django.contrib.admin',
    'django_bootstrap5',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'widget_tweaks',
    'employees.apps.EmployeesConfig',
    'api.apps.ApiConfig',
    'hikcentral.apps.HikcentralConfig',
    'calendar_app.apps.CalendarAppConfig',
    'documents.apps.DocumentsConfig',
    'requests_app.apps.RequestsAppConfig',
    'feed.apps.FeedConfig',
    'communications.apps.CommunicationsConfig',
    'bots',

]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'eusrr_backend.middleware.AuthRequiredMiddleware',
]

ROOT_URLCONF = 'eusrr_backend.urls'

TEMPLATES_DIR = BASE_DIR / 'templates'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [TEMPLATES_DIR],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'eusrr_backend.wsgi.application'


USE_SQLITE = os.getenv('USE_SQLITE', 'False').lower() == 'true'

DATABASES = {
    'default': {},
    'hikcentral': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'cms',
        'USER': 'postgres',
        'PASSWORD': None,
        'HOST': '127.0.0.1',
        'PORT': '5432',
        'OPTIONS': {
            'options': '-c search_path=platform'
        }
    }
}

if USE_SQLITE:
    # Конфигурация для SQLite
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
else:
    # Конфигурация для PostgreSQL
    DATABASES['default'] = {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.getenv('POSTGRES_DB', 'django'),
        'USER': os.getenv('POSTGRES_USER', 'django'),
        'PASSWORD': os.getenv('POSTGRES_PASSWORD', ''),
        'HOST': os.getenv('DB_HOST', ''),
        'PORT': os.getenv('DB_PORT', '5432')
    }

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


LANGUAGE_CODE = 'ru'

TIME_ZONE = 'Europe/Moscow'

USE_I18N = True

USE_TZ = True


STATIC_URL = 'static/'


DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'employees.Employee'

LOGIN_URL = 'register'
LOGIN_REDIRECT_URL = '/'
# LOGOUT_REDIRECT_URL = 'login'
REGISTRATION_AUTO_LOGIN = True


EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media/')

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

CSRF_TRUSTED_ORIGINS = os.getenv('CSRF_TRUSTED_ORIGINS', default='https://*.sytes.net').split(',')

ACCOUNT_EMAIL_VERIFICATION = 'mandatory'  # для allauth, если вдруг используешь
DEFAULT_FROM_EMAIL = 'noreply@yourdomain.com'
