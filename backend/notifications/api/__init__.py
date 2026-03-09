"""
REST API для системы уведомлений

Endpoints:
- GET /api/v1/notifications/ - список уведомлений
- GET /api/v1/notifications/<id>/ - детали уведомления
- GET /api/v1/notifications/unread/count/ - счетчик непрочитанных
- GET /api/v1/notifications/verb-types/ - статистика по типам
- GET /api/v1/notifications/preferences/ - настройки каналов
- PUT /api/v1/notifications/preferences/ - обновить настройки
- POST /api/v1/notifications/<id>/read/ - отметить прочитанным
- POST /api/v1/notifications/<id>/unread/ - отметить непрочитанным
- DELETE /api/v1/notifications/<id>/ - удалить уведомление
- DELETE /api/v1/notifications/delete-all-read/ - удалить прочитанные
- POST /api/v1/notifications/push/subscribe/ - подписаться на push
- DELETE /api/v1/notifications/push/unsubscribe/ - отписаться от push
"""

__all__ = ['views', 'urls']
