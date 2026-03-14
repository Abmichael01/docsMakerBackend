from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'

    def ready(self):
        import api.signals
        import os
        from django.conf import settings
        
        # Configure a writable home for rembg models (U2NET_HOME)
        # We put it in media/models/.u2net so it's persistent and writable
        models_dir = os.path.join(settings.BASE_DIR, 'media', 'models')
        os.makedirs(models_dir, exist_ok=True)
        os.environ['U2NET_HOME'] = os.path.join(models_dir, '.u2net')
        
        # Background download of AI models for rembg
        import threading
        try:
            from scripts.download_models import download_models
            threading.Thread(target=download_models, daemon=True).start()
        except ImportError:
            # Fallback for different import environments
            try:
                from .scripts.download_models import download_models
                threading.Thread(target=download_models, daemon=True).start()
            except (ImportError, ValueError):
                print("[ApiConfig] Warning: Could not import download_models script")
