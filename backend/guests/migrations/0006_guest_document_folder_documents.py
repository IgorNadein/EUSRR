from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0015_delete_documentcomment"),
        ("filer", "0018_alter_file_options"),
        ("guests", "0005_guest_last_name_optional"),
    ]

    operations = [
        migrations.AddField(
            model_name="guest",
            name="document_folder",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="guest_document_folders",
                to="filer.folder",
                verbose_name="Папка документов",
            ),
        ),
        migrations.AddField(
            model_name="guest",
            name="documents",
            field=models.ManyToManyField(
                blank=True,
                related_name="guests",
                to="documents.document",
                verbose_name="Документы гостя",
            ),
        ),
    ]
