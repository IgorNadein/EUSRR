"""
Миграция данных: создание типов уведомлений для модуля закупок.
"""

from django.db import migrations


def create_procurement_notification_types(apps, schema_editor):
    """Создать категорию и типы уведомлений для закупок."""
    NotificationCategory = apps.get_model('notifications', 'NotificationCategory')
    NotificationType = apps.get_model('notifications', 'NotificationType')

    # Создаём категорию
    category, _ = NotificationCategory.objects.get_or_create(
        code='procurement',
        defaults={
            'name': 'Закупки',
            'description': 'Уведомления модуля закупок и инвентаризации',
            'icon': 'bi-cart3',
            'color': '#17a2b8',
            'order': 60,
        }
    )

    # Типы уведомлений
    notification_types = [
        {
            'code': 'procurement_new_request',
            'name': 'Новая заявка на закупку',
            'description': 'Уведомление о создании новой заявки на закупку',
            'priority': 'normal',
            'default_channels': {'web': True, 'email': True, 'telegram': False},
        },
        {
            'code': 'procurement_pending_approval',
            'name': 'Требуется согласование',
            'description': 'Заявка ожидает вашего согласования',
            'priority': 'high',
            'default_channels': {'web': True, 'email': True, 'telegram': True},
        },
        {
            'code': 'procurement_approved',
            'name': 'Заявка одобрена',
            'description': 'Ваша заявка на закупку была одобрена',
            'priority': 'normal',
            'default_channels': {'web': True, 'email': True, 'telegram': False},
        },
        {
            'code': 'procurement_rejected',
            'name': 'Заявка отклонена',
            'description': 'Ваша заявка на закупку была отклонена',
            'priority': 'high',
            'default_channels': {'web': True, 'email': True, 'telegram': True},
        },
        {
            'code': 'procurement_stage_approved',
            'name': 'Этап согласования пройден',
            'description': 'Один из этапов согласования заявки завершён',
            'priority': 'low',
            'default_channels': {'web': True, 'email': False, 'telegram': False},
        },
        {
            'code': 'procurement_completed',
            'name': 'Закупка завершена',
            'description': 'Закупка по заявке успешно завершена',
            'priority': 'normal',
            'default_channels': {'web': True, 'email': True, 'telegram': False},
        },
        {
            'code': 'equipment_transferred',
            'name': 'Оборудование передано',
            'description': 'Оборудование передано в ваш отдел или вам',
            'priority': 'normal',
            'default_channels': {'web': True, 'email': False, 'telegram': False},
        },
        {
            'code': 'equipment_maintenance',
            'name': 'Обслуживание оборудования',
            'description': 'Запланировано или завершено обслуживание оборудования',
            'priority': 'low',
            'default_channels': {'web': True, 'email': False, 'telegram': False},
        },
    ]

    for nt_data in notification_types:
        NotificationType.objects.get_or_create(
            code=nt_data['code'],
            defaults={
                'category': category,
                'name': nt_data['name'],
                'description': nt_data['description'],
                'priority': nt_data['priority'],
                'default_channels': nt_data['default_channels'],
            }
        )


def reverse_procurement_notification_types(apps, schema_editor):
    """Удалить типы уведомлений для закупок."""
    NotificationCategory = apps.get_model('notifications', 'NotificationCategory')
    NotificationType = apps.get_model('notifications', 'NotificationType')

    NotificationType.objects.filter(code__startswith='procurement_').delete()
    NotificationType.objects.filter(code__startswith='equipment_').delete()
    NotificationCategory.objects.filter(code='procurement').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0004_alter_telegramuser_telegram_id'),
    ]

    operations = [
        migrations.RunPython(
            create_procurement_notification_types,
            reverse_procurement_notification_types,
        ),
    ]
