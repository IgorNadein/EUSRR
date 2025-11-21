"""
Telegram bot handlers для обработки команд пользователей
"""
import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
    ConversationHandler,
)
from telegram.constants import ParseMode
from telegram.error import TelegramError

from django.conf import settings
from django.utils import timezone

from .telegram_models import TelegramUser
from employees.models import Employee

logger = logging.getLogger(__name__)

# Состояния для ConversationHandler
WAITING_FOR_CONTACT = 1


class TelegramBotHandlers:
    """
    Обработчики команд Telegram бота
    """
    
    @staticmethod
    async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Команда /start - приветствие и инструкции
        """
        user = update.effective_user
        
        # Проверяем, привязан ли аккаунт
        try:
            tg_user = TelegramUser.objects.get(
                telegram_id=user.id,
                is_active=True
            )
            
            # Аккаунт уже привязан
            employee = tg_user.user
            await update.message.reply_text(
                f"👋 Привет, {employee.first_name}!\n\n"
                f"Ваш аккаунт уже привязан к EUSRR.\n\n"
                f"Доступные команды:\n"
                f"/settings - Настройки уведомлений\n"
                f"/unlink - Отвязать аккаунт\n"
                f"/help - Справка",
                parse_mode=ParseMode.HTML
            )
            
            # Обновляем время взаимодействия
            tg_user.update_last_interaction()
            
        except TelegramUser.DoesNotExist:
            # Аккаунт не привязан - показываем инструкцию
            await update.message.reply_text(
                "👋 Добро пожаловать в бот EUSRR!\n\n"
                "Этот бот будет отправлять вам уведомления из системы EUSRR.\n\n"
                "🔗 <b>Для привязки аккаунта:</b>\n"
                "1. Войдите в личный кабинет EUSRR\n"
                "2. Перейдите в настройки уведомлений\n"
                "3. Нажмите 'Привязать Telegram'\n"
                "4. Получите код привязки\n"
                "5. Отправьте команду: /link ВАШ_КОД\n\n"
                "❓ Помощь: /help",
                parse_mode=ParseMode.HTML
            )
    
    @staticmethod
    async def link_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Команда /link CODE - запрашивает код и контакт для привязки
        """
        user = update.effective_user
        
        # Проверяем что код указан
        if not context.args or len(context.args) == 0:
            await update.message.reply_text(
                "❌ Укажите код привязки.\n\n"
                "Использование: /link ВАШ_КОД\n\n"
                "Код можно получить в настройках уведомлений EUSRR.",
                parse_mode=ParseMode.HTML
            )
            return
        
        link_code = context.args[0].upper()
        
        # Проверяем что аккаунт еще не привязан
        if TelegramUser.objects.filter(
            telegram_id=user.id,
            is_active=True
        ).exists():
            await update.message.reply_text(
                "⚠️ Ваш Telegram уже привязан к аккаунту EUSRR.\n\n"
                "Если хотите привязать другой аккаунт, "
                "сначала используйте /unlink",
                parse_mode=ParseMode.HTML
            )
            return
        
        # Ищем пользователя с таким кодом
        try:
            tg_user = TelegramUser.objects.select_related('user').get(
                link_code=link_code,
                telegram_id__isnull=True
            )
            
            # Проверяем срок действия кода
            if not tg_user.is_link_code_valid():
                await update.message.reply_text(
                    "❌ Код привязки истёк.\n\n"
                    "Пожалуйста, получите новый код в настройках EUSRR.",
                    parse_mode=ParseMode.HTML
                )
                return
            
            # Сохраняем код в контексте для проверки контакта
            context.user_data['pending_link_code'] = link_code
            context.user_data['pending_tg_user_id'] = tg_user.id
            
            # Создаем кнопку "Поделиться контактом"
            from telegram import KeyboardButton, ReplyKeyboardMarkup
            
            keyboard = ReplyKeyboardMarkup(
                [[KeyboardButton("📱 Поделиться контактом", 
                                request_contact=True)]],
                one_time_keyboard=True,
                resize_keyboard=True
            )
            
            await update.message.reply_text(
                "🔐 <b>Подтверждение личности</b>\n\n"
                "Для безопасности нажмите кнопку ниже, "
                "чтобы поделиться вашим контактом.\n\n"
                "Мы проверим что он совпадает с данными, "
                "указанными при регистрации в EUSRR.",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
            
        except TelegramUser.DoesNotExist:
            await update.message.reply_text(
                "❌ Неверный код привязки.\n\n"
                "Проверьте код и попробуйте снова.\n"
                "Если код истёк, получите новый в настройках EUSRR.",
                parse_mode=ParseMode.HTML
            )
    
    @staticmethod
    async def contact_received(
        update: Update, 
        context: ContextTypes.DEFAULT_TYPE
    ):
        """
        Обработка полученного контакта для верификации
        """
        from telegram import ReplyKeyboardRemove
        
        user = update.effective_user
        contact = update.message.contact
        
        # Проверяем что контакт от самого пользователя
        if contact.user_id != user.id:
            await update.message.reply_text(
                "❌ Пожалуйста, поделитесь <b>своим</b> контактом, "
                "а не контактом другого пользователя.",
                parse_mode=ParseMode.HTML,
                reply_markup=ReplyKeyboardRemove()
            )
            return
        
        # Проверяем что есть pending привязка
        pending_code = context.user_data.get('pending_link_code')
        pending_tg_user_id = context.user_data.get('pending_tg_user_id')
        
        if not pending_code or not pending_tg_user_id:
            await update.message.reply_text(
                "❌ Нет активной попытки привязки.\n\n"
                "Сначала используйте команду /link КОД",
                parse_mode=ParseMode.HTML,
                reply_markup=ReplyKeyboardRemove()
            )
            return
        
        try:
            tg_user = TelegramUser.objects.select_related('user').get(
                id=pending_tg_user_id,
                link_code=pending_code
            )
            
            employee = tg_user.user
            
            # Проверяем совпадение данных
            telegram_field = employee.telegram.strip().lower()
            
            # Получаем username и phone из контакта
            contact_username = f"@{contact.username}".lower() \
                if contact.username else None
            contact_phone = contact.phone_number
            
            # Проверка совпадения
            match_found = False
            match_type = ""
            
            if telegram_field:
                # Проверка по username
                if contact_username and telegram_field == contact_username:
                    match_found = True
                    match_type = f"username ({contact_username})"
                
                # Проверка по номеру телефона
                elif contact_phone:
                    # Нормализуем номера (убираем + и пробелы)
                    normalized_contact = contact_phone.replace('+', '') \
                        .replace(' ', '').replace('-', '')
                    normalized_field = telegram_field.replace('+', '') \
                        .replace(' ', '').replace('-', '')
                    
                    if normalized_contact == normalized_field:
                        match_found = True
                        match_type = f"номер телефона ({contact_phone})"
            
            if not match_found:
                await update.message.reply_text(
                    "❌ <b>Данные не совпадают</b>\n\n"
                    f"Ваш контакт:\n"
                    f"Username: {contact_username or 'не указан'}\n"
                    f"Телефон: {contact_phone or 'не указан'}\n\n"
                    f"В профиле EUSRR указано: {telegram_field or 'не указано'}\n\n"
                    "Обновите поле 'Telegram' в вашем профиле EUSRR "
                    "и попробуйте снова.",
                    parse_mode=ParseMode.HTML,
                    reply_markup=ReplyKeyboardRemove()
                )
                
                # Очищаем pending данные
                context.user_data.clear()
                return
            
            # ✅ Данные совпали - привязываем аккаунт
            tg_user.telegram_id = user.id
            tg_user.telegram_username = user.username or ''
            tg_user.first_name = user.first_name or ''
            tg_user.last_name = user.last_name or ''
            tg_user.is_active = True
            tg_user.is_blocked = False
            tg_user.clear_link_code()
            tg_user.update_last_interaction()
            tg_user.save()
            
            await update.message.reply_text(
                f"✅ <b>Аккаунт успешно привязан!</b>\n\n"
                f"Подтверждено через: {match_type}\n\n"
                f"👤 Привязан к: {employee.get_full_name()}\n"
                f"📧 Email: {employee.email}\n\n"
                f"Теперь вы будете получать уведомления EUSRR в Telegram.\n\n"
                f"Доступные команды:\n"
                f"/settings - Настройки уведомлений\n"
                f"/unlink - Отвязать аккаунт\n"
                f"/help - Справка",
                parse_mode=ParseMode.HTML,
                reply_markup=ReplyKeyboardRemove()
            )
            
            logger.info(
                f"Telegram привязан через {match_type}: "
                f"{user.id} -> {employee.email}"
            )
            
            # Очищаем pending данные
            context.user_data.clear()
            
        except TelegramUser.DoesNotExist:
            await update.message.reply_text(
                "❌ Код привязки истёк или недействителен.\n\n"
                "Получите новый код в настройках EUSRR.",
                parse_mode=ParseMode.HTML,
                reply_markup=ReplyKeyboardRemove()
            )
            context.user_data.clear()
    
    @staticmethod
    async def unlink_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Команда /unlink - отвязка аккаунта
        """
        user = update.effective_user
        
        try:
            tg_user = TelegramUser.objects.get(
                telegram_id=user.id,
                is_active=True
            )
            
            employee_name = tg_user.user.get_full_name()
            
            # Отвязываем аккаунт
            tg_user.is_active = False
            tg_user.save()
            
            await update.message.reply_text(
                f"✅ <b>Аккаунт отвязан</b>\n\n"
                f"Связь с {employee_name} удалена.\n"
                f"Вы больше не будете получать уведомления.\n\n"
                f"Для повторной привязки используйте /link",
                parse_mode=ParseMode.HTML
            )
            
            logger.info(f"Telegram аккаунт отвязан: {user.id}")
            
        except TelegramUser.DoesNotExist:
            await update.message.reply_text(
                "⚠️ Ваш аккаунт не привязан к EUSRR.\n\n"
                "Используйте /start для инструкций по привязке.",
                parse_mode=ParseMode.HTML
            )
    
    @staticmethod
    async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Команда /settings - показать текущие настройки
        """
        user = update.effective_user
        
        try:
            tg_user = TelegramUser.objects.get(
                telegram_id=user.id,
                is_active=True
            )
            
            employee = tg_user.user
            
            # Получаем настройки уведомлений
            from .models import UserNotificationSettings, NotificationCategory
            
            settings_text = f"⚙️ <b>Настройки уведомлений</b>\n\n"
            settings_text += f"👤 Пользователь: {employee.get_full_name()}\n"
            settings_text += f"📧 Email: {employee.email}\n"
            settings_text += f"🔗 Telegram: @{tg_user.telegram_username or 'не указан'}\n\n"
            settings_text += "<b>Категории уведомлений:</b>\n\n"
            
            categories = NotificationCategory.objects.all()
            for category in categories:
                try:
                    user_settings = UserNotificationSettings.objects.get(
                        user=employee,
                        category=category
                    )
                    
                    # Эмодзи для категорий
                    emoji_map = {
                        'communications': '💬',
                        'documents': '📄',
                        'requests': '📋',
                        'calendar': '📅',
                        'department': '👥',
                        'profile': '👤',
                        'feed': '📰',
                        'system': '⚙️',
                    }
                    emoji = emoji_map.get(category.code, '🔔')
                    
                    status = "✅" if user_settings.send_telegram else "❌"
                    settings_text += f"{emoji} {category.name}: {status}\n"
                    
                except UserNotificationSettings.DoesNotExist:
                    pass
            
            # Создаем кнопку для перехода в настройки
            site_url = getattr(settings, 'SITE_URL', 'http://localhost:9000')
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(
                    "🔧 Изменить настройки",
                    url=f"{site_url}/notifications/settings/"
                )]
            ])
            
            await update.message.reply_text(
                settings_text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
            
            tg_user.update_last_interaction()
            
        except TelegramUser.DoesNotExist:
            await update.message.reply_text(
                "⚠️ Ваш аккаунт не привязан к EUSRR.\n\n"
                "Используйте /start для инструкций по привязке.",
                parse_mode=ParseMode.HTML
            )
    
    @staticmethod
    async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Команда /help - справка
        """
        await update.message.reply_text(
            "📖 <b>Справка по командам бота EUSRR</b>\n\n"
            "<b>Основные команды:</b>\n\n"
            "/start - Приветствие и инструкции\n"
            "/link КОД - Привязать аккаунт EUSRR\n"
            "/unlink - Отвязать аккаунт\n"
            "/settings - Показать текущие настройки\n"
            "/help - Эта справка\n\n"
            "<b>Как привязать аккаунт:</b>\n"
            "1. Войдите в личный кабинет EUSRR\n"
            "2. Откройте настройки уведомлений\n"
            "3. Нажмите 'Привязать Telegram'\n"
            "4. Скопируйте код привязки\n"
            "5. Отправьте: /link ВАШ_КОД\n\n"
            "<b>О боте:</b>\n"
            "Этот бот отправляет уведомления из системы EUSRR "
            "о новых сообщениях, документах, заявках и других событиях.\n\n"
            "Настроить какие уведомления получать можно в личном кабинете EUSRR.",
            parse_mode=ParseMode.HTML
        )
    
    @staticmethod
    async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """
        Обработчик неизвестных команд и текстовых сообщений
        """
        await update.message.reply_text(
            "❓ Неизвестная команда.\n\n"
            "Используйте /help для списка доступных команд.",
            parse_mode=ParseMode.HTML
        )


def create_telegram_bot_application() -> Optional[Application]:
    """
    Создает и настраивает приложение Telegram бота
    
    Returns:
        Настроенное приложение или None если токен не настроен
    """
    token = getattr(settings, 'TELEGRAM_BOT_TOKEN', None)
    if not token:
        logger.error("TELEGRAM_BOT_TOKEN не настроен в settings")
        return None
    
    # Создаем приложение
    application = Application.builder().token(token).build()
    
    # Регистрируем handlers
    handlers = TelegramBotHandlers
    
    application.add_handler(CommandHandler("start", handlers.start_command))
    application.add_handler(CommandHandler("link", handlers.link_command))
    application.add_handler(CommandHandler("unlink", handlers.unlink_command))
    application.add_handler(
        CommandHandler("settings", handlers.settings_command)
    )
    application.add_handler(CommandHandler("help", handlers.help_command))
    
    # Обработчик контактов (для верификации при привязке)
    application.add_handler(
        MessageHandler(filters.CONTACT, handlers.contact_received)
    )
    
    # Обработчик неизвестных команд и текстовых сообщений
    application.add_handler(
        MessageHandler(
            filters.COMMAND | filters.TEXT,
            handlers.unknown_command
        )
    )
    
    logger.info("Telegram bot application создан")
    
    return application


async def run_telegram_bot():
    """
    Запускает Telegram бота в режиме polling
    """
    application = create_telegram_bot_application()
    if not application:
        logger.error("Не удалось создать Telegram bot application")
        return
    
    logger.info("Запуск Telegram бота...")
    
    try:
        # Инициализация
        await application.initialize()
        await application.start()
        
        # Запуск polling
        await application.updater.start_polling(
            allowed_updates=Update.ALL_TYPES
        )
        
        logger.info("Telegram бот запущен и слушает обновления")
        
        # Ожидание остановки
        await application.updater.stop()
        await application.stop()
        await application.shutdown()
        
    except Exception as e:
        logger.error(f"Ошибка при запуске Telegram бота: {e}", exc_info=True)
