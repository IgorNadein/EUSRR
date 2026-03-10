# backend\communications\signals.py
from django.core.files.base import ContentFile
from django.db.models import F
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
            Chat.objects.create(
                type="department",
                department=instance,
                is_main=True,
                name=f"Основной чат {instance.name}"
            )


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


@receiver(post_save, sender='communications.Message')
def increment_unread_count_on_new_message(sender, instance, created, **kwargs):
    """
    Инкрементирует unread_count для всех участников чата (кроме автора)
    при создании нового сообщения.
    
    Денормализация: вместо подсчета COUNT(*) в реальном времени,
    обновляем кешированный счетчик инкрементом.
    """
    if not created or instance.is_deleted:
        return
    
    from communications.models import ChatReadState
    
    try:
        # Получаем всех участников чата
        chat = instance.chat
        participants = chat.get_participants.exclude(id=instance.author_id)
        
        # Инкрементируем счетчик для существующих ChatReadState
        # Только для тех, кто еще не прочитал это сообщение
        updated_count = ChatReadState.objects.filter(
            chat=chat,
            user__in=participants
        ).exclude(
            # Пропускаем тех, кто уже прочитал дальше этого сообщения
            last_read_message_id__gte=instance.id
        ).update(
            unread_count=F('unread_count') + 1
        )
        
        # Создаем ChatReadState для участников, у которых его еще нет
        existing_users = ChatReadState.objects.filter(
            chat=chat,
            user__in=participants
        ).values_list('user_id', flat=True)
        
        new_users = participants.exclude(id__in=existing_users)
        
        if new_users.exists():
            # Создаем ChatReadState с unread_count=1 для новых участников
            ChatReadState.objects.bulk_create([
                ChatReadState(
                    chat=chat,
                    user=user,
                    last_read_message=None,
                    unread_count=1
                )
                for user in new_users
            ], ignore_conflicts=True)
            
            logger.info(
                f"[increment_unread] Created {new_users.count()} new ChatReadState for msg={instance.id}"
            )
        
        logger.debug(
            f"[increment_unread] Updated {updated_count} ChatReadState for msg={instance.id} in chat={chat.id}"
        )
        
    except Exception as e:
        logger.error(f"Error incrementing unread_count for message {instance.id}: {e}", exc_info=True)
