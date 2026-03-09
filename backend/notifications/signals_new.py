"""
Сигнал notify для создания уведомлений
По образу django-notifications-hq

Использование:
    from notifications.signals import notify
    
    notify.send(
        sender=user,
        recipient=other_user,
        verb='liked',
        action_object=comment,
        target=post,
        description='liked your comment on "Post Title"',
        action_url='/posts/123/',
    )
"""

from django.dispatch import Signal


# Сигнал для создания уведомлений
notify = Signal()


def create_notification_handler(sender, **kwargs):
    """
    Обработчик сигнала notify
    Создает уведомление в БД
    
    Параметры:
        sender: Объект-актор (кто создал уведомление)
        recipient: User или список User (кому)
        verb: str - действие (обязательно)
        action_object: Объект действия (опционально)
        target: Целевой объект (опционально)
        description: str - описание (опционально)
        action_url: str - URL для перехода (опционально)
        data: dict - дополнительные данные (опционально)
        public: bool - публичное ли (по умолчанию True)
        timestamp: datetime - время создания (по умолчанию now)
    
    Возвращает:
        Notification или список Notification
    """
    from .models_new import Notification
    from django.contrib.auth import get_user_model
    from django.contrib.contenttypes.models import ContentType
    
    User = get_user_model()
    
    # Извлекаем параметры
    recipient = kwargs.pop('recipient', None)
    verb = kwargs.pop('verb', None)
    action_object = kwargs.pop('action_object', None)
    target = kwargs.pop('target', None)
    description = kwargs.pop('description', None)
    action_url = kwargs.pop('action_url', None)
    data = kwargs.pop('data', {})
    public = kwargs.pop('public', True)
    timestamp = kwargs.pop('timestamp', None)
    
    # Валидация
    if not recipient:
        raise ValueError('recipient is required')
    if not verb:
        raise ValueError('verb is required')
    
    # Поддержка множественных получателей
    recipients = recipient if isinstance(recipient, (list, tuple)) else [recipient]
    
    # Создаем уведомления
    notifications = []
    
    for recip in recipients:
        if not isinstance(recip, User):
            raise ValueError(f'recipient must be User instance, got {type(recip)}')
        
        # Подготовка данных для GenericForeignKey
        new_notification = Notification(
            recipient=recip,
            verb=verb,
            description=description or '',
            action_url=action_url or '',
            data=data,
            public=public,
        )
        
        # Actor
        if sender:
            new_notification.actor_content_type = ContentType.objects.get_for_model(sender)
            new_notification.actor_object_id = sender.pk
        
        # Action Object
        if action_object:
            new_notification.action_object_content_type = ContentType.objects.get_for_model(action_object)
            new_notification.action_object_object_id = action_object.pk
        
        # Target
        if target:
            new_notification.target_content_type = ContentType.objects.get_for_model(target)
            new_notification.target_object_id = target.pk
        
        # Timestamp
        if timestamp:
            new_notification.timestamp = timestamp
        
        new_notification.save()
        notifications.append(new_notification)
    
    # Возвращаем одно уведомление или список
    if len(notifications) == 1:
        return notifications[0]
    return notifications


# Подключаем обработчик
notify.connect(
    create_notification_handler,
    dispatch_uid='notifications.create_notification'
)
