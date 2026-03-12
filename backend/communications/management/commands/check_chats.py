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
            '--fix',
            action='store_true',
            help='Исправить все чаты с некорректными типами (заменить на group)',
        )
        parser.add_argument(
            '--change-type',
            nargs=2,
            metavar=('CHAT_ID', 'NEW_TYPE'),
            help='Изменить тип конкретного чата (например: --change-type 6 group)',
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
            '--stats',
            action='store_true',
            help='Показать статистику чатов по типам',
        )
        parser.add_argument(
            '--list-type',
            type=str,
            metavar='TYPE',
            help='Показать все чаты указанного типа (например: private)',
        )
        parser.add_argument(
            '--target-type',
            type=str,
            default='group',
            choices=VALID_TYPES,
            help='Целевой тип для исправления (по умолчанию: group)',
        )
        parser.add_argument(
            '--no-confirm',
            action='store_true',
            help='Не запрашивать подтверждение при удалении/изменении',
        )

    def handle(self, *args, **options):
        if options['stats']:
            self.show_stats()
        elif options['list_type']:
            self.list_chats_by_type(options['list_type'])
        elif options['find']:
            self.find_invalid_chats()
        elif options['check']:
            self.check_chat(options['check'])
        elif options['fix']:
            self.fix_invalid_chats(
                target_type=options['target_type'],
                no_confirm=options['no_confirm']
            )
        elif options['change_type']:
            chat_id = int(options['change_type'][0])
            new_type = options['change_type'][1]
            self.change_chat_type(chat_id, new_type, no_confirm=options['no_confirm'])
        elif options['cleanup']:
            self.cleanup_invalid_chats(no_confirm=options['no_confirm'])
        elif options['delete']:
            self.delete_chat(options['delete'], no_confirm=options['no_confirm'])
        else:
            self.stdout.write(self.style.ERROR('Укажите действие: --stats, --list-type, --find, --check, --fix, --change-type, --cleanup или --delete'))
            self.stdout.write('Используйте --help для справки')

    def show_stats(self):
        """Показывает статистику чатов по типам"""
        from django.db.models import Count
        
        total_chats = Chat.objects.count()
        self.stdout.write(self.style.SUCCESS(f'📊 Статистика чатов (всего: {total_chats})\n'))
        
        # Статистика по типам
        stats = Chat.objects.values('type').annotate(count=Count('id')).order_by('-count')
        
        type_labels = {
            'private': 'Личные диалоги',
            'group': 'Групповые чаты',
            'channel': 'Каналы',
            'announcement': 'Объявления',
            'global': 'Глобальные',
            'comments': 'Комментарии',
        }
        
        valid_count = 0
        invalid_count = 0
        
        for stat in stats:
            chat_type = stat['type']
            count = stat['count']
            label = type_labels.get(chat_type, f'❌ {chat_type} (некорректный)')
            
            if chat_type in VALID_TYPES:
                valid_count += count
                self.stdout.write(f'  ✅ {label}: {count}')
            else:
                invalid_count += count
                self.stdout.write(self.style.ERROR(f'  ❌ {label}: {count}'))
        
        if invalid_count > 0:
            self.stdout.write(self.style.WARNING(f'\n⚠️  Найдено {invalid_count} чатов с некорректными типами'))
            self.stdout.write(self.style.NOTICE('Для исправления используйте: python manage.py check_chats --fix'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n✅ Все {valid_count} чатов имеют корректные типы'))

    def list_chats_by_type(self, chat_type):
        """Показывает все чаты указанного типа"""
        chats = Chat.objects.filter(type=chat_type).order_by('-created_at')
        
        if not chats.exists():
            self.stdout.write(self.style.WARNING(f'⚠️  Чатов типа "{chat_type}" не найдено'))
            return
        
        count = chats.count()
        type_label = {
            'private': 'Личных диалогов',
            'group': 'Групповых чатов',
            'channel': 'Каналов',
            'announcement': 'Объявлений',
            'global': 'Глобальных чатов',
            'comments': 'Чатов комментариев',
        }.get(chat_type, f'Чатов типа "{chat_type}"')
        
        self.stdout.write(self.style.SUCCESS(f'📋 {type_label}: {count}\n'))
        
        for chat in chats:
            participants_count = chat.participants.count()
            messages_count = chat.messages.count() if hasattr(chat, 'messages') else 'N/A'
            
            self.stdout.write(f'ID {chat.id}: {chat.name}')
            self.stdout.write(f'  Участников: {participants_count}')
            self.stdout.write(f'  Сообщений: {messages_count}')
            self.stdout.write(f'  Создан: {chat.created_at.strftime("%Y-%m-%d %H:%M")}')
            if hasattr(chat, 'last_message') and chat.last_message:
                last_msg_date = getattr(chat.last_message, 'created_at', None)
                if last_msg_date:
                    self.stdout.write(f'  Последнее сообщение: {last_msg_date.strftime("%Y-%m-%d %H:%M")}')
            self.stdout.write('')
        
        self.stdout.write(self.style.SUCCESS(f'Всего найдено: {count} чатов'))

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
            self.stdout.write(self.style.NOTICE(f'Для изменения типа используйте: python manage.py check_chats --change-type {chat_id} group'))
            self.stdout.write(self.style.NOTICE(f'Для удаления используйте: python manage.py check_chats --delete {chat_id}'))
        else:
            self.stdout.write(self.style.SUCCESS(f'\n✅ Чат в порядке, тип корректен'))

    def fix_invalid_chats(self, target_type='group', no_confirm=False):
        """Исправляет все чаты с некорректными типами"""
        invalid_chats = Chat.objects.exclude(type__in=VALID_TYPES)
        
        if not invalid_chats.exists():
            self.stdout.write(self.style.SUCCESS('✅ Все чаты имеют корректные типы'))
            return
        
        count = invalid_chats.count()
        self.stdout.write(self.style.WARNING(f'⚠️  Найдено {count} чатов с некорректными типами\n'))
        self.stdout.write(f'Чаты для исправления (будет установлен тип: {target_type}):')
        
        for chat in invalid_chats:
            self.stdout.write(f'  • ID {chat.id}: {chat.name} (текущий тип: {chat.type} → новый тип: {target_type})')
        
        if not no_confirm:
            confirm = input(f'\n⚠️  Изменить тип у {count} чатов на "{target_type}"? (yes/no): ')
            if confirm.lower() not in ['yes', 'y', 'да']:
                self.stdout.write(self.style.ERROR('❌ Отменено'))
                return
        
        updated = invalid_chats.update(type=target_type)
        self.stdout.write(self.style.SUCCESS(f'\n✅ Успешно обновлено {updated} чатов'))
        self.stdout.write(f'Всем чатам установлен тип: {target_type}')

    def change_chat_type(self, chat_id, new_type, no_confirm=False):
        """Изменяет тип конкретного чата"""
        try:
            chat = Chat.objects.get(id=chat_id)
        except Chat.DoesNotExist:
            raise CommandError(f'❌ Чат с ID {chat_id} не найден')
        
        if new_type not in VALID_TYPES:
            raise CommandError(
                f'❌ Некорректный тип: {new_type}\n'
                f'Допустимые типы: {", ".join(VALID_TYPES)}'
            )
        
        self.stdout.write(f'Изменение типа чата ID {chat_id}:')
        self.stdout.write(f'  Название: {chat.name}')
        self.stdout.write(f'  Текущий тип: {chat.type}')
        self.stdout.write(f'  Новый тип: {new_type}')
        self.stdout.write(f'  Участников: {chat.participants.count()}')
        
        if chat.type == new_type:
            self.stdout.write(self.style.WARNING(f'\n⚠️  Чат уже имеет тип "{new_type}"'))
            return
        
        if not no_confirm:
            confirm = input(f'\n⚠️  Изменить тип с "{chat.type}" на "{new_type}"? (yes/no): ')
            if confirm.lower() not in ['yes', 'y', 'да']:
                self.stdout.write(self.style.ERROR('❌ Отменено'))
                return
        
        old_type = chat.type
        chat.type = new_type
        chat.save(update_fields=['type'])
        self.stdout.write(self.style.SUCCESS(f'\n✅ Тип чата "{chat.name}" изменен с "{old_type}" на "{new_type}"'))

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
