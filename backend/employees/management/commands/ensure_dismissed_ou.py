"""Management команда для создания OU=Dismissed в Active Directory.

Эта команда гарантирует наличие OU=Dismissed для хранения уволенных сотрудников.
Выполняется автоматически при активации LDAP или вручную администратором.
"""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    """Создаёт OU=Dismissed в Active Directory, если она отсутствует."""

    help = "Создаёт OU=Dismissed для хранения уволенных сотрудников в AD"

    def add_arguments(self, parser):
        """Добавляет аргументы командной строки."""
        parser.add_argument(
            "--force",
            action="store_true",
            help="Пересоздать OU даже если она уже существует (ОСТОРОЖНО!)",
        )
        parser.add_argument(
            "--description",
            type=str,
            default="Уволенные сотрудники",
            help="Описание для OU (по умолчанию: 'Уволенные сотрудники')",
        )

    def handle(self, *args, **options):
        """Выполняет создание OU=Dismissed."""
        ldap_enabled = getattr(settings, "LDAP_ENABLED", False)
        if not ldap_enabled:
            self.stdout.write(
                self.style.WARNING(
                    "LDAP отключен (LDAP_ENABLED=False). "
                    "Команда выполнена без изменений."
                )
            )
            return

        dismissed_base = getattr(settings, "LDAP_DISMISSED_BASE", None)
        if not dismissed_base:
            raise CommandError(
                "LDAP_DISMISSED_BASE не настроен в settings.py. "
                "Добавьте настройку и повторите команду."
            )

        force = options["force"]
        description = options["description"]

        self.stdout.write(f"Целевая OU: {dismissed_base}")
        self.stdout.write(f"Описание: {description}")
        self.stdout.write("")

        try:
            from employees.ldap.infrastructure.connections import _ldap

            with _ldap() as conn:
                # Проверяем существование OU
                from ldap3 import BASE

                ok = conn.search(
                    dismissed_base,
                    "(objectClass=organizationalUnit)",
                    search_scope=BASE,
                    attributes=["description"],
                )

                if ok and conn.entries:
                    if not force:
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"✓ OU=Dismissed уже существует: {dismissed_base}"
                            )
                        )
                        entry = conn.entries[0]
                        current_desc = (
                            entry.description.value
                            if hasattr(entry, "description")
                            else None
                        )
                        if current_desc:
                            self.stdout.write(
                                f"  Текущее описание: {current_desc}"
                            )
                        self.stdout.write("")
                        self.stdout.write(
                            "Используйте --force для пересоздания (ОСТОРОЖНО!)"
                        )
                        return
                    else:
                        # Force mode: удаляем и создаём заново
                        self.stdout.write(
                            self.style.WARNING(
                                "⚠ Режим --force: удаление существующей OU..."
                            )
                        )
                        # Проверяем, есть ли дочерние объекты
                        check = conn.search(
                            dismissed_base,
                            "(objectClass=*)",
                            attributes=["distinguishedName"],
                        )
                        if check and len(conn.entries) > 1:
                            raise CommandError(
                                f"OU содержит {len(conn.entries) - 1} объектов. "
                                "Удалите их вручную или используйте другой метод."
                            )

                        ok = conn.delete(dismissed_base)
                        if not ok:
                            raise CommandError(
                                f"Не удалось удалить OU: {conn.result}"
                            )
                        self.stdout.write(
                            self.style.SUCCESS("✓ Существующая OU удалена")
                        )

                # Создаём новую OU
                self.stdout.write("Создание OU=Dismissed...")
                ok = conn.add(
                    dismissed_base,
                    ["top", "organizationalUnit"],
                    {"description": description},
                )
                if not ok:
                    raise CommandError(
                        f"Не удалось создать OU: {conn.result}"
                    )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ OU=Dismissed успешно создана: {dismissed_base}"
                    )
                )
                self.stdout.write(f"  Описание: {description}")
                self.stdout.write("")
                self.stdout.write(
                    "Теперь уволенные сотрудники будут автоматически "
                    "перемещаться в эту OU."
                )

        except ImportError as e:
            raise CommandError(
                f"Не удалось импортировать LDAP модули: {e}"
            ) from e
        except Exception as e:
            raise CommandError(f"Ошибка при работе с LDAP: {e}") from e
