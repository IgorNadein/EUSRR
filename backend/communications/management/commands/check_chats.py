"""
Management команда для проверки и очистки чатов с некорректными типами.

Использование:
    # Найти все чаты с некорректными типами
    python manage.py check_chats --find
    
    # Проверить конкретный чат
    python manage.py check_chats --check 6
    
    # Удалить все чаты с некорректными типами
    python manage.py check_chats --cleanup
    
    # Удалить конкретный чат
    python manage.py check_chats --delete 6
"""

from django.core.management.base import BaseCommand, CommandError
from communications.models import Chat

VALID_TYPES = ["private", "group", "channel", "announcement", "global", "comments"]


class Command(BaseCommand):
    help = 'Проверка и очистка чатов с некорректными типами'

    def add_arguments(self, parser):
        parser.add_argument(
            '--find',
            action='store_true',
            help='Найти все чаты с некорректными типами',
        )
        parser.add_argument(
            '--check',
            type=int,
            metavar='CHAT_ID',
            help='Проверить конкретный чат по ID',
        )
        parser.add_argument(
            '--cleanup',
            action='store_true',
            help='Удалить все чаты с некорректными типами',
        )
        parser.add_argument(
            '--delete',
            type=int,
            metavar='CHAT_ID',
            help='Удалить конкретный чат по ID',
        )
        parser.add_argument(
            '--no-confirm',
            action='store_true',
            help='Не запрашивать подтверждение при удалении',
        )

    def handle(self, *args, **options):
        if options['find']:
            self.find_invalid_chats()
        elif options['check']:
            self.check_chat(options['check'])
        elif options['cleanup']:
            self.cleanup_invalid_chats(no_confirm=options['no_confirm'])
        elif options['delete']:
            self.delete_chat(options['delete'], no_confirm=options['no_confirm'])
        else:
            self.stdout.write(self.style.ERROR('Укажите действие: --find, --check, --cleanup или --delete'))
            self.stdout.write('Используйте --help для справки')

    def find_invalid_chats(self):
        """Находит все чаты с некорректными типами"""
        invalid_chats = Chat.objects.exclude(type__in=VALID_TYPES)
        
        if not invalid_chats.exists():
            self.stdout.write(self.style.SUCCESS('✅ Все чаты имеют корректные типы'))
            return
        
        count = invalid_chats.count()
        self.stdout.write(self.style.WARNING(f'⚠️  Найдено {count} чатов с некорректными типами:\n'))
        
        for chat in invalid_chats:
            self.stdout.write(f'ID {chat.id}:')
            self.stdout.write(f'  Название: {chat.name}')
            self.stdout.write(f'  Тип: {chat.type}')
            self.stdout.write(f'  Участников: {chat.participants.count()}')
            self.stdout.write(f'  Создан: {chat.created_at}')
            self.stdout.write('')
            
        self.stdout.write(self.style.WARNING(f'Всего найдено: {count} чатов'))
        self.stdout.write(self.style.NOTICE('Для удаления используйте: python manage.py check_chats --cleanup'))

    def check_chat(self, chat_id):
        """Проверяет конкретный чат"""
        try:
            chat = Chat.objects.get(id=chat_id)
        except Chat.DoesNotExist:
            raise CommandError(f'❌ Чат с ID {chat_id} не найден')
        
        self.stdout.write(f'Чат ID {chat_id}:')
        self.stdout.write(f'  Название: {chat.name}')
        self.stdout.write(f'  Тип: {chat.type}')
        self.stdout.write(f'  Участников: {chat.participants.count()}')
        self.stdout.write(f'  Создан: {chat.created_at}')
        
        if chat.type not in VALID_TYPES:
            self.stdout.write(self.style.ERROR(f'\n⚠️  Чат имеет некорректный тип: {chat.type}'))
            self.stdout.write(self.style.NOTICE(f'Допустимые типы: {", ".join(VALID_TYPES)}'))
            self.stdout.write(self.style.NOTICE(f'Для удаления используйте: python manage.py check_chats --delete {chat_id}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n✅ Чат в порядке, тип корректен'))

    def cleanup_invalid_chats(self, no_confirm=False):
        """Удаляет все чаты с некорректными типами"""
        invalid_chats = Chat.objects.exclude(type__in=VALID_TYPES)
        
        if not invalid_chats.exists():
            self.stdout.write(self.style.SUCCESS('✅ Все чаты имеют корректные типы'))
            return
        
        count = invalid_chats.count()
        self.stdout.write(self.style.WARNING(f'⚠️  Найдено {count} чатов с некорректными типами\n'))
        self.stdout.write('Чаты для удаления:')
        
        for chat in invalid_chats:
            self.stdout.write(f'  • ID {chat.id}: {chat.name} (тип: {chat.type})')
        
        if not no_confirm:
            confirm = input(f'\n⚠️  Удалить {count} чатов? (yes/no): ')
            if confirm.lower() not in ['yes', 'y', 'да']:
                self.stdout.write(self.style.ERROR('❌ Отменено'))
                return
        
        deleted, details = invalid_chats.delete()
        self.stdout.write(self.style.SUCCESS(f'\n✅ Успешно удалено {deleted} объектов'))
        
        # Показываем детали удаления
        if details:
            self.stdout.write('\nУдалено объектов по типам:')
            for model, count in details.items():
                self.stdout.write(f'  • {model}: {count}')

    def delete_chat(self, chat_id, no_confirm=False):
        """Удаляет конкретный чат"""
        try:
            chat = Chat.objects.get(id=chat_id)
        except Chat.DoesNotExist:
            raise CommandError(f'❌ Чат с ID {chat_id} не найден')
        
        self.stdout.write(f'Удаление чата ID {chat_id}:')
        self.stdout.write(f'  Название: {chat.name}')
        self.stdout.write(f'  Тип: {chat.type}')
        self.stdout.write(f'  Участников: {chat.participants.count()}')
        
        if not no_confirm:
            confirm = input('\n⚠️  Подтвердите удаление (yes/no): ')
            if confirm.lower() not in ['yes', 'y', 'да']:
                self.stdout.write(self.style.ERROR('❌ Отменено'))
                return
        
        chat_name = chat.name
        chat.delete()
        self.stdout.write(self.style.SUCCESS(f'\n✅ Чат "{chat_name}" (ID {chat_id}) успешно удален'))
