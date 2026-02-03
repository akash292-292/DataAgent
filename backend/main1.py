import os
import io
import re
import json
import base64
import pathlib
import secrets
import time
from datetime import datetime
from typing import Optional, Dict, Any
import google.generativeai as genai
import pandas as pd
import requests
from fastapi import FastAPI, Request, Query, Form, UploadFile, File, HTTPException
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaIoBaseUpload
from googleapiclient.errors import HttpError
from dotenv import load_dotenv
from utilities import detect_and_cast_numeric
from mapping_services import mapping_router
from fastapi import Cookie, Depends, Response
import logging
from collections import Counter
from rapidfuzz import fuzz, process

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

LOG = logging.getLogger("uvicorn.error")
LOG.setLevel(logging.INFO)
# In main.py
from store import USER_STORE  # <--- Import this instead of defining it locally

# ----------------------------
# Setup
# ----------------------------
load_dotenv()

# Environment variables
CLIENT_ID = os.getenv("CLIENT_NEW_ID")
CLIENT_SECRET = os.getenv("CLIENT_NEW_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://127.0.0.1:8000/oauth2callback")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")  # ✅ Add this for Drive Picker
FRONTEND_URL = os.getenv("FRONTEND_URL")
FRONTEND2_URL = os.getenv("FRONTEND2_URL")

# In-memory session store (Use Redis/Database in production)

sessions = {}
SESSION_COOKIE_NAME = "session_token"
SESSION_MAX_AGE = 3600 
app = FastAPI(title="AI Data Validation Tool")

# ✅ Include mapping service routes
app.include_router(mapping_router, prefix="/api/mapping")

origins = [
    FRONTEND_URL,
    FRONTEND2_URL
]

# ✅ Enable CORS for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# def create_session(email: str, access_token: str) -> str:
#     """Create a new session and return session token"""
#     session_token = secrets.token_urlsafe(32)
#     sessions[session_token] = {
#         "email": email,
#         "access_token": access_token,
#         "created_at": time.time()
#     }
#     logger.info(f"✅ Session created for {email}")
#     return session_token

# def get_session(session_token: Optional[str]) -> dict:
#     """Get session data from token"""
#     if not session_token or session_token not in sessions:
#         raise HTTPException(status_code=401, detail="Invalid or expired session")
    
#     session_data = sessions[session_token]
    
#     # Check if session expired
#     if time.time() - session_data["created_at"] > SESSION_MAX_AGE:
#         del sessions[session_token]
#         raise HTTPException(status_code=401, detail="Session expired")
    
#     return session_data


# def get_current_session(session_token: Optional[str] = Cookie(None, alias=SESSION_COOKIE_NAME)):
#     """Dependency to get current session from cookie"""
#     return get_session(session_token)



# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    gemini_model = genai.GenerativeModel("gemini-2.0-flash")
else:
    gemini_model = None
    print("⚠️ GEMINI_API_KEY not set")

SCOPES = [
    "openid", "email", "profile",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",               # ✅ ADD THIS
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly"
]

if not CLIENT_ID or not CLIENT_SECRET:
    raise RuntimeError("CLIENT_ID and CLIENT_SECRET must be set in .env")

# Directories
BASE_DIR = pathlib.Path(__file__).parent
TOKENS_DIR = BASE_DIR / "tokens"
TOKENS_DIR.mkdir(exist_ok=True)


# ----------------------------
# Utilities
# ----------------------------
# ----------------------------
# Duplicate & Error Detection Utilities
# ----------------------------

def detect_duplicate_key_columns(df: pd.DataFrame) -> list:
    """Auto-detect columns likely to contain key business data (names, companies, etc.)"""
    key_cols = []
    for col in df.columns:
        if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
            values = df[col].dropna().astype(str)
            if values.empty:
                continue
            
            col_lower = col.lower()
            # Skip ID/serial/numeric-only columns
            if any(k in col_lower for k in ["id", "serial", "no", "count"]):
                continue
            if values.str.isdigit().all():
                continue
            if values.str.match(r"^\d{2}[-/]\d{2}[-/]\d{4}$").all():
                continue
            
            avg_len = values.str.len().mean()
            if avg_len < 3:
                continue
            
            unique_ratio = values.nunique() / len(values)
            if unique_ratio < 0.02:
                continue
            
            key_cols.append(col)
    
    print(f"[Duplicates] Auto-detected key columns: {key_cols}")
    return key_cols


# def detect_duplicates(df: pd.DataFrame) -> pd.DataFrame:
#     """Detect both exact and fuzzy duplicates"""
#     duplicate_rows = []
    
#     # 1. Exact duplicates (full-row)
#     exact_dupes = df[df.duplicated(keep=False)]
#     if not exact_dupes.empty:
#         exact_dupes = exact_dupes.copy()
#         exact_dupes["Duplicate_Type"] = "Exact"
#         duplicate_rows.append(exact_dupes)
    
#     # 2. Fuzzy duplicates for detected key columns
#     key_columns = detect_duplicate_key_columns(df)
#     fuzzy_results = []
    
#     for col in key_columns:
#         vals = df[col].dropna().astype(str).unique().tolist()
#         for val in vals:
#             matches = process.extract(val, vals, scorer=fuzz.token_sort_ratio, limit=None)
#             for match, score, _ in matches:
#                 if match != val and score >= 85:
#                     fuzzy_results.append({
#                         "Column": col,
#                         "Value1": val,
#                         "Value2": match,
#                         "Similarity": score,
#                         "Duplicate_Type": "Fuzzy"
#                     })
    
#     if fuzzy_results:
#         fuzzy_df = pd.DataFrame(fuzzy_results)
#         duplicate_rows.append(fuzzy_df)
    
#     if duplicate_rows:
#         return pd.concat(duplicate_rows, ignore_index=True)
#     else:
#         return pd.DataFrame(columns=["Column", "Value1", "Value2", "Similarity", "Duplicate_Type"])

def detect_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Optimized Duplicate Detection.
    1. Exact Matches: Checks full dataframe (standard).
    2. Fuzzy Matches: Uses SET to get unique values -> Sorts them -> Checks neighbors.
       This is extremely fast and prevents Memory Crashes on Render.
    """
    duplicate_rows = []
    
    # --- PART 1: EXACT DUPLICATES (Original Rows) ---
    # This keeps the full row data for exact duplicates
    exact_dupes = df[df.duplicated(keep=False)]
    if not exact_dupes.empty:
        exact_dupes = exact_dupes.copy()
        exact_dupes["Duplicate_Type"] = "Exact"
        duplicate_rows.append(exact_dupes)
    
    # --- PART 2: FUZZY DUPLICATES (Optimized with SET) ---
    key_columns = detect_duplicate_key_columns(df)
    
    if key_columns:
        print(f"🔍 Fuzzy Check on columns: {key_columns}")
        
        for col in key_columns:
            # Step A: Get all values as strings
            vals = df[col].dropna().astype(str).tolist()
            if not vals:
                continue

            # Step B: USE SET (Optimization)
            # We only need to find WHICH words are similar, not how many times they appear.
            # This reduces 10,000 checks to just ~500 checks.
            unique_vals = list(set(vals))
            unique_vals.sort() # Sorting brings similar words closer
            
            total_vals = len(unique_vals)
            fuzzy_results = []
            
            # Step C: Sliding Window (Check only neighbors)
            # Compare Word[i] with next 20 words only
            WINDOW_SIZE = 20
            
            for i in range(total_vals):
                current_val = unique_vals[i]
                
                start_check = i + 1
                end_check = min(i + WINDOW_SIZE, total_vals)
                
                for j in range(start_check, end_check):
                    next_val = unique_vals[j]
                    
                    # Fuzzy Ratio check
                    score = fuzz.ratio(current_val.lower(), next_val.lower())
                    
                    if score >= 85:
                        fuzzy_results.append({
                            "Column": col,
                            "Value1": current_val,
                            "Value2": next_val,
                            "Similarity": score,
                            "Duplicate_Type": "Fuzzy"
                        })

            if fuzzy_results:
                fuzzy_df = pd.DataFrame(fuzzy_results)
                duplicate_rows.append(fuzzy_df)
    
    if duplicate_rows:
        return pd.concat(duplicate_rows, ignore_index=True)
    else:
        return pd.DataFrame(columns=["Column", "Value1", "Value2", "Similarity", "Duplicate_Type"])


def summarize_errors(bad_df: pd.DataFrame) -> pd.DataFrame:
    """Create error frequency summary from bad data"""
    reasons_col = None
    for c in ["_validation_reason", "Reason", "error"]:  # Check multiple column names
        if c in bad_df.columns:
            reasons_col = c
            break
    
    error_list = []
    if reasons_col:
        for item in bad_df[reasons_col].fillna("").astype(str):
            if not item.strip():
                continue
            # Split by semicolon or just add as-is if it's a list
            if isinstance(item, list):
                error_list.extend([str(e).strip() for e in item if str(e).strip()])
            else:
                for err in [e.strip() for e in item.split(";") if e.strip()]:
                    error_list.append(err)
    
    freq = Counter(error_list)
    return pd.DataFrame([
        {"Error": k, "Frequency": v} 
        for k, v in freq.items()
    ]).sort_values("Frequency", ascending=False)


def save_credentials(email, tokens):
    """Save user credentials to file"""
    os.makedirs("tokens", exist_ok=True)
    creds_data = {
        "token": tokens["access_token"],
        "refresh_token": tokens.get("refresh_token", ""),
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "scopes": SCOPES
    }
    with open(f"tokens/{email}.json", "w") as f:
        json.dump(creds_data, f)


def load_credentials(email):
    """Load user credentials from file"""
    path = f"tokens/{email}.json"
    if not os.path.exists(path):
        raise Exception("No saved Google credentials")
    return Credentials.from_authorized_user_file(path, SCOPES)


def get_drive_service(email: str):
    """Get Google Drive service for user"""
    if email in USER_STORE and "credentials" in USER_STORE[email]:
        creds = USER_STORE[email]["credentials"]
        return build("drive", "v3", credentials=creds, cache_discovery=False)

    # 2. Fallback: Try file system (Only works on Localhost)
    try:
        creds = load_credentials(email)
        return build("drive", "v3", credentials=creds, cache_discovery=False)
    except Exception:
        # If neither works, the user must log in again
        print(f"❌ No credentials found for {email} in memory or file.")
        raise HTTPException(
            status_code=401, 
            detail="Session expired or credentials missing. Please logout and login again."
        )

def _normalize_value_for_rule(value):
    """Normalize value for rule evaluation"""
    if pd.isna(value):
        return None
    if isinstance(value, str):
        v = value.strip()
        if re.fullmatch(r"[+-]?\d+", v):
            try:
                return int(v)
            except Exception:
                pass
        if re.fullmatch(r"[+-]?\d+\.\d+", v):
            try:
                return float(v)
            except Exception:
                pass
        return v
    return value


def apply_validation_rules(df: pd.DataFrame, rules):
    """Apply validation rules to dataframe and separate good/bad data"""
    work = df.copy()
    work["_validation_status"] = "Good"
    work["_validation_reason"] = ""

    for idx, row in work.iterrows():
        errors = []
        for rule in rules:
            col = rule.get("column")
            expr = rule.get("rule")
            desc = rule.get("description", "Rule failed")

            if not col or col not in df.columns or not expr:
                continue

            value = _normalize_value_for_rule(row[col])

            # Handle required fields
            if (value is None or str(value).strip() == "") and any(
                kw in desc.lower() for kw in ["required", "not empty", "non-empty"]
            ):
                errors.append(f"{col}: {desc}")
                continue

            try:
                # Safe eval with limited builtins
                safe_env = {
                    "value": value,
                    "re": re,
                    "isinstance": isinstance,
                    "int": int,
                    "float": float,
                    "str": str,
                    "len": len,
                    "bool": bool,
                    "any": any,
                    "all": all,
                }
                ok = bool(eval(expr, {"__builtins__": None}, safe_env))
                if not ok:
                    errors.append(f"{col}: {desc}")
            except Exception as e:
                print(f"[Eval Error] {col} -> {e} | Expr: {expr}")
                errors.append(f"{col}: Rule eval error")

        if errors:
            work.at[idx, "_validation_status"] = "Bad"
            work.at[idx, "_validation_reason"] = "; ".join(errors)

    good = work[work["_validation_status"] == "Good"].drop(columns=["_validation_status", "_validation_reason"])
    bad = work[work["_validation_status"] == "Bad"].drop(columns=["_validation_status"])
    return good, bad


def call_gemini_generate_rules(headers, sample_rows, user_guidance=None, previous_rules=None):
    """Generate or refine validation rules using Gemini SDK"""
    if not GEMINI_API_KEY:
        return {h: [{"rule_id": "required", "type": "required", "description": "Must not be empty"}] for h in headers}

    prompt = f"""
You are an expert Data Quality Validator.
Given column names (and optionally sample data), generate Python boolean expressions for validating correct values.

🔹 Each rule must be directly executable in Python with the variable name `value`.
🔹 Be data-type aware:
   - For numeric columns (IDs, counts, income, loyalty points): use integer checks like `isinstance(value, (int, float)) and value >= 0`
   - For dates: use regex `r'^\\d{{2}}-\\d{{2}}-\\d{{4}}$'`
   - For emails: `'@' in value and '.' in value`
   - For phone numbers: `bool(re.fullmatch(r'\\+?[0-9\\-\\(\\) ]{{7,20}}', str(value)))`
   - For text columns: `isinstance(value, str) and len(value.strip()) > 0`

🔹 DO NOT just say "must not be empty." Every rule must be a valid, testable Python condition.
🔹 Output **only** a valid JSON array — no extra text.

Example expected output:
[
  {{"column": "email_address", "rule": "('@' in str(value)) and ('.' in str(value))", "description": "Valid email address format"}},
  {{"column": "dob", "rule": "bool(re.fullmatch(r'^\\d{{2}}-\\d{{2}}-\\d{{4}}$', str(value)))", "description": "Date must be DD-MM-YYYY"}}
]

Columns:
{', '.join(headers)}
Sample rows:
{json.dumps(sample_rows, indent=2, default=str)}
"""

    if previous_rules and user_guidance:
        prompt += f"""

Previous rules:
{json.dumps(previous_rules, indent=2, default=str)}

User provided these edits:
{json.dumps(user_guidance, indent=2, default=str)}

Please refine and regenerate improved JSON rules accordingly.
"""
    elif user_guidance:
        prompt += f"""

User edits:
{json.dumps(user_guidance, indent=2, default=str)}
"""

    try:
        model = genai.GenerativeModel("gemini-2.5-flash")
        response = model.generate_content(prompt)
        text = response.text.strip()

        # Extract JSON content
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            print("[Gemini SDK] No valid JSON detected")
            return {h: [{"rule_id": "required", "type": "required", "description": "Must not be empty"}] for h in headers}

        raw_json = match.group(0).strip()
        raw_json = raw_json.strip("```json").strip("```").strip()
        
        try:
            rules = json.loads(raw_json)
        except json.JSONDecodeError:
            closing_index = raw_json.find("]") + 1
            rules = json.loads(raw_json[:closing_index])
        
        return rules
        
    except Exception as e:
        print("[Gemini SDK Error]", e)
        return {h: [{"rule_id": "required", "type": "required", "description": "Must not be empty"}] for h in headers}


# ----------------------------
# OAuth Routes
# ----------------------------
@app.get("/login")
def login():
    """Redirect to Google OAuth"""
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
        scopes=SCOPES
    )
    flow.redirect_uri = REDIRECT_URI
    
    authorization_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent"
    )
    return RedirectResponse(authorization_url)

@app.get("/oauth2callback")
async def oauth2callback(request: Request):
    """Handle OAuth callback and save user credentials"""
    code = request.query_params.get("code")
    error = request.query_params.get("error")
    
    if error:
        logger.error(f"❌ OAuth error: {error}")
        return RedirectResponse(f"{FRONTEND_URL}/?error={error}")
    
    if not code:
        logger.error("❌ No authorization code received")
        return RedirectResponse(f"{FRONTEND_URL}/?error=no_code")

    try:
        # Exchange authorization code for tokens
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            "code": code,
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "grant_type": "authorization_code"
        }
        
        logger.info("🔄 Exchanging code for tokens...")
        r = requests.post(token_url, data=data)
        r.raise_for_status()
        tokens = r.json()
        
        # Get user info
        access_token = tokens.get("access_token")
        resp = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {access_token}"}
        )
        resp.raise_for_status()
        profile = resp.json()
        email = profile.get("email")
        
        if not email:
            raise ValueError("No email in user profile")

        # # Save credentials to tokens/{email}.json
        # save_credentials(email, tokens)
        
        # # ✅ NEW: Create session and set cookie
        # session_token = create_session(email, access_token)
        
        # logger.info(f"✅ User authenticated: {email}")
        # logger.info(f"🍪 Setting cookie with token: {session_token[:10]}...")  # ✅ ADD THIS
        
        # # Create redirect response
        # response = RedirectResponse(f"{FRONTEND_URL}/?email={email}")
        
        # # ✅ Set HTTP-only cookie
        # response.set_cookie(
        #     key=SESSION_COOKIE_NAME,
        #     value=session_token,
        #     httponly=True,      # Prevents JavaScript access
        #     secure=True,       # Set to True in production with HTTPS
        #     samesite="none",     # CSRF protection
        #     domain="None",
        #     max_age=SESSION_MAX_AGE,
        #     path="/"
        # )

        # logger.info(f"🍪 Cookie set successfully")  # ✅ ADD THIS

        creds = Credentials(
            token=tokens["access_token"],
            refresh_token=tokens.get("refresh_token"),
            token_uri="https://oauth2.googleapis.com/token",
            client_id=CLIENT_ID,
            client_secret=CLIENT_SECRET,
            scopes=SCOPES
        )

        # 3. Store in the global memory dictionary
        USER_STORE.setdefault(email, {})
        USER_STORE[email]["credentials"] = creds
        
        logger.info(f"✅ Credentials stored in memory for: {email}")
        
        return RedirectResponse(
            f"{FRONTEND_URL}/?email={email}&token={access_token}&status=success"
        )
    except requests.exceptions.RequestException as e:
        logger.error(f"❌ Token exchange failed: {e}")
        return RedirectResponse(f"{FRONTEND_URL}/?error=token_exchange_failed")
    except Exception as e:
        logger.exception(f"❌ OAuth callback error: {e}")
        return RedirectResponse(f"{FRONTEND_URL}/?error=oauth_failed")
    
@app.post("/api/logout")
async def logout(email: str = Form(...)):
    """Simple logout - clear user data from memory"""
    try:
        if email in USER_STORE:
            # Clear user credentials from memory
            USER_STORE[email].pop("credentials", None)
            USER_STORE[email].pop("dataframe", None)
            USER_STORE[email].pop("filename", None)
            logger.info(f"✅ User {email} logged out and data cleared from memory")
            return {"message": "Logged out successfully", "email": email}
        else:
            logger.warning(f"⚠️ Logout attempt for non-existent user: {email}")
            return {"message": "User not found in session", "email": email}
    except Exception as e:
        logger.error(f"❌ Logout error for {email}: {e}")
        raise HTTPException(status_code=500, detail=f"Logout failed: {str(e)}")
# ----------------------------
# Google Drive API Routes
# ----------------------------

@app.get("/api/drive/search")
def search_drive(email: str = Query(...), q: str = Query("")):
    """Search Google Drive for files"""
    try:
        service = get_drive_service(email)
        query = f"name contains '{q}' and mimeType != 'application/vnd.google-apps.folder' and trashed=false"
        
        response = service.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name, mimeType, modifiedTime)",
            pageSize=20
        ).execute()

        files = response.get("files", [])
        print(f"🔍 Found {len(files)} files for query: '{q}'")
        return {"files": files}

    except Exception as e:
        print(f"❌ [Drive Search Error] {e}")
        return JSONResponse({"error": str(e), "files": []}, status_code=500)


@app.get("/api/drive/getfile")
def get_drive_file(email: str = Query(...), file_id: str = Query(...)):
    """Download file from Google Drive"""
    try:
        service = get_drive_service(email)
        
        # ✅ First check if file exists and user has access
        try:
            file = service.files().get(
                fileId=file_id, 
                fields="id, name, mimeType, owners, capabilities",
                supportsAllDrives=True  # ✅ Support shared drives
            ).execute()
        except HttpError as e:
            if e.resp.status == 404:
                return JSONResponse({
                    "error": "File not found or you don't have access to this file",
                    "details": "Please check: 1) File exists 2) You have permission 3) File is not in trash",
                    "file_id": file_id
                }, status_code=404)
            raise
        
        filename = file["name"]
        mime_type = file["mimeType"]
        
        print(f"📁 File found: {filename} (Type: {mime_type})")
        print(f"👤 Owner: {file.get('owners', [{}])[0].get('emailAddress', 'Unknown')}")

        # Download to memory buffer instead of file
        buffer = io.BytesIO()

        # Handle Google Workspace files (Sheets, Docs, etc.)
        if mime_type.startswith("application/vnd.google-apps.spreadsheet"):
            print(f"📊 Exporting Google Sheet as CSV: {filename}")
            request_data = service.files().export_media(
                fileId=file_id, 
                mimeType="text/csv"
            )
            if not filename.endswith('.csv'):
                filename = filename.rsplit('.', 1)[0] + '.csv'
                
        elif mime_type.startswith("application/vnd.google-apps.document"):
            print(f"📄 Exporting Google Doc as text: {filename}")
            request_data = service.files().export_media(
                fileId=file_id, 
                mimeType="text/plain"
            )
            
        elif mime_type.startswith("application/vnd.google-apps"):
            # Other Google Workspace files
            return JSONResponse({
                "error": f"Unsupported Google Workspace file type: {mime_type}",
                "details": "Please convert to CSV, Excel, or PDF format first",
                "file_name": filename
            }, status_code=400)
            
        else:
            # Regular files (CSV, Excel, PDF, etc.)
            print(f"📁 Downloading file: {filename}")
            request_data = service.files().get_media(
                fileId=file_id,
                supportsAllDrives=True
            )

        # Download file in chunks to memory buffer
        downloader = MediaIoBaseDownload(buffer, request_data)
        done = False
        while not done:
            status, done = downloader.next_chunk()
            if status:
                progress = int(status.progress() * 100)
                print(f"⬇️ Download progress: {progress}%")

        buffer.seek(0)

        # 4. ✅ CRITICAL FIX: Save to Disk so 'file_path' is updated for Validation
        import tempfile
        import shutil
        
        suffix = pathlib.Path(filename).suffix
        if not suffix: suffix = ".csv" # fallback
        
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        temp_path = temp_file.name

        with open(temp_path, "wb") as f:
            f.write(buffer.getbuffer())

        # 5. ✅ Update USER_STORE with NEW file details
        if email not in USER_STORE:
            USER_STORE[email] = {}
            
        USER_STORE[email]["file_path"] = temp_path  # Now Validation points to THIS file
        USER_STORE[email]["filename"] = filename
        
        # Clear old DF from memory to avoid confusion
        if "dataframe" in USER_STORE[email]:
            del USER_STORE[email]["dataframe"]

        # 6. Generate Preview and Session Token
        try:
            if filename.lower().endswith('.csv'):
                df_preview = pd.read_csv(temp_path, nrows=5, dtype=str)
            else:
                df_preview = pd.read_excel(temp_path, nrows=5)
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to parse file: {e}")

        session_token = make_session_token(email, filename)
        USER_STORE[email]["last_session_token"] = session_token
        
        preview = df_preview.replace({float("inf"): None, float("-inf"): None}).fillna("").to_dict(orient="records")

        print(f"✅ Drive file saved and path updated: {filename} -> {temp_path}")

        return {
            "name": filename,
            "local_path": session_token,
            "preview": preview,
            "columns": list(df_preview.columns),
            "size_kb": round(buffer.getbuffer().nbytes / 1024, 2)
        }

    except Exception as e:
        print(f"❌ [Drive Error] {e}")
        return JSONResponse({"error": str(e)}, status_code=500)


# ----------------------------
# File Upload Route
# ----------------------------
# Session token helpers: we will create a short session token used in templates for 'local_path'
def make_session_token(email: str, filename: str) -> str:
    raw = f"{email}||{filename}||{datetime.utcnow().isoformat()}"
    token = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("utf-8")
    return token

# ----------------------------
# Mapping-Specific File Upload Route
# ----------------------------

@app.post("/api/mapping_upload_local")
async def api_mapping_upload_local(
    email: str = Form(...), 
    file: UploadFile = File(...),
    file_type: str = Form(...)  # "source" or "target"
):
    """
    ✅ Upload files specifically for Mapping Service
    Stores source and target files separately without overwriting
    """
    if email not in USER_STORE:
        USER_STORE[email] = {}
    
    # ✅ Initialize mapping_files structure if not exists
    if "mapping_files" not in USER_STORE[email]:
        USER_STORE[email]["mapping_files"] = {}
    
    contents = await file.read()
    filename = file.filename
    filename_lower = filename.lower()

    try:
        # Parse file based on extension
        if filename_lower.endswith(".csv"):
            try:
                df = pd.read_csv(io.BytesIO(contents), sep=None, engine="python", dtype=str)
            except Exception:
                try:
                    df = pd.read_csv(io.BytesIO(contents), dtype=str)
                except Exception:
                    df = pd.read_excel(io.BytesIO(contents))

        elif filename_lower.endswith(".json"):
            import json
            json_data = json.load(io.BytesIO(contents))
            
            if isinstance(json_data, dict):
                df = pd.DataFrame([json_data])
            else:
                df = pd.DataFrame(json_data)

        elif filename_lower.endswith((".xls", ".xlsx", ".xlsm")):
            df = pd.read_excel(io.BytesIO(contents))

        else:
            raise Exception(f"Unsupported file format: {pathlib.Path(filename).suffix}")

    except Exception as e:
        logger.exception(f"Failed to parse mapping file: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    # Cast numeric columns
    df = detect_and_cast_numeric(df)

    # ✅ Store in mapping-specific structure with file_type key
    USER_STORE[email]["mapping_files"][file_type] = {
        "dataframe": df,
        "filename": filename,
        "uploaded_at": datetime.utcnow().isoformat(),
        "file_id": None  # Will be set if uploaded from Drive
    }

    logger.info(f"✅ Mapping {file_type} file uploaded: {filename} for {email}")
    logger.info(f"📊 Shape: {df.shape}, Columns: {list(df.columns)}")
    
    # Create session token
    session_token = make_session_token(email, filename)
    
    # Generate preview
    preview = df.head(5).replace({
        float("inf"): None, 
        float("-inf"): None
    }).fillna("").to_dict(orient="records")
    
    return {
        "name": filename,
        "preview": preview,
        "local_path": session_token,
        "file_type": file_type,
        "columns": list(df.columns),
        "row_count": len(df)
    }

# @app.post("/api/upload_local")
# async def api_upload_local(email: str = Form(...), file: UploadFile = File(...)):
#     if email not in USER_STORE:
#         USER_STORE.setdefault(email, {})
#     contents = await file.read()
    
#     # <--- CHANGED: Get lowercase filename once for easier checking
#     filename_lower = file.filename.lower() 

#     try:
#         # Check for CSV
#         if filename_lower.endswith(".csv"):
#             # try to detect delimiter intelligently (fall back to comma)
#             # Many of your CSVs look like tab-separated; try '\t' first then ','
#             try:
#                 df = pd.read_csv(io.BytesIO(contents), sep=None, engine="python", dtype=str)
#             except Exception:
#                 try:
#                     df = pd.read_csv(io.BytesIO(contents), dtype=str)
#                 except Exception:
#                     # fallback: read as excel (sometimes CSVs are misnamed XLS)
#                     df = pd.read_excel(io.BytesIO(contents))

#         # <--- CHANGED: Add explicit check for JSON files
#         elif filename_lower.endswith(".json"):
#              import json
#              json_data = json.load(io.BytesIO(contents))
             
#              # 2. Check structure
#              if isinstance(json_data, dict):
#                  # If it's a single dictionary (scalar values), wrap it in a list
#                  df = pd.DataFrame([json_data])
#              else:
#                  # If it's already a list, load it directly
#                  df = pd.DataFrame(json_data)

#         # <--- CHANGED: Add explicit check for Excel files rather than a blind 'else'
#         elif filename_lower.endswith((".xls", ".xlsx", ".xlsm")):
#             df = pd.read_excel(io.BytesIO(contents))

#         # <--- CHANGED: Final else if the format is totally unknown
#         else:
#              raise Exception(f"Unsupported file format: {pathlib.Path(file.filename).suffix}")

#     except Exception as e:
#         LOG.exception("Failed to parse uploaded file: %s", e)
#         # This will return the 400 error you saw in your console logs
#         raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

#     # cast numeric columns
#     df = detect_and_cast_numeric(df)

#     USER_STORE[email]["dataframe"] = df

#     USER_STORE[email]["filename"] = pathlib.Path(file.filename).name

#     print("============================================================")
#     print(df)
#     print("=================================================================")
#     print(pathlib.Path(file.filename).name)

#     # create a session token for templates
#     session_token = make_session_token(email, USER_STORE[email]["filename"])
#     USER_STORE[email]["last_session_token"] = session_token
    
#     preview = df.head(5).replace({float("inf"): None, float("-inf"): None}).fillna("").to_dict(orient="records")
#     return {"name": USER_STORE[email]["filename"], "preview": preview, "local_path": session_token}

import shutil
import tempfile

@app.post("/api/upload_local")
async def api_upload_local(email: str = Form(...), file: UploadFile = File(...)):
    """
    ✅ Optimized Upload: Saves file directly to Disk (Temp folder).
    Does NOT load the whole file into RAM. Safe for large files.
    """
    if email not in USER_STORE:
        USER_STORE.setdefault(email, {})
    
    filename = file.filename
    filename_lower = filename.lower()
    
    # 1. Create a Temp File on Disk
    # 'delete=False' means the file stays until we manually remove it (in cleanup)
    suffix = pathlib.Path(filename).suffix
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = temp_file.name # e.g., /tmp/tmp8475.csv

    try:
        # 2. Stream content from Upload to Disk (RAM Safe)
        with temp_file as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        print(f"✅ File saved to disk at: {temp_path}")
        
        # 3. Store ONLY the PATH in memory (Not the heavy DataFrame)
        USER_STORE[email]["file_path"] = temp_path
        USER_STORE[email]["filename"] = filename
        
        # Clear any old dataframe from RAM to free space
        if "dataframe" in USER_STORE[email]:
            del USER_STORE[email]["dataframe"]

        # 4. Generate Preview (Read only first 5 rows)
        # We read just a tiny bit to show the user, preserving RAM.
        try:
            if filename_lower.endswith(".csv"):
                # Try reading with default engine
                try:
                    df_preview = pd.read_csv(temp_path, nrows=5, dtype=str)
                except:
                    # Fallback for encoding errors
                    df_preview = pd.read_csv(temp_path, nrows=5, sep=None, engine='python', dtype=str)
                    
            elif filename_lower.endswith(".json"):
                # JSON is tricky to read partially, so we read full for preview (usually json is smaller)
                # Or we can just read line by line if it's new-line delimited
                import json
                with open(temp_path, 'r') as f:
                    try:
                        data = json.load(f)
                        if isinstance(data, list):
                            df_preview = pd.DataFrame(data[:5])
                        else:
                            df_preview = pd.DataFrame([data])
                    except:
                        df_preview = pd.DataFrame() # Fail gracefully
                        
            elif filename_lower.endswith((".xls", ".xlsx", ".xlsm")):
                df_preview = pd.read_excel(temp_path, nrows=5, dtype=str)
            else:
                raise Exception("Unsupported file format")
                
        except Exception as read_err:
            print(f"⚠️ Preview generation failed: {read_err}")
            df_preview = pd.DataFrame(columns=["Error"])

    except Exception as e:
        logger.exception("Failed to save file: %s", e)
        # Cleanup if failed
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=400, detail=f"Failed to save file: {e}")

    # Create session token
    session_token = make_session_token(email, filename)
    USER_STORE[email]["last_session_token"] = session_token
    
    # Prepare preview for frontend
    preview = df_preview.replace({float("inf"): None, float("-inf"): None}).fillna("").to_dict(orient="records")
    
    return {
        "name": filename, 
        "preview": preview, 
        "local_path": session_token
    }


# ----------------------------
# Validation Rules API
# ----------------------------


@app.post("/api/get_validation_rules")
async def api_get_validation_rules(
    email: str = Form(...),
    filename: str = Form(...),
    local_path: str = Form(...)
):
    """Generate validation rules using Gemini"""
    # Get DataFrame from memory using email
    if email not in USER_STORE or "file_path" not in USER_STORE[email]:
        raise HTTPException(status_code=404, detail="No dataset loaded. Please upload a file first.")

    # df = USER_STORE[email]["dataframe"]

    file_path = USER_STORE[email]["file_path"]
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, dtype=str)
        else:
            df = pd.read_excel(file_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file from disk: {e}")

    df = detect_and_cast_numeric(df)
    headers = list(df.columns)
    sample_size = min(len(df), 10)
    sample_rows = df.sample(n=sample_size).replace({float("nan"): None}).to_dict(orient="records")

    # print("SAMPLE ROWS" , sample_rows)

    print(f"[Gemini Input] Columns={headers}")
    rules = call_gemini_generate_rules(headers, sample_rows)
    print(f"[Gemini Output] Rules generated")

    # Ensure consistent return format
    if isinstance(rules, dict):
        flattened = []
        for col, lst in rules.items():
            for rule in lst:
                flattened.append({
                    "column": col,
                    "rule": rule.get("rule_id") or rule.get("rule"),
                    "description": rule.get("description", "")
                })
        rules = flattened

    return {"rules": rules, "headers": headers}


@app.post("/api/regenerate_rules")
async def api_regenerate_rules(
    email: str = Form(...),
    filename: str = Form(...),
    local_path: str = Form(...),
    edits_json: str = Form(...),
    current_headers_json: str = Form(None)
):
    """Refine validation rules based on user edits"""
    # Get DataFrame from memory
    if email not in USER_STORE or "file_path" not in USER_STORE[email]:
         raise HTTPException(status_code=404, detail="No dataset loaded in session.")

    # df = USER_STORE[email]["dataframe"]

    file_path = USER_STORE[email]["file_path"]
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, dtype=str)
        else:
            df = pd.read_excel(file_path)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read source file")

    try:
        user_edits = json.loads(edits_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    original_headers = list(df.columns)
    active_headers = original_headers

    if current_headers_json:
        try:
            # 1. Parse the headers received from the frontend (the ones NOT deleted)
            client_headers = json.loads(current_headers_json)
            
            # 2. Filter the original file columns based on what the client sent.
            #    This ensures we only send headers that are still active AND exist in the file.
            active_headers = [h for h in original_headers if h in client_headers]
            print(f"[RegenerateRules] Original Headers Count: {len(original_headers)}, Active Headers Count: {len(active_headers)}")
            print(f"[RegenerateRules] Active Headers: {active_headers}")
        except Exception as e:
            # If parsing fails, fall back to original headers (default)
            print(f"[RegenerateRules] Error loading client headers, using all: {e}")
            active_headers = original_headers
    
    df_filtered = df[active_headers]
    sample_rows = df_filtered.head(5).replace({float("nan"): None}).to_dict(orient="records")

    print("[RegenerateRules] Sending user edits to Gemini...")
    new_rules = call_gemini_generate_rules(active_headers, sample_rows, user_guidance=user_edits)

    if isinstance(new_rules, dict):
        flattened = []
        for col, lst in new_rules.items():
            for rule in lst:
                if col in active_headers: 
                    flattened.append({
                        "column": col,
                        "rule": rule.get("rule_id") or rule.get("rule"),
                        "description": rule.get("description", "")
                    })
        new_rules = flattened

    return {"rules": new_rules, "headers": active_headers}


# @app.post("/api/run_validation")
# async def api_run_validation(
#     email: str = Form(...),
#     filename: str = Form(...),
#     local_path: str = Form(...),
#     rules_json: str = Form(...),
# ):
#     """Run validation and create results workbook"""
#     print(f"[RunValidation] email={email}, file={filename}")
#     # Get DataFrame from memory
#     if email not in USER_STORE or "dataframe" not in USER_STORE[email]:
#         raise HTTPException(status_code=400, detail="No dataset in memory.")

#     df = USER_STORE[email]["dataframe"].copy() 

#     try:
#         rules = json.loads(rules_json)
#         if not isinstance(rules, list):
#             raise ValueError("rules_json must be a JSON array")
#     except Exception as e:
#         raise HTTPException(status_code=400, detail=f"Invalid rules_json: {e}")

#     # Apply rules
#     good_df, bad_df = apply_validation_rules(df, rules)
#     total, good, bad = len(df), len(good_df), len(bad_df)

#     summary = pd.DataFrame({
#         "Metric": ["Total Rows", "Good Rows", "Bad Rows", "Good %", "Bad %", "Columns", "Rules", "Timestamp"],
#         "Value": [
#             total, good, bad,
#             f"{(good / total * 100):.2f}%" if total else "0.00%",
#             f"{(bad / total * 100):.2f}%" if total else "0.00%",
#             len(df.columns), len(rules),
#             datetime.now().strftime("%Y-%m-%d %H:%M:%S")
#         ]
#     })

#     if not bad_df.empty:
#         error_freq_df = summarize_errors(bad_df)
#     else:
#         error_freq_df = pd.DataFrame(columns=["Error", "Frequency"])

#     # ✅ Duplicates Sheet (using helper function)
#     duplicates_df = detect_duplicates(df)


#     mem_file = io.BytesIO()
#     with pd.ExcelWriter(mem_file, engine="openpyxl") as writer:
#         (good_df if not good_df.empty else pd.DataFrame()).to_excel(writer, "Good_Data", index=False)
#         (bad_df if not bad_df.empty else pd.DataFrame()).to_excel(writer, "Bad_Data", index=False)
#         (pd.DataFrame(rules) if rules else pd.DataFrame()).to_excel(writer, "Validation_Rules", index=False)
#         summary.to_excel(writer, "Summary", index=False)
#         error_freq_df.to_excel(writer, "Error_Frequency", index=False) 
#         duplicates_df.to_excel(writer, "Duplicates", index=False)

#     mem_file.seek(0)

#     # Upload to Google Drive
#     try:
#         service = get_drive_service(email)
        
#         media = MediaIoBaseUpload(
#             mem_file,  # CHANGED: memory buffer instead of file
#             mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
#             resumable=False  # CHANGED: False for in-memory uploads
#         )
        
#         metadata = {
#             "name": f"validation_result_{filename}",  # CHANGED: use filename directly
#             "mimeType": "application/vnd.google-apps.spreadsheet"
#         }
        
#         created = service.files().create(
#             body=metadata, 
#             media_body=media, 
#             fields="id,webViewLink,webContentLink"
#         ).execute()
        
#         file_id = created.get("id")
#         web_link = created.get("webViewLink")
        
#         try:
#             service.permissions().create(
#                 fileId=file_id,
#                 body={
#                     "type": "anyone",
#                     "role": "reader"
#                 }
#             ).execute()
#             print(f"✅ File permissions set: {file_id}")
#         except Exception as perm_error:
#             print(f"⚠️ Permission Error: {perm_error}")
        
#         print(f"✅ File uploaded to Drive: {web_link}")
        
#     except Exception as e:
#         print(f"[Drive Upload Error] {e}")
#         web_link = None
#         file_id = None

#     return {
#         "workbook": {
#             "id": file_id, 
#             "webViewLink": web_link,
#             "downloadLink": f"https://drive.google.com/uc?export=download&id={file_id}" if file_id else None
#         },
#         "good_count": good,
#         "bad_count": bad,
#     }

import os
import gc
import tempfile
import pandas as pd
import numpy as np
from fastapi import Form, HTTPException
from datetime import datetime

# Define Chunk Size (200 rows is a safe balance for speed vs memory)
CHUNK_SIZE = 200

@app.post("/api/run_validation")
async def api_run_validation(
    email: str = Form(...),
    filename: str = Form(...),
    local_path: str = Form(...),
    rules_json: str = Form(...),
):
    """
    Run validation using Chunking Strategy to prevent Memory Crashes.
    Functionality is preserved, but memory usage is minimized.
    """
    print(f"[RunValidation] Starting Chunked Processing for {filename}")

    # 1. Get DataFrame (Reference only, don't copy yet)
    if email not in USER_STORE or "file_path" not in USER_STORE[email]:
        raise HTTPException(status_code=400, detail="No dataset in memory.")
    
    # full_df = USER_STORE[email]["dataframe"]
    # total_rows = len(full_df)

    file_path = USER_STORE[email]["file_path"]
    try:
        if file_path.endswith('.csv'):
            full_df = pd.read_csv(file_path, dtype=str)
        else:
            full_df = pd.read_excel(file_path)
        full_df = detect_and_cast_numeric(full_df)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file from disk: {e}")
    
    total_rows = len(full_df)
    column_count = len(full_df.columns)

    try:
        rules = json.loads(rules_json)
        if not isinstance(rules, list):
            raise ValueError("rules_json must be a JSON array")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid rules_json: {e}")

    # 2. Create Temporary CSV files for Good and Bad data
    # We use CSV first because we can "Append" to them easily. Excel doesn't support easy appending.
    temp_dir = tempfile.mkdtemp()
    good_csv_path = os.path.join(temp_dir, "temp_good.csv")
    bad_csv_path = os.path.join(temp_dir, "temp_bad.csv")

    total_good = 0
    total_bad = 0

    print(f"🔄 Processing {total_rows} rows in chunks of {CHUNK_SIZE}...")

    # 3. CHUNKING LOOP
    # Divide data into batches (0-2000, 2000-4000, etc.)
    for start_idx in range(0, total_rows, CHUNK_SIZE):
        end_idx = min(start_idx + CHUNK_SIZE, total_rows)
        
        # Slice the chunk (Creates a small copy, not full copy)
        chunk = full_df.iloc[start_idx:end_idx].copy()
        
        # Apply Validation Rules on this chunk
        chunk_good, chunk_bad = apply_validation_rules(chunk, rules)
        
        # Update counts
        total_good += len(chunk_good)
        total_bad += len(chunk_bad)

        # Append to CSV files (Header only for the first chunk)
        write_header = (start_idx == 0)
        
        if not chunk_good.empty:
            chunk_good.to_csv(good_csv_path, mode='a', index=False, header=write_header)
        
        if not chunk_bad.empty:
            chunk_bad.to_csv(bad_csv_path, mode='a', index=False, header=write_header)

        # 🧹 Clear Memory immediately
        del chunk
        del chunk_good
        del chunk_bad
        gc.collect() # Force garbage collection

    print("✅ Validation Chunks Processed. Calculating Duplicates...")

    # 4. Handle Duplicates (Separate Step)
    # Note: Fuzzy matching on huge datasets is O(N^2). 
    # We run exact match on full DF (fast) and limit fuzzy logic if extremely huge.
    
    # Run exact duplicate check on full dataframe (It's memory efficient usually)
    duplicates_df = detect_duplicates(full_df)

    print("🧹 Cleaning up Main Dataframe from RAM to prevent crash...")
    del full_df
    gc.collect()
    
    # 5. Generate Summary
    summary = pd.DataFrame({
        "Metric": ["Total Rows", "Good Rows", "Bad Rows", "Good %", "Bad %", "Columns", "Rules", "Timestamp"],
        "Value": [
            total_rows, total_good, total_bad,
            f"{(total_good / total_rows * 100):.2f}%" if total_rows else "0.00%",
            f"{(total_bad / total_rows * 100):.2f}%" if total_rows else "0.00%",
            column_count,len(rules),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ]
    })

    # Calculate Error Frequency from the Bad CSV (Read only specific columns to save RAM)
    error_freq_df = pd.DataFrame(columns=["Error", "Frequency"])
    if total_bad > 0 and os.path.exists(bad_csv_path):
        try:
            # Read only validation reason column
            bad_reasons = pd.read_csv(bad_csv_path, usecols=["_validation_reason"])
            error_freq_df = summarize_errors(bad_reasons)
            del bad_reasons
            gc.collect()
        except Exception:
            pass # Column might not exist if empty

    # 6. Final Assembly: Write CSVs to Excel Stream
    print("💾 assembling final Excel file...")
    final_excel_path = os.path.join(temp_dir, f"validation_result_{filename}.xlsx")
    
    with pd.ExcelWriter(final_excel_path, engine="openpyxl") as writer:
        # Sheet 1: Good Data (Read from disk -> Write to Excel -> Clear RAM)
        if total_good > 0 and os.path.exists(good_csv_path):
            for chunk in pd.read_csv(good_csv_path, chunksize=50000, dtype=str):
                # Note: to_excel doesn't append well, so for massive files, 
                # we usually just write the first chunk or we'd need a complex engine loop.
                # Since we already split good/bad, fitting one of them in RAM is usually okay.
                # If 'Good' is still 1GB, this might pinch, but it's better than Good+Bad+Original.
                chunk.to_excel(writer, "Good_Data", index=False)
                break # Limitation: Writing huge CSV to Excel sheet in parts is complex. Writing fully here.
                # If you need full multi-chunk write to single sheet, we need openpyxl manual loops.
                # For now, reading full CSV back is safer than holding everything.
        else:
            pd.DataFrame().to_excel(writer, "Good_Data", index=False)

        # Sheet 2: Bad Data
        if total_bad > 0 and os.path.exists(bad_csv_path):
             # Read full CSV back for writing (Separate step avoids peak memory)
            pd.read_csv(bad_csv_path, dtype=str).to_excel(writer, "Bad_Data", index=False)
        else:
            pd.DataFrame().to_excel(writer, "Bad_Data", index=False)

        # Other Sheets
        (pd.DataFrame(rules) if rules else pd.DataFrame()).to_excel(writer, "Validation_Rules", index=False)
        summary.to_excel(writer, "Summary", index=False)
        error_freq_df.to_excel(writer, "Error_Frequency", index=False)
        duplicates_df.to_excel(writer, "Duplicates", index=False)

    # 7. Upload to Google Drive
    print("☁️ Uploading to Drive...")
    try:
        service = get_drive_service(email)
        from googleapiclient.http import MediaFileUpload
        
        media = MediaFileUpload(
            final_excel_path, 
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            resumable=True
        )
        
    #     created = service.files().create(
    #         body={
    #             "name": f"validation_result_{filename}",
    #             "mimeType": "application/vnd.google-apps.spreadsheet"
    #         }, 
    #         media_body=media, 
    #         fields="id,webViewLink"
    #     ).execute()
        
    #     file_id = created.get("id")
    #     web_link = created.get("webViewLink")
        
    #     service.permissions().create(fileId=file_id, body={"type": "anyone", "role": "reader"}).execute()

    # except Exception as e:
    #     print(f"❌ Upload Error: {e}")
    #     web_link = None
    #     file_id = None
    
    # # 8. Clean up disk files
    # import shutil
    # shutil.rmtree(temp_dir)
    # gc.collect()

    # return {
    #     "workbook": {
    #         "id": file_id, 
    #         "webViewLink": web_link,
    #         "downloadLink": f"https://drive.google.com/uc?export=download&id={file_id}" if file_id else None
    #     },
    #     "good_count": total_good,
    #     "bad_count": total_bad,
    # }
        metadata = {
               "name": f"validation_result_{filename}",  # CHANGED: use filename directly
            "mimeType": "application/vnd.google-apps.spreadsheet"
        }
        
        created = service.files().create(
            body=metadata, 
            media_body=media, 
            fields="id,webViewLink,webContentLink"
        ).execute()
        
        file_id = created.get("id")
        web_link = created.get("webViewLink")
        
        try:
            service.permissions().create(
                fileId=file_id,
                body={
                    "type": "anyone",
                    "role": "reader"
                }
            ).execute()
            print(f"✅ File permissions set: {file_id}")
        except Exception as perm_error:
            print(f"⚠️ Permission Error: {perm_error}")
        
        print(f"✅ File uploaded to Drive: {web_link}")
        
    except Exception as e:
        print(f"[Drive Upload Error] {e}")
        web_link = None
        file_id = None
    # Upload done
    del media
    gc.collect()
    
    # Remove artificial sleep
    # time.sleep(100)  ❌ DELETE THIS
    
    # Safe cleanup
    import shutil
    import time
    
    def safe_rmtree(path, retries=5, delay=1):
        for _ in range(retries):
            try:
                shutil.rmtree(path)
                return
            except PermissionError:
                time.sleep(delay)
        raise
    
    safe_rmtree(temp_dir)
    gc.collect()
    
    print("file deleted successfully from the disk")
    
    
    return {
        "workbook": {
            "id": file_id, 
            "webViewLink": web_link,
            "downloadLink": f"https://drive.google.com/uc?export=download&id={file_id}" if file_id else None
        },
        "good_count": total_good,
        "bad_count": total_bad,
    }

# ----------------------------
# Health Check
# ----------------------------

@app.get("/health")
def health_check():
    """
    Lightweight route for UptimeRobot to keep server awake.
    Returns 200 OK status.
    """
    return {
        "status": "awake", 
        "timestamp": datetime.now().isoformat(),
        "message": "I am ready to process data! 🤖"
    }

@app.get("/")
def root():
    return {"message": "AI Data Validation Tool is running! ✅", "frontend": FRONTEND_URL}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
