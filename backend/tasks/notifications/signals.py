import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from tasks.models import TaskLinkedObject
from .handlers import notify_task_linked_object

logger = logging.getLogger(__name__)


@receiver(post_save, sender=TaskLinkedObject)
def notify_on_task_link_created(sender, instance, created, **kwargs):
    if not created:
        return
    try:
        notify_task_linked_object(instance)
    except Exception:
        logger.exception(
            "Failed to send task linked object notification for link %s",
            instance.id,
        )
