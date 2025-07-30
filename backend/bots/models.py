# bots/models.py
import uuid
from django.db import models
from django.contrib.auth import get_user_model

User = get_user_model()


class BotSubscriber(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='bot_subscription'
    )
    telegram_id = models.BigIntegerField(
        'Telegram ID',
        null=True, blank=True,
        unique=True
    )
    whatsapp_id = models.CharField(
        'WhatsApp ID',
        max_length=64,
        null=True, blank=True,
        unique=True
    )

    class Meta:
        verbose_name = 'Подписчик бота'
        verbose_name_plural = 'Подписчики ботов'

    def __str__(self):
        return f'{self.user} (TG={self.telegram_id or "-"} / WA={self.whatsapp_id or "-"})'
