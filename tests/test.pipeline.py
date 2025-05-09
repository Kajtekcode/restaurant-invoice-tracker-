import os
import shutil
from src.utils import download_media
from src.ocr import detect_text
from src.parser import parse_invoice_text
from src.sheets import store_invoice_data, get_spreadsheet
from src.price_changes import detect_price_changes
from src.payments import sync_invoice_status
from src.notifications import notify_price_changes, notify_payment_reminders
import logging

logger = logging.getLogger(__name__)

def run_test(test_name, image_path, paid_status, expected_outcome):
    """Run a test case for the invoice processing pipeline."""
    logger.info(f"Running test: {test_name}")
    try:
        filename = os.path.basename(image_path)
        base, ext = os.path.splitext(filename)
        new_filename = f"{base}_{paid_status}{ext}"
        dest_path = os.path.join("invoices", new_filename)
        shutil.copy(image_path, dest_path)
        text = detect_text(dest_path)
        if not text and "OCR failure" in expected_outcome:
            logger.info("Test passed: OCR failed as expected")
            return
        assert text, "OCR failed unexpectedly"
        parsed_data = parse_invoice_text(text, paid_status)
        if not parsed_data and "Parsing failure" in expected_outcome:
            logger.info("Test passed: Parsing failed as expected")
            return
        assert parsed_data, "Parsing failed unexpectedly"
        store_invoice_data(parsed_data)
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
        sync_invoice_status(spreadsheet)
        notify_payment_reminders(spreadsheet)
        logger.info(f"Test passed: {test_name}")
    except Exception as e:
        logger.error(f"Test failed: {test_name} - {e}")
    finally:
        if os.path.exists(dest_path):
            os.remove(dest_path)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    test_cases = [
        {
            "name": "Normal invoice (unpaid, price change)",
            "image_path": "tests/invoices/normal_invoice.jpg",
            "paid_status": "N",
            "expected_outcome": "Success"
        },
        {
            "name": "Blurry invoice (OCR failure)",
            "image_path": "tests/invoices/blurry_invoice.jpg",
            "paid_status": "N",
            "expected_outcome": "OCR failure"
        },
        {
            "name": "Invoice with missing data",
            "image_path": "tests/invoices/missing_data_invoice.jpg",
            "paid_status": "T",
            "expected_outcome": "Success"
        },
        {
            "name": "Invoice due in <3 days",
            "image_path": "tests/invoices/urgent_invoice.jpg",
            "paid_status": "N",
            "expected_outcome": "Success"
        }
    ]
    for test in test_cases:
        run_test(
            test["name"],
            test["image_path"],
            test["paid_status"],
            test["expected_outcome"]
        )