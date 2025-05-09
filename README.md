# Restaurant Invoice Tracker

Automates invoice processing for a restaurant, tracking ingredient prices and payment due dates.

## Features
- Receive invoice photos via WhatsApp.
- Extract text with Google Cloud Vision API.
- Parse data with xAI Grok-3.
- Store data in Google Sheets.
- Detect price changes (>5%) and notify via WhatsApp.
- Track payment due dates and send reminders for invoices due in <3 days.

## Setup
1. **Clone the repository**:
   ```bash
   git clone <repo-url>
   cd restaurant-invoice-tracker