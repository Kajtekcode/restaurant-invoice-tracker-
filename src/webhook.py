from flask import Flask, request
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from twilio.rest import Client
import os
import json
from src.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER, INVOICES_DIR
from src.utils import download_media, clean_old_invoices
from src.ocr import detect_text
from src.parser import parse_invoice_text
from src.sheets import store_invoice_data, get_spreadsheet
from src.price_changes import detect_price_changes
from src.payments import sync_invoice_status
from src.notifications import notify_price_changes, notify_payment_reminders
import logging
import logging.handlers

# Set up logging with rotation
handler = logging.handlers.RotatingFileHandler("app.log", maxBytes=10*1024*1024, backupCount=5)
handler.setFormatter(logging.Formatter("%(asctime)s - %(levelname)s - %(message)s"))
logging.getLogger().setLevel(logging.INFO)
logging.getLogger().addHandler(handler)
logging.getLogger().addHandler(logging.StreamHandler())
logger = logging.getLogger(__name__)

app = Flask(__name__)
limiter = Limiter(app, key_func=get_remote_address, default_limits=["200 per day", "50 per hour"])

# Initialize Twilio client
client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

@app.route("/whatsapp", methods=["POST"])
@limiter.limit("10 per minute")
def whatsapp_webhook():
    from_number = request.form.get("From")
    num_media = int(request.form.get("NumMedia", 0))
    body = request.form.get("Body", "").strip().upper()

    paid_status = "T" if "PAID" in body else "N"

    if num_media > 0:
        media_url = request.form.get("MediaUrl0")
        media_type = request.form.get("MediaContentType0")
        if media_type.startswith("image/"):
            try:
                filename = download_media(media_url, INVOICES_DIR)
                base, ext = os.path.splitext(filename)
                new_filename = f"{base}_{paid_status}{ext}"
                file_path = os.path.join(INVOICES_DIR, new_filename)
                os.rename(
                    os.path.join(INVOICES_DIR, filename),
                    file_path
                )
            except Exception as e:
                logger.error(f"Failed to download or rename image: {e}")
                client.messages.create(
                    body="Nie udało się pobrać obrazu faktury. Spróbuj ponownie.",
                    from_=TWILIO_WHATSAPP_NUMBER,
                    to=from_number
                )
                return "Download failed", 500

            text = detect_text(file_path)
            if not text:
                client.messages.create(
                    body="Nie udało się odczytać tekstu z faktury. Spróbuj ponownie.",
                    from_=TWILIO_WHATSAPP_NUMBER,
                    to=from_number
                )
                return "OCR failed", 500

            parsed_data = parse_invoice_text(text, paid_status)
            if not parsed_data:
                client.messages.create(
                    body="Nie udało się sparsować danych faktury. Sprawdź jakość lub format obrazu.",
                    from_=TWILIO_WHATSAPP_NUMBER,
                    to=from_number
                )
                return "Parsing failed", 500

            try:
                store_invoice_data(parsed_data)
            except Exception as e:
                logger.error(f"Failed to store data: {e}")
                client.messages.create(
                    body="Nie udało się zapisać danych faktury. Spróbuj ponownie później.",
                    from_=TWILIO_WHATSAPP_NUMBER,
                    to=from_number
                )
                return "Storage failed", 500

            try:
                spreadsheet = get_spreadsheet()
                price_changes_by_category = {}
                categories = ["JEDZENIE", "NAPOJE", "NAPOJE ALKOHOLOWE", "CHEMIA", "INNE"]
                for category in categories:
                    category_ingredients = [
                        ing for ing in parsed_data["ingredients"] if ing["category"] == category
                    ]
                    if category_ingredients:
                        changes = detect_price_changes(spreadsheet, category_ingredients, category)
                        if changes:
                            price_changes_by_category[category] = changes
                notify_price_changes(price_changes_by_category)
            except Exception as e:
                logger.error(f"Failed to detect price changes: {e}")

            try:
                sync_invoice_status(spreadsheet)
                notify_payment_reminders(spreadsheet)
            except Exception as e:
                logger.error(f"Failed to sync invoices or send reminders: {e}")
                client.messages.create(
                    body="Nie udało się zsynchronizować faktur lub wysłać przypomnień. Spróbuj ponownie później.",
                    from_=TWILIO_WHATSAPP_NUMBER,
                    to=from_number
                )
                return "Sync failed", 500

            clean_old_invoices(INVOICES_DIR, days=30)
            client.messages.create(
                body=f"Przetworzono fakturę: {new_filename} (Opłacona: {'Tak' if paid_status == 'T' else 'Nie'}). Zapisano {len(parsed_data['ingredients'])} składników.",
                from_=TWILIO_WHATSAPP_NUMBER,
                to=from_number
            )
            logger.info(f"Processed and stored invoice: {json.dumps(parsed_data, ensure_ascii=False)}")
            return "Invoice processed", 200
        else:
            client.messages.create(
                body="Proszę wysłać plik graficzny (np. JPG).",
                from_=TWILIO_WHATSAPP_NUMBER,
                to=from_number
            )
            return "Invalid media type", 400
    else:
        client.messages.create(
            body="Proszę wysłać zdjęcie faktury z dopiskiem 'Paid' lub 'Unpaid'.",
            from_=TWILIO_WHATSAPP_NUMBER,
            to=from_number
        )
        return "No media", 400

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)