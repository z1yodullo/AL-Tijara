from django.apps import AppConfig

class AppUsersConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'App_users'
    
    def ready(self):
        import App_users.signals