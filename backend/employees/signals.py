# users/signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .constants import ACTION_HIRED

from .models import Employee, EmployeeAction
from bots.models import BotSubscriber


@receiver(pre_save, sender=Employee)
def unbind_bot_subscriber_on_contact_change(sender, instance: Employee, **kwargs):
    # Игнорируем новых пользователей
    if instance.pk is None:
        return

    old = sender.objects.get(pk=instance.pk)
    try:
        sub = old.bot_subscription
    except BotSubscriber.DoesNotExist:
        return

    # Если очистили или изменили telegram в профиле — сбросим telegram_id
    if old.telegram and old.telegram != (instance.telegram or "").strip():
        sub.telegram_id = None
        sub.save(update_fields=["telegram_id"])

    # Аналогично для whatsapp
    if old.whatsapp and old.whatsapp != instance.whatsapp:
        sub.whatsapp_id = None
        sub.save(update_fields=["whatsapp_id"])

    if old.wechat and old.wechat != instance.wechat:
        sub.wechat_id = None
        sub.save(update_fields=["wechat_id"])


@receiver(post_save, sender=Employee)
def create_hired_action(sender, instance: Employee, created, **kwargs):
    """
    При первом сохранении нового сотрудника создаём событие «Принят».
    """
    if created:
        EmployeeAction.objects.create(
            employee=instance,
            action=ACTION_HIRED,
            date=instance.created_at or timezone.now(),
            comment="Автоматически: принят при регистрации",
        )
