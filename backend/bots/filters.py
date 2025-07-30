# bots/filters.py
from aiogram import types, F
from aiogram.filters import BaseFilter
from asgiref.sync import sync_to_async
from bots.models import BotSubscriber


class IsBoundSubscriber_tg(BaseFilter):
    """
    Пропускает только тех, чей telegram_id уже привязан.
    """

    async def __call__(self, event: types.Message | types.CallbackQuery) -> bool:
        user_id = event.from_user.id
        return await sync_to_async(
            BotSubscriber.objects.filter(telegram_id=user_id).exists
        )()


class IsEmployeeActive(BaseFilter):
    """
    Пропускает только работающих сотрудников
    (последний кадровый статус — активный).
    """

    async def __call__(self, event: types.Message | types.CallbackQuery) -> bool:
        user_id = event.from_user.id

        # Получаем подписчика вместе с юзером
        subscriber = await sync_to_async(
            lambda: BotSubscriber.objects.select_related('user')
            .filter(telegram_id=user_id)
            .first()
        )()

        if not subscriber or not subscriber.user:
            return False

        # Проверяем свойство is_actually_active у Employee
        return await sync_to_async(lambda u: u.is_actually_active)(subscriber.user)
