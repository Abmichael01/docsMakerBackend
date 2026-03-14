from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        import api.signals
        
        # Background download of AI models for rembg
        import threading
        from scripts.download_models import download_models
        threading.Thread(target=download_models, daemon=True).start()
