import gspread
from oauth2client.service_account import ServiceAccountCredentials
from openai import OpenAI
import os
import json
from google.cloud import vision
from datetime import datetime, timedelta
from tenacity import retry, stop_after_attempt, wait_fixed, retry_if_exception_type
import requests.exceptions

# Konfiguracja Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
session = requests.Session()
session.timeout = 30
gspread_client = gspread.authorize(creds, session=session)
spreadsheet = gspread_client.open_by_key('1GrLufeQeZMwP9vd3OYA2zhzh50FOiNFePWtP0PbCCXk')  # Zastąp TWOJ_ARKUSZ_ID


# Konfiguracja xAI API
xai_client = OpenAI(
    api_key=os.environ.get('XAI_API_KEY'),
    base_url="https://api.x.ai/v1"
)

def detect_text(image_path):
    os.environ["GRPC_POLL_STRATEGY"] = "poll"
    client_vision = vision.ImageAnnotatorClient()
    with open(image_path, 'rb') as image_file:
        content = image_file.read()
    image = vision.Image(content=content)
    response = client_vision.text_detection(image=image)
    return response.text_annotations[0].description if response.text_annotations else ""

def parse_invoice_text(text, paid_status):
    prompt = f"""
    Masz tekst z polskiej faktury. Wyodrębnij dane w formacie JSON, dokładnie przestrzegając struktury poniżej:
    {{
        "ingredients": [
            {{"name": "nazwa składnika", "price": liczba_zmiennoprzecinkowa, "category": "JEDZENIE|NAPOJE|NAPOJE ALKOHOLOWE|CHEMIA|INNE"}},
            ...
        ],
        "invoice_date": "DD.MM.YYYY",
        "due_date": "DD.MM.YYYY",
        "total": liczba_zmiennoprzecinkowa,
        "paid": "T|N",
        "seller": "nazwa sprzedawcy",
        "category": "JEDZENIE|NAPOJE|NAPOJE ALKOHOLOWE|CHEMIA|INNE"
    }}
    Tekst faktury: {text}
    Status płatności: {paid_status}
    - Ceny w 'ingredients' to ceny jednostkowe netto (np. za kg, sztukę, litr; kolumna 'Cena netto' lub cena za jednostkę miary).
    - Ignoruj ceny brutto i sumy pozycji.
    - 'invoice_date': Znajdź datę wystawienia faktury. Może być oznaczona jako 'Data wystawienia', 'Data sprzedaży', 'Data dokumenty sprzedaży/wydania', lub występować samodzielnie (np. '10.04.2025'). Jeśli niejasna, wybierz najbardziej prawdopodobną datę w formacie DD.MM.YYYY lub DD/MM/YYYY.
    - 'due_date': Znajdź datę płatności. Może być oznaczona jako 'Termin płatności', 'Płatne do', lub podana w formie 'Płatność X dni' (np. 'Płatność 7 dni'). Jeśli podano 'Płatność X dni', oblicz jako 'invoice_date' plus X dni. Jeśli brak, przyjmij 'invoice_date' plus 7 dni. Użyj formatu DD.MM.YYYY.
    - Przykłady dat:
      - 'PAKTURA VAT 051/04/2025, Termin płatności 01.05.2025' → "invoice_date": "10.04.2025", "due_date": "01.05.2025"
      - 'Data wystawienia: 15.04.2025, Płatność 10 dni' → "invoice_date": "15.04.2025", "due_date": "25.04.2025"
      - '20.04.2025' (samodzielna data) → "invoice_date": "20.04.2025", "due_date": "27.04.2025" (plus 7 dni)
    - Kategorie składników:
      - JEDZENIE: produkty spożywcze (np. kukurydza, tuńczyk, makaron, mąka, mięso, sery, chorizo, sałaty).
      - NAPOJE: napoje bezalkoholowe (np. woda, sok limonkowy, lemoniada).
      - NAPOJE ALKOHOLOWE: alkohol (np. wino, piwo, wódka).
      - CHEMIA: środki czystości, chemikalia.
      - INNE: pozostałe (np. opakowania, usługi).
    - Przykłady kategorii:
      - 'Woda źródlana gazowana 1,5Lx6szt Soleo' → NAPOJE
      - 'Sok 100% limonkowy z 44 limonek 1L Polenghi' → NAPOJE
      - 'Kukurydza kolby 2,5kg Oerlemans' → JEDZENIE
      - 'Pieprz czarny młotkowany 700g Horeca Aroma' → JEDZENIE
    - Kategoria faktury na podstawie dominującej kategorii składników.
    - Ignoruj pozycje, które nie są składnikami (np. rabaty, usługi).
    - Odpowiedz TYLKO poprawnym JSON-em, bez żadnego dodatkowego tekstu, komentarzy, znaków ```json ani innych elementów.
    - Jeśli dane są niejasne, pomiń niepewne pozycje, ale zachowaj poprawną strukturę JSON.
    """
    response = xai_client.chat.completions.create(
        model="grok-3-beta",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=2000
    )
    raw_response = response.choices[0].message.content
    print("Surowa odpowiedź Grok:", raw_response)
    try:
        return json.loads(raw_response)
    except json.JSONDecodeError:
        print("Błąd: Grok nie zwrócił poprawnego JSON")
        return None

@retry(stop=stop_after_attempt(3), wait=wait_fixed(2), retry=retry_if_exception_type(requests.exceptions.ConnectionError))
def get_worksheet(spreadsheet, title):
    return spreadsheet.worksheet(title)

def detect_price_changes(ingredients, sheet_data, category):
    prompt = f"""
    Masz nową listę składników z faktury w kategorii {category}: {json.dumps(ingredients, ensure_ascii=False)}.
    Porównaj ceny z poprzednimi danymi z arkusza dla kategorii {category}: {json.dumps(sheet_data, ensure_ascii=False)}.
    Wskaż składniki, których cena zmieniła się o więcej niż 5%.
    Odpowiedz w formacie JSON: [{{ "name": "składnik", "old_price": liczba, "new_price": liczba, "change_percent": liczba }}]
    - Jeśli arkusz jest pusty, zwróć pustą listę [].
    - Odpowiedz TYLKO poprawnym JSON-em, bez żadnego dodatkowego tekstu, komentarzy, znaków ```json ani innych elementów.
    Użyj modelu Grok-3-mini-beta.
    """
    response = xai_client.chat.completions.create(
        model="grok-3-mini-beta",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=500
    )
    raw_response = response.choices[0].message.content
    print(f"Surowa odpowiedź Grok-3-mini-beta dla {category}: '{raw_response}'")
    try:
        return json.loads(raw_response)
    except json.JSONDecodeError as e:
        print(f"Błąd: Grok-3-mini-beta nie zwrócił poprawnego JSON dla kategorii {category}: {e}")
        return []

def calculate_days_to_due(due_date):
    try:
        due = datetime.strptime(due_date, '%d.%m.%Y')
        today = datetime.now()
        days_left = (due - today).days
        return days_left, "ALERT: Płatność za <3 dni!" if days_left < 3 else ""
    except ValueError:
        return None, "Błąd daty"

def sync_invoice_status():
    unpaid_sheet = get_worksheet(spreadsheet, "Faktury Niezapłacone")
    paid_sheet = get_worksheet(spreadsheet, "Faktury Zapłacone")
    unpaid_data = unpaid_sheet.get_all_records()
    rows_to_move = []
    for i, row in enumerate(unpaid_data, start=2):
        if row['Opłacona (T/N)'] == 'T':
            rows_to_move.append((i, [
                row['Data Wystawienia'],
                row['Sprzedawca'],
                row['Kwota Całkowita (PLN)'],
                row['Kategoria'],
                row['Termin Płatności'],
                row['Opłacona (T/N)'],
                row['Dni do Zapłaty']
            ]))
    for row_idx, row_data in reversed(rows_to_move):
        paid_sheet.append_row(row_data)
        unpaid_sheet.delete_rows(row_idx)
    unpaid_data = unpaid_sheet.get_all_records()
    sorted_data = sorted(unpaid_data, key=lambda x: float(x['Dni do Zapłaty']) if x['Dni do Zapłaty'].replace('.', '').isdigit() else float('inf'))
    if sorted_data:
        unpaid_sheet.clear()
        unpaid_sheet.append_row([
            "Data Wystawienia", "Sprzedawca", "Kwota Całkowita (PLN)", "Kategoria",
            "Termin Płatności", "Opłacona (T/N)", "Dni do Zapłaty"
        ])
        for row in sorted_data:
            unpaid_sheet.append_row([
                row['Data Wystawienia'],
                row['Sprzedawca'],
                row['Kwota Całkowita (PLN)'],
                row['Kategoria'],
                row['Termin Płatności'],
                row['Opłacona (T/N)'],
                row['Dni do Zapłaty']
            ])

if __name__ == "__main__":
    sync_invoice_status()
    invoice_folder = "invoices"
    invoice_files = [f for f in os.listdir(invoice_folder) if f.endswith('.jpg')]
    if not invoice_files:
        print("Brak zdjęć w folderze invoices")
        exit()
    test_image = sorted(invoice_files)[-1]
    image_path = os.path.join(invoice_folder, test_image)
    paid_status = test_image.split('_')[-1].replace('.jpg', '')
    text = detect_text(image_path)
    print("Wyodrębniony tekst:")
    print(text)
    json_data = parse_invoice_text(text, paid_status)
    if not json_data:
        print("Nie udało się sparsować danych faktury")
        exit()

    days_left, alert = calculate_days_to_due(json_data['due_date'])
    target_sheet = get_worksheet(spreadsheet, "Faktury Zapłacone" if json_data['paid'] == 'T' else "Faktury Niezapłacone")
    target_sheet.append_row([
        json_data['invoice_date'],
        json_data['seller'],
        json_data['total'],
        json_data['category'],
        json_data['due_date'],
        json_data['paid'],
        alert if alert else days_left if days_left is not None else "Błąd daty"
    ])

    category_sheets = {}
    for category in ["JEDZENIE", "NAPOJE", "NAPOJE ALKOHOLOWE", "CHEMIA", "INNE"]:
        try:
            category_sheets[category] = get_worksheet(spreadsheet, category)
        except gspread.exceptions.WorksheetNotFound:
            print(f"Zakładka {category} nie znaleziona")
            continue
    for ingredient in json_data['ingredients']:
        category = ingredient['category']
        if category in category_sheets:
            category_sheets[category].append_row([
                json_data['invoice_date'],
                ingredient['name'],
                ingredient['price'],
                json_data['seller']
            ])

    for category in category_sheets:
        sheet_data = category_sheets[category].get_all_records()
        category_ingredients = [ing for ing in json_data['ingredients'] if ing['category'] == category]
        if category_ingredients and sheet_data:
            price_changes = detect_price_changes(category_ingredients, sheet_data, category)
            if price_changes:
                print(f"Wykryto zmiany cen (>5%) w kategorii {category}:")
                for change in price_changes:
                    print(f"Składnik: {change['name']}, Stara cena: {change['old_price']} PLN, Nowa cena: {change['new_price']} PLN, Zmiana: {change['change_percent']}%")

    sync_invoice_status()
    print("Dane zapisane do arkusza!")