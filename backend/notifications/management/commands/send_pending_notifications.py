"""
Команда для отправки неотправленных уведомлений.
Можно запускать периодически через cron или supervisor.
"""
import logging
from django.core.management.base import BaseCommand
from django.utils import timezone
from notifications.models import Notification
from notifications.services import NotificationService

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Отправить неотправленные уведомления'

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size',
            type=int,
            default=100,
            help='Количество уведомлений в одной порции (по умолчанию 100)'
        )
        parser.add_argument(
            '--max-age-minutes',
            type=int,
            default=60,
            help='Максимальный возраст неотправленных уведомлений в минутах'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        max_age = options['max_age_minutes']
        
        # Находим неотправленные уведомления
        cutoff_time = timezone.now() - timezone.timedelta(minutes=max_age)
        
        pending = Notification.objects.filter(
            sent_at__isnull=True,
            created_at__gte=cutoff_time
        ).select_related(
            'recipient',
            'notification_type'
        )[:batch_size]
        
        count = pending.count()
        
        if count == 0:
            self.stdout.write(
                self.style.SUCCESS('Нет неотправленных уведомлений')
            )
            return
        
        self.stdout.write(
            f'Найдено {count} неотправленных уведомлений'
        )
        
        success_count = 0
        error_count = 0
        
        for notification in pending:
            try:
                # Получаем настройки пользователя
                settings = NotificationService.get_user_settings(
                    notification.recipient,
                    notification.notification_type
                )
                
                # Отправляем
                NotificationService.send_notification(notification, settings)
                success_count += 1
                
                if success_count % 10 == 0:
                    self.stdout.write(f'  Отправлено: {success_count}/{count}')
                    
            except Exception as e:
                error_count += 1
                logger.error(
                    f'Ошибка отправки уведомления {notification.id}: {e}',
                    exc_info=True
                )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Завершено: успешно={success_count}, ошибок={error_count}'
            )
        )
