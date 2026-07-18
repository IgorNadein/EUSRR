from celery import shared_task

from tasks.notifications.handlers import dispatch_task_due_notifications


@shared_task(name="tasks.dispatch_task_due_notifications")
def dispatch_task_due_notifications_task():
    return dispatch_task_due_notifications()
