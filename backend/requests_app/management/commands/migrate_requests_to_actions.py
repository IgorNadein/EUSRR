"""
Management команда для миграции существующих заявок в кадровые события.

Использование:
    python manage.py migrate_requests_to_actions [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from requests_app.models import Request
from requests_app.enums import RequestStatus
from employees.models import EmployeeAction
from employees.signals import IMMEDIATE_ACTION_MAPPING, SCHEDULED_ACTION_MAPPING


class Command(BaseCommand):
    help = 'Создает EmployeeAction для всех одобренных заявок, у которых их еще нет'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет создано, но не создавать',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        
        if dry_run:
            self.stdout.write(self.style.WARNING('=== DRY RUN MODE ==='))
        
        # Объединяем все маппинги
        all_mappings = {**IMMEDIATE_ACTION_MAPPING, **SCHEDULED_ACTION_MAPPING}
        
        # Находим все одобренные заявки с типами, которые требуют EmployeeAction
        approved_requests = Request.objects.filter(
            status=RequestStatus.APPROVED,
            type__in=all_mappings.keys()
        ).select_related('employee', 'approver').order_by('created_at')
        
        total_requests = approved_requests.count()
        self.stdout.write(
            f'Найдено {total_requests} одобренных заявок типов: {list(all_mappings.keys())}'
        )
        
        created_count = 0
        skipped_count = 0
        errors = []
        
        for request in approved_requests:
            action_type = all_mappings.get(request.type)
            if not action_type:
                continue
            
            # Проверяем, существует ли уже событие для этой заявки
            existing = EmployeeAction.objects.filter(
                extra__request_id=request.id,
                action=action_type
            ).exists()
            
            if existing:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f'  SKIP: Request #{request.id} ({request.type}) - '
                        f'EmployeeAction уже существует'
                    )
                )
                continue
            
            # Определяем дату события
            action_date = request.date_from or request.decided_at or request.created_at or timezone.now()
            
            # Формируем комментарий
            action_comment = f"Заявление #{request.id}"
            if request.comment:
                action_comment += f": {request.comment[:200]}"
            
            # Готовим extra данные
            extra_data = {
                'request_id': request.id,
                'approved_by': request.approver.id if request.approver else None,
                'migrated': True,  # Помечаем что создано миграцией
                'migration_date': timezone.now().isoformat()
            }
            
            if dry_run:
                # action_date может быть date или datetime
                date_str = action_date.date() if hasattr(action_date, 'date') else action_date
                self.stdout.write(
                    self.style.SUCCESS(
                        f'  WOULD CREATE: Request #{request.id} ({request.type}) → '
                        f'EmployeeAction ({action_type}) for {request.employee} '
                        f'on {date_str}'
                    )
                )
                created_count += 1
            else:
                try:
                    with transaction.atomic():
                        action = EmployeeAction.objects.create(
                            employee=request.employee,
                            action=action_type,
                            date=action_date,
                            comment=action_comment,
                            extra=extra_data
                        )
                        
                        # Применяем эффекты (деактивация, LDAP sync)
                        self._apply_effects(action)
                        
                        created_count += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'  ✓ Created: EmployeeAction #{action.id} ({action_type}) '
                                f'from Request #{request.id} for {request.employee}'
                            )
                        )
                
                except Exception as e:
                    errors.append((request.id, str(e)))
                    self.stdout.write(
                        self.style.ERROR(
                            f'  ✗ Failed: Request #{request.id} - {e}'
                        )
                    )
        
        # Итоговая статистика
        self.stdout.write('\n' + '='*70)
        if dry_run:
            self.stdout.write(self.style.WARNING('DRY RUN - изменения не применены'))
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Обработано заявок: {total_requests}'
            )
        )
        
        if created_count:
            verb = 'Будет создано' if dry_run else 'Создано'
            self.stdout.write(
                self.style.SUCCESS(
                    f'{verb} событий: {created_count}'
                )
            )
        
        if skipped_count:
            self.stdout.write(
                self.style.WARNING(
                    f'Пропущено (уже существуют): {skipped_count}'
                )
            )
        
        if errors:
            self.stdout.write(
                self.style.ERROR(
                    f'\nОшибки ({len(errors)}):'
                )
            )
            for req_id, error in errors:
                self.stdout.write(f'  Request #{req_id}: {error}')
        
        if not dry_run and created_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    '\n✓ Миграция завершена успешно!'
                )
            )
    
    def _apply_effects(self, action):
        """Применяет эффекты кадрового события (как в EmployeeActionViewSet)."""
        try:
            from api.v1.employees.views.actions import EmployeeActionViewSet
            viewset = EmployeeActionViewSet()
            viewset._apply_effects(action)
        except Exception as e:
            # Не критично если эффекты не применились
            self.stdout.write(
                self.style.WARNING(
                    f'    Warning: Could not apply effects for action #{action.id}: {e}'
                )
            )
