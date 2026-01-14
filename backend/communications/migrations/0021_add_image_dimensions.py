# Generated migration for adding image dimensions

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('communications', '0020_availablereaction_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='messageattachment',
            name='width',
            field=models.IntegerField(null=True, blank=True, verbose_name='Ширина изображения'),
        ),
        migrations.AddField(
            model_name='messageattachment',
            name='height',
            field=models.IntegerField(null=True, blank=True, verbose_name='Высота изображения'),
        ),
    ]
