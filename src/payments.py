import logging
from datetime import datetime
from src.sheets import get_worksheet, get_spreadsheet
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
import gspread.exceptions

logger = logging.getLogger(__name__)

def calculate_days_to_due(due_date):
    """Calculate days until due date and return alert if <3 days."""
    try:
        due = datetime.strptime(due_date, "%d.%m.%Y")
        today = datetime.now()
        days_left = (due - today).days
        alert = "ALERT: Płatność za <3 dni!" if days_left < 3 and days_left >= 0 else ""
        return days_left, alert
    except ValueError as e:
        logger.error(f"Invalid date format for {due_date}: {e}")
        return None, "Błąd daty"

@retry(
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    retry=retry_if_exception_type(gspread.exceptions.APIError)
)
def sync_invoice_status(spreadsheet):
    """Synchronize invoices between Faktury Niezapłacone and Faktury Zapłacone."""
    try:
        unpaid_sheet = get_worksheet(spreadsheet, "Faktury Niezapłacone")
        paid_sheet = get_worksheet(spreadsheet, "Faktury Zapłacone")
        unpaid_data = unpaid_sheet.get_all_records()
        rows_to_move = []
        for i, row in enumerate(unpaid_data, start=2):
            if row["Opłacona (T/N)"] == "T":
                total_str = str(row["Kwota Całkowita (PLN)"]).replace(",", ".")
                total_float = float(total_str)
                total_formatted = f"{total_float:.2f}".replace(".", ",")
                rows_to_move.append((i, [
                    row["Data Wystawienia"],
                    row.get("Numer Faktury", ""),
                    row["Sprzedawca"],
                    total_formatted,
                    row["Kategoria"],
                    row["Termin Płatności"],
                    row["Opłacona (T/N)"],
                    ""
                ]))
        for row_idx, row_data in reversed(rows_to_move):
            paid_sheet.append_row(row_data)
            unpaid_sheet.delete_rows(row_idx)
            logger.info(f"Moved invoice {row_data[1]} to Faktury Zapłacone")
        unpaid_data = unpaid_sheet.get_all_records()
        updated_rows = []
        for row in unpaid_data:
            days_left, alert = calculate_days_to_due(row["Termin Płatności"])
            days_display = alert if alert else str(days_left) if days_left is not None else "Błąd daty"
            total_str = str(row["Kwota Całkowita (PLN)"]).replace(",", ".")
            total_float = float(total_str)
            total_formatted = f"{total_float:.2f}".replace(".", ",")
            updated_rows.append([
                row["Data Wystawienia"],
                row.get("Numer Faktury", ""),
                row["Sprzedawca"],
                total_formatted,
                row["Kategoria"],
                row["Termin Płatności"],
                row["Opłacona (T/N)"],
                days_display
            ])
        sorted_rows = sorted(
            updated_rows,
            key=lambda x: (
                float(x[7]) if x[7].replace(".", "").isdigit() else float("inf"),
                x[7]
            )
        )
        unpaid_sheet.clear()
        unpaid_sheet.append_row([
            "Data Wystawienia", "Numer Faktury", "Sprzedawca", "Kwota Całkowita (PLN)",
            "Kategoria", "Termin Płatności", "Opłacona (T/N)", "Dni do Zapłaty"
        ])
        for row in sorted_rows:
            unpaid_sheet.append_row(row)
        logger.info("Synchronized and sorted Faktury Niezapłacone")
    except Exception as e:
        logger.error(f"Failed to sync invoice status: {e}")
        raise

def update_payment_status(spreadsheet, invoice_data):
    """Update days to due for a new invoice."""
    try:
        unpaid_sheet = get_worksheet(spreadsheet, "Faktury Niezapłacone")
        if invoice_data["paid"] == "N":
            days_left, alert = calculate_days_to_due(invoice_data["due_date"])
            days_display = alert if alert else str(days_left) if days_left is not None else "Błąd daty"
        else:
            days_display = ""
        return days_display
    except Exception as e:
        logger.error(f"Failed to update payment status: {e}")
        return "Błąd daty"