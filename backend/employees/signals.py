# users/signals.py
import os
from django.core.files.base import ContentFile
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .constants import ACTION_HIRED

from .models import Employee, EmployeeAction


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
