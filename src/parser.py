from openai import OpenAI
import json
import logging
from src.config import XAI_API_KEY

logger = logging.getLogger(__name__)

client = OpenAI(api_key=XAI_API_KEY, base_url="https://api.x.ai/v1")

def parse_invoice_text(text, paid_status):
    """Parse OCR-extracted text into structured JSON using Grok-3."""
    prompt = f"""
    You are an expert at extracting data from Polish invoices. Parse the provided invoice text into a JSON object with the exact structure below. The invoice is in Polish, prices are in PLN, and formats may vary.

    ```json
    {{
        "ingredients": [
            {{
                "name": "string",
                "unit": "kg|l|szt|zgrz|kart",
                "net_price_per_unit": float,
                "vat_percent": float,
                "gross_price_per_unit": float,
                "category": "JEDZENIE|NAPOJE|NAPOJE ALKOHOLOWE|CHEMIA|INNE"
            }}
        ],
        "invoice_date": "DD.MM.YYYY",
        "due_date": "DD.MM.YYYY",
        "total": float,
        "paid": "T|N",
        "seller": "string",
        "category": "JEDZENIE|NAPOJE|NAPOJE ALKOHOLOWE|CHEMIA|INNE",
        "invoice_number": "string"
    }}
    ```

    **Input**:
    - Invoice text: {text}
    - Paid status: {paid_status} (T for paid, N for unpaid)

    **Instructions**:
    - **Ingredients**:
      - Extract each ingredient's name, unit, net price per unit, VAT percent, and gross price per unit.
      - Assign a category based on the ingredient:
        - JEDZENIE: Food items (e.g., kukurydza, mięso, makaron, sery).
        - NAPOJE: Non-alcoholic drinks (e.g., woda, sok, lemoniada).
        - NAPOJE ALKOHOLOWE: Alcoholic drinks (e.g., piwo, wino, wódka).
        - CHEMIA: Cleaning products or chemicals.
        - INNE: Other items (e.g., packaging, services).
      - Ignore non-ingredient items (e.g., discounts, fees).
      - Example: "Kukurydza kolby 2,5kg Oerlemans, Cena netto: 10,00 PLN, VAT: 5%" → 
        {{ "name": "Kukurydza kolby 2,5kg Oerlemans", "unit": "kg", "net_price_per_unit": 10.00, "vat_percent": 5.0, "gross_price_per_unit": 10.50, "category": "JEDZENIE" }}
    - **Invoice Date**:
      - Find the issuance date (e.g., "Data wystawienia", "Data sprzedaży", or standalone "10.04.2025").
      - Use format DD.MM.YYYY. If ambiguous, pick the most likely date.
    - **Due Date**:
      - Find the payment due date (e.g., "Termin płatności", "Płatne do", or "Płatność 7 dni").
      - If "Płatność X dni", calculate as invoice_date + X days.
      - If missing, assume invoice_date + 7 days.
      - Use format DD.MM.YYYY.
    - **Total**:
      - Extract the total invoice amount (gross, in PLN).
    - **Paid**:
      - Use the provided paid_status (T or N).
    - **Seller**:
      - Extract the seller's name (e.g., from "Sprzedawca" or header).
      - If missing, use "Unknown".
    - **Category**:
      - Assign based on the dominant ingredient category (most items).
      - If unclear, use "INNE".
    - **Invoice Number**:
      - Find the invoice number (e.g., "Numer faktury", "FV/2025/123", "2025-04-095").
      - If missing, use empty string ("").
    - **Rules**:
      - Return only valid JSON, no additional text or comments.
      - Skip unclear or incomplete ingredient entries but maintain JSON structure.
      - Handle Polish characters (e.g., ą, ę, ł) correctly.
      - If data is missing, use reasonable defaults (e.g., "Unknown" for seller, "" for invoice_number).

    **Example**:
    Input: "FAKTURA VAT 051/04/2025, Data wystawienia: 10.04.2025, Termin płatności: 17.04.2025, Sprzedawca: ABC Sp. z o.o., Kukurydza kolby 2,5kg Oerlemans, Cena netto: 10,00 PLN, VAT: 5%, Woda 1,5L, Cena netto: 2,00 PLN, VAT: 8%"
    Output:
    ```json
    {{
        "ingredients": [
            {{
                "name": "Kukurydza kolby 2,5kg Oerlemans",
                "unit": "kg",
                "net_price_per_unit": 10.00,
                "vat_percent": 5.0,
                "gross_price_per_unit": 10.50,
                "category": "JEDZENIE"
            }},
            {{
                "name": "Woda 1,5L",
                "unit": "l",
                "net_price_per_unit": 2.00,
                "vat_percent": 8.0,
                "gross_price_per_unit": 2.16,
                "category": "NAPOJE"
            }}
        ],
        "invoice_date": "10.04.2025",
        "due_date": "17.04.2025",
        "total": 12.66,
        "paid": "T",
        "seller": "ABC Sp. z o.o.",
        "category": "JEDZENIE",
        "invoice_number": "051/04/2025"
    }}
    ```
    """
    try:
        response = client.chat.completions.create(
            model="grok-3-beta",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2000,
            temperature=0.2
        )
        raw_response = response.choices[0].message.content
        logger.debug(f"Raw Grok response: {raw_response}")
        parsed_data = json.loads(raw_response)
        logger.info("Successfully parsed invoice data")
        return parsed_data
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON from Grok: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to parse invoice: {e}")
        return None