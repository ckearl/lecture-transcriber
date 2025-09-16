import os.path
import json
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

# If modifying these scopes, delete the file token.json.
# This scope allows full read/write/create/delete access to Drive.
# For upload-only, you could use 'https://www.googleapis.com/auth/drive.file'
SCOPES = ['https://www.googleapis.com/auth/drive']

def upload(audio_file_path: str, class_number: str = None, class_name: str = None, date: str = None, file_name: str = None):
    script_dir = os.path.dirname(__file__)
    
    print(f"Script directory: {script_dir}")
    
    with open(script_dir + '/folder_ids.json', 'r') as f:
        folder_ids = json.load(f)
        
    creds = None
    
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(script_dir +
                '/credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('drive', 'v3', credentials=creds)

        file_path = audio_file_path
        
        # file_name = os.path.basename(file_path)

        folder_id = folder_ids[class_name]

        # File metadata
        file_metadata = {
            'name': file_name,
            'parents': [folder_id] # Uncomment to upload to a specific folder
        }
        
        print(f"\t->Uploading file: {file_name} to folder ID: {folder_id}")
        
        file_type = os.path.splitext(file_name)[1].lower()
        mime_types = {
            '.mp3': 'audio/mpeg',
            '.wav': 'audio/wav',
            '.m4a': 'audio/mp4',
            '.flac': 'audio/flac'
        }

        # Media file upload
        # TODO: switch this back to 'audio/wav' if uploading .wav files
        # .mp3 mimetype is 'audio/mpeg'
        media = MediaFileUpload(
            file_path, mimetype=mime_types.get(file_type, 'application/octet-stream'), resumable=True)

        # Create the file on Google Drive
        print(f"Uploading {file_name}...")
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()

        print(f"File uploaded successfully! 🚀")
        print(f"File ID: {file.get('id')}")

    except HttpError as error:
        print(f'An error occurred: {error}')

