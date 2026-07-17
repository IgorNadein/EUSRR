from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0017_task_comment_activity"),
    ]

    operations = [
        migrations.AlterField(
            model_name="taskactivity",
            name="action",
            field=models.CharField(
                choices=[
                    ("created", "Создал задачу"),
                    ("updated", "Обновил задачу"),
                    ("claimed", "Взял задачу в работу"),
                    ("moved", "Переместил задачу"),
                    ("linked", "Связал объект"),
                    ("unlinked", "Убрал связь"),
                    ("attachment_added", "Добавил файл"),
                    ("attachment_removed", "Удалил файл"),
                    ("checklist_item_added", "Добавил пункт чек-листа"),
                    ("checklist_item_updated", "Изменил пункт чек-листа"),
                    ("checklist_item_completed", "Выполнил пункт чек-листа"),
                    ("checklist_item_reopened", "Вернул пункт чек-листа в работу"),
                    ("checklist_item_removed", "Удалил пункт чек-листа"),
                    ("comment_added", "Добавил комментарий"),
                    ("comment_edited", "Изменил комментарий"),
                    ("comment_removed", "Удалил комментарий"),
                ],
                max_length=32,
                verbose_name="Действие",
            ),
        ),
    ]
