import gspread
from oauth2client.service_account import ServiceAccountCredentials

scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key('1GrLufeQeZMwP9vd3OYA2zhzh50FOiNFePWtP0PbCCXk')  # Wstaw ARKUSZ_ID
print("Dostępne zakładki:", [ws.title for ws in spreadsheet.worksheets()])