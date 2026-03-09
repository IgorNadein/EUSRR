# Generated manually for creating v2 models

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('contenttypes', '0002_remove_content_type_name'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('notifications', '0010_drop_old_tables'),
    ]

    operations = [
        # Создаем новую модель Notification v2
        migrations.CreateModel(
            name='Notification',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('verb', models.CharField(db_index=True, help_text='Действие (liked, commented, mentioned и т.д.)', max_length=255, verbose_name='Действие')),
                ('description', models.TextField(blank=True, help_text='Описание уведомления', verbose_name='Описание')),
                ('action_url', models.CharField(blank=True, help_text='URL для перехода', max_length=500, verbose_name='URL действия')),
                ('data', models.JSONField(blank=True, default=dict, help_text='Дополнительные данные', verbose_name='Данные')),
                ('unread', models.BooleanField(db_index=True, default=True, help_text='Непрочитано', verbose_name='Непрочитано')),
                ('public', models.BooleanField(db_index=True, default=True, help_text='Публичное уведомление', verbose_name='Публичное')),
                ('deleted', models.BooleanField(db_index=True, default=False, help_text='Удалено (мягкое удаление)', verbose_name='Удалено')),
                ('emailed', models.BooleanField(default=False, help_text='Отправлено по email', verbose_name='Отправлено email')),
                ('timestamp', models.DateTimeField(auto_now_add=True, db_index=True, help_text='Время создания', verbose_name='Время создания')),
                ('timestamp_read', models.DateTimeField(blank=True, help_text='Время прочтения', null=True, verbose_name='Время прочтения')),
                ('actor_object_id', models.PositiveIntegerField(blank=True, help_text='ID актора', null=True)),
                ('action_object_object_id', models.PositiveIntegerField(blank=True, help_text='ID объекта действия', null=True)),
                ('target_object_id', models.PositiveIntegerField(blank=True, help_text='ID целевого объекта', null=True)),
                ('action_object_content_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notify_action_object', to='contenttypes.contenttype')),
                ('actor_content_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notify_actor', to='contenttypes.contenttype')),
                ('recipient', models.ForeignKey(help_text='Кому адресовано уведомление', on_delete=django.db.models.deletion.CASCADE, related_name='notifications', to=settings.AUTH_USER_MODEL, verbose_name='Получатель')),
                ('target_content_type', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='notify_target', to='contenttypes.contenttype')),
            ],
            options={
                'verbose_name': 'Уведомление',
                'verbose_name_plural': 'Уведомления',
                'db_table': 'notifications_notification_v2',
                'ordering': ['-timestamp'],
                'indexes': [
                    models.Index(fields=['recipient', '-timestamp'], name='notificatio_recipie_91dc91_idx'),
                    models.Index(fields=['recipient', 'unread', '-timestamp'], name='notificatio_recipie_9b2135_idx'),
                    models.Index(fields=['verb', '-timestamp'], name='notificatio_verb_1060e9_idx'),
                    models.Index(fields=['-timestamp'], name='notificatio_timesta_e0a5cf_idx'),
                ],
            },
        ),
        
        # Создаем модель UserChannelPreferences
        migrations.CreateModel(
            name='UserChannelPreferences',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('web_enabled', models.BooleanField(default=True, help_text='Включить веб-уведомления', verbose_name='Веб-уведомления')),
                ('email_enabled', models.BooleanField(default=True, help_text='Включить email уведомления', verbose_name='Email уведомления')),
                ('push_enabled', models.BooleanField(default=True, help_text='Включить push уведомления', verbose_name='Push уведомления')),
                ('email_frequency', models.CharField(choices=[('instant', 'Мгновенно'), ('daily', 'Ежедневно'), ('weekly', 'Еженедельно'), ('disabled', 'Отключено')], default='instant', help_text='Частота отправки email', max_length=20, verbose_name='Частота email')),
                ('disabled_verbs', models.JSONField(blank=True, default=list, help_text='Список отключенных типов уведомлений (verb)', verbose_name='Отключенные типы')),
                ('dnd_enabled', models.BooleanField(default=False, help_text='Включить режим "Не беспокоить"', verbose_name='Режим "Не беспокоить"')),
                ('dnd_start_time', models.TimeField(blank=True, null=True, help_text='Начало режима "Не беспокоить"', verbose_name='Начало DND')),
                ('dnd_end_time', models.TimeField(blank=True, null=True, help_text='Конец режима "Не беспокоить"', verbose_name='Конец DND')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='channel_preferences', to=settings.AUTH_USER_MODEL, verbose_name='Пользователь')),
            ],
            options={
                'verbose_name': 'Настройки каналов',
                'verbose_name_plural': 'Настройки каналов',
                'db_table': 'notifications_userchannelpreferences',
            },
        ),
    ]
