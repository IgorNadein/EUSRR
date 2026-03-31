"""Management command для синхронизации Django pk в LDAP employeeNumber.

Записывает id существующих в БД пользователей в атрибут employeeNumber
соответствующих записей Active Directory.
"""

from __future__ import annotations

import logging
from typing import Optional

from django.conf import settings
from django.core.management.base import BaseCommand

from employees.models import Employee, LdapSyncState
from employees.ldap.orm_models import LdapUser

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Записывает Django pk пользователей в LDAP атрибут employeeNumber."""

    help = (
        "Синхронизирует Django pk сотрудников в LDAP employeeNumber. "
        "По умолчанию dry-run, для применения используйте --no-dry-run."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=True,
            help="Сухой прогон без изменений (по умолчанию).",
        )
        parser.add_argument(
            "--no-dry-run",
            action="store_false",
            dest="dry_run",
            help="Применить изменения в LDAP.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Перезаписать employeeNumber даже если уже заполнен.",
        )
        parser.add_argument(
            "--user-id",
            type=int,
            default=None,
            help="Синхронизировать только конкретного пользователя по id.",
        )

    def handle(self, *args, **options) -> None:
        dry_run: bool = options["dry_run"]
        force: bool = options["force"]
        user_id: Optional[int] = options["user_id"]
        verbose: int = options.get("verbosity", 1)

        employee_id_attr = getattr(
            settings, "LDAP_EMPLOYEE_ID_ATTR", "employeeNumber"
        )

        if dry_run:
            self.stdout.write(
                self.style.WARNING("=== DRY-RUN режим (изменения НЕ применяются) ===")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS("=== ПРИМЕНЕНИЕ изменений в LDAP ===")
            )

        # Собираем пользователей с DN в LdapSyncState
        sync_states = LdapSyncState.objects.filter(
            model="employee",
            ldap_dn__isnull=False,
        ).exclude(ldap_dn="")

        if user_id:
            sync_states = sync_states.filter(object_pk=user_id)

        if not sync_states.exists():
            self.stdout.write(self.style.WARNING("Нет пользователей с LDAP DN."))
            return

        self.stdout.write(f"Найдено записей LdapSyncState: {sync_states.count()}")

        updated = 0
        skipped_already_set = 0
        skipped_no_employee = 0
        errors = 0

        for state in sync_states:
            dn = state.ldap_dn
            pk = state.object_pk

            # Проверяем что Employee существует
            try:
                employee = Employee.objects.get(pk=pk)
            except Employee.DoesNotExist:
                if verbose:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  [SKIP] pk={pk}: Employee не найден в БД"
                        )
                    )
                skipped_no_employee += 1
                continue

            # Читаем текущее значение employeeNumber через ORM
            try:
                ldap_user = LdapUser.objects.get(dn=dn)
                current_value = ldap_user.employee_number or None
            except LdapUser.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f"  [ERROR] pk={pk}, DN={dn}: не найден в LDAP"
                    )
                )
                errors += 1
                continue
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(
                        f"  [ERROR] pk={pk}, DN={dn}: не удалось прочитать — {e}"
                    )
                )
                errors += 1
                continue

            # Проверяем нужно ли обновлять
            expected_value = str(pk)

            if current_value == expected_value:
                if verbose > 1:
                    self.stdout.write(
                        f"  [OK] pk={pk}: уже установлено {employee_id_attr}={current_value}")
                skipped_already_set += 1
                continue

            if current_value and not force:
                if verbose:
                    self.stdout.write(
                        self.style.WARNING(
                            f"  [SKIP] pk={pk}: {employee_id_attr}={current_value} "
                            f"(отличается от pk, используйте --force)"
                        )
                    )
                skipped_already_set += 1
                continue

            # Записываем через ORM
            action = "UPDATE" if current_value else "SET"
            if verbose or dry_run:
                email = employee.email or "(no email)"
                self.stdout.write(
                    f"  [{action}] pk={pk}, email={email}, DN={dn}: "
                    f"{employee_id_attr}={current_value!r} -> {expected_value!r}"
                )

            if not dry_run:
                try:
                    ldap_user.employee_number = expected_value
                    ldap_user.save()
                    updated += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"  [ERROR] pk={pk}: не удалось записать — {e}"
                        )
                    )
                    errors += 1
            else:
                updated += 1

        # Итоги
        self.stdout.write("")
        self.stdout.write("=" * 50)

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS(f"Будет обновлено: {updated}")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(f"Обновлено: {updated}")
            )

        self.stdout.write(f"Пропущено (уже установлено): {skipped_already_set}")
        self.stdout.write(f"Пропущено (нет Employee): {skipped_no_employee}")

        if errors:
            self.stdout.write(
                self.style.ERROR(f"Ошибок: {errors}")
            )

        if dry_run and updated > 0:
            self.stdout.write("")
            self.stdout.write(
                self.style.WARNING(
                    "Для применения изменений запустите с --no-dry-run"
                )
            )
