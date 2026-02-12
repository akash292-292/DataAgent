"""
Security helpers for input validation and trusted-request checks.
"""
import re
from typing import Optional

from fastapi import HTTPException, Request

EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}$")


def normalize_email(raw_email: Optional[str], required: bool = True) -> Optional[str]:
    if raw_email is None:
        if required:
            raise HTTPException(status_code=400, detail="Email is required")
        return None
    email = raw_email.strip().lower()
    if not EMAIL_RE.fullmatch(email):
        raise HTTPException(status_code=400, detail="Invalid email format")
    if len(email) > 254:
        raise HTTPException(status_code=400, detail="Email is too long")
    return email


def validate_short_text(value: Optional[str], field_name: str, max_len: int = 256) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    if len(cleaned) > max_len:
        raise HTTPException(status_code=400, detail=f"{field_name} is too long")
    if "\x00" in cleaned:
        raise HTTPException(status_code=400, detail=f"{field_name} contains invalid characters")
    return cleaned


def validate_file_id(file_id: Optional[str], field_name: str = "file_id") -> Optional[str]:
    if file_id is None:
        return None
    candidate = file_id.strip()
    if not candidate:
        raise HTTPException(status_code=400, detail=f"{field_name} is required")
    if len(candidate) > 2048:
        raise HTTPException(status_code=400, detail=f"{field_name} is too long")
    if "\x00" in candidate:
        raise HTTPException(status_code=400, detail=f"{field_name} contains invalid characters")
    return candidate


def get_effective_email(request: Request, email: Optional[str]) -> str:
    """
    Resolve email from explicit input first, then from authenticated session cookie.
    """
    resolved = normalize_email(email, required=False)
    if resolved:
        return resolved

    session_email = request.cookies.get("session_email")
    resolved_session = normalize_email(session_email, required=False)
    if resolved_session:
        return resolved_session

    raise HTTPException(status_code=401, detail="No authenticated session email available")


def is_trusted_browser_request(request: Request, allowed_origins: list[str]) -> bool:
    origin = (request.headers.get("origin") or "").strip()
    referer = (request.headers.get("referer") or "").strip()
    if origin:
        return origin in allowed_origins
    if referer:
        return any(referer.startswith(allowed) for allowed in allowed_origins)
    return False
