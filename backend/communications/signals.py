# backend\communications\signals.py
from django.core.files.base import ContentFile
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from employees.models import Department
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Department)
def create_main_department_chat(sender, instance, created, **kwargs):
    from communications.models import Chat

    if created:
        if not Chat.objects.filter(
            type="department", department=instance, is_main=True
        ).exists():
            Chat.objects.create(type="department", department=instance, is_main=True)


@receiver(pre_save, sender='communications.Chat')
def compress_and_cleanup_chat_avatar(sender, instance, **kwargs):
    """
    Сжимает новый аватар чата и удаляет старый файл
    """
    if not instance.avatar:
        return

    # Если это новый объект (нет pk), просто сжимаем
    if not instance.pk:
        try:
            from common.image_utils import compress_avatar
            compressed = compress_avatar(instance.avatar.read())
            if compressed:
                instance.avatar.save(
                    instance.avatar.name,
                    ContentFile(compressed),
                    save=False
                )
        except Exception as e:
            logger.error(f"Error compressing new chat avatar: {e}")
        return

    # Проверяем, изменился ли файл аватара
    try:
        old_instance = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return

    old_avatar = old_instance.avatar
    new_avatar = instance.avatar

    # Если путь изменился - это новый файл
    if old_avatar and new_avatar and old_avatar.name != new_avatar.name:
        try:
            # Сжимаем новый аватар
            from common.image_utils import compress_avatar
            compressed = compress_avatar(new_avatar.read())
            if compressed:
                new_avatar.save(
                    new_avatar.name,
                    ContentFile(compressed),
                    save=False
                )

            # Удаляем старый файл
            if old_avatar.name:
                old_avatar.delete(save=False)
                logger.info(
                    f"Deleted old chat avatar: {old_avatar.name}"
                )
        except Exception as e:
            logger.error(f"Error processing chat avatar: {e}")
