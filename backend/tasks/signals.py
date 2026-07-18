from django.db import transaction
from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import TaskAttachment


@receiver(post_delete, sender=TaskAttachment)
def delete_task_attachment_file(sender, instance, **kwargs):
    if not instance.file or not instance.file.name:
        return

    storage = instance.file.storage
    name = instance.file.name
    transaction.on_commit(lambda: storage.delete(name) if storage.exists(name) else None)
