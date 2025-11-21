"""
Telegram sender для отправки уведомлений через Telegram бот
"""
import logging
from typing import Optional
import asyncio

from django.conf import settings
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)


class TelegramNotificationSender:
    """
    Класс для отправки уведомлений через Telegram бот.
    """
    
    # Маппинг категорий на emoji
    CATEGORY_EMOJI = {
        'communications': '💬',
        'documents': '📄',
        'requests': '📋',
        'calendar': '📅',
        'department': '👥',
        'profile': '👤',
        'feed': '📰',
        'system': '⚙️',
    }
    
    @classmethod
    def get_bot(cls) -> Optional[Bot]:
        """Получить экземпляр бота"""
        token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
        if not token:
            logger.error("TELEGRAM_BOT_TOKEN не настроен в settings")
            return None
        
        return Bot(token=token)
    
    @classmethod
    async def send_notification_async(
        cls,
        telegram_id: int,
        notification,
        site_url: str = None
    ) -> bool:
        """
        Асинхронная отправка уведомления в Telegram
        
        Args:
            telegram_id: ID пользователя в Telegram
            notification: объект Notification
            site_url: базовый URL сайта
            
        Returns:
            True если отправлено успешно, False иначе
        """
        bot = cls.get_bot()
        if not bot:
            return False
        
        try:
            # Получаем категорию
            category_code = notification.notification_type.category.code
            category_name = notification.notification_type.category.name
            emoji = cls.CATEGORY_EMOJI.get(category_code, '🔔')
            
            # Формируем текст сообщения
            text = f"{emoji} <b>{notification.title}</b>\n\n"
            text += f"{notification.message}\n\n"
            text += f"<i>Категория: {category_name}</i>"
            
            # Создаем кнопку действия если есть URL
            keyboard = None
            if notification.action_url:
                action_text = notification.action_text or 'Посмотреть'
                
                # Формируем полный URL
                if site_url:
                    if notification.action_url.startswith('http'):
                        url = notification.action_url
                    else:
                        # Убираем trailing slash из site_url если есть
                        base_url = site_url.rstrip('/')
                        url = f"{base_url}{notification.action_url}"
                else:
                    url = notification.action_url
                
                # Telegram не принимает:
                # 1. URL вида "http://site.com/" (только корень)
                # 2. localhost URL в inline кнопках
                url_without_trailing = url.rstrip('/')
                base_without_trailing = (
                    site_url.rstrip('/') if site_url else ''
                )
                
                is_valid_url = (
                    url_without_trailing and
                    url_without_trailing != base_without_trailing and
                    'localhost' not in url.lower() and
                    '127.0.0.1' not in url
                )
                
                if is_valid_url:
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(action_text, url=url)]
                    ])
                elif 'localhost' in url.lower() or '127.0.0.1' in url:
                    # Добавляем URL в текст сообщения
                    text += f"\n\n🔗 Ссылка: {url}"
            
            # Отправляем сообщение
            await bot.send_message(
                chat_id=telegram_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
            
            logger.info(
                f"Telegram уведомление отправлено: {notification.id} -> {telegram_id}"
            )
            return True
            
        except TelegramError as e:
            error_msg = str(e)
            
            # Обработка специфичных ошибок
            if "chat not found" in error_msg.lower():
                logger.warning(
                    f"Пользователь с Chat ID {telegram_id} не отправил /start боту"
                )
            elif "bot was blocked" in error_msg.lower() or "forbidden" in error_msg.lower():
                logger.warning(
                    f"Пользователь с Chat ID {telegram_id} заблокировал бота"
                )
            else:
                logger.error(
                    f"Ошибка отправки Telegram уведомления {notification.id}: {e}",
                    exc_info=True
                )
            
            return False
        
        except Exception as e:
            logger.error(
                f"Неожиданная ошибка отправки Telegram: {e}",
                exc_info=True
            )
            return False
    
    @classmethod
    def send_notification(
        cls,
        notification,
        chat_id: Optional[str] = None,
        site_url: str = None
    ) -> bool:
        """
        Синхронная обёртка для отправки уведомления
        
        Args:
            notification: объект Notification
            chat_id: Telegram Chat ID получателя (строка или число)
            site_url: базовый URL сайта
            
        Returns:
            True если отправлено успешно, False иначе
        """
        # Преобразуем chat_id в int
        if not chat_id:
            logger.warning(
                f"Chat ID не указан для {notification.recipient}"
            )
            return False
        
        try:
            telegram_id = int(chat_id)
        except (ValueError, TypeError):
            logger.error(
                f"Неверный формат Chat ID: {chat_id}"
            )
            return False
        
        # Получить site_url если не передан
        if not site_url:
            site_url = getattr(settings, 'SITE_URL', 'http://localhost:9000')
        
        # Запускаем асинхронную отправку
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            cls.send_notification_async(
                telegram_id,
                notification,
                site_url
            )
        )
    
    @classmethod
    def send_notification_by_username(
        cls,
        notification,
        telegram_username: str,
        site_url: str = None
    ) -> bool:
        """
        Отправка уведомления по @username без привязки аккаунта
        
        Args:
            notification: объект Notification
            telegram_username: @username или chat_id
            site_url: базовый URL сайта
            
        Returns:
            True если отправлено успешно
        """
        if not site_url:
            site_url = getattr(settings, 'SITE_URL', 'http://localhost:9000')
        
        # Убираем @ если есть
        username = telegram_username.strip().lstrip('@')
        
        # Пробуем отправить по username
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        async def send_by_username():
            bot = cls.get_bot()
            if not bot:
                return False
            
            try:
                # Формируем сообщение
                category_code = notification.notification_type.category.code
                emoji = cls.CATEGORY_EMOJI.get(category_code, '🔔')
                
                text = f"{emoji} <b>{notification.title}</b>\n\n"
                text += f"{notification.message}\n\n"
                
                # Кнопка действия
                keyboard = None
                if notification.action_url:
                    action_text = notification.action_text or 'Посмотреть'
                    if notification.action_url.startswith('http'):
                        url = notification.action_url
                    else:
                        url = f"{site_url}{notification.action_url}"
                    
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton(action_text, url=url)]
                    ])
                
                # Отправляем по @username
                await bot.send_message(
                    chat_id=f"@{username}",
                    text=text,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard,
                    disable_web_page_preview=True,
                )
                
                logger.info(
                    f"Telegram отправлено @{username}: {notification.id}"
                )
                return True
                
            except TelegramError as e:
                error_msg = str(e)
                if "chat not found" in error_msg.lower():
                    logger.warning(
                        f"Пользователь @{username} не начал диалог с ботом. "
                        f"Необходимо отправить /start боту."
                    )
                elif "bot was blocked" in error_msg.lower():
                    logger.warning(
                        f"Пользователь @{username} заблокировал бота."
                    )
                else:
                    logger.error(
                        f"Ошибка отправки @{username}: {e}",
                        exc_info=True
                    )
                return False
        
        return loop.run_until_complete(send_by_username())
    
    @classmethod
    async def send_message_async(
        cls,
        telegram_id: int,
        text: str,
        keyboard: Optional[InlineKeyboardMarkup] = None
    ) -> bool:
        """
        Отправка произвольного сообщения
        
        Args:
            telegram_id: ID получателя
            text: текст сообщения
            keyboard: inline клавиатура (опционально)
            
        Returns:
            True если отправлено успешно
        """
        bot = cls.get_bot()
        if not bot:
            return False
        
        try:
            await bot.send_message(
                chat_id=telegram_id,
                text=text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
                disable_web_page_preview=True,
            )
            return True
        except TelegramError as e:
            logger.error(f"Ошибка отправки сообщения в Telegram: {e}")
            return False
    
    @classmethod
    def send_message(
        cls,
        telegram_id: int,
        text: str,
        keyboard: Optional[InlineKeyboardMarkup] = None
    ) -> bool:
        """Синхронная обёртка для send_message_async"""
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(
            cls.send_message_async(telegram_id, text, keyboard)
        )
    
    @classmethod
    def test_bot_connection(cls) -> bool:
        """
        Тестирует подключение к Telegram боту
        
        Returns:
            True если бот доступен и настроен правильно
        """
        bot = cls.get_bot()
        if not bot:
            return False
        
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        async def test():
            try:
                me = await bot.get_me()
                logger.info(
                    f"Бот подключен: @{me.username} ({me.first_name})"
                )
                return True
            except TelegramError as e:
                logger.error(f"Ошибка подключения к боту: {e}")
                return False
        
        return loop.run_until_complete(test())
