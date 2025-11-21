"""
Signals для автоматической отвязки Telegram при изменении контактных данных
"""
from django.db.models.signals import pre_save
from django.dispatch import receiver
from employees.models import Employee
from notifications.telegram_models import TelegramUser
import logging

logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Employee)
def check_telegram_field_change(sender, instance, **kwargs):
    """
    Отвязывает Telegram аккаунт если пользователь изменил поле telegram
    """
    # Проверяем что это обновление существующего объекта
    if not instance.pk:
        return
    
    try:
        # Получаем старое значение из БД
        old_instance = Employee.objects.get(pk=instance.pk)
        old_telegram = old_instance.telegram.strip().lower()
        new_telegram = instance.telegram.strip().lower()
        
        # Если поле telegram изменилось
        if old_telegram != new_telegram:
            # Ищем привязанный Telegram аккаунт
            tg_users = TelegramUser.objects.filter(
                user=instance,
                is_active=True
            )
            
            if tg_users.exists():
                # Отвязываем все активные привязки
                count = tg_users.update(is_active=False)
                
                logger.info(
                    f"Telegram отвязан для {instance.email}: "
                    f"поле изменено с '{old_telegram}' на '{new_telegram}' "
                    f"(отвязано аккаунтов: {count})"
                )
                
                # Опционально: отправить уведомление пользователю
                from notifications.telegram_sender import (
                    TelegramNotificationSender
                )
                
                for tg_user in tg_users:
                    if tg_user.telegram_id:
                        try:
                            TelegramNotificationSender.send_message(
                                telegram_id=tg_user.telegram_id,
                                text=(
                                    "⚠️ <b>Аккаунт отвязан</b>\n\n"
                                    "Ваш Telegram аккаунт был отвязан от EUSRR, "
                                    "так как вы изменили поле 'Telegram' "
                                    "в своём профиле.\n\n"
                                    "Для повторной привязки используйте /link"
                                ),
                            )
                        except Exception as e:
                            logger.error(
                                f"Не удалось отправить уведомление об отвязке: {e}"
                            )
    
    except Employee.DoesNotExist:
        # Объект был удален между проверкой и сохранением
        pass
