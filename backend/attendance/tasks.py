import logging

from celery import shared_task

from attendance.services import run_attendance_auto_sync

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def dispatch_attendance_auto_sync(self):
    """Periodic dispatcher for attendance auto-sync settings."""
    try:
        settings = run_attendance_auto_sync(force=False)
        return {
            "status": settings.last_status,
            "success": settings.last_success_count,
            "errors": settings.last_error_count,
        }
    except Exception as exc:
        logger.exception("Attendance auto-sync dispatcher failed: %s", exc)
        raise


@shared_task(bind=True)
def run_attendance_auto_sync_now(self):
    """Run attendance auto-sync immediately using the saved settings."""
    settings = run_attendance_auto_sync(force=True)
    return {
        "status": settings.last_status,
        "success": settings.last_success_count,
        "errors": settings.last_error_count,
    }
