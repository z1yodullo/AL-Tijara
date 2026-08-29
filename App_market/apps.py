from django.apps import AppConfig

class AppMarketConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'App_market'
    verbose_name = 'Рынок'
    
    def ready(self):
        pass