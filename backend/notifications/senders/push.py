"""
Web Push отправитель для browser push notifications
"""
from push_notifications.models import WebPushDevice

from .base import BaseNotificationSender
from ..config import get


class PushNotificationSender(BaseNotificationSender):
    """
    Отправитель Web Push уведомлений через django-push-notifications.
    Доставляет уведомления в браузер даже когда вкладка закрыта.
    """
    
    def can_send(self, notification, user_preferences) -> bool:
        """Проверяет, включены ли push уведомления"""
        if not user_preferences.push_enabled:
            self.log_skip(notification, "push_enabled=False")
            return False
        return True
    
    def send(self, notification, **kwargs) -> bool:
        """
        Отправляет Web Push уведомление.
        
        Args:
            notification: Объект Notification
            **kwargs: Дополнительные параметры
            
        Returns:
            True если отправлено успешно, False иначе
        """
        try:
            user = notification.recipient
            
            # Получаем активные устройства через django-push-notifications
            devices = WebPushDevice.objects.filter(
                user=user,
                active=True
            )
            
            if not devices.exists():
                self.log_skip(notification, "no active push devices")
                return False
            
            # Формируем данные для push
            actor_str = str(notification.actor) if notification.actor else 'Система'
            title = f'{actor_str} {notification.verb}'
            body = notification.description or ''
            
            # Получаем иконки из конфигурации (None = browser default)
            default_icon = get('PUSH_DEFAULT_ICON')
            default_badge = get('PUSH_DEFAULT_BADGE')
            
            # django-push-notifications использует другой формат
            message = {
                'head': title,
                'body': body,
                'url': notification.action_url or '/',
                'tag': f'notification-{notification.id}',
                'requireInteraction': False,
                'data': {
                    'notification_id': notification.id,
                    'verb': notification.verb,
                }
            }
            
            # Добавляем иконки только если они настроены
            if default_icon:
                message['icon'] = default_icon
            if default_badge:
                message['badge'] = default_badge
            
            sent_count = 0
            failed_count = 0
            
            # Отправляем через все устройства пользователя
            for device in devices:
                try:
                    device.send_message(message)
                    sent_count += 1
                    self.logger.debug(
                        f"Push отправлен на device {device.id} ({device.browser})"
                    )
                except Exception as e:
                    failed_count += 1
                    self.logger.error(
                        f"Ошибка отправки push на device {device.id}: {e}"
                    )
                    # Деактивируем устройство если ошибка
                    if "expired" in str(e).lower() or "unregistered" in str(e).lower():
                        device.active = False
                        device.save()
                        self.logger.info(f"Device {device.id} деактивирован")
            
            if sent_count > 0:
                self.log_success(notification, f"{sent_count} devices")
                if failed_count > 0:
                    self.logger.warning(
                        f"Push отправлен частично: {sent_count} успешно, "
                        f"{failed_count} ошибок"
                    )
                return True
            else:
                self.log_skip(notification, f"no successful sends ({failed_count} failures)")
                return False
            
        except ImportError:
            self.log_skip(notification, "django-push-notifications not installed")
            return False
        except Exception as e:
            self.log_error(notification, e, f"user_{notification.recipient.id}")
            return False
