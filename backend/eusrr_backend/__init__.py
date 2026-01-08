"""
Инициализация проекта EUSRR
"""
# Это гарантирует, что приложение Celery загружается при старте Django
from .celery import app as celery_app

__all__ = ('celery_app',)
