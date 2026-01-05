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


class NotificationService:
    """Сервис для создания и отправки уведомлений"""

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
        logger.info(
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
            logger.info(
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
        
        logger.info(
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
        
        logger.info(
            f"[NotificationService.create_notification] ✅ Уведомление создано: "
            f"id={notification.id}, "
            f"action_url={action_url}"
        )

        # Отправить если нужно
        if send_immediately:
            logger.info(
                f"[NotificationService.create_notification] ➡️ Немедленная отправка notification_id={notification.id}"
            )
            NotificationService.send_notification(notification, settings)
        else:
            logger.info(
                f"[NotificationService.create_notification] ⏸️ Отложенная отправка notification_id={notification.id}"
            )

        return notification

    @staticmethod
    def send_notification(
        notification: Notification,
        settings: Optional[UserNotificationSettings] = None
    ):
        """Отправить уведомление по всем каналам"""
        logger.info(
            f"\n{'='*80}\n"
            f"[NotificationService.send_notification] 📤 НАЧАЛО ОТПРАВКИ\n"
            f"  notification_id={notification.id}\n"
            f"  recipient={notification.recipient.id} ({notification.recipient.email})\n"
            f"  type={notification.notification_type.code}\n"
            f"  title='{notification.title}'\n"
            f"{'='*80}"
        )
        
        if settings is None:
            settings = NotificationService.get_user_settings(
                notification.recipient,
                notification.notification_type
            )

        logger.info(
            f"[NotificationService.send_notification] Активные каналы: "
            f"{'✅' if settings.send_web else '❌'} Web, "
            f"{'✅' if settings.send_email else '❌'} Email, "
            f"{'✅' if settings.send_telegram else '❌'} Telegram"
        )

        # Отправить на веб (WebSocket)
        if settings.send_web:
            logger.info(
                f"[NotificationService.send_notification] 🌐 Отправка через WebSocket..."
            )
            try:
                NotificationService.send_web_notification(notification)
                notification.sent_web = True
                logger.info(
                    f"[NotificationService.send_notification] ✅ WebSocket: успешно отправлено"
                )
            except Exception as e:
                logger.error(
                    f"[NotificationService.send_notification] ❌ WebSocket: ошибка - {e}",
                    exc_info=True
                )
        else:
            logger.info(
                f"[NotificationService.send_notification] ⏭️ WebSocket: канал отключен"
            )

        # Отправить на email
        if settings.send_email:
            logger.info(
                f"[NotificationService.send_notification] 📧 Отправка Email..."
            )
            try:
                recipient_email = notification.recipient.email
                if recipient_email:
                    logger.info(
                        f"[NotificationService.send_notification] Email адрес: {recipient_email}"
                    )
                    success = EmailNotificationSender.send_notification_email(
                        notification=notification,
                        recipient_email=recipient_email,
                    )
                    notification.sent_email = success
                    if success:
                        logger.info(
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
            logger.info(
                f"[NotificationService.send_notification] ⏭️ Email: канал отключен"
            )

        # Отправить в Telegram
        if settings.send_telegram:
            logger.info(
                f"[NotificationService.send_notification] 💬 Отправка в Telegram..."
            )
            logger.info(
                f"[NotificationService.send_notification] Получатель: user_id={notification.recipient.id}"
            )
            try:
                # Проверяем наличие Telegram Chat ID в профиле
                telegram_chat_id = getattr(
                    notification.recipient, 'telegram', ''
                )
                if telegram_chat_id:
                    telegram_chat_id = telegram_chat_id.strip()
                
                logger.info(
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
                    
                    logger.info(
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
                        logger.info(
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
            logger.info(
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
        
        logger.info(
            f"\n{'='*80}\n"
            f"[NotificationService.send_notification] 🎯 ЗАВЕРШЕНО\n"
            f"  notification_id={notification.id}\n"
            f"  Результаты: "
            f"Web={'\u2705' if notification.sent_web else '\u274c'}, "
            f"Email={'\u2705' if notification.sent_email else '\u274c'}, "
            f"Telegram={'\u2705' if notification.sent_telegram else '\u274c'}\n"
            f"{'='*80}"
        )

    @staticmethod
    def send_web_notification(notification: Notification):
        """Отправить уведомление через WebSocket"""
        logger.info(
            f"[NotificationService.send_web_notification] НАЧАЛО: "
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
        logger.info(
            f"[NotificationService.send_web_notification] Отправка в группу: {group_name}"
        )

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification_new',
                'notification': notification_data
            }
        )
        
        logger.info(
            f"[NotificationService.send_web_notification] ✅ Уведомление отправлено в WebSocket"
        )

        # Обновить счетчик
        unread_count = Notification.objects.filter(
            recipient=notification.recipient,
            is_read=False,
            is_archived=False
        ).count()
        
        logger.info(
            f"[NotificationService.send_web_notification] Обновление счетчика: {unread_count} непрочитанных"
        )

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'notification_count_update',
                'count': unread_count
            }
        )
        
        logger.info(
            f"[NotificationService.send_web_notification] ✅ Счетчик обновлен"
        )

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
