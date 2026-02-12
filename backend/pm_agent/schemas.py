from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

# Authentication schemas
class LoginRequest(BaseModel):
    email: str
    name: Optional[str] = None
    google_id: Optional[str] = None

class LoginResponse(BaseModel):
    success: bool
    message: str
    session_id: Optional[str] = None
    user: Optional[Dict[str, Any]] = None

# LLM service schemas
class LLMChatRequest(BaseModel):
    message: str
    context: Optional[List[Dict[str, str]]] = None
    user_info: Optional[Dict[str, Any]] = None

class LLMChatResponse(BaseModel):
    response: str
    is_complete: bool
    next_question: Optional[str] = None

# Feedback schemas
class FeedbackRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    additional_comments: Optional[str] = None
    user_email: Optional[str] = None

class FeedbackResponse(BaseModel):
    success: bool
    message: str
    feedback_id: Optional[int] = None 