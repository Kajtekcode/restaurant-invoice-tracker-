import gspread
from oauth2client.service_account import ServiceAccountCredentials

# Zakres uprawnień
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)

# Otwórz arkusz
sheet = client.open_by_key('1GrLufeQeZMwP9vd3OYA2zhzh50FOiNFePWtP0PbCCXk').sheet1  # Zastąp ARKUSZ_ID
sheet.append_row(['Test', 'Dane', '123'])

print("Dodano wiersz do arkusza!")