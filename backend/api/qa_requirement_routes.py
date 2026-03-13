"""
QA Requirement Analysis Routes
--------------------------------
Endpoints:
  POST /api/qa/requirements/analyze    — analyze a requirements document
  POST /api/qa/requirements/follow-up  — second-pass gap/risk review

The analyze endpoint accepts multipart/form-data with:
  - file           (UploadFile, optional) — local document upload (.txt / .pdf / .docx)
  - file_id        (str, optional)        — Google Drive file ID
  - drive_filename (str, optional)        — original filename for Drive uploads
                                            (used to detect PDF/DOCX for native upload)
  - user_prompt    (str, optional)        — user's focus area / query (injected as a
                                            top-level directive, NOT merged into document)
  - document_text  (str, optional)        — plain text fallback (backwards-compatible)
  - email          (str, optional)        — user email for Drive token refresh
  - authorization  (Header, optional)     — Bearer token for Drive access
"""

import logging
from typing import Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, UploadFile
from pydantic import BaseModel, Field

from services.auth_service import get_fresh_access_token
from services.gdrive_service import download_file_bytes
from services.qa_requirement_service import (
    analyze_requirements,
    analyze_requirements_from_bytes,
    followup_requirements,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["QA Requirement Analysis"], prefix="/api/qa")


# --------------------------------------------------
# Request Schema (follow-up still uses JSON body)
# --------------------------------------------------
class FollowUpGapRequest(BaseModel):
    previous_analysis: str = Field(
        ...,
        example="Functional Requirements:\nFR-01 User login...",
    )


# --------------------------------------------------
# Endpoints
# --------------------------------------------------
@router.post("/requirements/analyze")
async def analyze_document(
    file: Optional[UploadFile] = File(None),
    file_id: Optional[str] = Form(None),
    drive_filename: Optional[str] = Form(None),
    user_prompt: Optional[str] = Form(None),
    document_text: Optional[str] = Form(None),
    email: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None),
):
    """
    Analyze a requirements document.

    Document content priority:
      1. Uploaded local file  → native Gemini upload for PDF/DOCX (images preserved)
      2. Google Drive file_id → native path if drive_filename ends in .pdf/.docx
      3. document_text        → plain text fallback

    user_prompt is passed as a separate query/focus directive to the LLM —
    it is NOT merged into the document body.
    """
    try:
        # ── 1. Local file upload ──────────────────────────────────────────
        if file and file.filename:
            raw = await file.read()
            logger.info("Received uploaded file: %s (%d bytes)", file.filename, len(raw))
            return await analyze_requirements_from_bytes(
                filename=file.filename,
                content=raw,
                user_prompt=user_prompt,
                user=email,
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

            # Use drive_filename for native dispatch if provided; else fall back to text
            if drive_filename:
                return await analyze_requirements_from_bytes(
                    filename=drive_filename,
                    content=raw,
                    user_prompt=user_prompt,
                    user=email,
                )
            # No filename → UTF-8 text fallback
            text = raw.decode("utf-8", errors="ignore")
            return await analyze_requirements(text, user_prompt=user_prompt, user=email)

        # ── 3. Plain text fallback ────────────────────────────────────────
        if document_text and document_text.strip():
            return await analyze_requirements(document_text.strip(), user_prompt=user_prompt, user=email)

        raise HTTPException(
            status_code=400,
            detail="No document provided. Supply a file, a Drive file ID, or document_text.",
        )

    except HTTPException:
        raise
    except RuntimeError as exc:
        logger.error("QA requirement service misconfigured: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Requirement analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))


@router.post("/requirements/follow-up")
def followup_analysis(payload: FollowUpGapRequest):
    try:
        return followup_requirements(payload.previous_analysis)
    except RuntimeError as exc:
        logger.error("QA requirement service misconfigured: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Requirement follow-up analysis failed")
        raise HTTPException(status_code=500, detail=str(exc))
