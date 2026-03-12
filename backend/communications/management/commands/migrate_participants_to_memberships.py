"""
Data migration: перенос участников из Chat.participants в ChatMembership

Использование:
    .venv/Scripts/python manage.py migrate_participants_to_memberships

Что делает:
1. Находит все чаты с participants
2. Для каждого participant создает ChatMembership с is_active=True
3. Сохраняет роли (member для обычных участников)
4. Не удаляет participants (только помечает как DEPRECATED)

ВАЖНО: Запустить ДО удаления поля participants!
"""

from django.core.management.base import BaseCommand
from django.db import transaction
from communications.models import Chat, ChatMembership


class Command(BaseCommand):
    help = 'Мигрирует участников из Chat.participants в ChatMembership'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать что будет сделано, без изменения БД',
        )
        parser.add_argument(
            '--verbose',
            action='store_true',
            help='Показывать детали для каждого чата',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        verbose = options['verbose']
        
        self.stdout.write(
            self.style.WARNING('=' * 70)
        )
        self.stdout.write(
            self.style.WARNING('МИГРАЦИЯ: Chat.participants → ChatMembership')
        )
        self.stdout.write(
            self.style.WARNING('=' * 70)
        )
        
        if dry_run:
            self.stdout.write(
                self.style.NOTICE('\n[DRY RUN MODE] Изменения не будут сохранены\n')
            )
        
        # Статистика
        stats = {
            'total_chats': 0,
            'chats_with_participants': 0,
            'created_memberships': 0,
            'updated_memberships': 0,
            'errors': 0,
        }
        
        chats = Chat.objects.all().prefetch_related('participants', 'memberships')
        stats['total_chats'] = chats.count()
        
        self.stdout.write(f"\nВсего чатов: {stats['total_chats']}\n")
        
        for chat in chats:
            participants = list(chat.participants.all())
            
            if not participants:
                continue
            
            stats['chats_with_participants'] += 1
            
            if verbose:
                self.stdout.write(
                    f"\nЧат #{chat.id} ({chat.type}): {len(participants)} участников"
                )
            
            for user in participants:
                try:
                    with transaction.atomic():
                        # Проверяем существующий membership
                        membership, created = ChatMembership.objects.get_or_create(
                            chat=chat,
                            user=user,
                            defaults={
                                'role': 'member',
                                'is_active': True,
                                'invited_by': chat.created_by,
                            }
                        )
                        
                        if created:
                            stats['created_memberships'] += 1
                            if verbose:
                                self.stdout.write(
                                    f"  ✓ Создан membership для {user.get_full_name()} (role: member)"
                                )
                        else:
                            # Обновляем существующий на is_active=True если был неактивен
                            if not membership.is_active:
                                if not dry_run:
                                    membership.is_active = True
                                    membership.left_at = None
                                    membership.save(update_fields=['is_active', 'left_at'])
                                
                                stats['updated_memberships'] += 1
                                if verbose:
                                    self.stdout.write(
                                        f"  ↻ Восстановлен membership для {user.get_full_name()}"
                                    )
                            else:
                                if verbose:
                                    self.stdout.write(
                                        f"  - Membership для {user.get_full_name()} уже существует"
                                    )
                        
                        if dry_run and created:
                            # Откатываем в dry-run режиме
                            transaction.set_rollback(True)
                
                except Exception as e:
                    stats['errors'] += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"  ✗ Ошибка для {user.get_full_name()}: {e}"
                        )
                    )
        
        # Итоговая статистика
        self.stdout.write('\n' + '=' * 70)
        self.stdout.write(self.style.SUCCESS('\nРЕЗУЛЬТАТЫ МИГРАЦИИ:'))
        self.stdout.write('=' * 70 + '\n')
        
        self.stdout.write(f"Всего чатов: {stats['total_chats']}")
        self.stdout.write(f"Чатов с participants: {stats['chats_with_participants']}")
        self.stdout.write(
            self.style.SUCCESS(
                f"Создано memberships: {stats['created_memberships']}"
            )
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Восстановлено memberships: {stats['updated_memberships']}"
            )
        )
        
        if stats['errors'] > 0:
            self.stdout.write(
                self.style.ERROR(f"Ошибок: {stats['errors']}")
            )
        
        self.stdout.write('\n' + '=' * 70)
        
        if dry_run:
            self.stdout.write(
                self.style.NOTICE(
                    '\n[DRY RUN] Для применения изменений запустите без --dry-run\n'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    '\n✓ Миграция завершена успешно!\n'
                )
            )
            self.stdout.write(
                self.style.WARNING(
                    'ВНИМАНИЕ: Поле Chat.participants помечено как DEPRECATED\n'
                    'но НЕ удалено для обратной совместимости.\n'
                    'После проверки работы системы можно будет удалить это поле.\n'
                )
            )
