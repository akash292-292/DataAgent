"""
Configuration Settings
Centralized configuration for the entire application
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ==================== OAUTH CONFIGURATION ====================
CLIENT_ID = os.getenv("CLIENT_NEW_ID")
CLIENT_SECRET = os.getenv("CLIENT_NEW_SECRET")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:8000/oauth2callback")

SCOPES = [
    "openid", 
    "email", 
    "profile",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/drive.file",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/drive.metadata.readonly"
]

# ==================== API KEYS ====================
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MAPPING_API_KEY = os.getenv("GEMINI_MAPPING_API_KEY", "").strip()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# ==================== MODEL CONFIGURATION ====================
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ==================== FRONTEND CONFIGURATION ====================
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3001")
FRONTEND2_URL = os.getenv("FRONTEND2_URL", "http://localhost:3001")

ALLOWED_ORIGINS = [
    FRONTEND_URL,
    FRONTEND2_URL,
    "http://localhost:3000",
    "http://localhost:3001",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001"
]

# ==================== SESSION CONFIGURATION ====================
SESSION_COOKIE_NAME = "session_token"
SESSION_MAX_AGE = 3600  # 1 hour

# ==================== MAPPING CONFIGURATION ====================
DEFAULT_HOST_SYSTEM = "Host System"
DEFAULT_TARGET_SYSTEM = "Target System"
DEFAULT_LLM_TIMEOUT = 200.0
DEFAULT_SIMILARITY_THRESHOLD = 0.4
SEMANTIC_WEIGHT = 0.65
STRING_WEIGHT = 0.35
MAX_EXECUTOR_WORKERS = 4

# ==================== FILE PROCESSING CONFIGURATION ====================
CHUNK_SIZE = 50000  # Rows per chunk for large file processing

# ==================== VALIDATION ====================
if not CLIENT_ID or not CLIENT_SECRET:
    raise RuntimeError("CLIENT_ID and CLIENT_SECRET must be set in .env")
