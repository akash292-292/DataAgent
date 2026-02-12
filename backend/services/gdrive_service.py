"""
Google Drive Services
Handles all Google Drive operations: upload, download, search, permissions
"""
import io
import ssl
import time
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
import pandas as pd
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from googleapiclient.errors import HttpError

from services.auth_service import get_drive_service
from utils.file_utils import safe_json_parse

logger = logging.getLogger(__name__)


# ==================== SEARCH & METADATA ====================

def find_folder_by_name(foldername: str, email: str, access_token: Optional[str] = None):
    """Find folder(s) by exact name."""
    service = get_drive_service(email, access_token)
    res = (
        service.files()
        .list(
            q=f"name='{foldername}' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id, name)",
            pageSize=10,
        )
        .execute()
    )
    return res.get("files", [])


def find_files_containing(keyword: str, email: str, access_token: Optional[str] = None):
    """Search files by partial name (case-insensitive)."""
    try:
        service = get_drive_service(email, access_token)
        query = f"name contains '{keyword}' and trashed=false"
        results = (
            service.files()
            .list(q=query, fields="files(id, name, mimeType, modifiedTime)", pageSize=20)
            .execute()
        )
        return results.get("files", [])
    except ssl.SSLEOFError:
        logger.warning("⚠️ SSL error, retrying...")
        time.sleep(1)
        return find_files_containing(keyword, email, access_token)
    except Exception as e:
        logger.error(f"❌ Error searching files: {e}")
        return []


def find_file_by_id(file_id: str, email: str, access_token: Optional[str] = None):
    """Get exact file metadata by ID."""
    try:
        service = get_drive_service(email, access_token)
        file = service.files().get(
            fileId=file_id,
            fields="id, name, mimeType, parents",
            supportsAllDrives=True
        ).execute()
        logger.info(f"✅ Found file: {file.get('name')} (ID: {file_id})")
        return file
    except HttpError as e:
        if e.resp.status == 404:
            logger.error(f"❌ File not found or no access: {file_id}")
        else:
            logger.error(f"❌ Error fetching file {file_id}: {e}")
        return None
    except Exception as e:
        logger.error(f"❌ Failed to fetch file metadata for {file_id}: {e}")
        return None


def get_file_metadata(file_id: str, email: str, access_token: Optional[str] = None):
    """Alias for find_file_by_id for backward compatibility"""
    return find_file_by_id(file_id, email, access_token)


# ==================== DOWNLOAD ====================

def download_file_bytes(file_id: str, email: str, access_token: Optional[str] = None) -> bytes:
    """
    Downloads or exports Google Drive files properly.
    Handles both native Google formats (Sheets, Docs) and regular files.
    """
    try:
        service = get_drive_service(email, access_token)
        file_meta = service.files().get(fileId=file_id, fields="id, name, mimeType").execute()
        mime_type = file_meta.get("mimeType", "")
        file_name = file_meta.get("name", "downloaded_file")

        # Google-native formats need to be exported
        export_mime_map = {
            "application/vnd.google-apps.spreadsheet": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.google-apps.document": "text/plain",
            "application/vnd.google-apps.presentation": "application/pdf",
        }

        if mime_type in export_mime_map:
            export_mime = export_mime_map[mime_type]
            logger.info(f"📤 Exporting Google file {file_name} as {export_mime}")
            request = service.files().export_media(fileId=file_id, mimeType=export_mime)
        else:
            # Normal binary download
            request = service.files().get_media(fileId=file_id)

        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        fh.seek(0)
        return fh.getvalue()

    except HttpError as err:
        logger.error(f"❌ Error downloading file {file_id}: {err}")
        raise


def extract_json_content_from_file(file_id: str, email: str, access_token: Optional[str] = None) -> Any:
    """Download and parse JSON from Google Drive file"""
    try:
        logger.info(f"Downloading from Google Drive: {file_id} for user: {email}")
        data = download_file_bytes(file_id, email, access_token)
        text = data.decode("utf-8", errors="ignore")
        return safe_json_parse(text)
    except Exception as e:
        logger.error(f"❌ Error extracting JSON from Drive: {e}")
        raise


# ==================== UPLOAD ====================

def upload_bytes_to_folder(
    folder_id: Optional[str],
    filename: str,
    data_bytes: bytes,
    mimetype: str,
    email: str,
    access_token: Optional[str] = None
):
    """Upload bytes to Drive using email-based credentials"""
    service = get_drive_service(email, access_token)
    media = MediaIoBaseUpload(io.BytesIO(data_bytes), mimetype=mimetype, resumable=True)
    metadata = {"name": filename}

    if folder_id:
        metadata["parents"] = [folder_id]

    uploaded = service.files().create(
        body=metadata,
        media_body=media,
        fields="id, name, size"
    ).execute()

    logger.info(f"✅ Uploaded '{filename}' to {email}'s Drive → ID: {uploaded['id']}")
    return uploaded


def create_shareable_link(file_id: str, email: str, access_token: Optional[str] = None) -> str:
    """Create shareable link using email-based credentials"""
    try:
        service = get_drive_service(email, access_token)
        service.permissions().create(
            fileId=file_id,
            body={"role": "reader", "type": "anyone"},
            fields="id"
        ).execute()
        link = f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"
        logger.info(f"✅ Created shareable link: {link}")
        return link
    except Exception as e:
        logger.warning(f"⚠️ Permission creation failed: {e}")
        return f"https://drive.google.com/file/d/{file_id}/view?usp=sharing"


def delete_file(file_id: str, email: str, access_token: Optional[str] = None):
    """Delete a file by ID."""
    service = get_drive_service(email, access_token)
    service.files().delete(fileId=file_id).execute()
    logger.info(f"🗑️ Deleted file: {file_id}")


# ==================== SPECIALIZED UPLOAD ====================

def upload_mapping_to_gdrive(
   mapping: List[Dict[str, Any]],
    host_file: Dict[str, str],
    target_file: Dict[str, str],
    folder: Optional[List[Dict[str, str]]],
    folder_id: Optional[str],
    host_system: str,
    target_system: str,
    email: str , # ✅ FIX: REQUIRED parameter,
    access_token: Optional[str] = None,
    source_data: Optional[Any] = None,
    target_data: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Convert mapping JSON → Excel and upload to Drive.
    Returns dict with upload details and file URL.
    """
    try:
        if not mapping:
            raise ValueError("Empty mapping provided")
        
        if not email:
            raise ValueError("Email is required for uploading to user's Drive")
        
        logger.info(f"Preparing Excel file with {len(mapping)} mappings for user: {email}")
        
        # Build Excel rows
        excel_rows = []
        for i, m in enumerate(mapping, start=1):
            details = m.get("details", {})
            
            excel_rows.append({
                "Mapping #": i,
                "Source System": host_system or DEFAULT_HOST_SYSTEM,
                "Source Field (JSON Path)": m.get("source", ""),
                "Source Data Type": details.get("source_data_type", ""),
                "Sample Source Value": details.get("source_sample", ""),
                "Transformation / Logic": details.get("transformation", "Direct Mapping"),
                "Target System": target_system or DEFAULT_TARGET_SYSTEM,
                "Target Field (API Name)": m.get("target", ""),
                "Target Data Type": details.get("target_data_type", ""),
                "Sample Target Value": details.get("target_sample", ""),
                "Comments / Notes": details.get("notes", ""),
            })

        df = pd.DataFrame(excel_rows)
        buf = io.BytesIO()
        
        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name="Field Mapping Specification")
            worksheet = writer.sheets["Field Mapping Specification"]
            for column in worksheet.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                worksheet.column_dimensions[column_letter].width = adjusted_width

            if source_data:
                # Data List aithe direct ga, Dict aithe List lo petti DataFrame cheyyali
                if isinstance(source_data, list):
                    df_source = pd.DataFrame(source_data)
                else:
                    df_source = pd.DataFrame([source_data]) # Wrap dict in list
                
                df_source.to_excel(writer, index=False, sheet_name="Source Payload")
            
            if target_data:
                if isinstance(target_data, list):
                    df_target = pd.DataFrame(target_data)
                else:
                    df_target = pd.DataFrame([target_data])
                
                df_target.to_excel(writer, index=False, sheet_name="Target Payload")
        
        buf.seek(0)
        excel_bytes = buf.getvalue()

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        host_name = host_system or host_file.get("name", "host")
        target_name = target_system or target_file.get("name", "target")
        
        host_clean = "".join(c if c.isalnum() else "_" for c in host_name)[:30]
        target_clean = "".join(c if c.isalnum() else "_" for c in target_name)[:30]
        
        filename = f"Field_Mapping_{host_clean}_to_{target_clean}_{timestamp}.xlsx"

        # ✅ FIX: ALWAYS use email-based credentials
        logger.info(f"✅ Uploading to Drive using credentials for: {email}")
        uploaded = upload_bytes_to_folder(
            folder_id, 
            filename, 
            excel_bytes,
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            email ,
            access_token
        )
        
        file_url = create_shareable_link(uploaded["id"], email , access_token)
        
        logger.info(f"✅ Mapping uploaded successfully to {email}'s Drive: {filename}")
        
        return {
            "uploaded": uploaded,
            "file_url": file_url,
            "filename": filename,
            "size_bytes": len(excel_bytes),
            "mapping_count": len(mapping),
            "uploaded_to": email
        }
        
    except Exception as e:
        logger.error(f"❌ Error uploading mapping to Drive: {e}")
        raise
