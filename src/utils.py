import requests
import os
from datetime import datetime, timedelta
from src.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, INVOICES_DIR
import logging

logger = logging.getLogger(__name__)

def download_media(media_url, invoices_dir):
    """Download media from Twilio and save it locally."""
    try:
        os.makedirs(invoices_dir, exist_ok=True)
        response = requests.get(media_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
        if response.status_code != 200:
            raise Exception(f"Failed to download media: {response.status_code}")
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"invoice_{timestamp}.jpg"
        file_path = os.path.join(invoices_dir, filename)
        with open(file_path, "wb") as f:
            f.write(response.content)
        logger.info(f"Downloaded media: {filename}")
        return filename
    except Exception as e:
        logger.error(f"Failed to download media: {e}")
        raise

def clean_old_invoices(invoices_dir, days=30):
    """Remove invoice images older than specified days."""
    try:
        threshold = datetime.now() - timedelta(days=days)
        for filename in os.listdir(invoices_dir):
            file_path = os.path.join(invoices_dir, filename)
            if os.path.isfile(file_path):
                file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                if file_mtime < threshold:
                    os.remove(file_path)
                    logger.info(f"Removed old invoice: {filename}")
    except Exception as e:
        logger.error(f"Failed to clean old invoices: {e}")