"""
Management команда для показа статистики уведомлений
"""
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db.models import Count, Q
from notifications.models import (
    Notification,
    NotificationType,
    WebPushSubscription,
)

User = get_user_model()


class Command(BaseCommand):
    help = 'Показать статистику уведомлений'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('\n📊 СТАТИСТИКА УВЕДОМЛЕНИЙ\n'))

        # Общая статистика уведомлений
        total_notifications = Notification.objects.count()
        unread_notifications = Notification.objects.filter(is_read=False).count()
        archived_notifications = Notification.objects.filter(is_archived=True).count()

        self.stdout.write('📧 Уведомления:')
        self.stdout.write(f'  Всего: {total_notifications}')
        self.stdout.write(f'  Непрочитанных: {unread_notifications}')
        self.stdout.write(f'  Архивных: {archived_notifications}')

        # Статистика по категориям
        self.stdout.write('\n📁 По категориям:')
        category_stats = Notification.objects.values(
            'notification_type__category__name'
        ).annotate(
            count=Count('id'),
            unread=Count('id', filter=Q(is_read=False))
        ).order_by('-count')

        for stat in category_stats[:10]:
            category_name = stat['notification_type__category__name'] or 'Unknown'
            self.stdout.write(
                f'  {category_name}: {stat["count"]} '
                f'(непрочитанных: {stat["unread"]})'
            )

        # Статистика по типам (топ 10)
        self.stdout.write('\n🔔 Топ-10 типов уведомлений:')
        type_stats = Notification.objects.values(
            'notification_type__name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]

        for stat in type_stats:
            type_name = stat['notification_type__name']
            self.stdout.write(f'  {type_name}: {stat["count"]}')

        # Статистика по пользователям (топ 10)
        self.stdout.write('\n👥 Топ-10 пользователей по уведомлениям:')
        user_stats = Notification.objects.values(
            'recipient__email'
        ).annotate(
            count=Count('id'),
            unread=Count('id', filter=Q(is_read=False))
        ).order_by('-count')[:10]

        for stat in user_stats:
            email = stat['recipient__email']
            self.stdout.write(
                f'  {email}: {stat["count"]} '
                f'(непрочитанных: {stat["unread"]})'
            )

        # Web Push подписки
        self.stdout.write('\n📱 Web Push подписки:')
        total_subs = WebPushSubscription.objects.count()
        active_subs = WebPushSubscription.objects.filter(is_active=True).count()
        error_subs = WebPushSubscription.objects.filter(
            error_count__gt=0
        ).count()

        self.stdout.write(f'  Всего: {total_subs}')
        self.stdout.write(f'  Активных: {active_subs}')
        self.stdout.write(f'  С ошибками: {error_subs}')

        # Подписки по устройствам
        if active_subs > 0:
            self.stdout.write('\n  По устройствам:')
            device_stats = WebPushSubscription.objects.filter(
                is_active=True
            ).values('device_name').annotate(
                count=Count('id')
            ).order_by('-count')

            for stat in device_stats[:10]:
                device = stat['device_name'] or 'Unknown'
                self.stdout.write(f'    {device}: {stat["count"]}')

        # Каналы доставки
        self.stdout.write('\n📤 Статистика доставки:')
        sent_web = Notification.objects.filter(sent_web=True).count()
        sent_email = Notification.objects.filter(sent_email=True).count()
        sent_telegram = Notification.objects.filter(sent_telegram=True).count()

        self.stdout.write(f'  Web: {sent_web}')
        self.stdout.write(f'  Email: {sent_email}')
        self.stdout.write(f'  Telegram: {sent_telegram}')

        # Типы уведомлений
        self.stdout.write('\n⚙️  Типы уведомлений:')
        total_types = NotificationType.objects.count()
        active_types = NotificationType.objects.filter(is_active=True).count()

        self.stdout.write(f'  Всего: {total_types}')
        self.stdout.write(f'  Активных: {active_types}')

        self.stdout.write('')
