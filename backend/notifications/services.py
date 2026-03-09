"""
DEPRECATED: Этот модуль удален в v2.0

Вместо NotificationService используйте:

1. Создание уведомлений:
   
   СТАРОЕ:
   NotificationService.create_notification(
       recipient=user,
       notification_type_code='message',
       title='Заголовок',
       message='Текст',
       action_url='/link/'
   )
   
   НОВОЕ:
   from notifications.signals import notify
   notify.send(
       sender=actor,
       recipient=user,
       verb='messaged',
       description='Текст',
       action_url='/link/'
   )

2. Отметка как прочитанное:
   
   СТАРОЕ:
   NotificationService.mark_as_read(notification_id, user)
   
   НОВОЕ:
   notification = Notification.objects.get(id=notification_id)
   notification.mark_as_read()

3. Настройки:
   
   СТАРОЕ:
   settings = NotificationService.get_user_settings(user)
   
   НОВОЕ:
   prefs = UserChannelPreferences.objects.get(user=user)
   # или через related name:
   prefs = user.channel_preferences

Документация: backend/notifications/README.md
"""

# Для обратной совместимости можно оставить минимальный stub
# который будет выбрасывать ошибки с подсказками как мигрировать

class NotificationService:
    """DEPRECATED: Удален в v2.0. См. docstring модуля."""
    
    @staticmethod
    def create_notification(*args, **kwargs):
        raise NotImplementedError(
            "NotificationService.create_notification() удален. "
            "Используйте: notify.send(sender=actor, recipient=user, verb='...', description='...')"
        )
    
    @staticmethod
    def create_notification_async(*args, **kwargs):
        raise NotImplementedError(
            "NotificationService.create_notification_async() удален. "
            "Все уведомления теперь асинхронны через Celery. "
            "Используйте: notify.send(...)"
        )
    
    @staticmethod
    def mark_as_read(*args, **kwargs):
        raise NotImplementedError(
            "NotificationService.mark_as_read() удален. "
            "Используйте: notification.mark_as_read()"
        )
    
    @staticmethod
    def mark_all_as_read(*args, **kwargs):
        raise NotImplementedError(
            "NotificationService.mark_all_as_read() удален. "
            "Используйте: Notification.objects.filter(...).mark_all_as_read()"
        )
    
    @staticmethod
    def get_user_settings(*args, **kwargs):
        raise NotImplementedError(
            "NotificationService.get_user_settings() удален. "
            "Используйте: user.channel_preferences или UserChannelPreferences.objects.get(user=user)"
        )

