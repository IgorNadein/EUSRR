"""
Django сигналы для автоматической генерации уведомлений в модуле Requests.

Обрабатывает события:
- Новое заявление (для ответственных/руководителей)
- Одобрение/отклонение заявления
- Комментарий к заявлению
- Изменение статуса заявления
"""

import logging
from django.db.models.signals import m2m_changed, post_save, pre_save
from django.dispatch import receiver

from ..models import Request
from .handlers import notify_new_request, notify_status_change

logger = logging.getLogger(__name__)


# Флаг для отслеживания новых заявлений, ожидающих уведомления
_pending_new_requests = set()


def dispatch_pending_new_request_notifications(instance: Request) -> None:
    """Отправляет отложенные уведомления о новой заявке ровно один раз.

    Используется, когда recipients/cc_users выставляются пачкой в serializer
    и m2m-сигналы нужно временно подавить, чтобы не отправлять уведомление
    до установки полного списка адресатов.
    """
    if instance.id in _pending_new_requests:
        _pending_new_requests.discard(instance.id)
        notify_new_request(instance)


@receiver(post_save, sender=Request)
def create_request_notifications(sender, instance, created, **kwargs):
    """
    Создает уведомления при создании или изменении заявления.

    Обрабатывает:
     1. Новое заявление - помечаем для отправки уведомлений
         после установки recipients
    2. Изменение статуса - уведомление автору
    """
    try:
        request_obj = instance

        # Логирование для отладки
        logger.debug(
            f"[SIGNAL] create_request_notifications: created={created}, "
            f"status={request_obj.status}, id={request_obj.id}"
        )

        if created and request_obj.status != "draft":
            # Помечаем заявление как ожидающее отправки уведомлений
            # Уведомления будут отправлены после установки recipients через
            # m2m_changed
            logger.debug(
                f"[SIGNAL] Помечаем заявление #{request_obj.id} для отправки "
                f"уведомлений после установки recipients"
            )
            _pending_new_requests.add(request_obj.id)

        if not created:
            # Проверяем изменение статуса через сохраненный атрибут _old_status
            if hasattr(request_obj, "_old_status"):
                old_status = request_obj._old_status
                new_status = request_obj.status

                if old_status != new_status:
                    logger.info(
                        f"[SIGNAL] Статус изменен для заявления #{
                            request_obj.id
                        }: {old_status} → {new_status}"
                    )
                    # Отправляем уведомления напрямую.
                    # channels.py автоматически
                    # сделает асинхронную отправку через Celery
                    notify_status_change(request_obj, old_status, new_status)

    except Exception as e:
        logger.exception(f"[SIGNAL ERROR] create_request_notifications: {e}")


@receiver(pre_save, sender=Request)
def track_status_change(sender, instance, **kwargs):
    """
    Сохраняем старый статус перед обновлением для отслеживания изменений.
    """
    if instance.pk:
        try:
            old_instance = Request.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except Request.DoesNotExist:
            instance._old_status = None


@receiver(m2m_changed, sender=Request.recipients.through)
def notify_on_recipients_changed(sender, instance, action, **kwargs):
    """
    Отправляет уведомления о новом заявлении ПОСЛЕ установки recipients.

    Срабатывает когда recipients устанавливаются через .set(), .add() и т.д.
    """
    try:
        if getattr(instance, "_suppress_new_request_notifications", False):
            return
        # Проверяем что это завершение операции установки recipients
        if action == "post_add" and instance.id in _pending_new_requests:
            logger.info(
                f"[M2M_SIGNAL] Recipients установлены для заявления #{
                    instance.id
                }, "
                f"отправляем уведомления"
            )
            _pending_new_requests.discard(instance.id)

            # Отправляем уведомления напрямую - channels.py автоматически
            # сделает асинхронную отправку через Celery
            notify_new_request(instance)

    except Exception as e:
        logger.exception(f"[SIGNAL ERROR] notify_on_recipients_changed: {e}")


@receiver(m2m_changed, sender=Request.cc_users.through)
def notify_on_cc_users_changed(sender, instance, action, **kwargs):
    """
    Дополнительная проверка для cc_users.

    Если recipients не были установлены, но установлены cc_users,
    также отправляем уведомления.
    """
    try:
        if getattr(instance, "_suppress_new_request_notifications", False):
            return
        # Если это завершение добавления cc_users И заявление все еще ожидает
        # уведомлений
        if action == "post_add" and instance.id in _pending_new_requests:
            # Проверяем что recipients пусты (значит уведомления еще не
            # отправлены)
            if instance.recipients.count() == 0:
                logger.info(
                    f"[M2M_SIGNAL] CC users установлены для заявления #{
                        instance.id
                    } "
                    f"(без recipients), отправляем уведомления"
                )
                _pending_new_requests.discard(instance.id)

                # Отправляем уведомления напрямую - channels.py автоматически
                # сделает асинхронную отправку через Celery
                notify_new_request(instance)

    except Exception as e:
        logger.exception(f"[SIGNAL ERROR] notify_on_cc_users_changed: {e}")
