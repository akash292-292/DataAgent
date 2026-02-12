"""
Shared In-Memory Storage
Central storage for user session data
"""
from typing import Dict, Any

# Shared in-memory storage for user sessions
USER_STORE: Dict[str, Dict[str, Any]] = {}
