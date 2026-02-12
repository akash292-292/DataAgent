"""
Authentication services for OAuth credential storage and Drive token handling.
"""
import base64
import json
import logging
import os
import secrets
from datetime import datetime
from typing import Optional

from fastapi import HTTPException
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from config.settings import CLIENT_ID, CLIENT_SECRET, SCOPES

logger = logging.getLogger(__name__)
TOKENS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "tokens"))


def _token_file(email: str) -> str:
    return os.path.join(TOKENS_DIR, f"{email}.json")


def save_credentials(email: str, tokens: dict):
    """Save user credentials to backend/tokens directory."""
    os.makedirs(TOKENS_DIR, exist_ok=True)
    creds_data = {
        "token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scopes": SCOPES,
    }
    with open(_token_file(email), "w", encoding="utf-8") as handle:
        json.dump(creds_data, handle)
    logger.info("Credentials saved for %s", email)


def load_credentials(email: str) -> Credentials:
    """Load user credentials from backend/tokens directory."""
    path = _token_file(email)
    if not os.path.exists(path):
        raise Exception("No saved Google credentials")
    return Credentials.from_authorized_user_file(path, SCOPES)


def credentials_exist(email: str) -> bool:
    return os.path.exists(_token_file(email))


def get_fresh_access_token(email: str) -> str:
    """Return a valid Google access token, refreshing if needed."""
    creds = load_credentials(email)
    if creds and creds.expired and creds.refresh_token:
        from google.auth.transport.requests import Request

        creds.refresh(Request())
        save_credentials(
            email,
            {
                "access_token": creds.token,
                "refresh_token": creds.refresh_token,
            },
        )
    if not creds or not creds.token:
        raise Exception("No valid Google access token available")
    return creds.token


def get_drive_service(email: str, access_token: Optional[str] = None):
    """Get Google Drive service for user."""
    try:
        if access_token:
            creds = Credentials(token=access_token)
            return build("drive", "v3", credentials=creds, cache_discovery=False)

        creds = load_credentials(email)
        if creds and creds.expired and creds.refresh_token:
            from google.auth.transport.requests import Request

            creds.refresh(Request())
            save_credentials(
                email,
                {
                    "access_token": creds.token,
                    "refresh_token": creds.refresh_token,
                },
            )

        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception as exc:
        logger.error("Failed to create Drive service for %s: %s", email, exc)
        raise HTTPException(status_code=401, detail=f"User not authenticated: {exc}")


def make_session_token(email: str, filename: str) -> str:
    raw = f"{email}||{filename}||{datetime.utcnow().isoformat()}"
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")


def create_session(email: str, access_token: str) -> str:
    return secrets.token_urlsafe(32)


def extract_access_token(authorization: Optional[str]) -> Optional[str]:
    if authorization and authorization.startswith("Bearer "):
        return authorization.replace("Bearer ", "").strip()
    return None
