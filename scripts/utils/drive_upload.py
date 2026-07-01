"""
scripts/utils/drive_upload.py
==============================
Google Drive upload utilities for the education data pipeline.

Provides:
  - upload_file_to_drive()      : upload a single file to a Drive folder
  - get_or_create_drive_folder(): look up or create a subfolder in Drive
  - upload_state_folder()       : recursively mirror a local folder to Drive

Authentication uses a service account JSON key file (path defined in config.py
as GOOGLE_SERVICE_ACCOUNT_JSON).  The service account must have Editor access
to the target Drive folder.

All errors are caught and logged — no function will raise or crash the pipeline.
"""

import logging
import sys
from pathlib import Path

# Ensure config is importable when called standalone
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy imports — these packages are optional at import time so that the rest
# of the pipeline can run even if google-api-python-client is not installed.
# ---------------------------------------------------------------------------
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
    _GOOGLE_AVAILABLE = True
except ImportError:
    _GOOGLE_AVAILABLE = False
    logger.warning(
        "google-api-python-client / google-auth not installed. "
        "Drive upload will be disabled. Run: pip install google-api-python-client google-auth google-auth-httplib2"
    )


def _get_drive_service():
    """
    Build and return an authenticated Google Drive API v3 service object.

    Uses the service account JSON file path from config.py.

    Returns
    -------
    googleapiclient.discovery.Resource | None
        Drive service object, or None if authentication fails.
    """
    if not _GOOGLE_AVAILABLE:
        logger.error("Google Drive client libraries not available.")
        return None

    try:
        from config import GOOGLE_SERVICE_ACCOUNT_JSON, ROOT_DIR
        sa_path = ROOT_DIR / GOOGLE_SERVICE_ACCOUNT_JSON
        if not sa_path.exists():
            logger.error(
                "Service account JSON not found at: %s. "
                "Place your credentials file there or update GOOGLE_SERVICE_ACCOUNT_JSON in config.py.",
                sa_path,
            )
            return None

        scopes = ["https://www.googleapis.com/auth/drive"]
        credentials = service_account.Credentials.from_service_account_file(
            str(sa_path), scopes=scopes
        )
        service = build("drive", "v3", credentials=credentials, cache_discovery=False)
        return service

    except Exception as exc:
        logger.error("Failed to build Drive service: %s", exc)
        return None


def get_or_create_drive_folder(parent_folder_id: str, folder_name: str) -> str | None:
    """
    Return the Drive folder ID for *folder_name* inside *parent_folder_id*.

    If a folder with that name already exists, its ID is returned.
    If it does not exist, a new folder is created and its ID is returned.

    Parameters
    ----------
    parent_folder_id : str
        The Google Drive folder ID of the parent directory.
    folder_name      : str
        The name of the subfolder to look up or create.

    Returns
    -------
    str | None
        Drive folder ID, or None on failure.
    """
    service = _get_drive_service()
    if service is None:
        return None

    try:
        # Search for existing folder
        query = (
            f"name = '{folder_name}' "
            f"and '{parent_folder_id}' in parents "
            f"and mimeType = 'application/vnd.google-apps.folder' "
            f"and trashed = false"
        )
        response = service.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name)",
        ).execute()

        files = response.get("files", [])
        if files:
            folder_id = files[0]["id"]
            logger.debug("Found existing Drive folder '%s' → id=%s", folder_name, folder_id)
            return folder_id

        # Create new folder
        metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
            "parents": [parent_folder_id],
        }
        created = service.files().create(body=metadata, fields="id").execute()
        folder_id = created.get("id")
        logger.info("Created Drive folder '%s' → id=%s", folder_name, folder_id)
        return folder_id

    except Exception as exc:
        logger.error(
            "get_or_create_drive_folder failed (parent=%s, name='%s'): %s",
            parent_folder_id, folder_name, exc,
        )
        return None


def upload_file_to_drive(local_file_path: str | Path, drive_folder_id: str) -> str | None:
    """
    Upload a single local file to a Google Drive folder.

    If a file with the same name already exists in that Drive folder, the upload
    is skipped (no duplicate created in Drive).

    Parameters
    ----------
    local_file_path : str | Path
        Absolute path to the file to upload.
    drive_folder_id : str
        The Google Drive folder ID to upload the file into.

    Returns
    -------
    str | None
        The Drive file ID on success, or None on skip/failure.
    """
    service = _get_drive_service()
    if service is None:
        return None

    local_path = Path(local_file_path)
    if not local_path.exists():
        logger.error("upload_file_to_drive: file does not exist: %s", local_path)
        return None

    filename = local_path.name

    try:
        # Check if file already exists in the target Drive folder
        query = (
            f"name = '{filename}' "
            f"and '{drive_folder_id}' in parents "
            f"and trashed = false"
        )
        response = service.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name)",
        ).execute()

        existing = response.get("files", [])
        if existing:
            existing_id = existing[0]["id"]
            logger.info(
                "Drive SKIP (already exists): '%s' → Drive id=%s",
                filename, existing_id,
            )
            return existing_id   # Return existing ID so caller can record it

        # Upload the file
        media = MediaFileUpload(str(local_path), resumable=True)
        metadata = {
            "name": filename,
            "parents": [drive_folder_id],
        }
        uploaded = service.files().create(
            body=metadata,
            media_body=media,
            fields="id",
        ).execute()
        drive_id = uploaded.get("id")
        logger.info("Drive UPLOAD success: '%s' → Drive id=%s", filename, drive_id)
        return drive_id

    except Exception as exc:
        logger.error("upload_file_to_drive failed for '%s': %s", filename, exc)
        return None


def upload_state_folder(local_state_path: str | Path, drive_root_folder_id: str) -> dict:
    """
    Recursively mirror a local state data folder to Google Drive.

    Walks the entire *local_state_path* directory tree, creates matching
    subfolders in Drive using get_or_create_drive_folder(), and uploads
    every file found using upload_file_to_drive().

    Parameters
    ----------
    local_state_path     : str | Path
        Root of the local state data directory (e.g. data/nevada/).
    drive_root_folder_id : str
        Drive folder ID to use as the mirror root.

    Returns
    -------
    dict
        Summary with keys "uploaded", "skipped", "failed" (int counts).
    """
    local_root = Path(local_state_path)
    summary = {"uploaded": 0, "skipped": 0, "failed": 0}

    if not local_root.exists():
        logger.error("upload_state_folder: local path does not exist: %s", local_root)
        return summary

    logger.info(
        "Starting Drive mirror: %s → Drive folder %s",
        local_root, drive_root_folder_id,
    )

    # Walk directory tree
    for item in sorted(local_root.rglob("*")):
        if item.is_dir():
            continue  # Folders are created on-demand before file upload

        # Build the relative path from the state root, e.g. assessments/by_race
        rel = item.relative_to(local_root)
        parts = list(rel.parts)

        # Traverse/create Drive folders to match local hierarchy
        current_folder_id = drive_root_folder_id
        for part in parts[:-1]:   # all directory parts except the filename
            current_folder_id = get_or_create_drive_folder(current_folder_id, part)
            if current_folder_id is None:
                logger.error("Could not get/create Drive folder '%s'. Skipping file: %s", part, item)
                summary["failed"] += 1
                break
        else:
            # Upload the file into the deepest folder
            drive_id = upload_file_to_drive(item, current_folder_id)
            if drive_id:
                summary["uploaded"] += 1
            else:
                summary["failed"] += 1

    logger.info(
        "Drive mirror complete: %d uploaded, %d skipped, %d failed",
        summary["uploaded"], summary["skipped"], summary["failed"],
    )
    return summary
