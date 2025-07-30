# from django.db.models.signals import post_save, m2m_changed
# from django.dispatch import receiver
# from .models import Document
# # from .tasks import send_document_to_recipients


# # @receiver(post_save, sender=Document)
# # def on_document_saved(sender, instance: Document, created, **kwargs):
# #     """
# #     При создании или обновлении документа — запускаем таск на рассылку.
# #     """
# #     # Можно ограничить только created==True, но чаще полезно:
# #     send_document_to_recipients(instance.id)


# # @receiver(m2m_changed, sender=Document.recipients.through)
# # def on_recipients_changed(sender, instance: Document, action, **kwargs):
# #     """
# #     Если поменялись получатели (m2m) — тоже пересылаем.
# #     """
# #     if action in ('post_add', 'post_remove', 'post_clear'):
# #         send_document_to_recipients(instance.id)


import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import Document
from .notification import notify_users_about_document

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Document)
def on_document_saved(sender, instance: Document, created, **kwargs):
    logger.info(f"[signals] Document Saved: id={instance.pk}, created={created}")
    try:
        notify_users_about_document(instance)
    except Exception as e:
        logger.exception(f"[signals] Error notifying users for document {instance.pk}: {e}")
