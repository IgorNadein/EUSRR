from __future__ import annotations


from django.conf import settings
from django.core.management.base import BaseCommand
from employees.ldap.config import SyncConfig
from employees.ldap.services.sync_service import (
    SyncService,
)


class Command(BaseCommand):
    """Зеркальный импорт из LDAP в Django:
    отделы (OU + managedBy) и пользователи.

    На этой итерации работает только направление LDAP -> Django.
    По умолчанию выполняется dry-run (ничего не меняет);
    применить изменения можно флагом --no-dry-run.
    """

    def add_arguments(self, parser) -> None:
        """Добавляет аргументы командной строки."""
        parser.add_argument(
            "--mode",
            choices=["ldap", "django"],
            default="ldap",
            help="Источник истины.",
        )
        parser.add_argument(
            "--scope",
            choices=["all", "departments", "users", "groups"],
            default="all",
            help="Область синхронизации.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=True,
            help="Сухой прогон (по умолчанию включён).",
        )
        parser.add_argument(
            "--no-dry-run",
            action="store_false",
            dest="dry_run",
            help="Отключить dry-run (изменения будут применены).",
        )
        parser.add_argument(
            "--max-changes",
            type=int,
            default=1000,
            help="Лимит изменений за прогон (зарезервировано).",
        )
        parser.add_argument(
            "--show-changes",
            action="store_true",
            help=(
                "Показать подробный список изменений "
                "(создание/обновление/удаление)."
            ),
        )

    def handle(self, *args, **opts) -> None:
        """Точка входа команды.

        Выполняет зеркальный импорт LDAP -> Django.
        """
        mode: str = opts["mode"]
        scope: str = opts["scope"]
        dry_run: bool = opts["dry_run"]
        max_changes: int = opts["max_changes"]
        cfg = SyncConfig(
            mode=mode,
            scope=scope,
            dry_run=dry_run,
            max_changes=max_changes,
            users_base_dn=getattr(settings, "LDAP_USERS_BASE", ""),
            departments_base_dn=getattr(settings, "LDAP_DEPARTMENTS_BASE", ""),
            groups_base_dn=getattr(settings, "LDAP_GROUPS_BASE", ""),
            show_changes=opts["show_changes"],
        )

        if mode == "ldap":
            total_changes = 0
            svc = SyncService()

            # Отделы
            if scope in ("all", "departments"):
                self.stdout.write(
                    self.style.NOTICE("[LDAP] Импорт отделов и managedBy...")
                )
                created_d, updated_d, deleted_d = svc.import_departments(cfg)
                total_changes += created_d + updated_d + deleted_d
                deleted_label = "к удалению" if cfg.dry_run else "удалено"
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[LDAP] Отделы: создано={created_d}, "
                        f"обновлено={updated_d}, {deleted_label}={deleted_d}"
                    )
                )

            # Пользователи
            if scope in ("all", "users"):
                self.stdout.write(
                    self.style.NOTICE("[LDAP] Импорт пользователей...")
                )
                created_u, updated_u, deleted_u = svc.import_users(cfg)
                total_changes += created_u + updated_u + deleted_u
                deleted_label = "к удалению" if cfg.dry_run else "удалено"
                self.stdout.write(
                    self.style.SUCCESS(
                        f"[LDAP] Пользователи: создано={created_u}, "
                        f"обновлено={updated_u}, {deleted_label}={deleted_u}"
                    )
                )

            self.stdout.write(
                self.style.SUCCESS(
                    "[LDAP] Завершено. Итого изменений: "
                    f"{total_changes} (dry_run={dry_run})"
                )
            )
        elif mode == "django":
            self.stdout.write(
                self.style.NOTICE(
                    "[DJANGO] Write-back пользователей "
                    "(логины, MOVE, avatar, группы)..."
                )
            )
            svc = SyncService()
            logins_set, moved, avatars_set, groups_added, groups_removed = (
                svc.export_users(cfg)
            )
            self.stdout.write(
                self.style.SUCCESS(
                    f"[DJANGO] Выполнено. sAM/UPN={logins_set}, "
                    f"MOVE={moved}, avatar={avatars_set}, "
                    f"groups +{groups_added}/-{groups_removed} "
                    f"(dry_run={dry_run})"
                )
            )
