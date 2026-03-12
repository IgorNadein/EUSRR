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
            '--export',
            type=str,
            metavar='TYPE',
            help='Экспортировать чаты указанного типа в JSON файл',
        )
        parser.add_argument(
            '--output',
            type=str,
            default='chats_export.json',
            help='Путь к файлу для экспорта (по умолчанию: chats_export.json)',
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
        elif options['export']:
            self.export_chats(options['export'], options['output'])
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
            self.stdout.write(self.style.ERROR('Укажите действие: --stats, --export, --list-type, --find, --check, --fix, --change-type, --cleanup или --delete'))
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

    def export_chats(self, chat_type, output_file):
        """Экспортирует чаты указанного типа в JSON файл"""
        import json
        from django.core.serializers.json import DjangoJSONEncoder
        
        chats = Chat.objects.filter(type=chat_type).order_by('-created_at')
        
        if not chats.exists():
            self.stdout.write(self.style.WARNING(f'Chats of type "{chat_type}" not found'))
            return
        
        export_data = []
        for chat in chats:
            participants_list = []
            for p in chat.participants.all():
                participants_list.append({
                    'id': p.id,
                    'email': p.email,
                    'first_name': getattr(p, 'first_name', ''),
                    'last_name': getattr(p, 'last_name', ''),
                })
            
            chat_data = {
                'id': chat.id,
                'name': chat.name,
                'type': chat.type,
                'created_at': chat.created_at.isoformat() if chat.created_at else None,
                'participants_count': chat.participants.count(),
                'participants': participants_list,
                'messages_count': chat.messages.count() if hasattr(chat, 'messages') else 0,
            }
            
            if hasattr(chat, 'last_message') and chat.last_message:
                last_msg_date = getattr(chat.last_message, 'created_at', None)
                if last_msg_date:
                    chat_data['last_message_at'] = last_msg_date.isoformat()
            
            export_data.append(chat_data)
        
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'total': len(export_data),
                'type': chat_type,
                'exported_at': DjangoJSONEncoder().default(None),
                'chats': export_data
            }, f, ensure_ascii=False, indent=2, cls=DjangoJSONEncoder)
        
        self.stdout.write(self.style.SUCCESS(f'Exported {len(export_data)} chats to {output_file}'))
        self.stdout.write(f'Type: {chat_type}')
        self.stdout.write(f'File size: {len(json.dumps(export_data))} bytes')

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
            
            # Заголовок чата
            self.stdout.write(self.style.SUCCESS(f'═══ ID {chat.id}: {chat.name or "[без названия]"} ═══'))
            
            # Базовые поля
            self.stdout.write(f'  📌 Тип: {chat.type}')
            self.stdout.write(f'  📅 Создан: {chat.created_at.strftime("%Y-%m-%d %H:%M")}')
            
            # Создатель
            if chat.created_by:
                creator_name = f"{getattr(chat.created_by, 'last_name', '')} {getattr(chat.created_by, 'first_name', '')}".strip()
                self.stdout.write(f'  👤 Создатель: {creator_name or chat.created_by.email}')
            else:
                self.stdout.write(f'  👤 Создатель: [не указан]')
            
            # Критичные флаги
            flags = []
            if getattr(chat, 'is_blocked', False):
                flags.append('🚫 ЗАБЛОКИРОВАН')
            if getattr(chat, 'is_main', False):
                flags.append('⭐ ОСНОВНОЙ')
            if getattr(chat, 'include_all_users', False):
                flags.append('👥 ВСЕ ПОЛЬЗОВАТЕЛИ')
            
            if flags:
                self.stdout.write(f'  🚩 Флаги: {" | ".join(flags)}')
            
            # Контекстный объект
            if hasattr(chat, 'context_content_type') and chat.context_content_type:
                ctx = f"{chat.context_content_type.model}"
                if hasattr(chat, 'context_object_id') and chat.context_object_id:
                    ctx += f" (ID: {chat.context_object_id})"
                self.stdout.write(f'  🔗 Контекст: {ctx}')
            
            # Аватар
            if chat.avatar:
                self.stdout.write(f'  🖼️  Аватар: {chat.avatar.url if hasattr(chat.avatar, "url") else "есть"}')
            
            # Описание
            if chat.description:
                desc = chat.description[:60] + '...' if len(chat.description) > 60 else chat.description
                self.stdout.write(f'  📝 Описание: {desc}')
            
            # Участники
            self.stdout.write(f'  👥 Участников: {participants_count}')
            
            if participants_count > 0:
                participants = chat.participants.all()
                for p in participants:
                    full_name = f"{getattr(p, 'last_name', '')} {getattr(p, 'first_name', '')}".strip()
                    email = getattr(p, 'email', 'N/A')
                    user_id = p.id
                    
                    # Проверяем membership для детальной инфы
                    membership_info = ""
                    try:
                        from communications.models import ChatMembership
                        membership = ChatMembership.objects.filter(chat=chat, user=p).first()
                        if membership:
                            role_emoji = {'owner': '👑', 'admin': '🔴', 'moderator': '🟠', 'member': '🟢', 'guest': '⚪'}.get(membership.role, '❓')
                            membership_info = f" {role_emoji}{membership.role}"
                            if not membership.is_active:
                                membership_info += " [НЕАКТИВЕН]"
                    except:
                        pass
                    
                    if full_name:
                        self.stdout.write(f'      • ID:{user_id} {full_name} ({email}){membership_info}')
                    else:
                        self.stdout.write(f'      • ID:{user_id} {email}{membership_info}')
            
            # Сообщения
            self.stdout.write(f'  💬 Сообщений: {messages_count}')
            
            # Последнее сообщение
            if hasattr(chat, 'last_message') and chat.last_message:
                last_msg = chat.last_message
                last_msg_date = getattr(last_msg, 'created_at', None)
                if last_msg_date:
                    last_msg_preview = getattr(last_msg, 'content', '')[:50]
                    self.stdout.write(f'  💭 Последнее сообщение: {last_msg_date.strftime("%Y-%m-%d %H:%M")}')
                    if last_msg_preview:
                        self.stdout.write(f'      "{last_msg_preview}..."')
            
            # JSON поля
            if hasattr(chat, 'flags') and chat.flags:
                self.stdout.write(f'  🏴 Flags: {chat.flags}')
            
            if hasattr(chat, 'extra_data') and chat.extra_data:
                self.stdout.write(f'  📦 Extra data: {chat.extra_data}')
            
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
