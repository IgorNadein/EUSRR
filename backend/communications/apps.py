# backend\communications\apps.py
from django.apps import AppConfig


class CommunicationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "communications"

    def ready(self):
        import communications.signals
        import communications.notifications  # Модуль уведомлений (signals регистрируются автоматически)
        import communications.rules  # django-rules: регистрация предикатов и правил доступа
        
        def create_main_global_chat(sender, **kwargs):
            """
            Создает главный глобальный чат при первом запуске.
            
            Использует flags['is_primary'] вместо is_main.
            Для обратной совместимости также устанавливает is_main=True.
            """
            from communications.models import Chat
            from django.db.models import Q

            # Проверяем по обоим полям (старому и новому)
            if not Chat.objects.filter(
                Q(type="global") & (
                    Q(is_main=True) | Q(flags__is_primary=True)
                )
            ).exists():
                Chat.objects.create(
                    type="global",
                    # NEW: flags
                    flags={'is_primary': True},
                    # DEPRECATED: для обратной совместимости
                    is_main=True
                )

