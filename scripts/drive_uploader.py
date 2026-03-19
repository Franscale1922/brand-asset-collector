"""
drive_uploader.py – Google Drive API helpers.

Uses service account authentication (no browser pop-up required).
Set SERVICE_ACCOUNT_FILE in config/settings.py or via environment variable
GOOGLE_SERVICE_ACCOUNT_JSON.

Handles idempotent folder creation and file upload with overwrite-by-name logic.
"""

import logging
import mimetypes
import os
from typing import Optional

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]

_HERE = os.path.dirname(os.path.abspath(__file__))
_CREDS_DIR = os.path.join(_HERE, "..", "credentials")

# Default service account key location – override via env var
_DEFAULT_SA_KEY = os.path.join(_CREDS_DIR, "service-account.json")


def get_drive_service(service_account_file: Optional[str] = None):
    """
    Authenticate using a service account and return a Google Drive API service.

    Priority for key file:
      1. `service_account_file` argument
      2. GOOGLE_SERVICE_ACCOUNT_JSON environment variable
      3. credentials/service-account.json (default)
    """
    key_path = (
        service_account_file
        or os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")
        or _DEFAULT_SA_KEY
    )

    if not os.path.exists(key_path):
        raise FileNotFoundError(
            f"Service account key not found at: {key_path}\n"
            "Copy your service account JSON to credentials/service-account.json\n"
            "or set the GOOGLE_SERVICE_ACCOUNT_JSON environment variable.\n"
            f"Service account email: local-websites-sheets@local-websites-490618.iam.gserviceaccount.com"
        )

    creds = service_account.Credentials.from_service_account_file(
        key_path, scopes=SCOPES
    )
    logger.debug("Authenticated via service account: %s", creds.service_account_email)
    return build("drive", "v3", credentials=creds)


def get_or_create_folder(service, parent_id: str, folder_name: str) -> str:
    """
    Get the Drive folder ID for `folder_name` inside `parent_id`.
    Creates the folder if it doesn't exist.
    Returns folder ID.
    """
    query = (
        f"name='{folder_name}' "
        f"and mimeType='application/vnd.google-apps.folder' "
        f"and '{parent_id}' in parents "
        f"and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])

    if files:
        folder_id = files[0]["id"]
        logger.debug("  Found existing Drive folder '%s' (id=%s)", folder_name, folder_id)
        return folder_id

    # Create
    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
        "parents": [parent_id],
    }
    folder = service.files().create(body=metadata, fields="id").execute()
    folder_id = folder["id"]
    logger.info("  Created Drive folder '%s' (id=%s)", folder_name, folder_id)
    return folder_id


def upload_file(
    service,
    folder_id: str,
    local_path: str,
    overwrite: bool = True,
) -> Optional[str]:
    """
    Upload a local file to a Drive folder.
    If `overwrite=True`, deletes any existing file with the same name first.
    Returns the Drive file ID.
    """
    filename = os.path.basename(local_path)
    mime_type, _ = mimetypes.guess_type(local_path)
    mime_type = mime_type or "application/octet-stream"

    if overwrite:
        # Find and delete existing file with same name
        query = f"name='{filename}' and '{folder_id}' in parents and trashed=false"
        results = service.files().list(q=query, fields="files(id)").execute()
        for f in results.get("files", []):
            service.files().delete(fileId=f["id"]).execute()
            logger.debug("  Deleted existing Drive file: %s", filename)

    media = MediaFileUpload(local_path, mimetype=mime_type, resumable=True)
    metadata = {"name": filename, "parents": [folder_id]}
    uploaded = service.files().create(
        body=metadata, media_body=media, fields="id"
    ).execute()
    file_id = uploaded.get("id")
    logger.info("  Uploaded '%s' → Drive (id=%s)", filename, file_id)
    return file_id


def upload_folder_contents(service, folder_id: str, local_dir: str) -> dict:
    """
    Upload all files in `local_dir` to the Drive `folder_id`.
    Returns dict mapping filename → Drive file ID.
    """
    results = {}
    for fname in os.listdir(local_dir):
        fpath = os.path.join(local_dir, fname)
        if os.path.isfile(fpath):
            file_id = upload_file(service, folder_id, fpath)
            if file_id:
                results[fname] = file_id
    return results
