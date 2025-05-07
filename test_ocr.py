from google.cloud import vision
import os

def detect_text(image_path):
    client = vision.ImageAnnotatorClient()
    with open(image_path, 'rb') as image_file:
        content = image_file.read()
    image = vision.Image(content=content)
    response = client.text_detection(image=image)
    return response.text_annotations[0].description if response.text_annotations else ""

if __name__ == "__main__":
    # Zastąp ścieżką do testowego zdjęcia (np. z folderu invoices)
    test_image = "invoices/test.jpg"  # Użyj istniejącego zdjęcia lub skopiuj jedno
    text = detect_text(test_image)
    print("Wyodrębniony tekst:", text)