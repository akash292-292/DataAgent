"""
QA Test Case Routes
--------------------
Endpoints:
  POST /api/qa/test-cases/generate        — generate test cases from a requirements document
  GET  /api/qa/test-cases/download/{file} — download the generated Excel file
  POST /api/qa/test-cases/follow-up       — generate additional edge/regression cases

The generate endpoint accepts multipart/form-data with:
  - file           (UploadFile, optional) — local document upload (.txt / .pdf / .docx)
  - file_id        (str, optional)        — Google Drive file ID
  - drive_filename (str, optional)        — original filename for Drive uploads
                                            (used to detect PDF/DOCX for native upload)
  - user_story     (str, optional)        — focus area / user story (optional query)
  - email          (str, optional)        — user email for Drive token refresh
  - authorization  (Header, optional)     — Bearer token for Drive access

A document (file or file_id) is mandatory. user_story is optional.
"""

import logging
from typing import Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from services.auth_service import get_fresh_access_token
from services.gdrive_service import download_file_bytes
from services.qa_testcase_service import (
    EXPORT_DIR,
    generate_followup_test_cases,
    generate_test_cases,
    generate_test_cases_from_bytes,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["QA Test Case Generation"], prefix="/api/qa")


# --------------------------------------------------
# Request Schema (follow-up still uses JSON body)
# --------------------------------------------------
class FollowUpTestCaseRequest(BaseModel):
    previous_test_cases: str = Field(
        ...,
        example="TC_001 | Happy Path | Successful password reset ...",
    )


# --------------------------------------------------
# Endpoints
# --------------------------------------------------
@router.post("/test-cases/generate")
async def generate(
    file: Optional[UploadFile] = File(None),
    file_id: Optional[str] = Form(None),
    drive_filename: Optional[str] = Form(None),
    user_story: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None),
):
    """
    Generate test cases from a requirements document (mandatory).

    Document content source (one required):
      1. Uploaded local file  → native Gemini upload for PDF/DOCX (images preserved)
      2. Google Drive file_id → native path if drive_filename ends in .pdf/.docx

    user_story is optional — injected as a top-level focus directive in the prompt.
    """
    focus = (user_story or "").strip() or None

    try:
        # ── 1. Local file upload ──────────────────────────────────────────
        if file and file.filename:
            raw = await file.read()
            logger.info("Received uploaded file: %s (%d bytes)", file.filename, len(raw))
            return generate_test_cases_from_bytes(
                filename=file.filename,
                content=raw,
                focus_query=focus,
            )

        # ── 2. Google Drive file ──────────────────────────────────────────
        if file_id:
            access_token = None
            if authorization and authorization.startswith("Bearer "):
                access_token = authorization.replace("Bearer ", "").strip()
            elif email:
                access_token = get_fresh_access_token(email)

            raw = download_file_bytes(file_id, email or "", access_token)
            logger.info("Fetched %d bytes from Drive file: %s", len(raw), file_id)

            # Use drive_filename for native dispatch if provided; else UTF-8 text fallback
            if drive_filename:
                return generate_test_cases_from_bytes(
                    filename=drive_filename,
                    content=raw,
                    focus_query=focus,
                )
            text = raw.decode("utf-8", errors="ignore")
            return generate_test_cases(document_content=text, focus_query=focus)

        # ── Validate: document is mandatory ──────────────────────────────
        raise HTTPException(
            status_code=400,
            detail="No document provided. Supply a file or a Google Drive file ID.",
        )

    except HTTPException:
        raise
    except RuntimeError as exc:
        logger.error("QA test case service misconfigured: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Test case generation failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/test-cases/download/{filename}")
def download_excel(filename: str):
    path = EXPORT_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found or has expired")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=filename,
    )


@router.post("/test-cases/follow-up")
def generate_followup(payload: FollowUpTestCaseRequest):
    try:
        return generate_followup_test_cases(payload.previous_test_cases)
    except RuntimeError as exc:
        logger.error("QA test case service misconfigured: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Follow-up test case generation failed")
        raise HTTPException(status_code=500, detail=str(exc))
