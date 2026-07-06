from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0007_add_procurement_request_link_kind"),
    ]

    operations = [
        migrations.AlterField(
            model_name="taskactivity",
            name="object_kind",
            field=models.CharField(
                blank=True,
                choices=[
                    ("message", "Сообщение"),
                    ("calendar_event", "Календарное событие"),
                    ("document", "Документ"),
                    ("request", "Заявление"),
                    ("procurement_request", "Заявка на закупку"),
                    ("employee", "Сотрудник"),
                ],
                max_length=32,
                verbose_name="Тип объекта",
            ),
        ),
        migrations.AlterField(
            model_name="tasklinkedobject",
            name="kind",
            field=models.CharField(
                choices=[
                    ("message", "Сообщение"),
                    ("calendar_event", "Календарное событие"),
                    ("document", "Документ"),
                    ("request", "Заявление"),
                    ("procurement_request", "Заявка на закупку"),
                    ("employee", "Сотрудник"),
                ],
                max_length=32,
                verbose_name="Тип связи",
            ),
        ),
    ]
