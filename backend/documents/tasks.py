# # import os
# # from dotenv import load_dotenv
# # from asgiref.sync import async_to_sync

# # from aiogram import Bot
# # from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# # from .models import Document
# # from django.contrib.auth import get_user_model
# # from bots.models import BotSubscriber
# # import logging

# # logger = logging.getLogger(__name__)


# # load_dotenv()
# # BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# # User = get_user_model()
# # telegram_bot = Bot(token=BOT_TOKEN)


# # def send_document_to_recipients(document_id: int):
# #     """
# #     Уведомляем в Telegram о появлении нового документа:
# #     — всем активным, если sent_to_all=True,
# #     — или тем, кто в recipients.
# #     """
# #     try:
# #         doc = Document.objects.get(pk=document_id)
# #     except Document.DoesNotExist:
# #         return

# #     # собираем подписчиков
# #     if doc.sent_to_all:
# #         subs = BotSubscriber.objects.filter(
# #             telegram_id__isnull=False,
# #             user__is_active=True
# #         )
# #     else:
# #         subs = BotSubscriber.objects.filter(
# #             telegram_id__isnull=False,
# #             user__in=doc.recipients.filter(is_active=True)
# #         )

# #     if not subs.exists():
# #         return

# #     # клавиатура: ведёт пользователя в бот, в раздел «Документы»
# #     kb = InlineKeyboardMarkup(inline_keyboard=[[
# #         InlineKeyboardButton(text="📄 Открыть документы",
# #                              callback_data="menu_docs")
# #     ]])

# #     text = (
# #         f"🆕 *Новый документ*: {doc.title}\n\n"
# #         f"{doc.description or ''}\n\n"
# #         f"Зайдите в раздел «Документы» в боте, чтобы скачать файл."
# #     )

# #     # шлём всем подписчикам
# #     for sub in subs:
# #         try:
# #             async_to_sync(telegram_bot.send_message)(
# #                 chat_id=sub.telegram_id,
# #                 text=text,
# #                 parse_mode="Markdown",
# #                 disable_web_page_preview=True,
# #                 reply_markup=kb,
# #             )
# #         except Exception as e:
# #             # Записываем в лог, на каком именно подписчике и с каким текстом упало
# #             logger.error(
# #                 f"[Telegram] Ошибка при отправке документу={doc.pk} "
# #                 f"пользователю={sub.user.pk} tg_id={sub.telegram_id}: {e}",
# #                 exc_info=True
# #             )
# #         else:
# #             logger.info(
# #                 f"[Telegram] Уведомление по документу={doc.pk} "
# #                 f"успешно отправлено пользователю={sub.user.pk}"
# #             )


# # documents/tasks.py
# import os
# from dotenv import load_dotenv
# from celery import shared_task
# from django.conf import settings
# from django.urls import reverse
# from django.utils import timezone
# from telegram import Bot as TgBot, InlineKeyboardButton, InlineKeyboardMarkup

# from .models import Document
# from django.contrib.auth import get_user_model
# from bots.models import BotSubscriber
# import logging

# logger = logging.getLogger(__name__)

# load_dotenv()
# TG_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN') or settings.TELEGRAM_BOT_TOKEN

# User = get_user_model()


# # @shared_task(bind=True, name="documents.send_document_to_recipients")
# def send_document_to_recipients(document_id):
#     try:
#         doc = Document.objects.get(pk=document_id)
#     except Document.DoesNotExist:
#         return

#     # Собираем подписчиков
#     if doc.sent_to_all:
#         subs = BotSubscriber.objects.filter(
#             telegram_id__isnull=False,
#             user__is_active=True,
#         )
#     else:
#         subs = BotSubscriber.objects.filter(
#             telegram_id__isnull=False,
#             user__in=doc.recipients.filter(is_active=True),
#         )
#     if not subs.exists():
#         return

#     # Синхронный телеграм-бот
#     bot = TgBot(token=TG_TOKEN)

#     # Кнопка «Открыть документы»
#     kb = InlineKeyboardMarkup(
#         [[ InlineKeyboardButton("📄 Открыть документы", callback_data="menu_docs") ]]
#     )

#     # Текст уведомления
#     text = (
#         f"🆕 *Новый документ*: {doc.title}\n\n"
#         f"{doc.description or ''}\n\n"
#         f"Дата публикации: {doc.uploaded_at.strftime('%d.%m.%Y %H:%M')}"
#     )

#     # for sub in subs:
#     #     try:
#     #         bot.send_message(
#     #             chat_id=sub.telegram_id,
#     #             text=text,
#     #             parse_mode="Markdown",
#     #             reply_markup=kb,
#     #             disable_web_page_preview=True
#     #         )
#     #     except Exception as e:
#     #         print(e)
#             # логируем, чтобы понимать, кому не дошло
#             # self.retry(exc=e, countdown=60, max_retries=3)

#     for sub in subs:
#         try:
#             bot.send_message(
#                 chat_id=sub.telegram_id,
#                 text=text,
#                 parse_mode="Markdown",
#                 disable_web_page_preview=True,
#                 reply_markup=kb,
#             )
#         except Exception as e:
#             # Записываем в лог, на каком именно подписчике и с каким текстом упало
#             logger.error(
#                 f"[Telegram] Ошибка при отправке документу={doc.pk} "
#                 f"пользователю={sub.user.pk} tg_id={sub.telegram_id}: {e}",
#                 exc_info=True
#             )
#         else:
#             logger.info(
#                 f"[Telegram] Уведомление по документу={doc.pk} "
#                 f"успешно отправлено пользователю={sub.user.pk}"
#             )
