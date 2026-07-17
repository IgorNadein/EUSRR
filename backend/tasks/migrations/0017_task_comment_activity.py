from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("tasks", "0016_taskboard_access_scope"),
    ]

    operations = [
        migrations.AlterField(
            model_name="taskactivity",
            name="action",
            field=models.CharField(
                choices=[
                    ("created", "Создал задачу"),
                    ("updated", "Обновил задачу"),
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
        migrations.AlterField(
            model_name="taskactivity",
            name="object_kind",
            field=models.CharField(
                blank=True,
                choices=[
                    ("post", "Новость"),
                    ("message", "Сообщение"),
                    ("calendar_event", "Календарное событие"),
                    ("document", "Документ"),
                    ("request", "Заявление"),
                    ("procurement_request", "Заявка на закупку"),
                    ("employee", "Сотрудник"),
                    ("guest", "Гость"),
                    ("guest_visit", "Заявка на гостевой визит"),
                    ("attendance_record", "Запись посещаемости"),
                    ("external_link", "Внешняя ссылка"),
                    ("checklist_item", "Пункт чек-листа"),
                    ("comment", "Комментарий"),
                ],
                max_length=32,
                verbose_name="Тип объекта",
            ),
        ),
    ]
