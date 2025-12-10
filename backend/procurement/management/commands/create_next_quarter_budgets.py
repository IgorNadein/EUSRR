"""
Management команда для создания бюджетов на следующий квартал.

Использование:
    python manage.py create_next_quarter_budgets
    
    # Создать для конкретного года/квартала:
    python manage.py create_next_quarter_budgets --year 2026 --quarter 1
    
    # Dry-run (без изменений в БД):
    python manage.py create_next_quarter_budgets --dry-run
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.utils import timezone

from employees.models import Department
from procurement.models import Budget


class Command(BaseCommand):
    help = 'Создать бюджеты на следующий квартал для всех отделов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--year',
            type=int,
            help='Год для создания бюджетов (по умолчанию следующий)',
        )
        parser.add_argument(
            '--quarter',
            type=int,
            choices=[1, 2, 3, 4],
            help='Квартал (1-4)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет создано, но не создавать',
        )
        parser.add_argument(
            '--default-amount',
            type=float,
            default=0.0,
            help='Сумма по умолчанию если нет текущего бюджета (₽)',
        )

    def handle(self, *args, **options):
        now = timezone.now()
        current_quarter = (now.month - 1) // 3 + 1
        
        # Определяем целевой квартал
        if options['year'] and options['quarter']:
            target_year = options['year']
            target_quarter = options['quarter']
        else:
            # По умолчанию - следующий квартал
            if current_quarter == 4:
                target_quarter = 1
                target_year = now.year + 1
            else:
                target_quarter = current_quarter + 1
                target_year = now.year
        
        self.stdout.write(
            self.style.SUCCESS(
                f'\n📊 Создание бюджетов на {target_year} Q{target_quarter}'
            )
        )
        
        if options['dry_run']:
            self.stdout.write(
                self.style.WARNING('🔍 DRY RUN - изменения не будут сохранены')
            )
        
        # Получаем все отделы
        departments = Department.objects.all()
        
        if not departments.exists():
            self.stdout.write(
                self.style.ERROR('❌ Не найдено ни одного отдела!')
            )
            return
        
        created_count = 0
        skipped_count = 0
        errors_count = 0
        
        default_amount = Decimal(str(options['default_amount']))
        
        self.stdout.write(f'\nВсего отделов: {departments.count()}\n')
        
        for dept in departments:
            # Проверяем существует ли уже бюджет
            exists = Budget.objects.filter(
                department=dept,
                year=target_year,
                quarter=target_quarter
            ).exists()
            
            if exists:
                self.stdout.write(
                    f'⏭️  {dept.name}: уже существует'
                )
                skipped_count += 1
                continue
            
            # Пытаемся скопировать бюджет из текущего квартала
            try:
                current_budget = Budget.objects.get(
                    department=dept,
                    year=now.year,
                    quarter=current_quarter
                )
                allocated = current_budget.allocated_amount
                source = f'текущий Q{current_quarter}'
            except Budget.DoesNotExist:
                allocated = default_amount
                source = 'по умолчанию'
            
            # Создаём бюджет
            if not options['dry_run']:
                try:
                    Budget.objects.create(
                        department=dept,
                        year=target_year,
                        quarter=target_quarter,
                        allocated_amount=allocated,
                        spent_amount=Decimal('0.00')
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ {dept.name}: {allocated:,.0f}₽ '
                            f'(из {source})'
                        )
                    )
                    created_count += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f'❌ {dept.name}: ошибка - {str(e)}'
                        )
                    )
                    errors_count += 1
            else:
                self.stdout.write(
                    f'🔍 {dept.name}: будет создан с {allocated:,.0f}₽ '
                    f'(из {source})'
                )
                created_count += 1
        
        # Итоги
        self.stdout.write('\n' + '=' * 60)
        
        if options['dry_run']:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✨ Будет создано: {created_count} бюджетов'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✨ Создано: {created_count} бюджетов'
                )
            )
        
        if skipped_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f'⏭️  Пропущено (уже существуют): {skipped_count}'
                )
            )
        
        if errors_count > 0:
            self.stdout.write(
                self.style.ERROR(f'❌ Ошибок: {errors_count}')
            )
        
        self.stdout.write('')
