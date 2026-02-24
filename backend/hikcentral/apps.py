# hikcentral/apps.py

from django.apps import AppConfig


class HikcentralConfig(AppConfig):
    name = 'hikcentral'

    def ready(self):
        import hikcentral.signals
