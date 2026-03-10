"""
Конфигурация приложения scheduling.
Применяет патчи к django-scheduler и регистрирует сигналы.
"""
from django.apps import AppConfig


class SchedulingConfig(AppConfig):
    """Конфигурация приложения для интеграции с django-scheduler."""
    
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'scheduling'
    verbose_name = 'Планирование и календарь'

    def ready(self):
        """
        Инициализация приложения:
        1. Применяет патчи к django-scheduler
        2. Регистрирует сигналы для уведомлений
        3. Загружает правила доступа (django-rules)
        """
        # Применяем патчи к django-scheduler
        from scheduling import patch
        patch.apply_patch()
        
        # Регистрируем сигналы для уведомлений
        import scheduling.notifications.signals  # noqa: F401
        
        # Загружаем правила доступа (django-rules)
        try:
            import scheduling.rules  # noqa: F401
        except ImportError:
            # rules.py опционален
            pass
