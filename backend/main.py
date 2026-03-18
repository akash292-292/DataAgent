"""
Main FastAPI Application - SECURE VERSION
Centralized application with all routes and middleware
"""

import logging
import os
import pathlib
import sys
import importlib.util
from datetime import datetime
from dotenv import dotenv_values

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from config.settings import ALLOWED_ORIGINS, FRONTEND_URL
from services.gemini_token_service import gemini_token_service
from core.redis import redis

# Import routers (modules)
from api import auth_routes
from api import drive_routes
from api import upload_routes
from api import validation_routes
from api import mapping_routes
from api import qa_requirement_routes
from api import qa_testcase_routes
from api import qa_excel_routes
from api import metadata_routes
from api import governance_routes


# -------------------------------------------------
# Logging configuration
# -------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# -------------------------------------------------
# Create required directories
# -------------------------------------------------
BASE_DIR = pathlib.Path(__file__).parent
TOKENS_DIR = BASE_DIR / "tokens"
TOKENS_DIR.mkdir(exist_ok=True)


# -------------------------------------------------
# Initialize FastAPI app
# -------------------------------------------------
app = FastAPI(
    title="AI Data Validation Tool",
    description="Automated data validation and mapping with AI",
    version="2.0.0"
)


# -------------------------------------------------
# ✅ SECURE CORS Configuration
# CRITICAL: allow_credentials=True enables cookies!
# -------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,  # Specify exact origins, not "*"
    allow_credentials=True,          # ✅ CRITICAL: Allows cookies to be sent
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"]             # ✅ Allows frontend to read response headers
)

logger.info(f"✅ CORS enabled for origins: {ALLOWED_ORIGINS}")


# -------------------------------------------------
# Include routers
# -------------------------------------------------
@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "frame-ancestors 'none'; "
        "object-src 'none'; "
        "img-src 'self' data: https:; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://apis.google.com https://accounts.google.com; "
        "style-src 'self' 'unsafe-inline' https:; "
        "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000 http://localhost:3000 http://localhost:3001 https://www.googleapis.com https://apis.google.com;"
    )
    if request.url.scheme == "https":
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


app.include_router(auth_routes.router)
app.include_router(drive_routes.router)
app.include_router(upload_routes.router)
app.include_router(validation_routes.router)
app.include_router(mapping_routes.router)
app.include_router(qa_requirement_routes.router)
app.include_router(qa_testcase_routes.router)
app.include_router(qa_excel_routes.router)
app.include_router(metadata_routes.router)
app.include_router(governance_routes.router)


async def mount_pm_portal_if_available(main_app: FastAPI):
    """
    Optionally mount PM Portal backend under /pm without impacting existing routes.
    """
    pm_main_path = os.getenv("PM_PORTAL_BACKEND_MAIN_PATH")
    if not pm_main_path:
        pm_main_path = str((BASE_DIR / "pm_agent" / "main.py").resolve())

    pm_main_file = pathlib.Path(pm_main_path)
    if not pm_main_file.exists():
        logger.info("PM backend not mounted. File not found: %s", pm_main_file)
        return

    pm_backend_dir = str(pm_main_file.parent)
    if pm_backend_dir not in sys.path:
        sys.path.insert(0, pm_backend_dir)

    # Load PM backend .env (if present) to mirror PM-PORTAL's original runtime configuration.
    pm_env_path = os.getenv("PM_PORTAL_ENV_PATH", str((pathlib.Path(pm_backend_dir) / ".env").resolve()))
    if pathlib.Path(pm_env_path).exists():
        pm_env_values = dotenv_values(pm_env_path)
        for key, value in pm_env_values.items():
            if value is None:
                continue
            # Keep existing process env unless explicitly overridden.
            os.environ.setdefault(key, value)
    else:
        logger.warning("PM env file not found: %s", pm_env_path)

    # Prefer PM-specific DB URL so PM module points to the exact DB it originally used.
    # pm_db_url = os.getenv("PM_PORTAL_DATABASE_URL") or os.getenv("DATABASE_URL")
    # if pm_db_url:
    #     os.environ["DATABASE_URL"] = pm_db_url
    #     logger.info("PM DATABASE_URL configured from env.")
    # else:
    #     allow_sqlite_fallback = os.getenv("PM_PORTAL_ALLOW_SQLITE_FALLBACK", "false").lower() == "true"
    #     if allow_sqlite_fallback:
    #         pm_sqlite = pathlib.Path(pm_backend_dir) / "pm_portal.db"
    #         os.environ["DATABASE_URL"] = f"sqlite:///{pm_sqlite.as_posix()}"
    #         logger.warning("PM DATABASE_URL missing. Using SQLite fallback at %s", pm_sqlite)
    #     else:
    #         logger.error(
    #             "PM backend not mounted: DATABASE_URL missing. "
    #             "Set PM_PORTAL_DATABASE_URL (preferred) or DATABASE_URL in PM env."
    #         )
    #         return


    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

    try:
        # Temporarily shadow similarly named local modules (services, models, etc.)
        # so PM backend imports resolve against PM-PORTAL/backend.
        shadowed_names = ["services", "models", "schemas", "db_migrations", "drive_service"]
        original_modules = {}
        for name in shadowed_names:
            if name in sys.modules:
                original_modules[name] = sys.modules[name]
                del sys.modules[name]
        for loaded_name in list(sys.modules.keys()):
            if (
                loaded_name.startswith("services.")
                or loaded_name.startswith("models.")
                or loaded_name.startswith("schemas.")
                or loaded_name.startswith("db_migrations.")
            ):
                original_modules[loaded_name] = sys.modules[loaded_name]
                del sys.modules[loaded_name]

        spec = importlib.util.spec_from_file_location("pm_portal_main", str(pm_main_file))
        if not spec or not spec.loader:
            logger.warning("PM backend mount skipped. Unable to load spec for %s", pm_main_file)
            return

        pm_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(pm_module)
        pm_app = getattr(pm_module, "app", None)

        if pm_app is None:
            logger.warning("PM backend mount skipped. No `app` object in %s", pm_main_file)
            return

        main_app.mount("/pm", pm_app)
        logger.info("PM backend mounted at /pm from %s", pm_main_file)
        #   0. Check Redis Connection
        try:
            print("[STARTUP] Checking Redis connection...")
            await redis.ping()
            print("[OK] Redis is running and connected")
            await gemini_token_service.seed_gemini_keys(redis)
        except Exception as e:
            print(f"[WARNING] Redis connection failed: {str(e)}")
            print("[WARNING] Continuing startup without Redis - some features may not work correctly")
        for name, module in original_modules.items():
            sys.modules[name] = module
    except Exception as exc:
        for name, module in original_modules.items():
            sys.modules[name] = module
        logger.exception("Failed to mount PM backend from %s: %s", pm_main_file, exc)


@app.on_event("startup")
async def startup_event():
    """Initialize PM backend on app startup"""
    await mount_pm_portal_if_available(app)


# -------------------------------------------------
# Base endpoints
# -------------------------------------------------
@app.get("/")
def root():
    """Root endpoint"""
    return {
        "message": "AI Data Validation Tool is running! ✅",
        "version": "2.0.0",
        "frontend": FRONTEND_URL,
        "docs": "/docs",
        "security": "Session-based authentication with httpOnly cookies"
    }


@app.get("/health")
def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "message": "Service is operational 🤖"
    }


# -------------------------------------------------
# ✅ NEW: Session cleanup endpoint (optional)
# -------------------------------------------------
@app.get("/api/admin/sessions")
def list_sessions():
    """List all active sessions (admin only - add auth later)"""
    from services.auth_service import SESSIONS
    
    return {
        "active_sessions": len(SESSIONS),
        "sessions": [
            {
                "id": sid[:8] + "...",
                "email": data["email"],
                "created_at": data["created_at"],
                "expires_at": data["expires_at"]
            }
            for sid, data in SESSIONS.items()
        ]
    }


# -------------------------------------------------
# Local development entry point
# -------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )
