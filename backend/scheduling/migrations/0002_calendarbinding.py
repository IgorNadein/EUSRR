from collections import defaultdict

from django.db import migrations, models
import django.db.models.deletion


def backfill_calendar_bindings(apps, schema_editor):
    Calendar = apps.get_model("schedule", "Calendar")
    CalendarBinding = apps.get_model("scheduling", "CalendarBinding")
    ContentType = apps.get_model("contenttypes", "ContentType")
    Department = apps.get_model("employees", "Department")

    department_ct, _ = ContentType.objects.get_or_create(
        app_label="employees",
        model="department",
    )
    department_ids = set(Department.objects.values_list("id", flat=True))

    table_names = set(schema_editor.connection.introspection.table_names())
    legacy_department_map = {}
    if "calendar_app_calendar" in table_names:
        with schema_editor.connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, owner_department_id
                FROM calendar_app_calendar
                WHERE owner_department_id IS NOT NULL
                """
            )
            legacy_department_map = {
                old_id: department_id
                for old_id, department_id in cursor.fetchall()
                if department_id in department_ids
            }

    candidates = defaultdict(list)
    for calendar in Calendar.objects.all().order_by("-id"):
        slug = calendar.slug or ""
        department_id = None
        priority = None

        if slug.startswith("legacy-calendar-"):
            try:
                legacy_id = int(slug.removeprefix("legacy-calendar-"))
            except ValueError:
                legacy_id = None
            if legacy_id is not None:
                department_id = legacy_department_map.get(legacy_id)
                priority = 0 if department_id is not None else None
        elif slug.startswith("department-"):
            tail = slug.removeprefix("department-")
            if tail.isdigit():
                department_id = int(tail)
                if department_id in department_ids:
                    priority = 1

        if department_id is None or priority is None:
            continue

        candidates[department_id].append((priority, calendar.id))

    for department_id, rows in candidates.items():
        priority, calendar_id = sorted(rows, key=lambda item: (item[0], -item[1]))[0]
        CalendarBinding.objects.get_or_create(
            calendar_id=calendar_id,
            defaults={
                "type": "department",
                "context_content_type_id": department_ct.id,
                "context_object_id": department_id,
            },
        )


class Migration(migrations.Migration):

    dependencies = [
        ("contenttypes", "0002_remove_content_type_name"),
        ("employees", "0047_alter_departmentpermission_code"),
        ("schedule", "0015_rename_indexes"),
        ("scheduling", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="CalendarBinding",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "type",
                    models.CharField(
                        choices=[
                            ("default", "Обычный"),
                            ("department", "Отдел"),
                        ],
                        db_index=True,
                        default="default",
                        max_length=32,
                        verbose_name="Тип привязки",
                    ),
                ),
                (
                    "context_object_id",
                    models.PositiveIntegerField(
                        blank=True,
                        null=True,
                        verbose_name="ID объекта контекста",
                    ),
                ),
                (
                    "flags",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        verbose_name="Флаги",
                    ),
                ),
                (
                    "extra_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        verbose_name="Доп. данные",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "calendar",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="binding",
                        to="schedule.calendar",
                        verbose_name="Календарь",
                    ),
                ),
                (
                    "context_content_type",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        to="contenttypes.contenttype",
                        verbose_name="Тип контекста",
                    ),
                ),
            ],
            options={
                "verbose_name": "Привязка календаря",
                "verbose_name_plural": "Привязки календарей",
            },
        ),
        migrations.AddIndex(
            model_name="calendarbinding",
            index=models.Index(
                fields=["type"], name="calendar_binding_type_idx"
            ),
        ),
        migrations.AddIndex(
            model_name="calendarbinding",
            index=models.Index(
                fields=["context_content_type", "context_object_id"],
                name="calendar_binding_context_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="calendarbinding",
            constraint=models.UniqueConstraint(
                condition=models.Q(
                    ("context_content_type__isnull", False),
                    ("context_object_id__isnull", False),
                    ("type", "department"),
                ),
                fields=("type", "context_content_type", "context_object_id"),
                name="uniq_department_calendar_binding",
            ),
        ),
        migrations.RunPython(
            backfill_calendar_bindings,
            migrations.RunPython.noop,
        ),
    ]
