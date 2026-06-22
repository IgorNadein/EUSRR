from django.db import migrations, models


def migrate_guest_state(apps, schema_editor):
    Guest = apps.get_model("guests", "Guest")
    for guest in Guest.objects.all().only("id", "is_active", "ldap_enabled"):
        old_is_active = bool(guest.is_active)
        old_ldap_enabled = bool(guest.ldap_enabled)
        guest.is_blacklisted = not old_is_active
        guest.is_active = old_ldap_enabled
        guest.save(update_fields=["is_blacklisted", "is_active"])


def reverse_guest_state(apps, schema_editor):
    Guest = apps.get_model("guests", "Guest")
    for guest in Guest.objects.all().only("id", "is_active", "is_blacklisted"):
        guest.ldap_enabled = bool(guest.is_active)
        guest.is_active = not bool(guest.is_blacklisted)
        guest.save(update_fields=["ldap_enabled", "is_active"])


class Migration(migrations.Migration):

    dependencies = [
        ("guests", "0003_guest_avatar_ldapguestuser_thumbnail_photo"),
    ]

    operations = [
        migrations.AddField(
            model_name="guest",
            name="is_blacklisted",
            field=models.BooleanField(
                db_index=True,
                default=False,
                verbose_name="Черный список",
            ),
        ),
        migrations.RunPython(migrate_guest_state, reverse_guest_state),
        migrations.RemoveIndex(
            model_name="guest",
            name="guest_ldap_enabled_idx",
        ),
        migrations.AddIndex(
            model_name="guest",
            index=models.Index(fields=["is_active"], name="guest_active_idx"),
        ),
        migrations.AlterField(
            model_name="guest",
            name="is_active",
            field=models.BooleanField(default=False, verbose_name="Активен по доступу"),
        ),
        migrations.RemoveField(
            model_name="guest",
            name="ldap_enabled",
        ),
    ]
