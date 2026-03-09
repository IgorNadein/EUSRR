"""
Централизованная конфигурация модуля notifications

Все настройки вынесены в один файл для удобства переиспользования.
Значения можно переопределить в settings.py проекта через NOTIFICATIONS_CONFIG.
"""
from django.conf import settings


# Базовая конфигурация по умолчанию
DEFAULT_CONFIG = {
    # === Каналы доставки ===
    'CHANNELS_ENABLED': {
        'email': True,
        'push': True,
        'websocket': True,
    },
    
    # === Email настройки ===
    'EMAIL_RATE_LIMIT': '10/m',  # 10 писем в минуту
    'EMAIL_MAX_RETRIES': 3,
    'EMAIL_RETRY_DELAY': 300,  # 5 минут в секундах
    'EMAIL_DEFAULT_FREQUENCY': 'instant',  # instant, daily, weekly, disabled
    
    # === Push настройки ===
    'PUSH_RATE_LIMIT': '50/m',  # 50 push в минуту
    'PUSH_MAX_RETRIES': 2,
    'PUSH_RETRY_DELAY': 60,  # 1 минута в секундах
    
    # === WebSocket настройки ===
    'WEBSOCKET_MAX_RETRIES': 1,
    'WEBSOCKET_RETRY_DELAY': 5,  # 5 секунд
    
    # === Digest настройки ===
    'DIGEST_DAILY_TIME': '09:00',  # Время отправки дейли дайджеста
    'DIGEST_WEEKLY_DAY': 'monday',  # День недели для weekly дайджеста
    'DIGEST_WEEKLY_TIME': '09:00',
    
    # === Общие настройки ===
    'SITE_NAME': 'My Site',  # Название сайта для email
    'DEFAULT_FROM_EMAIL': None,  # None = использовать settings.DEFAULT_FROM_EMAIL
    'NOTIFICATION_MAX_AGE_DAYS': 90,  # Храним уведомления 90 дней
    'UNREAD_NOTIFICATIONS_LIMIT': 100,  # Максимум непрочитанных для показа
    
    # === DND режим ===
    'DND_ENABLED': True,  # Включить поддержку "Не беспокоить"
    'DND_SILENT_CHANNELS': ['websocket'],  # В DND только silent websocket
}


def get_config():
    """
    Получить конфигурацию модуля.
    Объединяет DEFAULT_CONFIG с пользовательскими настройками из settings.NOTIFICATIONS_CONFIG
    
    Returns:
        dict: Итоговая конфигурация
        
    Usage:
        from notifications.config import get_config
        config = get_config()
        rate_limit = config['EMAIL_RATE_LIMIT']
    """
    config = DEFAULT_CONFIG.copy()
    
    # Обновляем из settings проекта
    user_config = getattr(settings, 'NOTIFICATIONS_CONFIG', {})
    config.update(user_config)
    
    return config


def get(key, default=None):
    """
    Получить конкретную настройку по ключу
    
    Args:
        key: Ключ настройки
        default: Значение по умолчанию если не найдено
        
    Returns:
        Значение настройки
        
    Usage:
        from notifications.config import get
        rate_limit = get('EMAIL_RATE_LIMIT', '10/m')
    """
    config = get_config()
    return config.get(key, default)


# Удобные алиасы для часто используемых настроек
def email_rate_limit():
    """Получить rate limit для email"""
    return get('EMAIL_RATE_LIMIT')


def email_max_retries():
    """Получить максимум retry для email"""
    return get('EMAIL_MAX_RETRIES')


def email_retry_delay():
    """Получить задержку retry для email"""
    return get('EMAIL_RETRY_DELAY')


def push_rate_limit():
    """Получить rate limit для push"""
    return get('PUSH_RATE_LIMIT')


def push_max_retries():
    """Получить максимум retry для push"""
    return get('PUSH_MAX_RETRIES')


def push_retry_delay():
    """Получить задержку retry для push"""
    return get('PUSH_RETRY_DELAY')


def websocket_max_retries():
    """Получить максимум retry для websocket"""
    return get('WEBSOCKET_MAX_RETRIES')


def websocket_retry_delay():
    """Получить задержку retry для websocket"""
    return get('WEBSOCKET_RETRY_DELAY')


def site_name():
    """Получить название сайта"""
    return get('SITE_NAME') or getattr(settings, 'SITE_NAME', 'My Site')


def from_email():
    """Получить from email"""
    return get('DEFAULT_FROM_EMAIL') or settings.DEFAULT_FROM_EMAIL
