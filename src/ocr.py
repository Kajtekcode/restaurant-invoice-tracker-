from google.cloud import vision
import os
import logging

logger = logging.getLogger(__name__)

def detect_text(image_path):
    """Extract text from an image using Google Cloud Vision API."""
    try:
        os.environ["GRPC_POLL_STRATEGY"] = "poll"
        client = vision.ImageAnnotatorClient()
        with open(image_path, "rb") as image_file:
            content = image_file.read()
        image = vision.Image(content=content)
        response = client.text_detection(image=image)
        if response.error.message:
            logger.error(f"OCR error: {response.error.message}")
            return None
        if not response.text_annotations:
            logger.warning("No text detected in image")
            return ""
        text = response.text_annotations[0].description
        logger.info(f"Extracted text from {image_path}: {text[:100]}...")
        return text
    except Exception as e:
        logger.error(f"Failed to process image {image_path}: {e}")
        return None