import os
import logging

# from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from asgiref.sync import async_to_sync

from bots.models import BotSubscriber

logger = logging.getLogger(__name__)
TG_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')


def notify_users_about_document(doc):
    """
    Синхронная рассылка в Telegram при появлении 
    нового/обновлении существующего документа.
    """
    logger.info(
        f"[notify] Start notifying for Document id={doc.pk} title={doc.title!r}")

    # Список подписчиков
    if doc.sent_to_all:
        subs_qs = BotSubscriber.objects.filter(
            telegram_id__isnull=False,
            user__is_active=True
        )
    else:
        subs_qs = BotSubscriber.objects.filter(
            telegram_id__isnull=False,
            user__in=doc.recipients.filter(is_active=True)
        )

    count = subs_qs.count()
    logger.info(
        f"[notify] Found {count} subscribers (sent_to_all={doc.sent_to_all})")
    if count == 0:
        return

    # Telegram Bot
    telegram_bot = Bot(token=TG_TOKEN)

    # клавиатура: ведёт пользователя в бот, в раздел «Документы»
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📄 Открыть документы",
                             callback_data="menu_docs")
    ]])

    text = (
        f"🆕 *Новый документ*: {doc.title}\n\n"
        f"{doc.description or ''}\n\n"
        f"Зайдите в раздел «Документы» в боте, чтобы скачать файл."
    )
    # шлём всем подписчикам
    for sub in subs_qs:
        try:
            async_to_sync(telegram_bot.send_message)(
                chat_id=sub.telegram_id,
                text=text,
                parse_mode="Markdown",
                disable_web_page_preview=True,
                reply_markup=kb,
            )
        except Exception as e:
            # Записываем в лог, на каком именно подписчике и с каким текстом упало
            logger.error(
                f"[Telegram] Ошибка при отправке документу={doc.pk} "
                f"пользователю={sub.user.pk} tg_id={sub.telegram_id}: {e}",
                exc_info=True
            )
        else:
            logger.info(
                f"[Telegram] Уведомление по документу={doc.pk} "
                f"успешно отправлено пользователю={sub.user.pk}"
            )



    # # Шлём каждому
    # for sub in subs_qs:
    #     tg_id = sub.telegram_id
    #     try:
    #         logger.info(f"[notify] Sending to tg_id={tg_id}")
    #         telegram_bot.send_message(
    #             chat_id=tg_id,
    #             text=text,
    #             parse_mode="Markdown",
    #             reply_markup=kb,
    #             disable_web_page_preview=True
    #         )
    #         logger.info(f"[notify]  → OK for tg_id={tg_id}")
    #     except Exception as e:
    #         logger.error(
    #             f"[notify]  → FAILED for tg_id={tg_id}: {e}", exc_info=True)

    # logger.info(f"[notify] Done notifying for Document id={doc.pk}")
