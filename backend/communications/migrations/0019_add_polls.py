# Generated migration for polls feature

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('communications', '0018_add_forwarded_metadata'),
    ]

    operations = [
        # Таблица голосований
        migrations.CreateModel(
            name='Poll',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID'
                )),
                ('question', models.CharField(
                    max_length=500,
                    verbose_name='Вопрос'
                )),
                ('is_anonymous', models.BooleanField(
                    default=False,
                    verbose_name='Анонимное голосование'
                )),
                ('is_multiple_choice', models.BooleanField(
                    default=False,
                    verbose_name='Множественный выбор'
                )),
                ('is_quiz', models.BooleanField(
                    default=False,
                    verbose_name='Викторина'
                )),
                ('allows_custom_answers', models.BooleanField(
                    default=False,
                    verbose_name='Разрешить свои варианты'
                )),
                ('is_closed', models.BooleanField(
                    default=False,
                    verbose_name='Голосование закрыто'
                )),
                ('closed_at', models.DateTimeField(
                    blank=True,
                    null=True,
                    verbose_name='Время закрытия'
                )),
                ('closes_at', models.DateTimeField(
                    blank=True,
                    null=True,
                    verbose_name='Автоматическое закрытие'
                )),
                ('created_at', models.DateTimeField(
                    auto_now_add=True,
                    verbose_name='Создано'
                )),
                ('updated_at', models.DateTimeField(
                    auto_now=True,
                    verbose_name='Обновлено'
                )),
                ('total_voters', models.IntegerField(
                    default=0,
                    verbose_name='Всего проголосовало'
                )),
                ('author', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='created_polls',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Автор'
                )),
                ('message', models.OneToOneField(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='poll',
                    to='communications.message',
                    verbose_name='Сообщение'
                )),
            ],
            options={
                'verbose_name': 'Голосование',
                'verbose_name_plural': 'Голосования',
                'ordering': ['-created_at'],
            },
        ),
        
        # Таблица вариантов ответа
        migrations.CreateModel(
            name='PollOption',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID'
                )),
                ('text', models.CharField(
                    max_length=200,
                    verbose_name='Текст варианта'
                )),
                ('position', models.IntegerField(
                    default=0,
                    verbose_name='Порядковый номер'
                )),
                ('vote_count', models.IntegerField(
                    default=0,
                    verbose_name='Количество голосов'
                )),
                ('is_correct', models.BooleanField(
                    default=False,
                    verbose_name='Правильный ответ'
                )),
                ('created_at', models.DateTimeField(
                    auto_now_add=True,
                    verbose_name='Создан'
                )),
                ('poll', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='options',
                    to='communications.poll',
                    verbose_name='Голосование'
                )),
            ],
            options={
                'verbose_name': 'Вариант ответа',
                'verbose_name_plural': 'Варианты ответов',
                'ordering': ['position', 'id'],
            },
        ),
        
        # Таблица голосов
        migrations.CreateModel(
            name='PollVote',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True,
                    primary_key=True,
                    serialize=False,
                    verbose_name='ID'
                )),
                ('voted_at', models.DateTimeField(
                    auto_now_add=True,
                    verbose_name='Время голосования'
                )),
                ('option', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='votes',
                    to='communications.polloption',
                    verbose_name='Выбранный вариант'
                )),
                ('poll', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='votes',
                    to='communications.poll',
                    verbose_name='Голосование'
                )),
                ('voter', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='poll_votes',
                    to=settings.AUTH_USER_MODEL,
                    verbose_name='Проголосовавший'
                )),
            ],
            options={
                'verbose_name': 'Голос',
                'verbose_name_plural': 'Голоса',
                'ordering': ['-voted_at'],
            },
        ),
        
        # Индексы и констрейнты
        migrations.AddIndex(
            model_name='poll',
            index=models.Index(
                fields=['message'],
                name='comm_msg_idx_poll'
            ),
        ),
        migrations.AddIndex(
            model_name='poll',
            index=models.Index(
                fields=['author', 'created_at'],
                name='comm_auth_created_poll'
            ),
        ),
        migrations.AddIndex(
            model_name='poll',
            index=models.Index(
                fields=['is_closed', 'closes_at'],
                name='comm_closed_closes_poll'
            ),
        ),
        migrations.AddIndex(
            model_name='polloption',
            index=models.Index(
                fields=['poll', 'position'],
                name='comm_poll_pos_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='pollvote',
            index=models.Index(
                fields=['poll', 'voter'],
                name='comm_poll_voter_idx'
            ),
        ),
        migrations.AddIndex(
            model_name='pollvote',
            index=models.Index(
                fields=['option'],
                name='comm_option_idx'
            ),
        ),
        
        # Уникальность голоса
        migrations.AddConstraint(
            model_name='pollvote',
            constraint=models.UniqueConstraint(
                fields=['poll', 'voter', 'option'],
                name='unique_vote_per_option'
            ),
        ),
    ]
