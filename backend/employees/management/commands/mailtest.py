from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from common.emails import send_templated_mail

class Command(BaseCommand):
    help = "Отправить тестовое письмо на указанный адрес"

    def add_arguments(self, parser):
        parser.add_argument("email", type=str)

    def handle(self, *args, **opts):
        to_email = opts["email"]
        try:
            sent = send_templated_mail(
                subject="Тестовое письмо",
                to=[to_email],
                template_base="emails/registration_verify_code",
                context={"code": "123456", "user": None},
            )
            self.stdout.write(self.style.SUCCESS(f"Письмо отправлено ({sent}). Бэкенд: {settings.EMAIL_BACKEND}"))
        except Exception as e:
            raise CommandError(f"Ошибка отправки: {e}")
