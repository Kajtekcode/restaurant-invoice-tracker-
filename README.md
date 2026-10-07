# Restaurant Invoice Tracker

WhatsApp bot that turns a restaurant invoice photo into rows in Google Sheets.
I built it after running a restaurant for 8 years, where invoices were typed in by hand.

## Flow

WhatsApp does not call this app directly. Twilio receives the message and sends a POST to `/whatsapp`.
The Flask webhook downloads the image, reads a paid flag from the caption (`PAID` means paid, anything else means unpaid), and runs:

1. Google Cloud Vision extracts the text (`src/ocr.py`).
2. `parse_invoice_text` sends that text to xAI and `parse_grok_response` turns the reply into a dict (`src/parser.py`). The second step has no network, so it is tested without an API key.
3. `store_invoice_data` writes the invoice and ingredients to Google Sheets (`src/sheets.py`).
4. Price changes and payment reminders are separate steps (`src/price_changes.py`, `src/payments.py`, `src/notifications.py`).
5. Local invoice images older than 30 days are deleted.

Sheets is intentional. It matched how the restaurant already worked. A multi-site version would use Postgres.

## Stack

Python, Flask, Twilio, Google Cloud Vision, xAI, Google Sheets, pytest.

## Setup

python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

Copy `.env.example` to `.env` and fill in Twilio, Google and xAI credentials. Do not commit `.env` or `credentials.json`.

pytest tests/test_parser.py -v

## Limits

Paid status comes from the message text, not from the invoice itself.
One request does OCR, the model call and the sheet write, so there is no queue.
Errors are reported back on WhatsApp, but the handlers are broad.