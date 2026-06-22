import ldapdb.models.fields
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("guests", "0002_ldapguestuser"),
    ]

    operations = [
        migrations.AddField(
            model_name="guest",
            name="avatar",
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to="guests/avatars",
                verbose_name="Фото",
            ),
        ),
        migrations.AddField(
            model_name="ldapguestuser",
            name="thumbnail_photo",
            field=ldapdb.models.fields.ImageField(
                blank=True,
                db_column="thumbnailPhoto",
                max_length=200,
            ),
        ),
    ]
