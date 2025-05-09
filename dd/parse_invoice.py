from openai import OpenAI
from google.cloud import vision
import os
import json


# Konfiguracja xAI API
client = OpenAI(
    api_key=os.environ.get('XAI_API_KEY'),
    base_url="https://api.x.ai/v1"
)

def detect_text(image_path):
    client_vision = vision.ImageAnnotatorClient()
    with open(image_path, 'rb') as image_file:
        content = image_file.read()
    image = vision.Image(content=content)
    response = client_vision.text_detection(image=image)
    return response.text_annotations[0].description if response.text_annotations else ""

def parse_invoice_text(text, paid_status):
    prompt = f"""
    Masz tekst z polskiej faktury. Wyodrębnij dane w formacie JSON:
    - ingredients: lista składników z nazwą, ceną (PLN, liczba zmiennoprzecinkowa) i kategorią (NAPOJE ALKOHOLOWE, JEDZENIE, CHEMIA, INNE)
    - invoice_date: data faktury (format DD.MM.YYYY)
    - due_date: data płatności (format DD.MM.YYYY, oblicz jeśli podano np. "termin płatności 10 dni")
    - total: kwota całkowita (PLN, liczba zmiennoprzecinkowa)
    - paid: status płatności ("T" lub "N")
    Tekst faktury: {text}
    Status płatności: {paid_status}
    Odpowiedz TYLKO w formacie JSON. Upewnij się, że daty są w formacie DD.MM.YYYY, a ceny i kwota całkowita to liczby zmiennoprzecinkowe.
    """
    response = client.chat.completions.create(
        model="grok-3-beta",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=1000
    )
    try:
        # Parsuj odpowiedź jako JSON
        return json.loads(response.choices[0].message.content)
    except json.JSONDecodeError:
        print("Błąd: Grok nie zwrócił poprawnego JSON")
        return None

if __name__ == "__main__":
    # Przetwórz ostatnie zdjęcie z folderu invoices
    invoice_folder = "invoices"
    invoice_files = [f for f in os.listdir(invoice_folder) if f.endswith('.jpg')]
    if not invoice_files:
        print("Brak zdjęć w folderze invoices")
        exit()
    test_image = sorted(invoice_files)[-1]  # Ostatnie zdjęcie
    image_path = os.path.join(invoice_folder, test_image)
    paid_status = test_image.split('_')[-1].replace('.jpg', '')  # Pobierz status (T/N)
    text = detect_text(image_path)
    print("Wyodrębniony tekst:")
    print(text)
    json_data = parse_invoice_text(text, paid_status)
    if json_data:
        print("\nSparsowane dane JSON:")
        print(json.dumps(json_data, indent=2, ensure_ascii=False))