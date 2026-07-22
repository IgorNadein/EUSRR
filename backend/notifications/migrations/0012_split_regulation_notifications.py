from django.db import migrations


DOCUMENT_TO_REGULATION_VERBS = {
    "document_ready": "regulation_ready",
    "document_signed_all": "regulation_signed_all",
    "document_comment": "regulation_comment",
    "document_comment_reply": "regulation_comment_reply",
}


def _regulation_metadata(document):
    if (
        document.acknowledgement_required
        and not document.acknowledgement_for_all
    ):
        departments = document.acknowledgement_departments.all()
    elif not document.sent_to_all:
        departments = document.departments.all()
    else:
        departments = document.departments.none()

    department_rows = list(
        departments.order_by("name", "id").values("id", "name")
    )
    if department_rows:
        scope = "department"
    elif document.sent_to_all:
        scope = "company"
    else:
        scope = "personal"

    return {
        "is_regulation": True,
        "regulation_scope": scope,
        "regulation_department_ids": [row["id"] for row in department_rows],
        "regulation_department_names": [
            row["name"] for row in department_rows
        ],
    }


def split_existing_regulation_notifications(apps, schema_editor):
    Document = apps.get_model("documents", "Document")
    Notification = apps.get_model("notifications", "Notification")
    UserChannelPreferences = apps.get_model(
        "notifications",
        "UserChannelPreferences",
    )

    regulations = {
        str(document.pk): (
            document.pk,
            _regulation_metadata(document),
        )
        for document in Document.objects.filter(is_regulation=True).iterator()
    }
    pending = []
    notifications = Notification.objects.filter(
        verb__in=DOCUMENT_TO_REGULATION_VERBS,
    ).only(
        "id",
        "verb",
        "data",
        "description",
        "action_url",
        "action_object_object_id",
    )

    for notification in notifications.iterator():
        data = notification.data if isinstance(notification.data, dict) else {}
        document_id = data.get("document_id")
        regulation = regulations.get(str(document_id))
        if regulation is None:
            regulation = regulations.get(
                str(notification.action_object_object_id)
            )
        if regulation is None:
            continue

        resolved_document_id, metadata = regulation
        notification.verb = DOCUMENT_TO_REGULATION_VERBS[notification.verb]
        title = data.get("title")
        if isinstance(title, str):
            title = title.replace("Документ", "Регламент").replace(
                "документ",
                "регламент",
            )
        notification.data = {
            **data,
            **({"title": title} if isinstance(title, str) else {}),
            **metadata,
        }
        if notification.description:
            notification.description = (
                notification.description
                .replace("загрузил документ", "опубликовал регламент")
                .replace("Документ", "Регламент")
                .replace("документом", "регламентом")
                .replace("документ", "регламент")
            )
        notification.action_url = (
            "/documents?section=regulations"
            f"&document={resolved_document_id}"
        )
        pending.append(notification)

    if pending:
        Notification.objects.bulk_update(
            pending,
            ["verb", "data", "description", "action_url"],
            batch_size=500,
        )

    preferences_to_update = []
    for preferences in UserChannelPreferences.objects.only(
        "id",
        "disabled_verbs",
    ).iterator():
        disabled_verbs = list(preferences.disabled_verbs or [])
        changed = False
        for document_verb, regulation_verb in (
            DOCUMENT_TO_REGULATION_VERBS.items()
        ):
            if (
                document_verb in disabled_verbs
                and regulation_verb not in disabled_verbs
            ):
                disabled_verbs.append(regulation_verb)
                changed = True
        if changed:
            preferences.disabled_verbs = disabled_verbs
            preferences_to_update.append(preferences)

    if preferences_to_update:
        UserChannelPreferences.objects.bulk_update(
            preferences_to_update,
            ["disabled_verbs"],
            batch_size=500,
        )


def merge_regulation_notifications_back(apps, schema_editor):
    Notification = apps.get_model("notifications", "Notification")
    UserChannelPreferences = apps.get_model(
        "notifications",
        "UserChannelPreferences",
    )
    reverse_verbs = {
        regulation_verb: document_verb
        for document_verb, regulation_verb in (
            DOCUMENT_TO_REGULATION_VERBS.items()
        )
    }
    pending = []
    for notification in Notification.objects.filter(
        verb__in=reverse_verbs,
    ).only("id", "verb", "data", "action_url").iterator():
        data = notification.data if isinstance(notification.data, dict) else {}
        for key in (
            "is_regulation",
            "regulation_scope",
            "regulation_department_ids",
            "regulation_department_names",
        ):
            data.pop(key, None)
        notification.verb = reverse_verbs[notification.verb]
        notification.data = data
        notification.action_url = "/documents"
        pending.append(notification)

    if pending:
        Notification.objects.bulk_update(
            pending,
            ["verb", "data", "action_url"],
            batch_size=500,
        )

    preferences_to_update = []
    for preferences in UserChannelPreferences.objects.only(
        "id",
        "disabled_verbs",
    ).iterator():
        disabled_verbs = list(preferences.disabled_verbs or [])
        filtered_verbs = [
            verb for verb in disabled_verbs if verb not in reverse_verbs
        ]
        if filtered_verbs != disabled_verbs:
            preferences.disabled_verbs = filtered_verbs
            preferences_to_update.append(preferences)

    if preferences_to_update:
        UserChannelPreferences.objects.bulk_update(
            preferences_to_update,
            ["disabled_verbs"],
            batch_size=500,
        )


class Migration(migrations.Migration):
    dependencies = [
        ("documents", "0017_document_acknowledgement_audience"),
        ("notifications", "0011_initial"),
    ]

    operations = [
        migrations.RunPython(
            split_existing_regulation_notifications,
            merge_regulation_notifications_back,
        ),
    ]
