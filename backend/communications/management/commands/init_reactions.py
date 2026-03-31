# backend/communications/management/commands/init_reactions.py
"""Команда для инициализации дефолтных реакций"""

from django.core.management.base import BaseCommand
from communications.models import AvailableReaction


class Command(BaseCommand):
    help = 'Инициализирует дефолтные реакции в БД'

    def handle(self, *args, **options):
        default_reactions = [
            ('👍', 'Лайк', 1),
            ('❤️', 'Сердце', 2),
            ('😂', 'Смех', 3),
            ('😮', 'Удивление', 4),
            ('😢', 'Грусть', 5),
            ('🙏', 'Спасибо', 6),
            ('👏', 'Аплодисменты', 7),
            ('🔥', 'Огонь', 8),
        ]

        created_count = 0
        updated_count = 0

        for emoji, name, order in default_reactions:
            reaction, created = AvailableReaction.objects.get_or_create(
                emoji=emoji,
                defaults={
                    'name': name,
                    'order': order,
                    'is_active': True
                }
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f'✓ Создана реакция: {emoji} {name}'
                    )
                )
            else:
                # Обновляем порядок если изменился
                if reaction.order != order:
                    reaction.order = order
                    reaction.save(update_fields=['order'])
                    updated_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f'↻ Обновлён порядок: {emoji} {name}'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.NOTICE(
                            f'- Уже существует: {emoji} {name}'
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f'\nГотово! Создано: {created_count}, '
                f'Обновлено: {updated_count}'
            )
        )
