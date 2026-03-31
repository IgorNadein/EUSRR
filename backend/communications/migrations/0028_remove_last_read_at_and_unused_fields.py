# Generated manually - Remove deprecated fields from ChatReadState
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('communications', '0027_remove_message_edit_history_and_more'),
    ]

    operations = [
        # Удаляем индекс, который использует last_read_at
        migrations.RemoveIndex(
            model_name='chatreadstate',
            name='communicati_chat_id_edefdb_idx',
        ),

        # Удаляем устаревшие поля
        migrations.RemoveField(
            model_name='chatreadstate',
            name='last_read_at',
        ),
        migrations.RemoveField(
            model_name='chatreadstate',
            name='unread_mentions_count',
        ),
        migrations.RemoveField(
            model_name='chatreadstate',
            name='unread_thread_replies_count',
        ),
    ]
