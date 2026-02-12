"""
Memory Management Utilities
Functions for managing USER_STORE and session data
"""
import logging
from typing import Any, Optional
import pandas as pd

from utils.file_utils import decode_session_token

logger = logging.getLogger(__name__)

# Import the shared store
from store import USER_STORE
import uuid
from typing import Any, Dict

# Simple in-memory store
_MEMORY_STORE: Dict[str, Any] = {}


def store_data_in_memory(data: Any, filename: str | None = None) -> str:
    """
    Stores parsed file content in memory and
    returns a session token
    """
    token = f"session_{uuid.uuid4().hex}"
    _MEMORY_STORE[token] = {
        "data": data,
        "filename": filename
    }
    return token


def get_data_from_memory(token: str, file_type: str | None = None) -> Any:
    """
    Retrieves stored data using session token
    """
    if token not in _MEMORY_STORE:
        raise KeyError("Session expired or invalid token")

    return _MEMORY_STORE[token]["data"]


def is_session_token(value: str | None) -> bool:
    return isinstance(value, str) and value.startswith("session_")


def get_data_from_memory(token: str, file_type: Optional[str] = None) -> Any:
    """
    Retrieves DataFrame from USER_STORE based on token and file_type
    
    Args:
        token: Session token containing email||filename||timestamp
        file_type: "source" or "target" for mapping files
    
    Returns:
        List of dicts (JSON-ready data) or None
    """
    decoded = decode_session_token(token)
    if not decoded:
        return None
    
    email, filename, timestamp = decoded
    
    logger.info(f"🔍 Looking up memory data for: {email} | File: {filename} | Type: {file_type}")

    if email not in USER_STORE:
        logger.error(f"❌ User {email} not found in USER_STORE.")
        return None

    user_data = USER_STORE[email]

    # Priority 1: Check mapping_files if file_type provided
    if file_type and "mapping_files" in user_data:
        if file_type in user_data["mapping_files"]:
            df = user_data["mapping_files"][file_type]["dataframe"]
            logger.info(f"✅ Found mapping {file_type} file: {user_data['mapping_files'][file_type]['filename']}")
            return df.to_dict(orient="records")
        else:
            logger.error(f"❌ Mapping {file_type} file not found")
            return None

    # Priority 2: Fallback to regular dataframe (for profiling)
    if "dataframe" not in user_data:
        logger.error("❌ No dataframe found in user session.")
        return None

    df = user_data["dataframe"]
    logger.info(f"✅ Found profiling dataframe: {filename}")
    return df.to_dict(orient="records")


def store_dataframe(email: str, df: pd.DataFrame, filename: str):
    """
    Store DataFrame in USER_STORE for a user
    
    Args:
        email: User's email
        df: DataFrame to store
        filename: Original filename
    """
    if email not in USER_STORE:
        USER_STORE[email] = {}
    
    USER_STORE[email]["dataframe"] = df
    USER_STORE[email]["filename"] = filename
    logger.info(f"✅ Stored dataframe for {email}: {filename}")


def store_mapping_file(email: str, df: pd.DataFrame, filename: str, file_type: str):
    """
    Store mapping file (source/target) in USER_STORE
    
    Args:
        email: User's email
        df: DataFrame to store
        filename: Original filename
        file_type: "source" or "target"
    """
    if email not in USER_STORE:
        USER_STORE[email] = {}
    
    if "mapping_files" not in USER_STORE[email]:
        USER_STORE[email]["mapping_files"] = {}
    
    USER_STORE[email]["mapping_files"][file_type] = {
        "dataframe": df,
        "filename": filename
    }
    logger.info(f"✅ Stored {file_type} mapping file for {email}: {filename}")


def get_user_dataframe(email: str) -> Optional[pd.DataFrame]:
    """
    Get user's main dataframe from USER_STORE
    
    Args:
        email: User's email
    
    Returns:
        DataFrame or None
    """
    if email not in USER_STORE or "dataframe" not in USER_STORE[email]:
        return None
    return USER_STORE[email]["dataframe"]


def get_user_filename(email: str) -> Optional[str]:
    """
    Get user's stored filename from USER_STORE
    
    Args:
        email: User's email
    
    Returns:
        Filename or None
    """
    if email not in USER_STORE or "filename" not in USER_STORE[email]:
        return None
    return USER_STORE[email]["filename"]


def clear_user_session(email: str):
    """
    Clear all data for a user from USER_STORE
    
    Args:
        email: User's email
    """
    if email in USER_STORE:
        del USER_STORE[email]
        logger.info(f"✅ Cleared session for {email}")
