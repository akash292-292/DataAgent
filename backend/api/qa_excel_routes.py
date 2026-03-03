"""
QA Excel Utilities Routes
--------------------------
Endpoint:
  POST /api/qa/excel/fetch-bytes — fetch raw Excel bytes from Google Drive
                                    so the client can parse sheets with SheetJS

Used by the QA workspace frontend to retrieve an Excel file's raw bytes from
Google Drive before the user selects which sheet to analyze. The selected sheet
is then converted to CSV client-side and submitted to the normal
/api/qa/requirements/analyze or /api/qa/test-cases/generate endpoints.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Form, Header, HTTPException
from fastapi.responses import Response

from services.auth_service import get_fresh_access_token
from services.gdrive_service import download_file_bytes

logger = logging.getLogger(__name__)

router = APIRouter(tags=["QA Excel Utilities"], prefix="/api/qa")


@router.post("/excel/fetch-bytes")
async def fetch_excel_bytes(
    file_id: str = Form(...),
    email: Optional[str] = Form(None),
    authorization: Optional[str] = Header(None),
):
    """
    Fetch raw Excel bytes from Google Drive.

    Returns the file as application/octet-stream so the client can parse
    sheet names and content with SheetJS before submitting to the QA endpoints.
    """
    try:
        access_token = None
        if authorization and authorization.startswith("Bearer "):
            access_token = authorization.replace("Bearer ", "").strip()
        elif email:
            access_token = get_fresh_access_token(email)

        raw = download_file_bytes(file_id, email or "", access_token)
        logger.info(
            "Fetched %d bytes from Drive file %s for Excel sheet preview",
            len(raw), file_id,
        )
        return Response(content=raw, media_type="application/octet-stream")

    except RuntimeError as exc:
        logger.error("Excel fetch service error: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to fetch Excel bytes from Drive")
        raise HTTPException(status_code=500, detail=str(exc))
