"""
Management команда для запуска Telegram бота
"""
import asyncio
import logging

from django.core.management.base import BaseCommand

from notifications.telegram_bot import run_telegram_bot

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Запускает Telegram бота для уведомлений'
    
    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS('Запуск Telegram бота...')
        )
        
        try:
            asyncio.run(run_telegram_bot())
        except KeyboardInterrupt:
            self.stdout.write(
                self.style.WARNING('\nTelegram бот остановлен')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Ошибка при запуске бота: {e}')
            )
            logger.error(f"Ошибка при запуске бота: {e}", exc_info=True)
