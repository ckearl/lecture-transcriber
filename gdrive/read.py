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


def get_credentials():
    """Get valid Google Drive API credentials."""
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

    return creds


def get_files_in_folder(service, folder_id, class_name):
    """Get all files in a specific folder."""
    files = []
    page_token = None

    try:
        while True:
            query = f"'{folder_id}' in parents and trashed=false"

            response = service.files().list(
                q=query,
                pageSize=100,
                fields="nextPageToken, files(id, name, mimeType)",
                pageToken=page_token
            ).execute()

            items = response.get('files', [])

            for item in items:
                # Only include actual files, not folders
                if item['mimeType'] != 'application/vnd.google-apps.folder':
                    files.append(item['name'])
                    print(f"Found in {class_name}: {item['name']}")

            page_token = response.get('nextPageToken')
            if not page_token:
                break

    except HttpError as error:
        print(f'An error occurred reading {class_name}: {error}')

    return files


def read(class_name: str):
    """Read files from a specific class folder."""
    if class_name not in folder_ids:
        print(f"Class '{class_name}' not found in folder_ids.json")
        return []

    try:
        creds = get_credentials()
        service = build('drive', 'v3', credentials=creds)

        folder_id = folder_ids[class_name]
        files = get_files_in_folder(service, folder_id, class_name)

        if not files:
            print(f'No files found in folder "{class_name}"')
        else:
            print(f'Found {len(files)} files in "{class_name}"')

        return files

    except HttpError as error:
        print(f'An error occurred: {error}')
        return []


def loop():
    """Loop through all class folders and return all filenames."""
    all_files = []
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

    try:
        creds = get_credentials()
        service = build('drive', 'v3', credentials=creds)

        for class_name in folder_ids.keys():
            if class_name != 'lecture recordings':  # Skip the parent folder
                print(f"\nScanning folder: {class_name}")
                files = get_files_in_folder(
                    service, folder_ids[class_name], class_name)
                current_files[class_name] = files
                all_files.extend(files)

        print(f"\nTotal files found across all folders: {len(all_files)}")
        return all_files

    except Exception as error:
        print(f'An error occurred in loop(): {error}')
        return []
