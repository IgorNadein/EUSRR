# backend/calendar_app/management/commands/migrate_birthdays_to_scheduler.py
"""
Management команда для миграции событий дней рождения из calendar_app в django-scheduler.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from employees.models import Employee


class Command(BaseCommand):
    help = 'Мигрирует события дней рождения из calendar_app в django-scheduler'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано без фактической миграции',
        )
        parser.add_argument(
            '--delete-old',
            action='store_true',
            help='Удалить старые события дней рождения из calendar_app',
        )
    
    def handle(self, *args, **options):
        # NOTE: Используем новый Service Layer из employees
        from employees.services import UpsertBirthdayEventService
        from calendar_app.models import CalendarEvent
        from schedule.models import Calendar
        
        dry_run = options['dry_run']
        delete_old = options['delete_old']
        
        self.stdout.write(self.style.WARNING('\n' + '='*80))
        self.stdout.write(self.style.WARNING('МИГРАЦИЯ ДНЕЙ РОЖДЕНИЯ: calendar_app → django-scheduler'))
        self.stdout.write(self.style.WARNING('='*80 + '\n'))
        
        if dry_run:
            self.stdout.write(self.style.NOTICE('🔍 Режим DRY-RUN (изменения не применяются)\n'))
        
        # Проверяем наличие календаря компании
        try:
            company_cal = Calendar.objects.get(slug='company-global')
            self.stdout.write(self.style.SUCCESS(f'✅ Календарь компании найден: {company_cal.name}\n'))
        except Calendar.DoesNotExist:
            self.stdout.write(self.style.ERROR('❌ Календарь компании (company-global) не найден!'))
            self.stdout.write(self.style.WARNING('   Запустите миграцию: python manage.py migrate calendar_app'))
            return
        
        # Получаем всех активных сотрудников с датой рождения
        employees = Employee.objects.filter(is_active=True)
        total = employees.count()
        
        self.stdout.write(f'📊 Найдено активных сотрудников: {total}\n')
        
        migrated = 0
        skipped = 0
        errors = 0
        
        with transaction.atomic():
            for emp in employees:
                birthday = emp.birth_date  # Используем напрямую поле модели
                
                if not birthday:
                    skipped += 1
                    continue
                
                try:
                    if not dry_run:
                        UpsertBirthdayEventService.execute({'employee': emp})
                    
                    migrated += 1
                    name = emp.get_full_name() if hasattr(emp, 'get_full_name') else str(emp)
                    self.stdout.write(
                        f'  ✅ {name} ({birthday.strftime("%d.%m.%Y")})'
                    )
                
                except Exception as e:
                    errors += 1
                    self.stdout.write(
                        self.style.ERROR(f'  ❌ Ошибка для {emp}: {e}')
                    )
            
            if dry_run:
                self.stdout.write(self.style.NOTICE('\n⚠️  DRY-RUN: транзакция откатывается'))
                raise Exception('Dry run rollback')
        
        self.stdout.write('\n' + '-'*80)
        self.stdout.write(self.style.SUCCESS(f'✅ Мигрировано: {migrated}'))
        self.stdout.write(self.style.WARNING(f'⏭️  Пропущено (нет даты рождения): {skipped}'))
        if errors > 0:
            self.stdout.write(self.style.ERROR(f'❌ Ошибок: {errors}'))
        
        # Удаление старых событий
        if delete_old and not dry_run:
            self.stdout.write('\n' + '-'*80)
            self.stdout.write('🗑️  Удаление старых событий дней рождения из calendar_app...')
            
            old_birthdays = CalendarEvent.objects.filter(
                source__startswith='employee:',
                source__endswith=':birthday'
            )
            count = old_birthdays.count()
            old_birthdays.delete()
            
            self.stdout.write(self.style.SUCCESS(f'✅ Удалено старых событий: {count}'))
        
        self.stdout.write('\n' + '='*80)
        self.stdout.write(self.style.SUCCESS('МИГРАЦИЯ ЗАВЕРШЕНА'))
        self.stdout.write('='*80 + '\n')
