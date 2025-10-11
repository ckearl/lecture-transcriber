import os
import io
from pathlib import Path
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.errors import HttpError
from .read import get_credentials


def download_file(file_id: str, destination_path: str) -> bool:
    """Download a file from Google Drive.

    Args:
        file_id: Google Drive file ID
        destination_path: Local path where the file should be saved

    Returns:
        True if successful, False otherwise
    """
    try:
        creds = get_credentials()
        service = build('drive', 'v3', credentials=creds)

        # Get file metadata to show progress
        file_metadata = service.files().get(fileId=file_id, fields='name,size').execute()
        file_name = file_metadata.get('name')
        file_size = int(file_metadata.get('size', 0))

        print(f"Downloading {file_name} ({file_size / (1024*1024):.1f} MB)...")

        # Download the file
        request = service.files().get_media(fileId=file_id)

        # Create parent directory if it doesn't exist
        Path(destination_path).parent.mkdir(parents=True, exist_ok=True)

        fh = io.FileIO(destination_path, 'wb')
        downloader = MediaIoBaseDownload(fh, request)

        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                print(f"Download progress: {int(status.progress() * 100)}%")

        fh.close()
        print(f"✅ Downloaded: {file_name}")
        return True

    except HttpError as error:
        print(f"❌ Download failed: {error}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error during download: {e}")
        return False


def download_file_to_temp(file_id: str, filename: str) -> str:
    """Download a file to a temporary directory.

    Args:
        file_id: Google Drive file ID
        filename: Name for the downloaded file

    Returns:
        Path to the downloaded file, or None if failed
    """
    temp_dir = Path("temp_downloads")
    temp_dir.mkdir(exist_ok=True)

    destination_path = temp_dir / filename

    if download_file(file_id, str(destination_path)):
        return str(destination_path)
    return None
