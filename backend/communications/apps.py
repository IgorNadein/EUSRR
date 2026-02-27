# backend\communications\apps.py
from django.apps import AppConfig


class CommunicationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "communications"

    def ready(self):
        import communications.signals
        import communications.notification_signals  # Подключаем signals уведомлений
        import communications.rules  # django-rules: регистрация предикатов и правил доступа
        
        def create_main_global_chat(sender, **kwargs):
            from communications.models import Chat

            if not Chat.objects.filter(type="global", is_main=True).exists():
                Chat.objects.create(type="global", is_main=True)

