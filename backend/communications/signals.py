# backend\communications\signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from employees.models import Department


@receiver(post_save, sender=Department)
def create_main_department_chat(sender, instance, created, **kwargs):
    from communications.models import Chat

    if created:
        if not Chat.objects.filter(
            type="department", department=instance, is_main=True
        ).exists():
            Chat.objects.create(type="department", department=instance, is_main=True)
