"""
Mapping routes for source/target field mapping.
"""
import json
import logging
import os
from typing import Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile

from config.settings import DEFAULT_HOST_SYSTEM, DEFAULT_TARGET_SYSTEM
from services.auth_service import get_fresh_access_token
from services.gdrive_service import (
    extract_json_content_from_file,
    find_file_by_id,
    upload_mapping_to_gdrive,
)
from utils.file_parsers import parse_uploaded_file
from utils.file_utils import is_local_file, is_session_token
from utils.memory_utils import get_data_from_memory, store_data_in_memory
from utils.security import get_effective_email, validate_file_id, validate_short_text

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Mapping"], prefix="/api/mapping")


@router.post("/smart_mapping_with_files")
async def smart_with_files(
    request: Request,
    email: Optional[str] = Form(None),
    host_file_id: Optional[str] = Form(None),
    target_file_id: Optional[str] = Form(None),
    host_file: Optional[UploadFile] = File(None),
    target_file: Optional[UploadFile] = File(None),
    host_file_type: Optional[str] = Form(None),
    target_file_type: Optional[str] = Form(None),
    host_system: str = Form(DEFAULT_HOST_SYSTEM),
    target_system: str = Form(DEFAULT_TARGET_SYSTEM),
    authorization: Optional[str] = Header(None),
):
    """
    Smart mapping with Google Drive files, local uploads, or in-memory session tokens.
    """
    try:
        user_email = get_effective_email(request, email)
        host_file_id = validate_file_id(host_file_id, "host_file_id")
        target_file_id = validate_file_id(target_file_id, "target_file_id")
        host_system = validate_short_text(host_system, "host_system", 120) or DEFAULT_HOST_SYSTEM
        target_system = validate_short_text(target_system, "target_system", 120) or DEFAULT_TARGET_SYSTEM

        access_token = None
        if authorization and authorization.startswith("Bearer "):
            access_token = authorization.replace("Bearer ", "").strip()
        else:
            access_token = get_fresh_access_token(user_email)

        form = await request.form()
        uploaded_files = [value for value in form.values() if hasattr(value, "filename")]
        if uploaded_files:
            if not host_file:
                host_file = uploaded_files[0]
            if len(uploaded_files) > 1 and not target_file:
                target_file = uploaded_files[1]

        host_fields = None
        host_meta = None
        if host_file:
            content = await host_file.read()
            host_fields = parse_uploaded_file(host_file.filename, content)
            host_file_id = store_data_in_memory(host_fields, filename=host_file.filename)
            host_meta = {"id": "session", "name": host_file.filename}
        elif host_file_id and is_session_token(host_file_id):
            host_fields = get_data_from_memory(host_file_id)
            host_meta = {"id": "session", "name": "host_session.json"}
        elif host_file_id and is_local_file(host_file_id):
            with open(host_file_id, "r", encoding="utf-8") as handle:
                host_fields = json.load(handle)
            host_meta = {"id": host_file_id, "name": os.path.basename(host_file_id)}
        elif host_file_id:
            host_meta = find_file_by_id(host_file_id, user_email, access_token)
            if not host_meta:
                raise HTTPException(status_code=404, detail=f"Host file not found in Drive: {host_file_id}")
            host_fields = extract_json_content_from_file(host_file_id, user_email, access_token)
        else:
            raise HTTPException(status_code=400, detail="No host file provided")

        target_fields = None
        target_meta = None
        if target_file:
            content = await target_file.read()
            target_fields = parse_uploaded_file(target_file.filename, content)
            target_file_id = store_data_in_memory(target_fields, filename=target_file.filename)
            target_meta = {"id": "session", "name": target_file.filename}
        elif target_file_id and is_session_token(target_file_id):
            target_fields = get_data_from_memory(target_file_id)
            target_meta = {"id": "session", "name": "target_session.json"}
        elif target_file_id and is_local_file(target_file_id):
            with open(target_file_id, "r", encoding="utf-8") as handle:
                target_fields = json.load(handle)
            target_meta = {"id": target_file_id, "name": os.path.basename(target_file_id)}
        elif target_file_id:
            target_meta = find_file_by_id(target_file_id, user_email, access_token)
            if not target_meta:
                raise HTTPException(status_code=404, detail=f"Target file not found in Drive: {target_file_id}")
            target_fields = extract_json_content_from_file(target_file_id, user_email, access_token)
        else:
            raise HTTPException(status_code=400, detail="No target file provided")

        # Lazy import to avoid heavy model initialization during backend startup.
        from services.mapping_services import llm_field_mapping

        mapping = llm_field_mapping(
            host_fields,
            target_fields,
            host_system,
            target_system,
            llm_timeout=200.0,
        )

        parent_id = host_meta["parents"][0] if host_meta.get("parents") else None
        upload_resp = upload_mapping_to_gdrive(
            mapping,
            host_meta,
            target_meta,
            None,
            parent_id,
            os.path.splitext(host_meta["name"])[0],
            os.path.splitext(target_meta["name"])[0],
            user_email,
            access_token,
            source_data=host_fields,
            target_data=target_fields,
        )

        final_url = upload_resp.get("webViewLink") or upload_resp.get("file_url") or upload_resp.get("alternateLink")
        return {"status": "success", "count": len(mapping), "file_url": final_url}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Mapping failed")
        raise HTTPException(status_code=500, detail=str(exc))
