from django.apps import AppConfig


class SearchConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'search'
    
    def ready(self):
        """Импортируем регистрации watson при запуске приложения."""
        import search.search_indexes  # noqa: F401
