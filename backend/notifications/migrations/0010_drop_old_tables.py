# Generated manually for safe migration from v1 to v2

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0009_add_document_related_notification_type'),
    ]

    operations = [
        # Разделяем операции на БД и состояние Django
        migrations.SeparateDatabaseAndState(
            database_operations=[
                # Удаляем все старые таблицы (безопасно - IF EXISTS)
                migrations.RunSQL(
                    sql="""
                        DROP TABLE IF EXISTS notifications_notification;
                        DROP TABLE IF EXISTS notifications_notificationtype;
                        DROP TABLE IF EXISTS notifications_notificationcategory;
                        DROP TABLE IF EXISTS notifications_notificationtemplate;
                        DROP TABLE IF EXISTS notifications_usernotificationsettings;
                        DROP TABLE IF EXISTS notifications_telegramuser;
                        DROP TABLE IF EXISTS notifications_webpushsubscription;
                    """,
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                # Удаляем модели из состояния Django
                # Порядок важен: сначала связанные модели, потом основные
                migrations.DeleteModel(name='UserNotificationSettings'),
                migrations.DeleteModel(name='NotificationTemplate'),
                migrations.DeleteModel(name='TelegramUser'),
                migrations.DeleteModel(name='WebPushSubscription'),
                migrations.DeleteModel(name='Notification'),
                migrations.DeleteModel(name='NotificationType'),
                migrations.DeleteModel(name='NotificationCategory'),
            ],
        ),
    ]
