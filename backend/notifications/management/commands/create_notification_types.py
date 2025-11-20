from django.core.management.base import BaseCommand
from notifications.models import NotificationCategory, NotificationType


class Command(BaseCommand):
    help = 'Создать начальные типы уведомлений'

    def handle(self, *args, **options):
        self.stdout.write('Создание категорий и типов уведомлений...\n')

        # Категории и их типы
        categories_data = {
            'communications': {
                'name': 'Коммуникации',
                'icon': 'bi-chat-dots',
                'color': 'primary',
                'order': 1,
                'types': [
                    {
                        'code': 'chat_new_message',
                        'name': 'Новое сообщение в чате',
                        'description': 'Получено новое сообщение',
                        'priority': 'normal',
                        'default_channels': {
                            'web': True,
                            'email': False,
                            'telegram': True
                        },
                        'is_groupable': True,
                        'grouping_window_minutes': 5,
                    },
                    {
                        'code': 'chat_mention',
                        'name': 'Упоминание в сообщении',
                        'description': 'Вас упомянули в сообщении (@username)',
                        'priority': 'high',
                        'default_channels': {
                            'web': True,
                            'email': False,
                            'telegram': True
                        },
                        'is_groupable': False,
                    },
                    {
                        'code': 'chat_reply',
                        'name': 'Ответ на ваше сообщение',
                        'description': 'Кто-то ответил на ваше сообщение',
                        'priority': 'normal',
                        'default_channels': {
                            'web': True,
                            'email': False,
                            'telegram': True
                        },
                        'is_groupable': True,
                    },
                    {
                        'code': 'chat_added_to_chat',
                        'name': 'Добавление в чат',
                        'description': 'Вас добавили в новый чат/группу',
                        'priority': 'normal',
                        'default_channels': {
                            'web': True,
                            'email': False,
                            'telegram': False
                        },
                        'is_groupable': False,
                    },
                ],
            },
            'documents': {
                'name': 'Документы',
                'icon': 'bi-file-earmark-text',
                'color': 'info',
                'order': 2,
                'types': [
                    {
                        'code': 'document_ready',
                        'name': 'Документ на ознакомление',
                        'description': 'Новый документ требует ознакомления',
                        'priority': 'high',
                        'default_channels': {
                            'web': True,
                            'email': True,
                            'telegram': True
                        },
                        'is_groupable': False,
                    },
                    {
                        'code': 'document_signed_all',
                        'name': 'Документ подписан всеми',
                        'description': 'Все участники ознакомились',
                        'priority': 'normal',
                        'default_channels': {
                            'web': True,
                            'email': False,
                            'telegram': False
                        },
                        'is_groupable': False,
                    },
                    {
                        'code': 'document_reminder',
                        'name': 'Напоминание об ознакомлении',
                        'description': 'Срок ознакомления истекает',
                        'priority': 'urgent',
                        'default_channels': {
                            'web': True,
                            'email': True,
                            'telegram': True
                        },
                        'is_groupable': False,
                    },
                    {
                        'code': 'document_comment',
                        'name': 'Комментарий к документу',
                        'description': 'Новый комментарий к документу',
                        'priority': 'normal',
                        'default_channels': {
                            'web': True,
                            'email': False,
                            'telegram': False
                        },
                        'is_groupable': True,
                    },
                ],
            },
            'requests': {
                'name': 'Заявления',
                'icon': 'bi-clipboard-check',
                'color': 'success',
                'order': 3,
                'types': [
                    {
                        'code': 'request_new',
                        'name': 'Новая заявка',
                        'description': 'Поступила новая заявка на рассмотрение',
                        'priority': 'high',
                        'default_channels': {
                            'web': True,
                            'email': True,
                            'telegram': True
                        },
                        'is_groupable': True,
                    },
                    {
                        'code': 'request_approved',
                        'name': 'Заявка одобрена',
                        'description': 'Ваша заявка одобрена',
                        'priority': 'high',
                        'default_channels': {
                            'web': True,
                            'email': True,
                            'telegram': True
                        },
                        'is_groupable': False,
                    },
                    {
                        'code': 'request_rejected',
                        'name': 'Заявка отклонена',
                        'description': 'Ваша заявка отклонена',
                        'priority': 'high',
                        'default_channels': {
                            'web': True,
                            'email': True,
                            'telegram': True
                        },
                        'is_groupable': False,
                    },
                    {
                        'code': 'request_comment',
                        'name': 'Комментарий к заявке',
                        'description': 'Новый комментарий к вашей заявке',
                        'priority': 'normal',
                        'default_channels': {
                            'web': True,
                            'email': False,
                            'telegram': True
                        },
                        'is_groupable': True,
                    },
                    {
                        'code': 'request_status_changed',
                        'name': 'Изменение статуса заявки',
                        'description': 'Статус вашей заявки изменен',
                        'priority': 'normal',
                        'default_channels': {
                            'web': True,
                            'email': False,
                            'telegram': True
                        },
                        'is_groupable': False,
                    },
                ],
            },
            'calendar': {
                'name': 'Календарь',
                'icon': 'bi-calendar-event',
                'color': 'warning',
                'order': 4,
                'types': [
                    {
                        'code': 'event_created',
                        'name': 'Новое событие',
                        'description': 'Добавлено новое событие в календарь',
                        'priority': 'normal',
                        'default_channels': {
                            'web': True,
                            'email': False,
                            'telegram': False
                        },
                        'is_groupable': True,
                    },
                    {
                        'code': 'event_reminder_hour',
                        'name': 'Напоминание за час',
                        'description': 'Событие начнется через час',
                        'priority': 'high',
                        'default_channels': {
                            'web': True,
                            'email': False,
                            'telegram': True
                        },
                        'is_groupable': False,
                    },
                    {
                        'code': 'event_reminder_day',
                        'name': 'Напоминание за день',
                        'description': 'Событие начнется завтра',
                        'priority': 'normal',
                        'default_channels': {
                            'web': True,
                            'email': True,
                            'telegram': False
                        },
                        'is_groupable': False,
                    },
                    {
                        'code': 'event_changed',
                        'name': 'Изменение события',
                        'description': 'Детали события изменены',
                        'priority': 'normal',
                        'default_channels': {
                            'web': True,
                            'email': False,
                            'telegram': True
                        },
                        'is_groupable': False,
                    },
                    {
                        'code': 'event_cancelled',
                        'name': 'Отмена события',
                        'description': 'Событие отменено',
                        'priority': 'high',
                        'default_channels': {
                            'web': True,
                            'email': True,
                            'telegram': True
                        },
                        'is_groupable': False,
                    },
                ],
            },
            'department': {
                'name': 'Отдел',
                'icon': 'bi-people',
                'color': 'secondary',
                'order': 5,
                'types': [
                    {
                        'code': 'department_new_employee',
                        'name': 'Новый сотрудник в отделе',
                        'description': 'В ваш отдел добавлен новый сотрудник',
                        'priority': 'low',
                        'default_channels': {
                            'web': True,
                            'email': False,
                            'telegram': False
                        },
                        'is_groupable': True,
                    },
                    {
                        'code': 'department_employee_left',
                        'name': 'Сотрудник покинул отдел',
                        'description': 'Сотрудник больше не в вашем отделе',
                        'priority': 'low',
                        'default_channels': {
                            'web': True,
                            'email': False,
                            'telegram': False
                        },
                        'is_groupable': True,
                    },
                    {
                        'code': 'department_structure_changed',
                        'name': 'Изменение структуры отдела',
                        'description': 'Структура отдела была изменена',
                        'priority': 'normal',
                        'default_channels': {
                            'web': True,
                            'email': False,
                            'telegram': False
                        },
                        'is_groupable': False,
                    },
                    {
                        'code': 'department_new_head',
                        'name': 'Новый руководитель',
                        'description': 'Назначен новый руководитель отдела',
                        'priority': 'high',
                        'default_channels': {
                            'web': True,
                            'email': True,
                            'telegram': False
                        },
                        'is_groupable': False,
                    },
                    {
                        'code': 'department_announcement',
                        'name': 'Объявление для отдела',
                        'description': 'Важное объявление для вашего отдела',
                        'priority': 'high',
                        'default_channels': {
                            'web': True,
                            'email': True,
                            'telegram': True
                        },
                        'is_groupable': False,
                    },
                ],
            },
            'profile': {
                'name': 'Профиль',
                'icon': 'bi-person-circle',
                'color': 'dark',
                'order': 6,
                'types': [
                    {
                        'code': 'profile_data_changed',
                        'name': 'Изменение данных профиля',
                        'description': 'Администратор изменил ваши данные',
                        'priority': 'normal',
                        'default_channels': {
                            'web': True,
                            'email': True,
                            'telegram': False
                        },
                        'is_groupable': False,
                        'is_required': True,
                    },
                    {
                        'code': 'profile_password_changed',
                        'name': 'Изменение пароля',
                        'description': 'Ваш пароль был изменен',
                        'priority': 'urgent',
                        'default_channels': {
                            'web': True,
                            'email': True,
                            'telegram': True
                        },
                        'is_groupable': False,
                        'is_required': True,
                    },
                    {
                        'code': 'profile_email_changed',
                        'name': 'Изменение email',
                        'description': 'Ваш email адрес был изменен',
                        'priority': 'urgent',
                        'default_channels': {
                            'web': True,
                            'email': True,
                            'telegram': True
                        },
                        'is_groupable': False,
                        'is_required': True,
                    },
                    {
                        'code': 'profile_messenger_linked',
                        'name': 'Привязка мессенджера',
                        'description': 'Мессенджер успешно привязан к профилю',
                        'priority': 'normal',
                        'default_channels': {
                            'web': True,
                            'email': False,
                            'telegram': False
                        },
                        'is_groupable': False,
                    },
                    {
                        'code': 'profile_new_login',
                        'name': 'Вход из нового места',
                        'description': 'Обнаружен вход из нового места/устройства',
                        'priority': 'high',
                        'default_channels': {
                            'web': True,
                            'email': True,
                            'telegram': True
                        },
                        'is_groupable': False,
                        'is_required': True,
                    },
                ],
            },
            'feed': {
                'name': 'Новости',
                'icon': 'bi-newspaper',
                'color': 'danger',
                'order': 7,
                'types': [
                    {
                        'code': 'feed_new_post',
                        'name': 'Новая новость',
                        'description': 'Опубликована новая новость',
                        'priority': 'low',
                        'default_channels': {
                            'web': True,
                            'email': False,
                            'telegram': False
                        },
                        'is_groupable': True,
                    },
                    {
                        'code': 'feed_post_comment',
                        'name': 'Комментарий к новости',
                        'description': 'Новый комментарий к вашей новости',
                        'priority': 'normal',
                        'default_channels': {
                            'web': True,
                            'email': False,
                            'telegram': False
                        },
                        'is_groupable': True,
                    },
                    {
                        'code': 'feed_post_reaction',
                        'name': 'Реакция на новость',
                        'description': 'Кто-то отреагировал на вашу новость',
                        'priority': 'low',
                        'default_channels': {
                            'web': True,
                            'email': False,
                            'telegram': False
                        },
                        'is_groupable': True,
                        'grouping_window_minutes': 60,
                    },
                ],
            },
            'system': {
                'name': 'Система',
                'icon': 'bi-gear',
                'color': 'light',
                'order': 8,
                'types': [
                    {
                        'code': 'system_maintenance',
                        'name': 'Технические работы',
                        'description': 'Запланированы технические работы',
                        'priority': 'urgent',
                        'default_channels': {
                            'web': True,
                            'email': True,
                            'telegram': True
                        },
                        'is_groupable': False,
                        'is_required': True,
                    },
                    {
                        'code': 'system_announcement',
                        'name': 'Важное объявление',
                        'description': 'Общее важное объявление',
                        'priority': 'high',
                        'default_channels': {
                            'web': True,
                            'email': True,
                            'telegram': True
                        },
                        'is_groupable': False,
                        'is_required': True,
                    },
                    {
                        'code': 'system_new_feature',
                        'name': 'Новый функционал',
                        'description': 'Добавлен новый функционал',
                        'priority': 'low',
                        'default_channels': {
                            'web': True,
                            'email': False,
                            'telegram': False
                        },
                        'is_groupable': False,
                    },
                    {
                        'code': 'system_policy_change',
                        'name': 'Изменение политик',
                        'description': 'Изменены политики безопасности',
                        'priority': 'high',
                        'default_channels': {
                            'web': True,
                            'email': True,
                            'telegram': False
                        },
                        'is_groupable': False,
                        'is_required': True,
                    },
                ],
            },
        }

        # Создание категорий и типов
        created_categories = 0
        created_types = 0

        for cat_code, cat_data in categories_data.items():
            # Создать или обновить категорию
            category, created = NotificationCategory.objects.update_or_create(
                code=cat_code,
                defaults={
                    'name': cat_data['name'],
                    'icon': cat_data['icon'],
                    'color': cat_data['color'],
                    'order': cat_data['order'],
                }
            )
            if created:
                created_categories += 1
                self.stdout.write(
                    self.style.SUCCESS(f'✓ Создана категория: {category.name}')
                )

            # Создать типы для категории
            for type_data in cat_data['types']:
                notification_type, created = (
                    NotificationType.objects.update_or_create(
                        code=type_data['code'],
                        defaults={
                            'category': category,
                            'name': type_data['name'],
                            'description': type_data.get('description', ''),
                            'priority': type_data.get('priority', 'normal'),
                            'default_channels': type_data.get(
                                'default_channels', {'web': True}
                            ),
                            'is_groupable': type_data.get('is_groupable', True),
                            'grouping_window_minutes': type_data.get(
                                'grouping_window_minutes', 5
                            ),
                            'is_required': type_data.get('is_required', False),
                        }
                    )
                )
                if created:
                    created_types += 1
                    self.stdout.write(f'  → Создан тип: {notification_type.name}')

        self.stdout.write('\n')
        self.stdout.write(
            self.style.SUCCESS(
                f'Успешно создано:\n'
                f'  Категорий: {created_categories}\n'
                f'  Типов: {created_types}\n'
            )
        )
