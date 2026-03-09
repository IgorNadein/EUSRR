"""
Web Push отправитель для browser push notifications
"""
from django.conf import settings

from .base import BaseNotificationSender


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
            from push_notifications.models import WebPushDevice
            from ..web_push_models import WebPushSubscription
            
            user = notification.recipient
            
            # Получаем активные подписки
            subscriptions = WebPushSubscription.objects.filter(
                user=user,
                is_active=True
            )
            
            if not subscriptions.exists():
                self.log_skip(notification, "no active push subscriptions")
                return False
            
            # Формируем данные для push
            actor_str = str(notification.actor) if notification.actor else 'Система'
            title = f'{actor_str} {notification.verb}'
            body = notification.description or ''
            
            push_data = {
                'head': title,
                'body': body,
                'icon': '/static/img/logo.png',
                'url': notification.action_url or '/',
                'tag': f'notification-{notification.id}',
                'requireInteraction': False,
            }
            
            sent_count = 0
            # Отправляем через django-push-notifications
            for sub in subscriptions:
                try:
                    # Используем push_notifications для отправки
                    device = WebPushDevice.objects.filter(
                        registration_id=sub.endpoint
                    ).first()
                    
                    if device:
                        device.send_message(
                            message=push_data,
                            extra={
                                'notification_id': notification.id
                            }
                        )
                        sent_count += 1
                        self.logger.debug(f"Push отправлен на device {device.id}")
                        
                except Exception as e:
                    self.logger.error(
                        f"Ошибка отправки push на subscription {sub.id}: {e}"
                    )
                    continue
            
            if sent_count > 0:
                self.log_success(notification, f"{sent_count} devices")
                return True
            else:
                self.log_skip(notification, "no successful sends")
                return False
            
        except ImportError:
            self.log_skip(notification, "django-push-notifications not installed")
            return False
        except Exception as e:
            self.log_error(notification, e, f"user_{notification.recipient.id}")
            return False
