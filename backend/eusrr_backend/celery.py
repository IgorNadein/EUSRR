"""
Конфигурация Celery для проекта EUSRR
"""
import os
from celery import Celery

# Устанавливаем настройки Django по умолчанию
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')

app = Celery('eusrr_backend')

# Загружаем конфигурацию из Django settings
# namespace='CELERY' означает что все настройки Celery в settings.py
# должны начинаться с префикса CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Автоматически находит tasks.py в каждом приложении
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Тестовая задача для проверки работоспособности Celery"""
    print(f'Request: {self.request!r}')
