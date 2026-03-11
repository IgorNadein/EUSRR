# users/signals.py
import os
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from django.db.models import Q
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .constants import ACTION_HIRED

from .models import Employee, EmployeeAction, Department


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


@receiver(post_save, sender=Department)
def create_main_department_chat(sender, instance, created, **kwargs):
    """
    Создает главный чат для нового отдела (EUSRR-specific logic).
    
    Использует GenericFK (context_object) и flags['is_primary'].
    """
    if not created:
        return
    
    try:
        from communications.models import Chat
        
        dept_ct = ContentType.objects.get_for_model(Department)
        
        # Проверка: существует ли уже чат для этого отдела
        existing = Chat.objects.filter(
            type="channel",
            context_content_type=dept_ct,
            context_object_id=instance.id,
            flags__is_primary=True
        ).exists()
        
        if not existing:
            Chat.objects.create(
                type="channel",
                context_content_type=dept_ct,
                context_object_id=instance.id,
                flags={'is_primary': True},
                is_main=True,
                name=f"Основной чат {instance.name}"
            )
    except ImportError:
        # communications app не установлен - пропускаем
        pass
