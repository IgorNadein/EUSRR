"""Management-команда для работы с очередью LDAP retry.

Примеры:
    # Показать статистику очереди
    python manage.py ldap_queue status

    # Повторить все pending-операции
    python manage.py ldap_queue retry

    # Повторить failed-операции (сбрасывает счётчик попыток)
    python manage.py ldap_queue retry --failed

    # Очистить completed-записи старше 7 дней
    python manage.py ldap_queue cleanup --days 7
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = "Управление очередью отложенных LDAP-операций (retry)"

    def add_arguments(self, parser):
        subparsers = parser.add_subparsers(dest="action")

        subparsers.add_parser("status", help="Показать статистику очереди")

        retry_parser = subparsers.add_parser(
            "retry", help="Запустить повтор операций"
        )
        retry_parser.add_argument(
            "--failed",
            action="store_true",
            help="Включить failed-записи (сбросить счётчик попыток)",
        )

        cleanup_parser = subparsers.add_parser(
            "cleanup", help="Очистить старые записи"
        )
        cleanup_parser.add_argument(
            "--days",
            type=int,
            default=30,
            help=(
                "Удалять completed/failed записи старше N дней "
                "(по умолчанию 30)"
            ),
        )

    def handle(self, *args, **options):
        action = options.get("action")
        if action == "status":
            self._status()
        elif action == "retry":
            self._retry(include_failed=options.get("failed", False))
        elif action == "cleanup":
            self._cleanup(days=options["days"])
        else:
            self.stderr.write("Укажите действие: status, retry, cleanup")

    def _status(self):
        from employees.models import LdapSyncQueue

        total = LdapSyncQueue.objects.count()
        by_status = {}
        for s in LdapSyncQueue.Status:
            count = LdapSyncQueue.objects.filter(status=s.value).count()
            by_status[s.label] = count

        self.stdout.write(f"\nОчередь LDAP sync: {total} записей")
        for label, count in by_status.items():
            self.stdout.write(f"  {label}: {count}")

        # Последние 5 failed
        failed = LdapSyncQueue.objects.filter(
            status=LdapSyncQueue.Status.FAILED,
        ).order_by("-updated_at")[:5]
        if failed:
            self.stdout.write("\nПоследние ошибки:")
            for item in failed:
                self.stdout.write(
                    f"  [{item.pk}] {item.operation} "
                    f"{item.model_name}:{item.object_pk} "
                    f"попыток: {item.attempts}/{item.max_attempts} "
                    f"— {item.last_error[:100]}"
                )

    def _retry(self, include_failed: bool):
        from employees.models import LdapSyncQueue
        from employees.tasks import process_ldap_queue_item

        qs = LdapSyncQueue.objects.filter(status=LdapSyncQueue.Status.PENDING)

        if include_failed:
            failed_qs = LdapSyncQueue.objects.filter(
                status=LdapSyncQueue.Status.FAILED
            )
            reset_count = failed_qs.count()
            # Сбрасываем failed → pending
            failed_qs.update(
                status=LdapSyncQueue.Status.PENDING,
                attempts=0,
                next_retry_at=None,
            )
            self.stdout.write(
                f"Сброшено {reset_count} failed-записей → pending"
            )
            qs = LdapSyncQueue.objects.filter(
                status=LdapSyncQueue.Status.PENDING
            )

        pks = list(qs.values_list("pk", flat=True))
        for pk in pks:
            process_ldap_queue_item.delay(pk)

        self.stdout.write(
            self.style.SUCCESS(f"Запущено {len(pks)} задач в Celery")
        )

    def _cleanup(self, days: int):
        from employees.models import LdapSyncQueue

        cutoff = timezone.now() - timedelta(days=days)
        deleted, _ = LdapSyncQueue.objects.filter(
            status__in=[
                LdapSyncQueue.Status.COMPLETED,
                LdapSyncQueue.Status.FAILED,
            ],
            updated_at__lt=cutoff,
        ).delete()
        self.stdout.write(
            self.style.SUCCESS(f"Удалено {deleted} старых записей")
        )
