"""
Management команда для очистки устаревших Web Push подписок
"""
from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from notifications.models import WebPushSubscription


class Command(BaseCommand):
    help = 'Очистка устаревших Web Push подписок'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Удалить неактивные подписки старше N дней (по умолчанию: 30)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет удалено, но не удалять'
        )
    
    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        cutoff_date = timezone.now() - timedelta(days=days)
        
        self.stdout.write(
            self.style.WARNING(
                f'\n{"DRY RUN - " if dry_run else ""}Очистка подписок старше {days} дней '
                f'(до {cutoff_date.strftime("%Y-%m-%d %H:%M")})\n'
            )
        )
        
        # Находим кандидатов на удаление
        inactive_old = WebPushSubscription.objects.filter(
            is_active=False,
            updated_at__lt=cutoff_date
        )
        
        high_error = WebPushSubscription.objects.filter(
            error_count__gte=10,
            updated_at__lt=cutoff_date
        )
        
        # Статистика
        total_before = WebPushSubscription.objects.count()
        inactive_count = inactive_old.count()
        high_error_count = high_error.count()
        
        self.stdout.write('📊 Статистика до очистки:')
        self.stdout.write(f'  Всего подписок: {total_before}')
        self.stdout.write(f'  Неактивных старше {days} дней: {inactive_count}')
        self.stdout.write(f'  С 10+ ошибками старше {days} дней: {high_error_count}')
        
        if not dry_run:
            # Удаляем неактивные
            if inactive_count > 0:
                deleted_inactive, _ = inactive_old.delete()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'\n✅ Удалено {deleted_inactive} неактивных подписок'
                    )
                )
            
            # Удаляем с большим количеством ошибок
            if high_error_count > 0:
                deleted_errors, _ = high_error.delete()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✅ Удалено {deleted_errors} подписок с множественными ошибками'
                    )
                )
            
            total_after = WebPushSubscription.objects.count()
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n🎯 Осталось подписок: {total_after} '
                    f'(освобождено: {total_before - total_after})'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f'\n⚠️  DRY RUN - ничего не удалено. '
                    f'Было бы удалено: {inactive_count + high_error_count} подписок'
                )
            )
        
        # Показываем текущую статистику по активным подпискам
        active_subs = WebPushSubscription.objects.filter(is_active=True)
        active_count = active_subs.count()
        
        if active_count > 0:
            self.stdout.write('\n📱 Активные подписки по устройствам:')
            
            device_stats = {}
            for sub in active_subs:
                device = sub.device_name or 'Unknown'
                device_stats[device] = device_stats.get(device, 0) + 1
            
            for device, count in sorted(device_stats.items(), key=lambda x: x[1], reverse=True):
                self.stdout.write(f'  {device}: {count}')
        
        self.stdout.write('')
