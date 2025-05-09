import gspread
from oauth2client.service_account import ServiceAccountCredentials
from src.config import SPREADSHEET_ID, CREDENTIALS_PATH
import logging
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
import gspread.exceptions

logger = logging.getLogger(__name__)

SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

def get_spreadsheet():
    """Connect to Google Sheets."""
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_PATH, SCOPE)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        logger.info("Connected to Google Sheets")
        return spreadsheet
    except Exception as e:
        logger.error(f"Failed to connect to Google Sheets: {e}")
        raise

@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    retry=retry_if_exception_type(gspread.exceptions.APIError)
)
def get_worksheet(spreadsheet, title):
    """Get a worksheet by title with retry logic."""
    try:
        worksheet = spreadsheet.worksheet(title)
        logger.debug(f"Accessed worksheet: {title}")
        return worksheet
    except gspread.exceptions.WorksheetNotFound:
        logger.error(f"Worksheet {title} not found")
        raise

def update_or_append_ingredient(worksheet, ingredient, invoice_date, seller):
    """Update or append an ingredient's price in the category sheet."""
    try:
        records = worksheet.get_all_records()
        for i, record in enumerate(records, start=2):
            if record["Składnik"] == ingredient["name"]:
                sheet_net_price = float(str(record["Cena netto (za JM)"]).replace(",", "."))
                if abs(sheet_net_price - ingredient["net_price_per_unit"]) < 0.01:
                    logger.debug(f"Ingredient {ingredient['name']} already exists with same price")
                    return
                else:
                    worksheet.update(
                        range_name=f"A{i}:G{i}",
                        values=[[
                            invoice_date,
                            ingredient["name"],
                            ingredient["unit"],
                            f"{ingredient['net_price_per_unit']:.2f}".replace(".", ","),
                            ingredient["vat_percent"],
                            f"{ingredient['gross_price_per_unit']:.2f}".replace(".", ","),
                            seller
                        ]]
                    )
                    logger.info(f"Updated ingredient {ingredient['name']} in {worksheet.title}")
                    return
        worksheet.append_row([
            invoice_date,
            ingredient["name"],
            ingredient["unit"],
            f"{ingredient['net_price_per_unit']:.2f}".replace(".", ","),
            ingredient["vat_percent"],
            f"{ingredient['gross_price_per_unit']:.2f}".replace(".", ","),
            seller
        ])
        logger.info(f"Appended ingredient {ingredient['name']} to {worksheet.title}")
    except Exception as e:
        logger.error(f"Failed to update ingredient {ingredient['name']}: {e}")
        raise

def update_invoice_status(spreadsheet, invoice_data):
    """Update invoice details in Faktury Niezapłacone or Faktury Zapłacone."""
    try:
        from src.payments import update_payment_status
        target_sheet_title = "Faktury Zapłacone" if invoice_data["paid"] == "T" else "Faktury Niezapłacone"
        worksheet = get_worksheet(spreadsheet, target_sheet_title)
        total_formatted = f"{invoice_data['total']:.2f}".replace(".", ",")
        days_display = update_payment_status(spreadsheet, invoice_data)
        worksheet.append_row([
            invoice_data["invoice_date"],
            invoice_data.get("invoice_number", ""),
            invoice_data["seller"],
            total_formatted,
            invoice_data["category"],
            invoice_data["due_date"],
            invoice_data["paid"],
            days_display
        ])
        logger.info(f"Added invoice {invoice_data.get('invoice_number', 'unknown')} to {target_sheet_title}")
    except Exception as e:
        logger.error(f"Failed to update invoice status: {e}")
        raise

def store_invoice_data(invoice_data):
    """Store all invoice data in Google Sheets."""
    try:
        spreadsheet = get_spreadsheet()
        category_sheets = ["JEDZENIE", "NAPOJE", "NAPOJE ALKOHOLOWE", "CHEMIA", "INNE"]
        for ingredient in invoice_data["ingredients"]:
            category = ingredient["category"]
            if category in category_sheets:
                worksheet = get_worksheet(spreadsheet, category)
                update_or_append_ingredient(
                    worksheet,
                    ingredient,
                    invoice_data["invoice_date"],
                    invoice_data["seller"]
                )
        update_invoice_status(spreadsheet, invoice_data)
        logger.info("Successfully stored invoice data")
    except Exception as e:
        logger.error(f"Failed to store invoice data: {e}")
        raise