"""
Management команда для миграции существующих заявок в кадровые события.

Использование:
    python manage.py migrate_requests_to_actions [--dry-run]
"""

from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone

from requests_app.models import Request
from requests_app.enums import RequestStatus
from employees.signals import IMMEDIATE_ACTION_MAPPING, SCHEDULED_ACTION_MAPPING
from employees.services.request_actions import (
    build_request_action_comment,
    create_request_action,
    get_existing_request_action,
)


# Маппинг для событий возврата из отпуска/больничного
RETURN_ACTION_MAPPING = {
    "vacation": "returned_from_leave",
    "sick_leave": "returned_from_sick_leave",
    "day_off": "returned_from_day_off",
}


class Command(BaseCommand):
    help = (
        "Создает EmployeeAction для всех одобренных заявок, "
        "у которых их еще нет"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать что будет создано, но не создавать",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        if dry_run:
            self.stdout.write(self.style.WARNING("=== DRY RUN MODE ==="))

        # Объединяем все маппинги
        all_mappings = {**IMMEDIATE_ACTION_MAPPING, **SCHEDULED_ACTION_MAPPING}

        # Находим все одобренные заявки с типами, которые требуют EmployeeAction
        approved_requests = (
            Request.objects.filter(
                status=RequestStatus.APPROVED, type__in=all_mappings.keys()
            )
            .select_related("employee", "approver")
            .order_by("created_at")
        )

        total_requests = approved_requests.count()
        self.stdout.write(
            "Найдено "
            f"{total_requests} одобренных заявок типов: "
            f"{list(all_mappings.keys())}"
        )

        created_count = 0
        skipped_count = 0
        return_count = 0  # Счётчик событий возврата
        errors = []

        for request in approved_requests:
            action_type = all_mappings.get(request.type)
            if not action_type:
                continue

            existing = get_existing_request_action(request, action_type)
            should_create_main = existing is None

            if existing:
                skipped_count += 1
                self.stdout.write(
                    self.style.WARNING(
                        f"  SKIP: Request #{request.id} ({request.type}) - "
                        f"EmployeeAction уже существует"
                    )
                )

            # Проверяем нужно ли создать событие возврата
            should_create_return = False
            return_action = None
            return_date = None

            if request.type in RETURN_ACTION_MAPPING and request.date_to:
                return_action = RETURN_ACTION_MAPPING.get(request.type)
                return_date = request.date_to + timedelta(days=1)

                if return_action:
                    existing_return = get_existing_request_action(
                        request, return_action
                    )
                    should_create_return = existing_return is None

            # Если нечего создавать - пропускаем
            if not should_create_main and not should_create_return:
                continue

            # Определяем дату события и нормализуем к datetime с timezone
            raw_date = (
                request.date_from
                or request.decided_at
                or request.created_at
                or timezone.now()
            )
            if isinstance(raw_date, datetime):
                action_date = (
                    raw_date
                    if timezone.is_aware(raw_date)
                    else timezone.make_aware(raw_date)
                )
            else:
                # Конвертируем date в datetime
                action_date = timezone.make_aware(
                    datetime.combine(raw_date, datetime.min.time())
                )

            # Готовим extra данные
            extra_data = {
                "approved_by": request.approver.id
                if request.approver
                else None,
                "migrated": True,  # Помечаем что создано миграцией
                "migration_date": timezone.now().isoformat(),
            }

            if dry_run:
                # Создаём основное событие
                if should_create_main:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  WOULD CREATE: Request #{request.id} "
                            f"({request.type}) → "
                            f"EmployeeAction ({action_type}) "
                            f"for {request.employee} "
                            f"on {action_date.date()}"
                        )
                    )
                    created_count += 1

                # Создаём событие возврата
                if should_create_return:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"  WOULD CREATE RETURN: Request #{request.id} → "
                            f"EmployeeAction ({return_action}) on {return_date}"
                        )
                    )
                    return_count += 1
            else:
                try:
                    # Создаём основное событие
                    if should_create_main:
                        action, created = create_request_action(
                            request=request,
                            action_type=action_type,
                            action_date=request.date_from
                            or request.decided_at
                            or request.created_at,
                            comment=build_request_action_comment(request),
                            extra=extra_data,
                        )
                        if created:
                            self._apply_effects(action)
                            created_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    f"  ✓ Created: EmployeeAction #{action.id} "
                                    f"({action_type}) "
                                    f"from Request #{request.id} "
                                    f"for {request.employee}"
                                )
                            )
                        else:
                            skipped_count += 1

                    # Создаём событие возврата
                    if should_create_return and return_action and return_date:
                        return_comment = (
                            f"Автоматически: окончание "
                            f"{request.get_type_display().lower()} "
                            f"(заявка #{request.id})"
                        )
                        return_action_obj, created = create_request_action(
                            request=request,
                            action_type=return_action,
                            action_date=return_date,
                            comment=return_comment,
                            extra={
                                "auto_return": True,
                                "migrated": True,
                                "migration_date": timezone.now().isoformat(),
                            },
                        )
                        if created:
                            self._apply_effects(return_action_obj)
                            return_count += 1
                            self.stdout.write(
                                self.style.SUCCESS(
                                    "  ✓ Created RETURN: EmployeeAction "
                                    f"#{return_action_obj.id}"
                                    " "
                                    f"({return_action}) on {return_date}"
                                )
                            )
                        else:
                            skipped_count += 1

                except Exception as e:
                    errors.append((request.id, str(e)))
                    self.stdout.write(
                        self.style.ERROR(
                            f"  ✗ Failed: Request #{request.id} - {e}"
                        )
                    )

        # Итоговая статистика
        self.stdout.write("\n" + "=" * 70)
        if dry_run:
            self.stdout.write(
                self.style.WARNING("DRY RUN - изменения не применены")
            )

        self.stdout.write(
            self.style.SUCCESS(f"Обработано заявок: {total_requests}")
        )

        if created_count:
            verb = "Будет создано" if dry_run else "Создано"
            self.stdout.write(
                self.style.SUCCESS(f"{verb} событий: {created_count}")
            )

        if return_count:
            verb = "Будет создано" if dry_run else "Создано"
            self.stdout.write(
                self.style.SUCCESS(f"{verb} событий возврата: {return_count}")
            )

        if skipped_count:
            self.stdout.write(
                self.style.WARNING(
                    f"Пропущено (уже существуют): {skipped_count}"
                )
            )

        if errors:
            self.stdout.write(self.style.ERROR(f"\nОшибки ({len(errors)}):"))
            for req_id, error in errors:
                self.stdout.write(f"  Request #{req_id}: {error}")

        if not dry_run and created_count > 0:
            self.stdout.write(
                self.style.SUCCESS("\n✓ Миграция завершена успешно!")
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
                    f"    Warning: Could not apply effects for action #{
                        action.id
                    }: {e}"
                )
            )
