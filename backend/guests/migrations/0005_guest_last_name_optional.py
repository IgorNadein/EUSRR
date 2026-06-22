from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("guests", "0004_guest_blacklist_remove_ldap_enabled"),
    ]

    operations = [
        migrations.AlterField(
            model_name="guest",
            name="last_name",
            field=models.CharField(blank=True, max_length=150, verbose_name="Фамилия"),
        ),
    ]
