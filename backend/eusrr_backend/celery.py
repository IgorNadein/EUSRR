"""
Конфигурация Celery для проекта EUSRR
"""
import os
from celery import Celery
from celery.schedules import crontab

# Устанавливаем настройки Django по умолчанию
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')

app = Celery('eusrr_backend')

# Загружаем конфигурацию из Django settings
# namespace='CELERY' означает что все настройки Celery в settings.py
# должны начинаться с префикса CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматически находит tasks.py в каждом приложении
app.autodiscover_tasks()

# Periodic tasks (Celery Beat)
app.conf.beat_schedule = {
    'cleanup-missed-returns': {
        'task': 'requests_app.tasks.cleanup_missed_returns',
        'schedule': crontab(hour=0, minute=5),  # Каждый день в 00:05
    },
    'process-due-personnel-actions': {
        'task': 'requests_app.tasks.process_due_personnel_actions',
        'schedule': crontab(hour=0, minute=10),  # Каждый день в 00:10
    },
    'attendance-auto-sync-dispatcher': {
        'task': 'attendance.tasks.dispatch_attendance_auto_sync',
        'schedule': 60.0,
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Тестовая задача для проверки работоспособности Celery"""
    print(f'Request: {self.request!r}')
