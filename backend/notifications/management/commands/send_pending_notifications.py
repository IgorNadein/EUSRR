"""
DEPRECATED V2.0:
Эта команда больше не используется в v2.

В v2 уведомления отправляются автоматически через:
- notifications.channels.py (post_save сигнал)
- Celery задачи: send_notification_task.delay()

Если нужно переотправить уведомление вручную:
    from notifications.tasks.base import send_notification_task
    send_notification_task.delay(notification_id=123)

Для массовой отправки см. документацию в backend/notifications/README.md
"""

import logging
from django.core.management.base import BaseCommand

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "[DEPRECATED] Команда удалена в v2.0 - см. docstring"

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.WARNING(
                "[DEPRECATED] Команда send_pending_notifications "
                "удалена в v2.0\n"
                "Уведомления отправляются автоматически через Celery.\n"
                "См. backend/notifications/README.md "
                "для деталей."
            )
        )
        return
