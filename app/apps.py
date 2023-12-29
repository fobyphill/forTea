import os
from django.apps import AppConfig



class AppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'app'
    def ready(self):
        from app import updater
        if os.environ.get('RUN_MAIN'):
            updater.start()
