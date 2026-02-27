"""
Email sender для системы уведомлений.
Отправляет красивые HTML письма с уведомлениями.
"""
import logging
from typing import Optional

from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

from common.emails import send_templated_mail

logger = logging.getLogger(__name__)


class EmailNotificationSender:
    """
    Класс для отправки email уведомлений.
    Использует HTML шаблоны для красивого оформления.
    """
    
    # Маппинг категорий на иконки для email
    CATEGORY_ICONS = {
        'communications': '💬',
        'documents': '📄',
        'requests': '📋',
        'calendar': '📅',
        'department': '👥',
        'profile': '👤',
        'feed': '📰',
        'system': '⚙️',
    }
    
    # Маппинг категорий на цвета
    CATEGORY_COLORS = {
        'communications': '#0d6efd',  # primary
        'documents': '#198754',        # success
        'requests': '#ffc107',         # warning
        'calendar': '#dc3545',         # danger
        'department': '#6f42c1',       # purple
        'profile': '#0dcaf0',          # info
        'feed': '#fd7e14',             # orange
        'system': '#6c757d',           # secondary
    }
    
    @classmethod
    def send_notification_email(
        cls,
        notification,
        recipient_email: str,
        custom_subject: Optional[str] = None,
    ) -> bool:
        """
        Отправляет email уведомление пользователю.
        
        Args:
            notification: объект Notification
            recipient_email: email получателя
            custom_subject: кастомная тема письма (опционально)
            
        Returns:
            True если отправлено успешно, False иначе
        """
        logger.info(
            f"[EmailNotificationSender.send_notification_email] НАЧАЛО: "
            f"notification_id={notification.id}, "
            f"recipient={recipient_email}"
        )
        
        try:
            # Получаем категорию
            category_code = notification.notification_type.category.code
            category_name = notification.notification_type.category.name
            
            logger.info(
                f"[EmailNotificationSender] Категория: {category_name} ({category_code})"
            )
            
            # Формируем тему письма
            if custom_subject:
                subject = custom_subject
            else:
                icon = cls.CATEGORY_ICONS.get(category_code, '🔔')
                subject = f"{icon} {notification.title}"
            
            logger.info(
                f"[EmailNotificationSender] Тема письма: '{subject}'"
            )
            
            # Формируем контекст для шаблона
            context = {
                'notification': notification,
                'category_name': category_name,
                'category_icon': cls.CATEGORY_ICONS.get(category_code, '🔔'),
                'category_color': cls.CATEGORY_COLORS.get(category_code, '#0d6efd'),
                'action_url': cls._get_full_url(notification.action_url),
                'action_text': notification.action_text or 'Посмотреть',
                'site_name': getattr(settings, 'SITE_NAME', 'EUSRR'),
                'site_url': cls._get_site_url(),
            }
            
            logger.info(
                f"[EmailNotificationSender] ➡️ Вызов send_templated_mail: "
                f"template='notifications/email/notification', "
                f"to={recipient_email}"
            )
            
            # Отправляем email
            send_templated_mail(
                subject=subject,
                to=[recipient_email],
                template_base='notifications/email/notification',
                context=context,
            )
            
            logger.info(
                f"[EmailNotificationSender] ✅ Email УСПЕШНО отправлен: "
                f"notification_id={notification.id} -> {recipient_email}"
            )
            return True
            
        except Exception as e:
            logger.error(
                f"[EmailNotificationSender] ❌ ОШИБКА отправки email: "
                f"notification_id={notification.id}, "
                f"recipient={recipient_email}, "
                f"error={type(e).__name__}: {e}",
                exc_info=True
            )
            return False
    
    @classmethod
    def send_digest_email(
        cls,
        recipient_email: str,
        notifications: list,
        digest_type: str = 'daily',
    ) -> bool:
        """
        Отправляет дайджест уведомлений.
        
        Args:
            recipient_email: email получателя
            notifications: список объектов Notification
            digest_type: тип дайджеста ('daily' или 'weekly')
            
        Returns:
            True если отправлено успешно, False иначе
        """
        try:
            if not notifications:
                return False
            
            # Группируем по категориям
            grouped = {}
            for notif in notifications:
                category = notif.notification_type.category.code
                if category not in grouped:
                    grouped[category] = []
                grouped[category].append(notif)
            
            # Формируем тему
            digest_name = 'Ежедневный' if digest_type == 'daily' else 'Еженедельный'
            subject = f"📬 {digest_name} дайджест уведомлений ({len(notifications)})"
            
            # Формируем контекст
            context = {
                'notifications': notifications,
                'grouped_notifications': grouped,
                'digest_type': digest_type,
                'digest_name': digest_name,
                'total_count': len(notifications),
                'category_icons': cls.CATEGORY_ICONS,
                'category_colors': cls.CATEGORY_COLORS,
                'site_name': getattr(settings, 'SITE_NAME', 'EUSRR'),
                'site_url': cls._get_site_url(),
            }
            
            # Отправляем дайджест
            send_templated_mail(
                subject=subject,
                to=[recipient_email],
                template_base='notifications/email/digest',
                context=context,
            )
            
            logger.info(
                f"Дайджест отправлен: {len(notifications)} уведомлений -> {recipient_email}"
            )
            return True
            
        except Exception as e:
            logger.error(
                f"Ошибка отправки дайджеста на {recipient_email}: {e}",
                exc_info=True
            )
            return False
    
    @staticmethod
    def _get_site_url() -> str:
        """Получает базовый URL сайта из настроек."""
        # Пробуем получить из настроек
        if hasattr(settings, 'SITE_URL'):
            return settings.SITE_URL
        
        # Формируем из ALLOWED_HOSTS
        if settings.ALLOWED_HOSTS and settings.ALLOWED_HOSTS[0] != '*':
            host = settings.ALLOWED_HOSTS[0]
            protocol = 'https' if getattr(settings, 'SECURE_SSL_REDIRECT', False) else 'http'
            return f"{protocol}://{host}"
        
        return 'http://localhost:9000'
    
    @staticmethod
    def _get_full_url(path: str) -> str:
        """Преобразует относительный URL в абсолютный."""
        if not path:
            return ''
        
        if path.startswith('http://') or path.startswith('https://'):
            return path
        
        site_url = EmailNotificationSender._get_site_url()
        return f"{site_url}{path}"
    
    @classmethod
    def test_email_connection(cls, test_email: str) -> bool:
        """
        Тестирует подключение к email серверу.
        
        Args:
            test_email: email для отправки тестового письма
            
        Returns:
            True если успешно, False иначе
        """
        try:
            from django.core.mail import send_mail
            
            send_mail(
                subject='🔔 Тест системы уведомлений EUSRR',
                message='Это тестовое письмо. Если вы его получили, значит настройки email работают корректно.',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[test_email],
                fail_silently=False,
            )
            
            logger.info(f"Тестовое письмо успешно отправлено на {test_email}")
            return True
            
        except Exception as e:
            logger.error(f"Ошибка отправки тестового письма: {e}", exc_info=True)
            return False
