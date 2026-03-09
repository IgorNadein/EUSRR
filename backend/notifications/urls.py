"""
URL routing для модуля notifications

Для обратной совместимости импортирует из api.urls
"""
from notifications.api.urls import urlpatterns, app_name  # noqa

__all__ = ['urlpatterns', 'app_name']
