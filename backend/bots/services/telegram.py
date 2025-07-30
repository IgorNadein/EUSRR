import os
import logging
from datetime import timedelta

from dotenv import load_dotenv

import django
from django.conf import settings
from django.db import models
from django.utils import timezone

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    FSInputFile,
)
from aiogram.exceptions import TelegramBadRequest
from asgiref.sync import sync_to_async
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from django.contrib.auth import get_user_model

from calendar_app.models import CompanyEvent
from bots.models import BotSubscriber
from bots.filters import IsBoundSubscriber_tg, IsEmployeeActive
from documents.models import Document, DocumentAcknowledgement

# Если запускается вне manage.py, настраиваем Django
if not settings.configured:
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
    django.setup()

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Загрузка .env
load_dotenv()
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Модель сотрудника
Employee = get_user_model()

# Отделы для inline‑меню
DEPARTMENTS = {
    "department_manager": {
        "title": "Менеджеры",
        "groups": [
            {"name": "Группа 1",    "link": "https://t.me/manager_group"},
            {"name": "Рабочий чат", "link": "https://t.me/manager_workchat"},
        ],
    },
    "department_tech": {
        "title": "Технари",
        "groups": [
            {"name": "Группа 1",    "link": "https://t.me/tech_group"},
            {"name": "Рабочий чат", "link": "https://t.me/tech_workchat"},
        ],
    },
}

# — Клавиатуры —


def get_contact_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[[
            KeyboardButton(text="📲 Поделиться контактом", request_contact=True)
        ]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def get_department_kb() -> InlineKeyboardMarkup:
    buttons = [
        InlineKeyboardButton(text=dept["title"], callback_data=key)
        for key, dept in DEPARTMENTS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=[buttons])


def main_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📅 Календарь",
                             callback_data="menu_calendar"),
        InlineKeyboardButton(text="📊 Статус",    callback_data="menu_status"),
        InlineKeyboardButton(text="📄 Документы", callback_data="menu_docs"),
    ]])


def department_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 На сегодня",
                              callback_data="cal_today")],
        [InlineKeyboardButton(text="🗓 На неделю",
                              callback_data="cal_week")],
        [InlineKeyboardButton(text="📆 На месяц",
                              callback_data="cal_month")],
        [InlineKeyboardButton(text="◀️ Главное меню",
                              callback_data="go_main")],
    ])


async def safe_edit(
    call: types.CallbackQuery,
    text: str,
    inline_kb: InlineKeyboardMarkup | None = None,
    **kwargs
):
    """
    Редактирует call.message:
    - если передан inline_kb — edit_text,
    - иначе — answer.
    """
    msg = call.message
    try:
        if inline_kb:
            await msg.edit_text(text, reply_markup=inline_kb, **kwargs)
        else:
            await msg.answer(text, **kwargs)
    except TelegramBadRequest as e:
        await call.answer(text=f"Загрузка...", cache_time=10)
        # await msg.answer(text, reply_markup=inline_kb, **kwargs)

# — ORM‑хелперы —


@sync_to_async
def find_employee_by_phone(phone: str):
    return Employee.objects.filter(telegram__endswith=phone[-10:]).first()


@sync_to_async
def find_employee_by_username(username: str):
    uname = username.lower().lstrip('@')
    return Employee.objects.filter(
        models.Q(telegram__iexact=uname) |
        models.Q(telegram__iexact='@' + uname)
    ).first()


@sync_to_async
def bind_telegram(user, tg_id: int):
    BotSubscriber.objects.filter(telegram_id=tg_id).exclude(user=user)\
                         .update(telegram_id=None)
    return BotSubscriber.objects.update_or_create(
        user=user, defaults={"telegram_id": tg_id}
    )


@sync_to_async
def _get_subscriber_user(tg_id: int):
    sub = BotSubscriber.objects.select_related("user")\
        .filter(telegram_id=tg_id).first()
    return sub.user if sub and sub.user else None


@sync_to_async
def _get_user_documents(user):
    from django.db.models import Q
    return list(
        Document.objects.filter(Q(sent_to_all=True) | Q(recipients=user))
        .distinct().order_by('-uploaded_at')
    )


@sync_to_async
def _has_acknowledged(user, document):
    return DocumentAcknowledgement.objects.filter(user=user, document=document).exists()


@sync_to_async
def _acknowledge(user, document):
    return DocumentAcknowledgement.objects.get_or_create(user=user, document=document)


@sync_to_async
def _get_one_time_events(date):
    return list(CompanyEvent.objects.filter(
        recurrence=CompanyEvent.ONE_TIME, date=date
    ))


@sync_to_async
def _get_annual_events():
    return list(CompanyEvent.objects.filter(recurrence=CompanyEvent.ANNUAL))


@sync_to_async
def _get_subscribers():
    return list(BotSubscriber.objects.filter(telegram_id__isnull=False))

# — Ежедневная рассылка —


async def send_daily_notifications():
    today = timezone.localdate()
    one_time = await _get_one_time_events(today)
    annual_all = await _get_annual_events()
    annual_today = [
        ev for ev in annual_all
        if (ev.date.month, ev.date.day) == (today.month, today.day)
    ]
    events = one_time + annual_today
    if not events:
        logger.info("Нет событий на сегодня.")
        return

    subs = await _get_subscribers()
    for sub in subs:
        for ev in events:
            text = (
                f"📅 *{ev.title}*\n"
                f"Дата: `{ev.date:%d.%m.%Y}`\n"
                f"{ev.description or ''}"
            )
            try:
                await bot.send_message(
                    sub.telegram_id,
                    text,
                    parse_mode="Markdown",
                )
            except:
                logger.exception(f"Не удалось отправить {sub.telegram_id}")

scheduler = AsyncIOScheduler(timezone=settings.TIME_ZONE)
scheduler.add_job(send_daily_notifications, "cron", hour=9, minute=0)


async def on_startup_dispatcher():
    logger.info("Запуск APScheduler…")
    scheduler.start()

dp.startup.register(on_startup_dispatcher)

# — Хендлеры бота —


@dp.message(CommandStart())
async def cmd_start(msg: types.Message):
    await msg.answer(
        "Здравствуйте! Чтобы подключиться, пожалуйста, поделитесь контактом:",
        reply_markup=get_contact_kb()
    )


@dp.message(lambda m: m.contact is not None)
async def on_contact(msg: types.Message):
    phone = msg.contact.phone_number
    tg_id = msg.from_user.id
    user = (
        await find_employee_by_phone(phone)
        or (msg.from_user.username and await find_employee_by_username(msg.from_user.username))
    )
    if not user:
        return await msg.answer("❌ Профиль не найден.")
    await bind_telegram(user, tg_id)
    await msg.answer(
        f"✅ Спасибо, {user.first_name}! Выберите отдел:",
        reply_markup=get_department_kb()
    )


@dp.callback_query(F.data.startswith("department_"), IsBoundSubscriber_tg(), IsEmployeeActive())
async def department_selected(call: types.CallbackQuery):
    dept = DEPARTMENTS.get(call.data)
    text = (
        f"*{dept['title']}*:\n" +
        "\n".join(f"• [{g['name']}]({g['link']})" for g in dept["groups"])
    ) if dept else "Неизвестный отдел."
    await safe_edit(call, text, inline_kb=main_menu_kb(), parse_mode="Markdown")
    await call.answer()


@dp.callback_query(F.data == "menu_calendar", IsBoundSubscriber_tg(), IsEmployeeActive())
async def menu_calendar(call: types.CallbackQuery):
    await safe_edit(call, "Выберите период для просмотра:", inline_kb=department_menu_kb())
    await call.answer()


@dp.callback_query(F.data == "menu_status", IsBoundSubscriber_tg(), IsEmployeeActive())
async def menu_status(call: types.CallbackQuery):
    user = await _get_subscriber_user(call.from_user.id)
    status = await sync_to_async(lambda u: u.employment_status)(user) if user else "неизвестен"
    text = f"Ваш статус: *{status}*"
    await safe_edit(call, text, inline_kb=main_menu_kb(), parse_mode="Markdown")
    # await call.answer(cache_time=60, text="Смотрите статус в сообщении")


@dp.callback_query(F.data == "cal_today", IsBoundSubscriber_tg(), IsEmployeeActive())
async def calendar_today(call: types.CallbackQuery):
    today = timezone.localdate()
    evs = (await _get_one_time_events(today)) + [
        ev for ev in await _get_annual_events()
        if (ev.date.month, ev.date.day) == (today.month, today.day)
    ]
    text = ("Событий на сегодня нет." if not evs
            else "📅 События сегодня:\n" + "\n".join(f"• {e.title} ({e.date:%d.%m})" for e in evs))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Главное меню", callback_data="go_main")
    ]])
    await safe_edit(call, text, inline_kb=kb)
    await call.answer()


@dp.callback_query(F.data == "cal_week", IsBoundSubscriber_tg(), IsEmployeeActive())
async def calendar_week(call: types.CallbackQuery):
    start, end = timezone.localdate(), timezone.localdate() + timedelta(days=6)
    one = await _get_one_time_events(start)
    ann = await _get_annual_events()
    evs = one + [
        ev for ev in ann
        if (start.month, start.day) <= (ev.date.month, ev.date.day) <= (end.month, end.day)
    ]
    text = ("Событий на эту неделю нет." if not evs
            else f"📅 С {start:%d.%m} по {end:%d.%m}:\n" + "\n".join(f"• {e.title} ({e.date:%d.%m})" for e in evs))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Главное меню", callback_data="go_main")
    ]])
    await safe_edit(call, text, inline_kb=kb)
    await call.answer()


@dp.callback_query(F.data == "cal_month", IsBoundSubscriber_tg(), IsEmployeeActive())
async def calendar_month(call: types.CallbackQuery):
    today = timezone.localdate()
    start = today.replace(day=1)
    nm = start.replace(month=(start.month % 12) + 1,
                       year=start.year + (start.month // 12))
    end = nm - timedelta(days=1)
    one = await _get_one_time_events(start)
    ann = await _get_annual_events()
    evs = one + [
        ev for ev in ann
        if (start.month, start.day) <= (ev.date.month, ev.date.day) <= (end.month, end.day)
    ]
    text = ("Событий в этом месяце нет." if not evs
            else f"📅 {today:%B %Y}:\n" + "\n".join(f"• {e.title} ({e.date:%d.%m})" for e in evs))
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="◀️ Главное меню", callback_data="go_main")
    ]])
    await safe_edit(call, text, inline_kb=kb)
    await call.answer()


@dp.callback_query(F.data == "go_main", IsBoundSubscriber_tg(), IsEmployeeActive())
async def go_main(call: types.CallbackQuery):
    await safe_edit(call, "Главное меню:", inline_kb=main_menu_kb())
    await call.answer()

# — Документы через бот —


@dp.callback_query(F.data == "menu_docs", IsBoundSubscriber_tg(), IsEmployeeActive())
async def menu_docs(call: types.CallbackQuery):
    user = await _get_subscriber_user(call.from_user.id)
    docs = await _get_user_documents(user) if user else []
    if not docs:
        text = "У вас нет доступных документов."
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="◀️ Главное меню",
                                 callback_data="go_main")
        ]])
    else:
        text = "📄 Ваши документы:\nВыберите для просмотра:"
        rows = [
            [InlineKeyboardButton(
                text=d.title[:30] + ("…" if len(d.title) > 30 else ""),
                callback_data=f"doc_{d.id}"
            )]
            for d in docs[:5]
        ]
        rows.append([InlineKeyboardButton(
            text="◀️ Главное меню", callback_data="go_main")])
        kb = InlineKeyboardMarkup(inline_keyboard=rows)

    await safe_edit(call, text, inline_kb=kb)
    await call.answer()


@dp.callback_query(F.data.startswith("doc_"), IsBoundSubscriber_tg(), IsEmployeeActive())
async def show_document(call: types.CallbackQuery):
    user = await _get_subscriber_user(call.from_user.id)
    doc_id = int(call.data.split("_", 1)[1])
    doc = await sync_to_async(Document.objects.get)(pk=doc_id)

    caption = (
        f"*{doc.title}*\n\n"
        f"{doc.description or ''}\n\n"
        f"Загружен: {doc.uploaded_at:%d.%m.%Y %H:%M}"
    )
    already = await _has_acknowledged(user, doc)

    rows = []
    if not already:
        rows.append([InlineKeyboardButton(
            text="✅ Ознакомился", callback_data=f"ack_{doc.id}")])
    rows.append([InlineKeyboardButton(
        text="◀️ Документы", callback_data="menu_docs")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)

    file_input = FSInputFile(
        path=doc.file.path, filename=os.path.basename(doc.file.name))
    await bot.send_document(
        chat_id=call.from_user.id,
        document=file_input,
        caption=caption,
        parse_mode="Markdown",
        reply_markup=kb
    )
    await call.answer()


@dp.callback_query(F.data.startswith("ack_"), IsBoundSubscriber_tg(), IsEmployeeActive())
async def ack_document(call: types.CallbackQuery):
    user = await _get_subscriber_user(call.from_user.id)
    doc_id = int(call.data.split("_", 1)[1])
    await _acknowledge(user, await sync_to_async(Document.objects.get)(pk=doc_id))

    old = call.message.reply_markup.inline_keyboard
    new = [row for row in old if not any(
        btn.callback_data == f"ack_{doc_id}" for btn in row)]
    kb = InlineKeyboardMarkup(inline_keyboard=new)

    await call.message.edit_reply_markup(reply_markup=kb)
    await call.answer("Ознакомление зафиксировано.")


def run_telegram_bot():
    dp.run_polling(bot)


if __name__ == "__main__":
    run_telegram_bot()
