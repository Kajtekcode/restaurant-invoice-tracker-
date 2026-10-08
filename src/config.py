from dotenv import load_dotenv
import os

load_dotenv()

# Twilio credentials
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_WHATSAPP_NUMBER = os.getenv("TWILIO_WHATSAPP_NUMBER")
NOTIFICATION_WHATSAPP_NUMBER = os.getenv("NOTIFICATION_WHATSAPP_NUMBER")

# xAI API key
XAI_API_KEY = os.getenv("XAI_API_KEY")

# Google Sheets
SPREADSHEET_ID = os.getenv("SPREADSHEET_ID")


# Local storage
INVOICES_DIR = "invoices"