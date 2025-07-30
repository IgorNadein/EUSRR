from django.core.management.base import BaseCommand
from bots.services.telegram import run_telegram_bot


class Command(BaseCommand):
    help = "Запуск Telegram-бота для рассылки и привязки сотрудников"

    def handle(self, *args, **options):
        run_telegram_bot()
