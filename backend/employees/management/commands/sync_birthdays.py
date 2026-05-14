"""
Management команда для массовой синхронизации дней рождений.
Использует Service Layer для инкапсуляции бизнес-логики.

Примеры использования:
    python manage.py sync_birthdays
    python manage.py sync_birthdays --dry-run
"""

from django.core.management.base import BaseCommand
from django.db import transaction

from employees.services import BulkSyncBirthdaysService


class Command(BaseCommand):
    help = (
        "Синхронизирует события дней рождений всех сотрудников "
        "с django-scheduler"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать действия без выполнения изменений",
        )

    def handle(self, *args, **options):
        dry_run = options.get("dry_run", False)

        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "DRY-RUN режим: изменения не будут применены"
                )
            )

        self.stdout.write("Запуск синхронизации дней рождений...")

        try:
            with transaction.atomic():
                result = BulkSyncBirthdaysService.execute({})

                if dry_run:
                    # Откатываем транзакцию в dry-run режиме
                    transaction.set_rollback(True)

                self._print_results(result)

                if dry_run:
                    self.stdout.write(
                        self.style.WARNING(
                            "\nИзменения НЕ применены (dry-run режим)"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            "\n✅ Синхронизация завершена успешно!"
                        )
                    )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"\n❌ Ошибка при синхронизации: {e}")
            )
            raise

    def _print_results(self, result):
        """Выводит результаты синхронизации."""
        self.stdout.write("\n" + "=" * 60)
        self.stdout.write("РЕЗУЛЬТАТЫ СИНХРОНИЗАЦИИ:")
        self.stdout.write("=" * 60)

        self.stdout.write(f"Обработано сотрудников: {result['total']}")
        self.stdout.write(
            self.style.SUCCESS(f"  ✓ Создано событий: {result['created']}")
        )
        self.stdout.write(
            self.style.SUCCESS(f"  ✓ Обновлено событий: {result['updated']}")
        )
        self.stdout.write(
            self.style.SUCCESS(f"  ✓ Удалено устаревших событий: {result['deleted']}")
        )

        if result["skipped"] > 0:
            self.stdout.write(
                self.style.WARNING(f"  ⚠ Пропущено: {result['skipped']}")
            )

        if result["errors"]:
            self.stdout.write(
                self.style.ERROR(f"\n  ✗ Ошибок: {len(result['errors'])}")
            )
            for error in result["errors"][:5]:  # Показать первые 5 ошибок
                self.stdout.write(
                    self.style.ERROR(
                        f"    - Employee ID {error['employee_id']}: "
                        f"{error['error']}"
                    )
                )

            if len(result["errors"]) > 5:
                self.stdout.write(
                    self.style.ERROR(
                        f"    ... и еще {len(result['errors']) - 5} ошибок"
                    )
                )
