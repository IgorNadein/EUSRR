"""Вспомогательный модуль для постановки LDAP-операций в очередь retry."""

import logging

logger = logging.getLogger(__name__)


def _enqueue(operation: str, model_name: str, object_pk, payload: dict):
    """Ставит неудавшуюся LDAP-операцию в очередь для отложенного retry.

    Создаёт запись LdapSyncQueue и сразу пытается запустить Celery-задачу.
    Если Celery недоступен — periodic task process_ldap_queue подберёт позже.
    """
    from employees.models import LdapSyncQueue

    item = LdapSyncQueue.objects.create(
        operation=operation,
        model_name=model_name,
        object_pk=str(object_pk),
        payload=payload,
    )

    try:
        from employees.tasks import process_ldap_queue_item
        process_ldap_queue_item.delay(item.pk)
    except Exception:
        pass  # Celery недоступен — periodic task подберёт позже

    logger.info(
        "Enqueued LDAP operation %s for %s:%s (queue_id=%d)",
        operation, model_name, object_pk, item.pk,
    )
    return item
