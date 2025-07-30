# calendar_app/signals.py

from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from .models import CompanyEvent
from users.models import Employee

@receiver(pre_save, sender=Employee)
def cache_old_birth_date(sender, instance: Employee, **kwargs):
    """
    Перед сохранением запомним старую дату рождения,
    чтобы потом удалить соответствующее событие.
    """
    if instance.pk:
        try:
            old = Employee.objects.get(pk=instance.pk)
            instance._old_birth_date = old.birth_date
        except Employee.DoesNotExist:
            instance._old_birth_date = None
    else:
        instance._old_birth_date = None

@receiver(post_save, sender=Employee)
def create_or_update_birthday(sender, instance: Employee, created, **kwargs):
    """
    После сохранения:
    - Удаляем старое событие, если birth_date поменялась.
    - Если указана новая birth_date — создаём или обновляем событие.
    """
    title = f'День рождения: {instance.last_name} {instance.first_name}'

    old_date = getattr(instance, '_old_birth_date', None)
    new_date = instance.birth_date

    # 1. Удаляем старое событие, если дата изменилась и старое было задано
    if old_date and old_date != new_date:
        CompanyEvent.objects.filter(
            title=title,
            date=old_date,
            recurrence=CompanyEvent.ANNUAL,
            created_by=instance
        ).delete()

    # 2. Создаём/обновляем новое ежегодное событие
    if new_date:
        CompanyEvent.objects.update_or_create(
            title=title,
            date=new_date,
            recurrence=CompanyEvent.ANNUAL,
            created_by=instance,
            defaults={'description': f'Авто-создано для {instance.get_full_name()}'}
        )
    else:
        # Если дата убрана — тоже удаляем старое, если оно осталось
        CompanyEvent.objects.filter(
            title=title,
            recurrence=CompanyEvent.ANNUAL,
            created_by=instance
        ).delete()
