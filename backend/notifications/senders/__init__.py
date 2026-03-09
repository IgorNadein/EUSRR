"""
Отправители уведомлений по различным каналам
"""
from .base import BaseNotificationSender
from .email import EmailNotificationSender
from .websocket import WebSocketNotificationSender
from .push import PushNotificationSender

__all__ = [
    'BaseNotificationSender',
    'EmailNotificationSender',
    'WebSocketNotificationSender',
    'PushNotificationSender',
]
