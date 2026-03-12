"""
Management command для управления правами участников в чатах

Примеры использования:

# Назначить администратора
python manage.py manage_chat_permissions --chat-id 62 --user-id 10 --role admin

# Назначить персональные права
python manage.py manage_chat_permissions --chat-id 62 --user-id 10 \\
    --can-add-members --can-pin-messages

# Показать участников чата
python manage.py manage_chat_permissions --chat-id 62 --list

# Удалить права (деактивировать membership)
python manage.py manage_chat_permissions --chat-id 62 --user-id 10 --remove
"""

from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from communications.models import Chat, ChatMembership

User = get_user_model()


class Command(BaseCommand):
    help = 'Управление правами участников в чатах'

    def add_arguments(self, parser):
        parser.add_argument(
            '--chat-id',
            type=int,
            required=True,
            help='ID чата'
        )
        parser.add_argument(
            '--user-id',
            type=int,
            help='ID пользователя'
        )
        parser.add_argument(
            '--role',
            choices=['admin', 'moderator', 'member', 'guest'],
            help='Роль пользователя в чате'
        )
        parser.add_argument(
            '--can-add-members',
            action='store_true',
            help='Разрешить добавлять участников'
        )
        parser.add_argument(
            '--can-remove-members',
            action='store_true',
            help='Разрешить удалять участников'
        )
        parser.add_argument(
            '--can-pin-messages',
            action='store_true',
            help='Разрешить закреплять сообщения'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='Показать список участников чата'
        )
        parser.add_argument(
            '--remove',
            action='store_true',
            help='Удалить права (деактивировать membership)'
        )

    def handle(self, *args, **options):
        chat_id = options['chat_id']
        user_id = options.get('user_id')
        role = options.get('role')
        can_add_members = options.get('can_add_members')
        can_remove_members = options.get('can_remove_members')
        can_pin_messages = options.get('can_pin_messages')
        list_members = options.get('list')
        remove = options.get('remove')

        # Проверяем существование чата
        try:
            chat = Chat.objects.get(pk=chat_id)
        except Chat.DoesNotExist:
            raise CommandError(f'Чат с ID {chat_id} не найден')

        self.stdout.write(self.style.SUCCESS(
            f'\\n📱 Чат: {chat.name or f"#{chat_id}"} '
            f'({chat.get_type_display()})'
        ))
        self.stdout.write(f'   Создатель: {chat.created_by}\\n')

        # Режим списка участников
        if list_members:
            self._list_members(chat)
            return

        # Для остальных операций требуется user_id
        if not user_id:
            raise CommandError(
                'Требуется указать --user-id (или используйте --list)'
            )

        # Проверяем существование пользователя
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            raise CommandError(f'Пользователь с ID {user_id} не найден')

        # Режим удаления прав
        if remove:
            self._remove_permissions(chat, user)
            return

        # Режим назначения прав
        self._assign_permissions(
            chat, user, role,
            can_add_members, can_remove_members, can_pin_messages
        )

    def _list_members(self, chat):
        """Показать список участников чата"""
        memberships = chat.memberships.select_related('user').filter(
            is_active=True
        ).order_by('-role', 'joined_at')

        if not memberships.exists():
            self.stdout.write('   Нет записей в ChatMembership')
            participants = chat.participants.all()
            if participants.exists():
                self.stdout.write(
                    f'   Участники через participants: '
                    f'{participants.count()}'
                )
            return

        self.stdout.write(self.style.SUCCESS(
            f'👥 Участники чата ({memberships.count()}):\\n'
        ))

        for m in memberships:
            role_emoji = {
                'admin': '🔴',
                'moderator': '🟠',
                'member': '🟢',
                'guest': '⚪'
            }.get(m.role, '❓')

            flags = []
            if m.can_add_members:
                flags.append('➕ add')
            if m.can_remove_members:
                flags.append('➖ remove')
            if m.can_pin_messages:
                flags.append('📌 pin')

            flags_str = f" [{', '.join(flags)}]" if flags else ""

            self.stdout.write(
                f'   {role_emoji} {m.user.get_full_name()} '
                f'(ID: {m.user_id}) - {m.get_role_display()}'
                f'{flags_str}'
            )

    def _remove_permissions(self, chat, user):
        """Удалить права (деактивировать membership)"""
        try:
            membership = ChatMembership.objects.get(
                chat=chat,
                user=user,
                is_active=True
            )
            membership.is_active = False
            membership.save()

            self.stdout.write(self.style.SUCCESS(
                f'✅ Права пользователя {user.get_full_name()} удалены'
            ))
        except ChatMembership.DoesNotExist:
            self.stdout.write(self.style.WARNING(
                f'⚠️  Активный membership для пользователя '
                f'{user.get_full_name()} не найден'
            ))

    def _assign_permissions(
        self, chat, user, role,
        can_add_members, can_remove_members, can_pin_messages
    ):
        """Назначить права пользователю"""
        # Если не указана роль, используем текущую или member по умолчанию
        if not role:
            try:
                existing = ChatMembership.objects.get(
                    chat=chat, user=user, is_active=True
                )
                role = existing.role
            except ChatMembership.DoesNotExist:
                role = 'member'

        # Создать или обновить membership
        membership, created = ChatMembership.objects.get_or_create(
            chat=chat,
            user=user,
            defaults={
                'role': role,
                'can_add_members': can_add_members,
                'can_remove_members': can_remove_members,
                'can_pin_messages': can_pin_messages,
                'invited_by': chat.created_by,
                'is_active': True,
            }
        )

        if not created:
            # Обновить существующий membership
            if role:
                membership.role = role
            if can_add_members:
                membership.can_add_members = True
            if can_remove_members:
                membership.can_remove_members = True
            if can_pin_messages:
                membership.can_pin_messages = True
            membership.is_active = True
            membership.save()

        # Убедиться, что user в participants
        if user not in chat.participants.all():
            chat.participants.add(user)

        # Вывод результата
        action = '🆕 Создан' if created else '🔄 Обновлен'
        role_emoji = {
            'admin': '🔴',
            'moderator': '🟠',
            'member': '🟢',
            'guest': '⚪'
        }.get(role, '❓')

        self.stdout.write(
            f'\\n{action} membership для {user.get_full_name()}:'
        )
        self.stdout.write(
            f'   {role_emoji} Роль: {membership.get_role_display()}'
        )

        if membership.can_add_members:
            self.stdout.write('   ➕ Может добавлять участников')
        if membership.can_remove_members:
            self.stdout.write('   ➖ Может удалять участников')
        if membership.can_pin_messages:
            self.stdout.write('   📌 Может закреплять сообщения')

        self.stdout.write(self.style.SUCCESS('\\n✅ Права успешно назначены'))
