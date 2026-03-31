"""
Celery задачи для модуля communications
"""
from celery import shared_task
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger(__name__)


@shared_task
def cleanup_orphaned_attachments():
    """
    Очистка временных вложений без привязки к сообщению.
    Удаляет MessageAttachment с message=null старше 1 часа.
    """
    from communications.models import MessageAttachment

    cutoff_time = timezone.now() - timedelta(hours=1)

    orphaned = MessageAttachment.objects.filter(
        message__isnull=True,
        uploaded_at__lt=cutoff_time
    )

    count = orphaned.count()

    if count > 0:
        logger.info(
            f'[cleanup_orphaned_attachments] Found {count} orphaned attachments')

        # Удаляем файлы и записи
        for attachment in orphaned:
            try:
                if attachment.file:
                    attachment.file.delete()
                attachment.delete()
            except Exception as e:
                logger.error(
                    f'[cleanup_orphaned_attachments] Error deleting attachment {
                        attachment.id}: {e}')

        logger.info(
            f'[cleanup_orphaned_attachments] Cleaned up {count} orphaned attachments')

    return count
