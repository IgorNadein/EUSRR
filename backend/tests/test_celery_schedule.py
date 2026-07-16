from django.conf import settings

from eusrr_backend.celery import app


def test_due_personnel_actions_are_scheduled():
    entry = settings.CELERY_BEAT_SCHEDULE["process-due-personnel-actions"]

    assert entry["task"] == "requests_app.tasks.process_due_personnel_actions"


def test_scheduled_tasks_are_registered():
    app.loader.import_default_modules()
    app.autodiscover_tasks(force=True)

    missing = [
        entry["task"]
        for entry in settings.CELERY_BEAT_SCHEDULE.values()
        if entry["task"] not in app.tasks
    ]

    assert missing == []
