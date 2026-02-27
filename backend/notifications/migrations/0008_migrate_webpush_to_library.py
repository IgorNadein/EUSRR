# Generated migration for migrating WebPushSubscription to django-push-notifications

from django.db import migrations


def migrate_webpush_subscriptions(apps, schema_editor):
    """Мигрировать существующие WebPushSubscription в WebPushDevice"""
    WebPushSubscription = apps.get_model('notifications', 'WebPushSubscription')
    WebPushDevice = apps.get_model('push_notifications', 'WebPushDevice')
    
    migrated_count = 0
    for subscription in WebPushSubscription.objects.filter(is_active=True):
        try:
            # Создаем WebPushDevice для каждой подписки
            WebPushDevice.objects.create(
                user=subscription.user,
                registration_id=subscription.endpoint,
                p256dh=subscription.p256dh_key,
                auth=subscription.auth_key,
                browser=subscription.device_name or 'Unknown',
                active=subscription.is_active,
            )
            migrated_count += 1
        except Exception as e:
            print(f"Error migrating subscription {subscription.id}: {e}")
    
    print(f"✅ Migrated {migrated_count} WebPush subscriptions to django-push-notifications")


def reverse_migration(apps, schema_editor):
    """Откат: удаляем все WebPushDevice"""
    WebPushDevice = apps.get_model('push_notifications', 'WebPushDevice')
    count = WebPushDevice.objects.all().delete()[0]
    print(f"Deleted {count} WebPushDevice records")


class Migration(migrations.Migration):

    dependencies = [
        ('notifications', '0007_merge_20260227_1639'),  # Последняя миграция notifications
        ('push_notifications', '0010_alter_gcmdevice_options_and_more'),  # Последняя миграция библиотеки
    ]

    operations = [
        migrations.RunPython(migrate_webpush_subscriptions, reverse_migration),
    ]
