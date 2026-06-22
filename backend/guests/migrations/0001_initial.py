from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


GUEST_ID_START = 900_000_000_000_001
GUEST_ID_MAX = 999_999_999_999_999


def create_guest_id_sequence(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE SEQUENCE IF NOT EXISTS guests_guest_id_seq
            START WITH 900000000000001
            INCREMENT BY 1
            MINVALUE 900000000000001
            MAXVALUE 999999999999999
            NO CYCLE
            """
        )


def drop_guest_id_sequence(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return
    with schema_editor.connection.cursor() as cursor:
        cursor.execute("DROP SEQUENCE IF EXISTS guests_guest_id_seq")


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ("documents", "0015_delete_documentcomment"),
        ("employees", "0053_cleanup_department_role_permissions"),
    ]

    operations = [
        migrations.RunPython(create_guest_id_sequence, drop_guest_id_sequence),
        migrations.CreateModel(
            name="Guest",
            fields=[
                ("id", models.BigIntegerField(editable=False, primary_key=True, serialize=False)),
                ("last_name", models.CharField(max_length=150, verbose_name="Фамилия")),
                ("first_name", models.CharField(max_length=150, verbose_name="Имя")),
                ("patronymic", models.CharField(blank=True, max_length=150, verbose_name="Отчество")),
                ("birth_date", models.DateField(blank=True, null=True, verbose_name="Дата рождения")),
                ("phone", models.CharField(blank=True, max_length=64, verbose_name="Телефон")),
                ("email", models.EmailField(blank=True, max_length=254, verbose_name="Email")),
                ("organization", models.CharField(blank=True, max_length=255, verbose_name="Организация")),
                ("position", models.CharField(blank=True, max_length=255, verbose_name="Должность")),
                ("comment", models.TextField(blank=True, verbose_name="Комментарий")),
                ("is_active", models.BooleanField(default=True, verbose_name="Активен")),
                ("ldap_enabled", models.BooleanField(default=False, verbose_name="LDAP в Active OU")),
                ("ldap_username", models.CharField(blank=True, max_length=150, verbose_name="LDAP username")),
                ("ldap_upn", models.CharField(blank=True, max_length=255, verbose_name="LDAP UPN")),
                ("ldap_last_synced_at", models.DateTimeField(blank=True, null=True, verbose_name="Последняя LDAP синхронизация")),
                ("ldap_last_error", models.TextField(blank=True, verbose_name="Последняя LDAP ошибка")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="created_guests", to=settings.AUTH_USER_MODEL, verbose_name="Создал")),
            ],
            options={
                "verbose_name": "Гость",
                "verbose_name_plural": "Гости",
                "ordering": ["last_name", "first_name", "id"],
            },
        ),
        migrations.CreateModel(
            name="GuestVisit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("inviter_snapshot_name", models.CharField(blank=True, max_length=255, verbose_name="ФИО приглашающего на момент создания")),
                ("inviter_snapshot_email", models.EmailField(blank=True, max_length=254, verbose_name="Email приглашающего на момент создания")),
                ("purpose", models.TextField(verbose_name="Цель приглашения")),
                ("visit_comment", models.TextField(blank=True, verbose_name="Комментарий заявителя")),
                ("admin_comment", models.TextField(blank=True, verbose_name="Комментарий администратора")),
                ("status", models.CharField(choices=[("draft", "Черновик"), ("pending", "На рассмотрении"), ("needs_info", "Требуется информация"), ("approved", "Одобрено"), ("rejected", "Отклонено"), ("cancelled", "Отменено"), ("expired", "Истекло"), ("revoked", "Отозвано")], db_index=True, default="draft", max_length=24, verbose_name="Статус")),
                ("access_starts_at", models.DateTimeField(blank=True, null=True, verbose_name="Начало доступа")),
                ("access_expires_at", models.DateTimeField(blank=True, null=True, verbose_name="Окончание доступа")),
                ("all_day", models.BooleanField(default=True, verbose_name="Полные сутки")),
                ("unlimited", models.BooleanField(default=False, verbose_name="Бессрочно")),
                ("submitted_at", models.DateTimeField(blank=True, null=True, verbose_name="Отправлено на рассмотрение")),
                ("decided_at", models.DateTimeField(blank=True, null=True, verbose_name="Решение принято")),
                ("decision_comment", models.TextField(blank=True, verbose_name="Комментарий к решению")),
                ("cancelled_at", models.DateTimeField(blank=True, null=True)),
                ("cancel_reason", models.TextField(blank=True)),
                ("revoked_at", models.DateTimeField(blank=True, null=True)),
                ("revoke_reason", models.TextField(blank=True)),
                ("expired_at", models.DateTimeField(blank=True, null=True)),
                ("inviter_inactive", models.BooleanField(db_index=True, default=False)),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Создано")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Обновлено")),
                ("cancelled_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="cancelled_guest_visits", to=settings.AUTH_USER_MODEL)),
                ("decided_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="decided_guest_visits", to=settings.AUTH_USER_MODEL, verbose_name="Решение принял")),
                ("documents", models.ManyToManyField(blank=True, related_name="guest_visits", to="documents.document", verbose_name="Документы")),
                ("guest", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="visits", to="guests.guest", verbose_name="Гость")),
                ("host_department", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="guest_visits", to="employees.department", verbose_name="Отдел приглашающего")),
                ("inviter", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="guest_visits", to=settings.AUTH_USER_MODEL, verbose_name="Приглашающий")),
                ("revoked_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="revoked_guest_visits", to=settings.AUTH_USER_MODEL)),
            ],
            options={
                "verbose_name": "Гостевой визит",
                "verbose_name_plural": "Гостевые визиты",
                "ordering": ["-created_at"],
                "permissions": [("view_all_guestvisit", "Может просматривать все гостевые визиты"), ("decide_guestvisit", "Может принимать решения по гостевым визитам"), ("manage_guestaccount", "Может управлять гостевыми учетками")],
            },
        ),
        migrations.CreateModel(
            name="GuestVisitEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("event_type", models.CharField(choices=[("created", "Создано"), ("submitted", "Отправлено"), ("needs_info_requested", "Запрошена информация"), ("info_provided", "Информация предоставлена"), ("approved", "Одобрено"), ("rejected", "Отклонено"), ("decision_changed", "Решение изменено"), ("cancelled", "Отменено"), ("revoked", "Отозвано"), ("expired", "Истекло"), ("ldap_created", "LDAP создан"), ("ldap_updated", "LDAP обновлен"), ("ldap_enabled", "LDAP перемещен в Active OU"), ("ldap_disabled", "LDAP перемещен в Deactivated OU"), ("ldap_failed", "Ошибка LDAP"), ("ldap_skipped", "LDAP пропущен"), ("document_attached", "Документ прикреплен"), ("document_removed", "Документ удален"), ("inviter_inactive_detected", "Приглашающий неактивен")], db_index=True, max_length=48, verbose_name="Тип события")),
                ("from_status", models.CharField(blank=True, max_length=24)),
                ("to_status", models.CharField(blank=True, max_length=24)),
                ("comment", models.TextField(blank=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("actor", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="guest_visit_events", to=settings.AUTH_USER_MODEL, verbose_name="Автор события")),
                ("visit", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="guests.guestvisit", verbose_name="Визит")),
            ],
            options={
                "verbose_name": "Событие гостевого визита",
                "verbose_name_plural": "События гостевых визитов",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.AddIndex(model_name="guest", index=models.Index(fields=["last_name", "first_name"], name="guest_name_idx")),
        migrations.AddIndex(model_name="guest", index=models.Index(fields=["email"], name="guest_email_idx")),
        migrations.AddIndex(model_name="guest", index=models.Index(fields=["phone"], name="guest_phone_idx")),
        migrations.AddIndex(model_name="guest", index=models.Index(fields=["ldap_enabled"], name="guest_ldap_enabled_idx")),
        migrations.AddConstraint(model_name="guest", constraint=models.CheckConstraint(condition=models.Q(("id__gte", GUEST_ID_START), ("id__lte", GUEST_ID_MAX)), name="guest_id_in_guest_range")),
        migrations.AddIndex(model_name="guestvisit", index=models.Index(fields=["status", "created_at"], name="guestvisit_status_created_idx")),
        migrations.AddIndex(model_name="guestvisit", index=models.Index(fields=["inviter", "created_at"], name="guestvisit_inviter_created_idx")),
        migrations.AddIndex(model_name="guestvisit", index=models.Index(fields=["access_starts_at", "access_expires_at"], name="guestvisit_access_idx")),
        migrations.AddIndex(model_name="guestvisit", index=models.Index(fields=["guest", "status"], name="guestvisit_guest_status_idx")),
        migrations.AddConstraint(model_name="guestvisit", constraint=models.CheckConstraint(condition=models.Q(("unlimited", True), ("access_expires_at__isnull", True), ("access_starts_at__isnull", True), ("access_starts_at__lt", models.F("access_expires_at")), _connector="OR"), name="guest_visit_access_range_valid")),
        migrations.AddIndex(model_name="guestvisitevent", index=models.Index(fields=["visit", "-created_at"], name="guestevent_visit_created_idx")),
        migrations.AddIndex(model_name="guestvisitevent", index=models.Index(fields=["event_type", "-created_at"], name="guestevent_type_created_idx")),
    ]
