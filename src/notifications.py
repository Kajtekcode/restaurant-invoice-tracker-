from twilio.rest import Client
from src.config import TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_WHATSAPP_NUMBER
import os
import smtplib
from email.mime.text import MIMEText
import logging
import json

logger = logging.getLogger(__name__)

client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

def send_whatsapp_notification(content_sid, content_variables, to_number=None):
    """Send a WhatsApp notification using a template."""
    try:
        to_number = to_number or os.getenv("NOTIFICATION_WHATSAPP_NUMBER")
        if not to_number:
            logger.error("No WhatsApp number configured for notifications")
            return False
        message = client.messages.create(
            from_=TWILIO_WHATSAPP_NUMBER,
            to=to_number,
            content_sid=content_sid,
            content_variables=json.dumps(content_variables)
        )
        logger.info(f"Sent WhatsApp notification with SID: {message.sid}")
        return True
    except Exception as e:
        logger.error(f"Failed to send WhatsApp notification: {e}")
        return False

def send_email_notification(subject, message, to_email=None):
    """Send a notification via email."""
    try:
        sender = os.getenv("EMAIL_SENDER")
        password = os.getenv("EMAIL_PASSWORD")
        recipient = to_email or os.getenv("EMAIL_RECIPIENT")
        if not all([sender, password, recipient]):
            logger.error("Email configuration incomplete")
            return False
        msg = MIMEText(message)
        msg["Subject"] = subject
        msg["From"] = sender
        msg["To"] = recipient
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(sender, password)
            server.sendmail(sender, recipient, msg.as_string())
        logger.info(f"Sent email notification: {subject}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email notification: {e}")
        return False

def notify_price_changes(price_changes_by_category):
    """Notify about price changes >5% using a WhatsApp template."""
    if not price_changes_by_category:
        return
    content_sid = "HX39bfa570490a5a5aa7e5ad2371436979"  # price_change_notification
    for category, changes in price_changes_by_category.items():
        for change in changes:
            content_variables = {
                "1": category,
                "2": change["name"],
                "3": f"{change['old_price']:.2f}".replace(".", ","),
                "4": f"{change['new_price']:.2f}".replace(".", ","),
                "5": f"{change['change_percent']:+.2f}".replace(".", ",")
            }
            send_whatsapp_notification(content_sid, content_variables)
    # Fallback to email with free-form message
    if os.getenv("EMAIL_SENDER"):
        message = "Zmiany cen składników (>5%):\n"
        for category, changes in price_changes_by_category.items():
            message += f"\nKategoria: {category}\n"
            for change in changes:
                message += (
                    f"- {change['name']}: {change['old_price']:.2f} PLN → "
                    f"{change['new_price']:.2f} PLN ({change['change_percent']:+.2f}%)\n"
                )
        send_email_notification("Zmiany Cen Składników", message.strip())

def notify_payment_reminders(spreadsheet):
    """Notify about unpaid invoices due in <3 days using a WhatsApp template."""
    try:
        from src.payments import calculate_days_to_due
        unpaid_sheet = spreadsheet.worksheet("Faktury Niezapłacone")
        unpaid_data = unpaid_sheet.get_all_records()
        content_sid = "HX96688fa611964bde3348ff65389b54df"  # payment_reminder
        urgent_invoices = []
        for row in unpaid_data:
            if row["Opłacona (T/N)"] == "N":
                days_left, alert = calculate_days_to_due(row["Termin Płatności"])
                if alert:
                    invoice_info = {
                        "invoice_number": row.get("Numer Faktury", "brak numeru"),
                        "seller": row["Sprzedawca"],
                        "amount": row["Kwota Całkowita (PLN)"],
                        "due_date": row["Termin Płatności"],
                        "days_left": str(days_left)
                    }
                    content_variables = {
                        "1": invoice_info["invoice_number"],
                        "2": invoice_info["seller"],
                        "3": invoice_info["amount"],
                        "4": invoice_info["due_date"],
                        "5": invoice_info["days_left"]
                    }
                    send_whatsapp_notification(content_sid, content_variables)
                    urgent_invoices.append(invoice_info)
        # Fallback to email with free-form message
        if os.getenv("EMAIL_SENDER") and urgent_invoices:
            message = "Przypomnienia o płatnościach (<3 dni):\n"
            for inv in urgent_invoices:
                message += (
                    f"Faktura {inv['invoice_number']}, Sprzedawca: {inv['seller']}, "
                    f"Kwota: {inv['amount']} PLN, Termin: {inv['due_date']} ({inv['days_left']} dni)\n"
                )
            send_email_notification("Przypomnienia o Płatnościach", message.strip())
        logger.info(f"Sent payment reminders for {len(urgent_invoices)} invoices")
    except Exception as e:
        logger.error(f"Failed to send payment reminders: {e}")