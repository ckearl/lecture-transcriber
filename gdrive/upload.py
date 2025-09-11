import os.path
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





def upload(audio_file_path: str, class_number: str, class_name: str, date: str, file_name: str):
    creds = None
    
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)

    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                'credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)

        # Save the credentials for the next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('drive', 'v3', credentials=creds)

        file_path = audio_file_path
        
        file_name = os.path.basename(file_path)

        folder_id = '1PewFdbSlJ0hDAKuShx1tNvu-g-pJYCbj'

        # File metadata
        file_metadata = {
            'name': file_name,
            'parents': [folder_id] # Uncomment to upload to a specific folder
        }

        # Media file upload
        # .wav mimetype is 'audio/wav'
        media = MediaFileUpload(
            file_path, mimetype='audio/wav', resumable=True)

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

