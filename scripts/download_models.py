import rembg
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def download_models():
    models = ["isnet-general-use"]
    
    for model in models:
        logger.info(f"Downloading/Initializing model: {model}...")
        try:
            # initializing a session forces a download if not present
            rembg.new_session(model)
            logger.info(f"Successfully initialized {model}")
        except Exception as e:
            logger.error(f"Failed to download {model}: {e}")

if __name__ == "__main__":
    download_models()
