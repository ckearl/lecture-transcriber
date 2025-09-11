import os.path
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Use the same scopes as the upload script
SCOPES = ['https://www.googleapis.com/auth/drive']

script_dir = os.path.dirname(__file__)

with open(script_dir + '/folder_ids.json', 'r') as f:
    folder_ids = json.load(f)
    
current_files = {
    "MBA 500 Career Development": [],
	"MBA 501 Corporate Financial Reporting": [],
	"MBA 505 Leadership": [],
	"MBA 520 Business Finance": [],
	"MBA 530 Operations Management": [],
	"MBA 548 Strategic Human Resource Mgt": [],
	"MBA 550 Marketing Management": [],
	"MBA 593R Management Seminar": []
}

def read(class_name: str):
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('drive', 'v3', credentials=creds)

        # --- LIST FILES IN A FOLDER ---

        folder_id = folder_ids[class_name]

        # The 'q' parameter is a search query.
        # Here, it's searching for all files ('*') whose 'parents' list contains the folder_id.
        query = f"'{folder_id}' in parents"

        response = service.files().list(
            q=query,
            pageSize=100,  # Adjust as needed
            fields="nextPageToken, files(id, name)"
        ).execute()

        items = response.get('files', [])

        if not items:
            print('No files found in this folder.')
        else:
            print(f'Files in folder "{class_name}":')
            for item in items:
                print(f"{item['name']} ({item['id']})")
                current_files[class_name].append(item['name'])

    except HttpError as error:
        print(f'An error occurred: {error}')


def loop():
    for class_name in folder_ids.keys():
        if class_name != 'lecture recordings':
            read(class_name)