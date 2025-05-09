from twilio.rest import Client
from src.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER, NOTIFICATION_WHATSAPP_NUMBER
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

message = client.messages.create(
    from_=TWILIO_WHATSAPP_NUMBER,
    to=NOTIFICATION_WHATSAPP_NUMBER,
    content_sid="HX39bfa570490a5a5aa7e5ad2371436979",  # price_change_notification for testing
    content_variables=json.dumps({
        "1": "JEDZENIE",
        "2": "Kukurydza kolby 2,5kg Oerlemans",
        "3": "10,50",
        "4": "12,00",
        "5": "+14,29"
    })
)
logger.info(f"Message sent with SID: {message.sid}")