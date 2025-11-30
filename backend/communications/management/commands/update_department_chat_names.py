"""
Management command для обновления названий основных чатов отделов
"""
from django.core.management.base import BaseCommand
from communications.models import Chat


class Command(BaseCommand):
    help = 'Обновляет названия основных чатов отделов'

    def handle(self, *args, **options):
        # Находим все основные чаты отделов без названия
        chats = Chat.objects.filter(
            type='department',
            is_main=True
        ).select_related('department')

        updated = 0
        for chat in chats:
            if not chat.name or chat.name == '':
                old_name = chat.name or '(пусто)'
                chat.name = f"Основной чат {chat.department.name}"
                chat.save()
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Обновлен чат ID {chat.id}: '
                        f'"{old_name}" → "{chat.name}"'
                    )
                )
                updated += 1

        if updated == 0:
            self.stdout.write(
                self.style.WARNING('Нет чатов для обновления')
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'\n✓ Обновлено названий: {updated}'
                )
            )
