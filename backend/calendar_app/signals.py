# backend/calendar_app/signals.py
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver

from employees.models import Employee
from .models import CompanyEvent, Recurrence


@receiver(pre_save, sender=Employee)
def remember_old_birth_date(sender, instance: Employee, **kwargs):
    """
    Запоминаем старую дату рождения, чтобы понять изменилось ли поле.
    """
    if not instance.pk:
        instance._old_birth_date = None
        return
    try:
        old = sender.objects.only("birth_date").get(pk=instance.pk)
        instance._old_birth_date = old.birth_date
    except sender.DoesNotExist:
        instance._old_birth_date = None


@receiver(post_save, sender=Employee)
def create_or_update_birthday(sender, instance: Employee, created: bool, **kwargs):
    """
    Синхронизируем ежегодное событие «День рождения ...»:
    - При смене даты: удаляем старое и создаём/обновляем новое;
    - При очистке даты: удаляем событие.
    """
    # Во время loaddata/migrations может приходить raw
    if kwargs.get("raw"):
        return

    # Формируем заголовок без лишних пробелов, even if names are empty
    first = (instance.first_name or "").strip()
    last = (instance.last_name or "").strip()
    space = " " if first and last else ""
    title = f"День рождения: {last}{space}{first}".strip()

    old_date = getattr(instance, "_old_birth_date", None)
    new_date = instance.birth_date
    annual = Recurrence.ANNUAL  # TextChoices member ("annual")

    # 1) Если дата менялась — удаляем событие со старой датой
    if old_date and old_date != new_date:
        CompanyEvent.objects.filter(
            title=title,
            date=old_date,
            recurrence=annual,
            created_by=instance,
        ).delete()

    # 2) Если есть новая дата — создаём/обновляем событие
    if new_date:
        CompanyEvent.objects.update_or_create(
            title=title,
            date=new_date,
            recurrence=annual,
            created_by=instance,
            defaults={
                "description": f"Авто-создано для {getattr(instance, 'get_full_name', lambda: '')() or instance.pk}"
            },
        )
    # 3) Если дату убрали — подчистим возможные хвосты
    elif old_date:
        CompanyEvent.objects.filter(
            title=title,
            recurrence=annual,
            created_by=instance,
        ).delete()
