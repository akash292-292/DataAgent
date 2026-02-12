"""
Google Drive Routes
API endpoints for Google Drive operations
"""
import gc
import io
import logging
import pathlib
import tempfile

import pandas as pd
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaIoBaseDownload

from services.auth_service import get_drive_service, get_fresh_access_token, make_session_token
from utils.file_utils import detect_and_cast_numeric
from utils.memory_utils import USER_STORE
from utils.security import get_effective_email, validate_file_id, validate_short_text

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Google Drive"], prefix="/api/drive")


@router.get("/search")
def search_drive(request: Request, email: str = Query(None), q: str = Query("")):
    """Search Google Drive for files."""
    try:
        user_email = get_effective_email(request, email)
        query_text = validate_short_text(q, "query", max_len=120) or ""
        service = get_drive_service(user_email)
        query = (
            f"name contains '{query_text}' and "
            "mimeType != 'application/vnd.google-apps.folder' and trashed=false"
        )

        response = service.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name, mimeType, modifiedTime)",
            pageSize=20,
        ).execute()

        files = response.get("files", [])
        logger.info("Drive search found %s files", len(files))
        return {"files": files}
    except Exception as exc:
        logger.error("Drive search error: %s", exc)
        return JSONResponse({"error": str(exc), "files": []}, status_code=500)


@router.get("/getfile")
def get_drive_file(request: Request, email: str = Query(None), file_id: str = Query(...)):
    """
    Download file from Google Drive and save to disk.
    """
    try:
        user_email = get_effective_email(request, email)
        normalized_file_id = validate_file_id(file_id)
        service = get_drive_service(user_email)

        try:
            file = service.files().get(
                fileId=normalized_file_id,
                fields="id, name, mimeType, owners, capabilities",
                supportsAllDrives=True,
            ).execute()
        except HttpError as exc:
            if exc.resp.status == 404:
                return JSONResponse(
                    {
                        "error": "File not found or access denied",
                        "details": "Ensure the file exists and your account has permission.",
                        "file_id": normalized_file_id,
                    },
                    status_code=404,
                )
            raise

        filename = file["name"]
        mime_type = file["mimeType"]
        logger.info("Drive file selected: %s (%s)", filename, mime_type)

        buffer = io.BytesIO()
        if mime_type.startswith("application/vnd.google-apps.spreadsheet"):
            request_data = service.files().export_media(
                fileId=normalized_file_id, mimeType="text/csv"
            )
            if not filename.endswith(".csv"):
                filename = filename.rsplit(".", 1)[0] + ".csv"
        elif mime_type.startswith("application/vnd.google-apps.document"):
            request_data = service.files().export_media(
                fileId=normalized_file_id, mimeType="text/plain"
            )
        elif mime_type.startswith("application/vnd.google-apps"):
            return JSONResponse(
                {
                    "error": f"Unsupported Google Workspace file type: {mime_type}",
                    "details": "Convert to CSV, Excel, or PDF first.",
                    "file_name": filename,
                },
                status_code=400,
            )
        else:
            request_data = service.files().get_media(
                fileId=normalized_file_id, supportsAllDrives=True
            )

        downloader = MediaIoBaseDownload(buffer, request_data)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        buffer.seek(0)

        suffix = pathlib.Path(filename).suffix or ".csv"
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_path = temp_file.name
        with open(temp_path, "wb") as handle:
            handle.write(buffer.getbuffer())

        USER_STORE.setdefault(user_email, {})
        USER_STORE[user_email]["file_path"] = temp_path
        USER_STORE[user_email]["filename"] = filename
        if "dataframe" in USER_STORE[user_email]:
            del USER_STORE[user_email]["dataframe"]
        gc.collect()

        try:
            if filename.lower().endswith(".csv"):
                df_preview = pd.read_csv(temp_path, nrows=5, dtype=str)
            else:
                df_preview = pd.read_excel(temp_path, nrows=5)
        except Exception as exc:
            raise HTTPException(status_code=400, detail=f"Failed to parse file: {exc}")

        df_preview = detect_and_cast_numeric(df_preview)
        session_token = make_session_token(user_email, filename)
        USER_STORE[user_email]["last_session_token"] = session_token
        preview = (
            df_preview.replace({float("inf"): None, float("-inf"): None})
            .fillna("")
            .to_dict(orient="records")
        )

        return {
            "name": filename,
            "local_path": session_token,
            "preview": preview,
            "columns": list(df_preview.columns),
            "size_kb": round(buffer.getbuffer().nbytes / 1024, 2),
        }
    except Exception as exc:
        logger.error("Drive file error: %s", exc)
        return JSONResponse({"error": str(exc)}, status_code=500)


@router.get("/picker-token")
def get_picker_token(request: Request, email: str = Query(None)):
    """
    Return a fresh access token for Google Picker.
    Do not persist this token in browser storage.
    """
    user_email = get_effective_email(request, email)
    access_token = get_fresh_access_token(user_email)
    return {"access_token": access_token}
