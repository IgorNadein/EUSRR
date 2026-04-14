from django.db import migrations, models


def copy_legacy_pin_to_global(apps, schema_editor):
    Post = apps.get_model("feed", "Post")
    Post.objects.filter(pinned=True).update(pinned_global=True)


class Migration(migrations.Migration):

    dependencies = [
        ("feed", "0008_alter_post_body"),
    ]

    operations = [
        migrations.AddField(
            model_name="post",
            name="pinned_global",
            field=models.BooleanField(
                default=False,
                verbose_name="Закреплено в общей ленте",
            ),
        ),
        migrations.AddField(
            model_name="post",
            name="pinned_department",
            field=models.BooleanField(
                default=False,
                verbose_name="Закреплено в ленте отдела",
            ),
        ),
        migrations.RunPython(
            copy_legacy_pin_to_global,
            migrations.RunPython.noop,
        ),
        migrations.AlterModelOptions(
            name="post",
            options={
                "ordering": ["-pinned_global", "-created_at"],
                "verbose_name": "Публикация",
                "verbose_name_plural": "Публикации",
            },
        ),
        migrations.RemoveIndex(
            model_name="post",
            name="feed_post_pinned_e86c9a_idx",
        ),
        migrations.AddIndex(
            model_name="post",
            index=models.Index(
                fields=["pinned_global", "created_at"],
                name="feed_post_pin_global_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="post",
            index=models.Index(
                fields=["pinned_department", "created_at"],
                name="feed_post_pin_department_idx",
            ),
        ),
    ]
