"""
Базовый класс для всех отправителей уведомлений
"""
from abc import ABC, abstractmethod
from typing import Optional
import logging

logger = logging.getLogger(__name__)


class BaseNotificationSender(ABC):
    """
    Абстрактный базовый класс для отправителей уведомлений.

    Все отправители должны наследоваться от этого класса и реализовать метод send().
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def send(self, notification, **kwargs) -> bool:
        """
        Отправляет уведомление через конкретный канал.

        Args:
            notification: Объект Notification
            **kwargs: Дополнительные параметры для канала

        Returns:
            True если отправлено успешно, False иначе
        """
        pass

    def can_send(self, notification, user_preferences) -> bool:
        """
        Проверяет, можно ли отправить уведомление через этот канал.

        Args:
            notification: Объект Notification
            user_preferences: UserChannelPreferences

        Returns:
            True если можно отправлять, False иначе
        """
        return True

    def log_success(self, notification, recipient: str):
        """Логирует успешную отправку"""
        self.logger.info(
            f"✅ Уведомление отправлено: "
            f"notification_id={notification.id}, "
            f"recipient={recipient}, "
            f"channel={self.__class__.__name__}"
        )

    def log_error(
            self,
            notification,
            error: Exception,
            recipient: Optional[str] = None):
        """Логирует ошибку отправки"""
        self.logger.error(
            f"❌ Ошибка отправки: "
            f"notification_id={notification.id}, "
            f"recipient={recipient}, "
            f"channel={self.__class__.__name__}, "
            f"error={type(error).__name__}: {error}",
            exc_info=True
        )

    def log_skip(self, notification, reason: str):
        """Логирует пропуск отправки"""
        self.logger.debug(
            f"⏭️ Отправка пропущена: "
            f"notification_id={notification.id}, "
            f"channel={self.__class__.__name__}, "
            f"reason={reason}"
        )
