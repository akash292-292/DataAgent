"""
File Utilities
Helper functions for file handling, token management, and data extraction
"""
import os
import json
import base64
import logging
from typing import Any, Optional
import pandas as pd

logger = logging.getLogger(__name__)


def is_local_file(file_path: str) -> bool:
    """Check if the provided path is a local physical file"""
    if not file_path:
        return False
    try:
        return os.path.exists(file_path) and os.path.isfile(file_path)
    except Exception:
        return False


def is_session_token(token: str) -> bool:
    """
    Check if the string is a base64 encoded session token.
    Logic: It must decode successfully and contain the '||' delimiter.
    """
    if not token or len(token) < 20:
        return False
    try:
        decoded = base64.urlsafe_b64decode(token).decode("utf-8")
        return "||" in decoded
    except Exception:
        return False


def decode_session_token(token: str) -> Optional[tuple]:
    """
    Decode session token and return (email, filename, timestamp)
    Returns None if token is invalid
    """
    try:
        decoded = base64.urlsafe_b64decode(token).decode("utf-8")
        parts = decoded.split("||")
        if len(parts) < 3:
            logger.error("❌ Invalid token format")
            return None
        return parts[0], parts[1], parts[2]
    except Exception as e:
        logger.error(f"❌ Error decoding token: {e}")
        return None


def safe_json_parse(text: str) -> Any:
    """
    Safely parse JSON text, handling common formatting issues
    """
    try:
        # Remove markdown code blocks
        text = text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        return json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"❌ JSON parse error: {e}")
        raise


def extract_json_content_from_file_local(file_path: str) -> Any:
    """Read and parse JSON from local file"""
    try:
        logger.info(f"Reading local file: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        return safe_json_parse(text)
    except Exception as e:
        logger.error(f"❌ Error reading local file {file_path}: {e}")
        raise


def detect_and_cast_numeric(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect columns that are truly numeric (not phone numbers, not IDs with text)
    and convert them safely to int or float.
    """
    numeric_cols = []
    for col in df.columns:
        col_values = df[col].dropna().astype(str)
        if col_values.empty:
            continue

        # Skip columns with '@', alphabetic chars, or long 10+ digit numbers (phones)
        if col_values.str.contains(r"[A-Za-z@]", regex=True).any():
            continue

        # Check if at least 95% of values look numeric (integers or floats)
        numeric_like_ratio = col_values.str.match(r"^-?\d+(\.\d+)?$").mean()
        if numeric_like_ratio > 0.95:
            # Further safeguard: skip 10+ digit numbers (likely contact numbers)
            if col_values.str.len().mean() >= 10:
                continue

            try:
                # Convert safely
                df[col] = pd.to_numeric(df[col], errors="coerce").astype("Int64")
                numeric_cols.append(col)
            except Exception as e:
                logger.warning(f"[NumericCast] Skipped {col}: {e}")

    logger.info(f"[NumericCast] Converted numeric columns: {numeric_cols}")
    return df


def normalize_value_for_rule(value):
    """
    Normalize value for rule evaluation
    CRITICAL: Check for date/phone/email patterns BEFORE numeric conversion
    This prevents dates like "29-04-2001" from being incorrectly parsed
    """
    import re
    
    if pd.isna(value):
        return None
    
    if isinstance(value, str):
        v = value.strip()
        
        # ✅ PRIORITY 1: Check for date patterns FIRST (before numeric conversion)
        # Common date patterns: DD-MM-YYYY, DD/MM/YYYY, YYYY-MM-DD, MM-DD-YYYY
        date_patterns = [
            r'^\d{1,2}[-/]\d{1,2}[-/]\d{2,4}$',  # DD-MM-YYYY or DD/MM/YYYY
            r'^\d{4}[-/]\d{1,2}[-/]\d{1,2}$',    # YYYY-MM-DD or YYYY/MM/DD
            r'^\d{1,2}[-/]\d{1,2}[-/]\d{2}$',    # DD-MM-YY or DD/MM/YY
        ]
        
        for pattern in date_patterns:
            if re.match(pattern, v):
                # It's a date string - return as-is for string validation
                return v
        
        # ✅ PRIORITY 2: Check for phone patterns (10+ digits with optional separators)
        if re.match(r'^\+?[\d\s\-\(\)]{10,}$', v):
            # It's a phone number - return as string
            return v
        
        # ✅ PRIORITY 3: Check for email patterns
        if '@' in v and '.' in v:
            # It's an email - return as string
            return v
        
        # NOW try numeric conversion (only if not date/phone/email)
        # Pure integer (no decimals, no separators)
        if re.fullmatch(r"[+-]?\d+", v):
            try:
                return int(v)
            except Exception:
                pass
        
        # Pure float
        if re.fullmatch(r"[+-]?\d+\.\d+", v):
            try:
                return float(v)
            except Exception:
                pass
        
        # Everything else stays as string
        return v
    
    return value
