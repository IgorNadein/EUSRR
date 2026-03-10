"""
Приложение scheduling - интеграция и расширение django-scheduler.

Содержит:
- Патчи для исправления багов django-scheduler
- Систему уведомлений для событий календаря
- Правила доступа (django-rules)
"""

default_app_config = 'scheduling.apps.SchedulingConfig'
