# drive_service.py

from pydantic import BaseModel
from typing import List, Dict, Any
import requests
import os
import io

# --- Google Drive Configuration ---
# Mapping for Google Workspace MIME types to standard formats for export
DRIVE_EXPORT_MIME_TYPES = {
    'application/vnd.google-apps.document': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', # Export Google Doc as .docx
    'application/vnd.google-apps.spreadsheet': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # Export Google Sheet as .xlsx
    'application/vnd.google-apps.presentation': 'application/vnd.openxmlformats-officedocument.presentationml.presentation', # Export Google Slides as .pptx
    'application/vnd.google-apps.drawing': 'image/png', # Export Google Drawing as PNG
}

# Pydantic model to receive data from the frontend
class DriveUploadRequest(BaseModel):
    files: List[Dict[str, Any]]
    access_token: str
    user_email: str = None
# --- END Google Drive Configuration ---


def download_drive_file_content(file_id: str, file_name: str, mime_type: str, access_token: str) -> dict:
    """
    Downloads the binary content of a Google Drive file using the access token, 
    handling native (Docs, Sheets) and blob (PDF, DOCX) formats.
    Returns: {"success": bool, "content": bytes, "final_file_name": str, "file_type": str, "error": str}
    """
    headers = {
        'Authorization': f'Bearer {access_token}'
    }
    
    is_native_format = mime_type.startswith('application/vnd.google-apps.')
    
    try:
        if is_native_format:
            # Handle Google Workspace native files (must use files.export)
            target_mime = DRIVE_EXPORT_MIME_TYPES.get(mime_type)
            if not target_mime:
                return {"success": False, "error": f"Unsupported Google native format: {mime_type}"}

            export_extension = target_mime.split('.')[-1]
            if export_extension == 'document': export_extension = 'docx'
            elif export_extension == 'sheet': export_extension = 'xlsx'
            elif export_extension == 'presentation': export_extension = 'pptx'
            elif export_extension == 'png': export_extension = 'png'
            
            # Ensure the filename is clean and has the new extension
            base_name = os.path.splitext(file_name)[0].replace(' ', '_')
            final_file_name = f"{base_name}.{export_extension}"
            file_type = export_extension
            
            api_url = f"https://www.googleapis.com/drive/v3/files/{file_id}/export"
            params = {'mimeType': target_mime}
            
            print(f"[DRIVE-DOWNLOAD] Exporting native file: {file_name} as {final_file_name} ({target_mime})")
            response = requests.get(api_url, headers=headers, params=params, stream=True)
            
        else:
            # Handle Blob Files (PDF, DOCX, JPG, etc., use alt=media)
            api_url = f"https://www.googleapis.com/drive/v3/files/{file_id}"
            params = {'alt': 'media'}
            
            final_file_name = file_name.replace(' ', '_')
            file_type = file_name.lower().split('.')[-1] if '.' in file_name else mime_type.split('/')[-1]
            
            print(f"[DRIVE-DOWNLOAD] Downloading blob file: {file_name} (type: {file_type})")
            response = requests.get(api_url, headers=headers, params=params, stream=True)

        if response.status_code == 200:
            file_content = response.content
            print(f"[DRIVE-DOWNLOAD] Download successful, size: {len(file_content)} bytes")
            return {
                "success": True, 
                "content": file_content, 
                "final_file_name": final_file_name, 
                "file_type": file_type, 
                "error": None
            }
        else:
            error_msg = response.text
            print(f"[DRIVE-DOWNLOAD] API Failed: {response.status_code} - {error_msg}")
            return {"success": False, "error": f"Drive API failed: {response.status_code} - {error_msg}"}
            
    except requests.exceptions.RequestException as e:
        print(f"[DRIVE-DOWNLOAD] Request error: {str(e)}")
        return {"success": False, "error": f"Network error during download: {str(e)}"}
    except Exception as e:
        import traceback
        print(f"[DRIVE-DOWNLOAD] Unexpected error: {str(e)}\n{traceback.format_exc()}")
        return {"success": False, "error": f"Internal download error: {str(e)}"}