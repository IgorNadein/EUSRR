# users/signals.py
import os
from django.core.files.base import ContentFile
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone
from .constants import ACTION_HIRED

from .models import Employee, EmployeeAction
from bots.models import BotSubscriber


@receiver(pre_save, sender=Employee)
def compress_and_cleanup_avatar(sender, instance: Employee, **kwargs):
    """Сжимает новый аватар и удаляет старый файл при замене."""
    # Импортируем здесь, чтобы избежать циклических импортов
    from common.image_utils import compress_avatar
    
    # Проверяем, загружен ли новый файл аватара
    if instance.avatar and hasattr(instance.avatar, 'file'):
        try:
            # Читаем данные нового аватара
            instance.avatar.seek(0)
            original_data = instance.avatar.read()
            
            # Сжимаем изображение
            compressed_data = compress_avatar(original_data)
            
            # Если сжатие дало результат меньшего размера, заменяем
            if len(compressed_data) < len(original_data):
                # Получаем имя файла
                filename = instance.avatar.name.split('/')[-1]
                if not filename.lower().endswith('.jpg'):
                    # Меняем расширение на .jpg
                    filename = filename.rsplit('.', 1)[0] + '.jpg'
                
                # Заменяем файл на сжатый
                instance.avatar.save(
                    filename,
                    ContentFile(compressed_data),
                    save=False
                )
        except Exception as e:
            # Логируем ошибку, но не прерываем сохранение
            print(f"Error compressing avatar: {e}")
    
    # Удаляем старый файл если он был заменен
    if instance.pk is None:
        return
    
    try:
        old = sender.objects.get(pk=instance.pk)
    except sender.DoesNotExist:
        return
    
    # Если аватар изменился или удален
    if old.avatar and old.avatar != instance.avatar:
        # Удаляем старый файл с диска
        if os.path.isfile(old.avatar.path):
            try:
                os.remove(old.avatar.path)
            except Exception as e:
                print(f"Error deleting old avatar: {e}")


@receiver(pre_save, sender=Employee)
def unbind_bot_subscriber_on_contact_change(
    sender, instance: Employee, **kwargs
):
    # Игнорируем новых пользователей
    if instance.pk is None:
        return

    old = sender.objects.get(pk=instance.pk)
    try:
        sub = old.bot_subscription
    except BotSubscriber.DoesNotExist:
        return

    # Если очистили или изменили telegram в профиле — сбросим telegram_id
    if old.telegram and old.telegram != (instance.telegram or "").strip():
        sub.telegram_id = None
        sub.save(update_fields=["telegram_id"])

    # Аналогично для whatsapp
    if old.whatsapp and old.whatsapp != instance.whatsapp:
        sub.whatsapp_id = None
        sub.save(update_fields=["whatsapp_id"])

    if old.wechat and old.wechat != instance.wechat:
        sub.wechat_id = None
        sub.save(update_fields=["wechat_id"])


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
