"""
drive_uploader.py – Google Drive API helpers.

Handles OAuth 2.0 authentication, idempotent folder creation,
and file upload with overwrite-by-name logic.
"""

import logging
import mimetypes
import os
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive"]

# Resolved at runtime from config
_HERE = os.path.dirname(os.path.abspath(__file__))
_CONFIG_DIR = os.path.join(_HERE, "..", "config")
_CREDS_DIR = os.path.join(_HERE, "..", "credentials")

CLIENT_SECRETS = os.path.join(_CREDS_DIR, "client_secrets.json")
TOKEN_FILE = os.path.join(_CREDS_DIR, "token.json")


def get_drive_service():
    """Authenticate and return a Google Drive API service instance."""
    creds = None

    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CLIENT_SECRETS):
                raise FileNotFoundError(
                    f"Missing OAuth client secrets at: {CLIENT_SECRETS}\n"
                    "Download from GCP Console → APIs & Services → Credentials → "
                    "OAuth 2.0 Client IDs → Download JSON → save as credentials/client_secrets.json"
                )
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS, SCOPES)
            creds = flow.run_local_server(port=0)

        with open(TOKEN_FILE, "w") as token:
            token.write(creds.to_json())

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
