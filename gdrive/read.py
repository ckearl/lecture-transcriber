import os.path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# Use the same scopes as the upload script
SCOPES = ['https://www.googleapis.com/auth/drive']


def read():
    """Lists the files in a specific Google Drive folder."""
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

        # IMPORTANT: Replace this with the ID of the folder you want to list
        folder_id = 'YOUR_FOLDER_ID_HERE'

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
            print('Files in folder:')
            for item in items:
                print(f"  - {item['name']} (ID: {item['id']})")

    except HttpError as error:
        print(f'An error occurred: {error}')


if __name__ == '__main__':
    main()
