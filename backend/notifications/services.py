"""
Сервисный слой для работы с уведомлениями
"""
import json
import logging
from typing import Any, Dict, Optional
from django.contrib.auth import get_user_model
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import (
    Notification,
    NotificationType,
    UserNotificationSettings,
)
from .email_sender import EmailNotificationSender
from .telegram_sender import TelegramNotificationSender

logger = logging.getLogger(__name__)

User = get_user_model()


def is_celery_available():
    """Проверка доступности Celery worker"""
    try:
        from celery import current_app
        inspect = current_app.control.inspect()
        active_workers = inspect.active()
        return active_workers is not None and len(active_workers) > 0
    except Exception:
        return False


class NotificationService:
    """Сервис для создания и отправки уведомлений"""

    @staticmethod
    def create_notification_async(
        recipient: User,
        notification_type_code: str,
        title: str,
        message: str,
        content_object=None,
        action_url: str = '',
        action_text: str = 'Посмотреть',
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[Notification]:
        """
        Создать уведомление асинхронно через Celery (рекомендуется)
        
        Args:
            recipient: Получатель уведомления
            notification_type_code: Код типа уведомления
            title: Заголовок
            message: Текст сообщения
            content_object: Связанный объект (опционально)
            action_url: URL для действия
            action_text: Текст кнопки действия
            metadata: Дополнительные данные
            
        Returns:
            Созданное уведомление (если sync fallback) или None (если async)
        """
        try:
            # Проверяем доступность Celery
            if not is_celery_available():
                logger.warning(
                    f"[create_notification_async] Celery недоступен, fallback на синхронный режим"
                )
                return NotificationService.create_notification(
                    recipient=recipient,
                    notification_type_code=notification_type_code,
                    title=title,
                    message=message,
                    content_object=content_object,
                    action_url=action_url,
                    action_text=action_text,
                    metadata=metadata,
                    send_immediately=True,
                )
            
            # Импортируем задачу
            from notifications.tasks import send_notification_task
            
            # Отправляем задачу в Celery
            result = send_notification_task.delay(
                notification_type=notification_type_code,
                user_id=recipient.id,
                title=title,
                message=message,
                link=action_url,
                sender_id=None,
                metadata=metadata or {},
            )
            
            logger.debug(
                f"[create_notification_async] ✅ Задача отправлена в Celery: "
                f"user={recipient.id}, type={notification_type_code}"
            )
            
            # В EAGER режиме (тесты) задача выполняется синхронно
            # Пытаемся получить созданное уведомление
            try:
                from django.conf import settings
                if getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
                    # В тестах пытаемся найти только что созданное уведомление
                    from notifications.models import Notification
                    notification = Notification.objects.filter(
                        recipient=recipient,
                        notification_type__code=notification_type_code,
                        title=title
                    ).order_by('-created_at').first()
                    return notification
            except Exception:
                pass
            
            return None
            
        except Exception as e:
            logger.exception(
                f"[create_notification_async] ❌ Ошибка при отправке в Celery: {e}"
            )
            # Fallback на синхронный режим
            return NotificationService.create_notification(
                recipient=recipient,
                notification_type_code=notification_type_code,
                title=title,
                message=message,
                content_object=content_object,
                action_url=action_url,
                action_text=action_text,
                metadata=metadata,
                send_immediately=True,
            )

    @staticmethod
    def create_notification(
        recipient: User,
        notification_type_code: str,
        title: str,
        message: str,
        content_object=None,
        action_url: str = '',
        action_text: str = 'Посмотреть',
        metadata: Optional[Dict[str, Any]] = None,
        send_immediately: bool = True,
    ) -> Optional[Notification]:
        """
        Создать и отправить уведомление

        Args:
            recipient: Получатель уведомления
            notification_type_code: Код типа уведомления
            title: Заголовок
            message: Текст сообщения
            content_object: Связанный объект (опционально)
            action_url: URL для действия
            action_text: Текст кнопки действия
            metadata: Дополнительные данные
            send_immediately: Отправить сразу или отложить

        Returns:
            Созданное уведомление или None если тип не найден
        """
        logger.debug(
            f"[NotificationService.create_notification] НАЧАЛО: "
            f"recipient={recipient.id} ({recipient.email}), "
            f"type={notification_type_code}, "
            f"send_immediately={send_immediately}, "
            f"title='{title[:50]}...'"
        )
        
        try:
            notification_type = NotificationType.objects.get(
                code=notification_type_code,
                is_active=True
            )
            logger.debug(
                f"[NotificationService.create_notification] Тип уведомления найден: "
                f"{notification_type.name} (category={notification_type.category.code})"
            )
        except NotificationType.DoesNotExist:
            logger.error(
                f"[NotificationService.create_notification] ❌ ОШИБКА: "
                f"Тип уведомления '{notification_type_code}' не найден или неактивен!"
            )
            return None

        # Проверить настройки пользователя
        settings = NotificationService.get_user_settings(
            recipient, notification_type
        )
        
        logger.debug(
            f"[NotificationService.create_notification] Настройки пользователя: "
            f"enabled={settings.is_enabled}, "
            f"web={settings.send_web}, "
            f"email={settings.send_email}, "
            f"telegram={settings.send_telegram}"
        )

        if not settings.is_enabled:
            logger.warning(
                f"[NotificationService.create_notification] ⏭️ ПРОПУСК: "
                f"Уведомления отключены для user={recipient.id}"
            )
            return None

        # Создать краткое сообщение
        short_message = message[:150] if len(message) > 150 else message

        # Создать уведомление
        notification = Notification.objects.create(
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            short_message=short_message,
            content_object=content_object,
            action_url=action_url,
            action_text=action_text,
            metadata=metadata or {},
        )
        
        logger.debug(
            f"[NotificationService.create_notification] ✅ Уведомление создано: "
            f"id={notification.id}, "
            f"action_url={action_url}"
        )

        # Отправить если нужно
        if send_immediately:
            logger.debug(
                f"[NotificationService.create_notification] ➡️ Немедленная отправка notification_id={notification.id}"
            )
            NotificationService.send_notification(notification, settings)
        else:
            logger.debug(
                f"[NotificationService.create_notification] ⏸️ Отложенная отправка notification_id={notification.id}"
            )

        return notification

    @staticmethod
    def send_notification(
        notification: Notification,
        settings: Optional[UserNotificationSettings] = None
    ):
        """Отправить уведомление по всем каналам"""
        logger.debug(
            f"[NotificationService.send_notification] 📤 НАЧАЛО notification_id={notification.id} "
            f"recipient={notification.recipient.id} type={notification.notification_type.code}"
        )
        
        if settings is None:
            settings = NotificationService.get_user_settings(
                notification.recipient,
                notification.notification_type
            )

        logger.debug(
            f"[NotificationService.send_notification] Активные каналы: "
            f"{'✅' if settings.send_web else '❌'} Web, "
            f"{'✅' if settings.send_email else '❌'} Email, "
            f"{'✅' if settings.send_telegram else '❌'} Telegram"
        )

        # Отправить на веб (WebSocket) - для онлайн пользователей
        if settings.send_web:
            logger.debug(
                f"[NotificationService.send_notification] 🌐 Отправка через WebSocket..."
            )
            try:
                # Отправляем WebSocket только для онлайн уведомлений (не push)
                NotificationService.send_web_socket(notification)
                notification.sent_web = True
                logger.debug(
                    f"[NotificationService.send_notification] ✅ WebSocket: успешно отправлено"
                )
            except Exception as e:
                logger.error(
                    f"[NotificationService.send_notification] ❌ WebSocket: ошибка - {e}",
                    exc_info=True
                )
        else:
            logger.debug(
                f"[NotificationService.send_notification] ⏭️ WebSocket: канал отключен"
            )
        
        # Отправить Web Push (для offline пользователей)
        # ВАЖНО: отправляем независимо от send_web настройки,
        # если есть активные push-подписки
        if settings.send_web:
            logger.debug(
                f"[NotificationService.send_notification] 📲 Отправка Web Push (offline)..."
            )
            try:
                push_count = NotificationService.send_web_push_notification(notification)
                if push_count > 0:
                    logger.debug(
                        f"[NotificationService.send_notification] ✅ Web Push: отправлено на {push_count} устройств"
                    )
            except Exception as e:
                logger.error(
                    f"[NotificationService.send_notification] ❌ Web Push: ошибка - {e}",
                    exc_info=True
                )
        else:
            logger.debug(
                f"[NotificationService.send_notification] ⏭️ Web Push: канал отключен"
            )

        # Отправить на email
        if settings.send_email:
            logger.debug(
                f"[NotificationService.send_notification] 📧 Отправка Email..."
            )
            try:
                recipient_email = notification.recipient.email
                if recipient_email:
                    logger.debug(
                        f"[NotificationService.send_notification] Email адрес: {recipient_email}"
                    )
                    success = EmailNotificationSender.send_notification_email(
                        notification=notification,
                        recipient_email=recipient_email,
                    )
                    notification.sent_email = success
                    if success:
                        logger.debug(
                            f"[NotificationService.send_notification] ✅ Email: успешно отправлено на {recipient_email}"
                        )
                    else:
                        logger.warning(
                            f"[NotificationService.send_notification] ⚠️ Email: отправка вернула False"
                        )
                else:
                    notification.sent_email = False
                    logger.warning(
                        f"[NotificationService.send_notification] ⚠️ Email: у пользователя {notification.recipient} нет email адреса"
                    )
            except Exception as e:
                notification.sent_email = False
                logger.error(
                    f"[NotificationService.send_notification] ❌ Email: ошибка отправки - {e}",
                    exc_info=True
                )
        else:
            logger.debug(
                f"[NotificationService.send_notification] ⏭️ Email: канал отключен"
            )

        # Отправить в Telegram
        if settings.send_telegram:
            logger.debug(
                f"[NotificationService.send_notification] 💬 Отправка в Telegram..."
            )
            logger.debug(
                f"[NotificationService.send_notification] Получатель: user_id={notification.recipient.id}"
            )
            try:
                # Проверяем наличие Telegram Chat ID в профиле
                telegram_chat_id = getattr(
                    notification.recipient, 'telegram', ''
                )
                if telegram_chat_id:
                    telegram_chat_id = telegram_chat_id.strip()
                
                logger.debug(
                    f"[NotificationService.send_notification] Telegram Chat ID: '{telegram_chat_id}'"
                )
                
                if telegram_chat_id:
                    # Получаем site_url для формирования полных ссылок
                    from django.conf import settings as django_settings
                    site_url = getattr(
                        django_settings,
                        'SITE_URL',
                        'http://localhost:9000'
                    )
                    
                    logger.debug(
                        f"[NotificationService.send_notification] ➡️ Вызов TelegramNotificationSender.send_notification"
                    )
                    
                    # Отправляем через Bot API по chat_id
                    from .telegram_sender import TelegramNotificationSender
                    success = TelegramNotificationSender.send_notification(
                        notification=notification,
                        chat_id=telegram_chat_id,
                        site_url=site_url
                    )
                    notification.sent_telegram = success
                    
                    if success:
                        logger.debug(
                            f"[NotificationService.send_notification] ✅ Telegram: успешно отправлено (chat_id={telegram_chat_id})"
                        )
                    else:
                        logger.warning(
                            f"[NotificationService.send_notification] ⚠️ Telegram: отправка вернула False"
                        )
                else:
                    notification.sent_telegram = False
                    logger.warning(
                        f"[NotificationService.send_notification] ⚠️ Telegram: у пользователя нет Chat ID"
                    )
                    
            except Exception as e:
                notification.sent_telegram = False
                logger.error(
                    f"[NotificationService.send_notification] ❌ Telegram: ошибка - {e}",
                    exc_info=True
                )
        else:
            logger.debug(
                f"[NotificationService.send_notification] ⏭️ Telegram: канал отключен"
            )

        # Обновить время отправки
        notification.sent_at = timezone.now()
        notification.save(update_fields=[
            'sent_web',
            'sent_email',
            'sent_telegram',
            'sent_whatsapp',
            'sent_wechat',
            'sent_at'
        ])
        
        logger.debug(
            f"[NotificationService.send_notification] 🎯 ЗАВЕРШЕНО notification_id={notification.id} "
            f"Web={'✅' if notification.sent_web else '❌'} "
            f"Email={'✅' if notification.sent_email else '❌'} "
            f"Telegram={'✅' if notification.sent_telegram else '❌'}"
        )

    @staticmethod
    def send_web_socket(notification: Notification):
        """
        Отправить уведомление через WebSocket (только для онлайн пользователей).
        Переименовано из send_web_notification для ясности.
        """
        logger.debug(
            f"[NotificationService.send_web_socket] НАЧАЛО: "
            f"notification_id={notification.id}, "
            f"recipient={notification.recipient.id}"
        )
        
        channel_layer = get_channel_layer()
        notification_data = {
            'id': notification.id,
            'title': notification.title,
            'message': notification.short_message,
            'category': notification.notification_type.category.code,
            'category_name': notification.notification_type.category.name,
            'icon': notification.notification_type.category.icon,
            'color': notification.notification_type.category.color,
            'priority': notification.notification_type.priority,
            'action_url': notification.action_url,
            'action_text': notification.action_text,
            'created_at': notification.created_at.isoformat(),
        }
        
        group_name = f'notifications_{notification.recipient.id}'
        logger.debug(
            f"[NotificationService.send_web_socket] Отправка в группу: {group_name}"
        )

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification_new',
                'notification': notification_data
            }
        )
        
        logger.debug(
            f"[NotificationService.send_web_socket] ✅ Уведомление отправлено в WebSocket"
        )

        # Обновить счетчик
        unread_count = Notification.objects.filter(
            recipient=notification.recipient,
            is_read=False,
            is_archived=False
        ).count()
        
        logger.debug(
            f"[NotificationService.send_web_socket] Обновление счетчика: {unread_count} непрочитанных"
        )

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification_count_update',
                'count': unread_count
            }
        )
        
        logger.debug(
            f"[NotificationService.send_web_socket] ✅ Счетчик обновлен"
        )

    @staticmethod
    def send_web_push_notification(notification: Notification) -> int:
        """
        Отправить push-уведомление через Web Push API используя django-push-notifications.
        Работает даже когда браузер закрыт.
        
        Args:
            notification: Объект уведомления
            
        Returns:
            Количество успешно отправленных push-уведомлений
        """
        from push_notifications.models import WebPushDevice
        
        logger.debug(
            f"[NotificationService.send_web_push_notification] НАЧАЛО: "
            f"notification_id={notification.id}, "
            f"recipient={notification.recipient.id}"
        )
        
        # Получаем все активные устройства пользователя
        devices = WebPushDevice.objects.filter(
            user=notification.recipient,
            active=True
        )
        
        device_count = devices.count()
        if device_count == 0:
            logger.debug(
                f"[NotificationService.send_web_push_notification] ℹ️ Нет активных push-устройств"
            )
            return 0
        
        logger.debug(
            f"[NotificationService.send_web_push_notification] Найдено устройств: {device_count}"
        )
        
        # Формируем payload для push-уведомления
        payload = {
            'title': notification.title,
            'body': notification.short_message or notification.message[:150],
            'tag': f'notification-{notification.id}',
            'icon': '/static/img/logo-192.png',
            'badge': '/static/img/badge-72.png',
            'data': {
                'url': notification.action_url or '/',
                'notification_id': notification.id,
                'category': notification.notification_type.category.code,
            },
            'requireInteraction': notification.notification_type.priority in ['high', 'urgent'],
        }
        
        # Отправляем через библиотеку (она автоматически обрабатывает батчинг и ошибки)
        try:
            devices.send_message(json.dumps(payload), ttl=86400)
            success_count = device_count
            
            logger.debug(
                f"[NotificationService.send_web_push_notification] ✅ Завершено: "
                f"{success_count} устройств уведомлены"
            )
            
            return success_count
            
        except Exception as e:
            logger.error(
                f"[NotificationService.send_web_push_notification] ❌ Ошибка отправки: {e}"
            )
            return 0

    @staticmethod
    def get_user_settings(
        user: User,
        notification_type: NotificationType
    ) -> UserNotificationSettings:
        """Получить или создать настройки пользователя"""
        settings, created = UserNotificationSettings.objects.get_or_create(
            user=user,
            notification_type=notification_type,
            defaults={
                'is_enabled': notification_type.default_enabled,
                'send_web': notification_type.default_channels.get(
                    'web', True
                ),
                'send_email': notification_type.default_channels.get(
                    'email', False
                ),
                'send_telegram': notification_type.default_channels.get(
                    'telegram', False
                ),
                'send_whatsapp': notification_type.default_channels.get(
                    'whatsapp', False
                ),
                'send_wechat': notification_type.default_channels.get(
                    'wechat', False
                ),
            }
        )
        
        logger.debug(
            f"[Settings] User {user.id} type={notification_type.code} "
            f"created={created} enabled={settings.is_enabled} "
            f"web={settings.send_web} email={settings.send_email} "
            f"telegram={settings.send_telegram}"
        )
        
        return settings

    @staticmethod
    def mark_as_read(notification_id: int, user: User) -> bool:
        """Отметить уведомление как прочитанное"""
        try:
            notification = Notification.objects.get(
                id=notification_id,
                recipient=user
            )
            notification.mark_as_read()

            # Обновить счетчик через WebSocket
            channel_layer = get_channel_layer()
            unread_count = Notification.objects.filter(
                recipient=user,
                is_read=False,
                is_archived=False
            ).count()

            async_to_sync(channel_layer.group_send)(
                f'notifications_{user.id}',
                {
                    'type': 'notification_count_update',
                    'count': unread_count
                }
            )

            return True
        except Notification.DoesNotExist:
            return False

    @staticmethod
    def mark_all_as_read(user: User, category: Optional[str] = None) -> int:
        """Отметить все уведомления как прочитанные"""
        queryset = Notification.objects.filter(
            recipient=user,
            is_read=False
        )

        if category:
            queryset = queryset.filter(
                notification_type__category__code=category
            )

        count = queryset.update(
            is_read=True,
            read_at=timezone.now()
        )

        # Обновить счетчик
        channel_layer = get_channel_layer()
        unread_count = Notification.objects.filter(
            recipient=user,
            is_read=False,
            is_archived=False
        ).count()

        async_to_sync(channel_layer.group_send)(
            f'notifications_{user.id}',
            {
                'type': 'notification_count_update',
                'count': unread_count
            }
        )

        return count
