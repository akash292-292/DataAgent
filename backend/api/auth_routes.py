"""
OAuth routes and lightweight session endpoints.
"""
import logging
import os
import secrets

import requests
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse

from config.settings import (
    ALLOWED_ORIGINS,
    CLIENT_ID,
    CLIENT_SECRET,
    FRONTEND_URL,
    REDIRECT_URI,
    SCOPES,
)
from services.auth_service import credentials_exist, save_credentials
from utils.security import is_trusted_browser_request

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Authentication"])


def _set_csrf_cookie(response: Response, token: str):
    response.set_cookie(
        key="csrf_token",
        value=token,
        httponly=False,
        secure=False,
        samesite="lax",
        max_age=3600,
    )


@router.get("/login")
def login():
    """Redirect to Google OAuth."""
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = REDIRECT_URI

    authorization_url, _state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    return RedirectResponse(authorization_url)


@router.get("/oauth2callback")
async def oauth2callback(request: Request):
    """Handle OAuth callback, persist token, and redirect to frontend."""
    code = request.query_params.get("code")
    error = request.query_params.get("error")

    if error:
        logger.error("OAuth error: %s", error)
        return RedirectResponse(f"{FRONTEND_URL}/?error={error}")

    try:
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code",
        }

        token_response = requests.post(token_url, data=data, timeout=30)
        token_response.raise_for_status()
        tokens = token_response.json()

        access_token = tokens.get("access_token")
        profile_response = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        profile_response.raise_for_status()
        profile = profile_response.json()
        email = profile.get("email")

        if not email:
            raise HTTPException(status_code=400, detail="Email not found in Google profile")

        save_credentials(email, tokens)

        redirect = RedirectResponse(f"{FRONTEND_URL}/?email={email}&status=success")
        redirect.set_cookie(
            key="session_email",
            value=email,
            httponly=True,
            secure=False,
            samesite="lax",
            max_age=3600,
        )
        _set_csrf_cookie(redirect, secrets.token_urlsafe(32))
        return redirect
    except Exception as exc:
        logger.exception("OAuth callback error: %s", exc)
        return RedirectResponse(f"{FRONTEND_URL}/?error=oauth_failed")


@router.get("/api/verify-session")
def verify_session(request: Request):
    """Check whether browser has a valid signed-in session."""
    email = request.cookies.get("session_email")
    if not email:
        raise HTTPException(status_code=401, detail="No active session")

    if not credentials_exist(email):
        raise HTTPException(status_code=401, detail="Session expired")

    return {"authenticated": True, "email": email}


@router.post("/api/logout")
def logout(request: Request, response: Response):
    """Clear session cookie."""
    if not is_trusted_browser_request(request, ALLOWED_ORIGINS):
        raise HTTPException(status_code=403, detail="Blocked by CSRF protection")
    csrf_cookie = request.cookies.get("csrf_token")
    csrf_header = request.headers.get("x-csrf-token")
    if csrf_cookie and csrf_cookie != csrf_header:
        raise HTTPException(status_code=403, detail="Invalid CSRF token")
    response.delete_cookie(key="session_email")
    response.delete_cookie(key="csrf_token")
    return {"success": True, "message": "Logged out"}


@router.get("/api/csrf-token")
def csrf_token(response: Response):
    token = secrets.token_urlsafe(32)
    _set_csrf_cookie(response, token)
    return {"csrf_token": token}
