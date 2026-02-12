from sqlalchemy.orm import Session
from models import User, Session as UserSession
from schemas import LoginRequest, LoginResponse
import uuid
from datetime import datetime, timedelta
import os
import requests
from urllib.parse import urlencode

class AuthService:
    def __init__(self):
        self.secret_key = os.getenv("SECRET_KEY", "demo-secret-key")
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.google_redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    
    def get_google_auth_url(self, prompt: str = None) -> str:
        """Generate Google OAuth URL"""
        # Check if Google OAuth is properly configured
        if not self.google_client_id or not self.google_redirect_uri:
            raise ValueError("Google OAuth not configured. Please set GOOGLE_CLIENT_ID and GOOGLE_REDIRECT_URI environment variables.")
        
        params = {
            'client_id': self.google_client_id,
            'redirect_uri': self.google_redirect_uri,
            'scope': 'openid email profile https://www.googleapis.com/auth/drive.readonly',
            'response_type': 'code',
            'access_type': 'offline'
        }
        
        # Add prompt parameter if provided (e.g., 'select_account' for account selection)
        if prompt:
            params['prompt'] = prompt
        
        auth_url = "https://accounts.google.com/o/oauth2/auth"
        query_string = urlencode(params)  # Properly URL-encode all parameters
        return f"{auth_url}?{query_string}"
    
    def exchange_code_for_token(self, code: str) -> dict:
        """Exchange authorization code for access token"""
        token_url = "https://oauth2.googleapis.com/token"
        data = {
            'client_id': self.google_client_id,
            'client_secret': self.google_client_secret,
            'code': code,
            'grant_type': 'authorization_code',
            'redirect_uri': self.google_redirect_uri
        }
        
        print(f"🔐 [AUTH-SERVICE] Exchanging code for token...")
        print(f"🔐 [AUTH-SERVICE] Redirect URI: {self.google_redirect_uri}")
        print(f"🔐 [AUTH-SERVICE] Client ID: {self.google_client_id[:20] if self.google_client_id else 'None'}...")
        
        response = requests.post(token_url, data=data)
        result = response.json()
        
        if 'error' in result:
            print(f"❌ [AUTH-SERVICE] Token exchange error: {result.get('error')} - {result.get('error_description', 'No description')}")
        else:
            print(f"✅ [AUTH-SERVICE] Token exchange successful")
        
        return result
    
    def get_user_info(self, access_token: str) -> dict:
        """Get user information from Google"""
        user_info_url = "https://www.googleapis.com/oauth2/v2/userinfo"
        headers = {'Authorization': f'Bearer {access_token}'}
        
        response = requests.get(user_info_url, headers=headers)
        return response.json()
    
    def authenticate_user(self, code: str, db: Session) -> LoginResponse:
        """Authenticate user with Google OAuth"""
        try:
            # Exchange code for token
            token_data = self.exchange_code_for_token(code)
            if 'error' in token_data:
                return LoginResponse(
                    success=False,
                    session_id="",
                    user=None,
                    message=f"Token exchange failed: {token_data.get('error_description', 'Unknown error')}"
                )
            
            # Get user info from Google
            user_info = self.get_user_info(token_data['access_token'])
            
            # Check if user exists in database
            user = db.query(User).filter(User.google_id == user_info['id']).first()
            
            if not user:
                # Create new user
                user = User(
                    email=user_info['email'],
                    name=user_info['name'],
                    google_id=user_info['id']
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            
            # Create session
            session_id = f"session_{uuid.uuid4()}"
            session = UserSession(
                id=session_id,
                user_id=user.id,
                is_active=True,
                expires_at=datetime.now() + timedelta(hours=24)
            )
            db.add(session)
            db.commit()
            
            return LoginResponse(
                success=True,
                session_id=session_id,
                user={
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "google_id": user.google_id
                },
                message="Login successful"
            )
            
        except Exception as e:
            return LoginResponse(
                success=False,
                session_id="",
                user=None,
                message=f"Authentication failed: {str(e)}"
            )
    
    def simulate_login(self, request: LoginRequest) -> LoginResponse:
        """Simulate Google OAuth login - creates a demo user and session"""
        try:
            # In a real implementation, this would validate Google OAuth tokens
            # For demo purposes, we'll create a mock user and session
            
            # Generate a demo user if email is provided
            user_data = {
                "id": 1,
                "email": request.email,
                "name": request.name or "Demo User",
                "google_id": request.google_id or f"google_{uuid.uuid4().hex[:8]}"
            }
            
            # Generate session ID
            session_id = str(uuid.uuid4())
            
            # In a real app, we'd save to database
            # For demo, we'll return the session data
            
            return LoginResponse(
                success=True,
                message="Login successful (demo mode)",
                session_id=session_id,
                user=user_data
            )
            
        except Exception as e:
            return LoginResponse(
                success=False,
                message=f"Login failed: {str(e)}",
                session_id=None,
                user=None
            )
    
    def simulate_logout(self) -> dict:
        """Simulate logout"""
        return {
            "success": True,
            "message": "Logout successful (demo mode)"
        }
    
    def validate_session(self, session_id: str) -> bool:
        """Validate if a session is active (demo implementation)"""
        # In a real app, this would check the database
        # For demo, we'll accept any non-empty session ID
        return bool(session_id and len(session_id) > 0)
    
    def login_by_email(self, email: str, name: str = None, db: Session = None) -> LoginResponse:
        """Login user by email address directly (for development/testing purposes).
        
        This method:
        1. Finds or creates a user by email
        2. Creates a new session
        3. Returns session info
        
        Note: This bypasses Google OAuth verification. Use only for trusted environments.
        """
        if not email:
            return LoginResponse(
                success=False,
                session_id="",
                user=None,
                message="Email is required."
            )
        
        if not db:
            return LoginResponse(
                success=False,
                session_id="",
                user=None,
                message="Database session is required."
            )
        
        try:
            email = email.strip().lower()
            
            # Validate email domain - only allow @forsysinc.com emails
            allowed_domain = "@forsysinc.com"
            if not email.endswith(allowed_domain):
                return LoginResponse(
                    success=False,
                    session_id="",
                    user=None,
                    message=f"Access restricted to {allowed_domain} email addresses only."
                )
            
            # Try to find user by email first
            user = db.query(User).filter(User.email == email).first()
            
            if not user:
                # User doesn't exist, create new user
                # Generate a unique google_id for email-based users (format: email_xxx)
                google_id = f"email_{uuid.uuid4().hex[:16]}"
                
                # Extract name from email if not provided (e.g., john.doe@example.com -> John Doe)
                if not name:
                    email_parts = email.split('@')[0]
                    name = email_parts.replace('.', ' ').replace('_', ' ').title()
                
                user = User(
                    email=email,
                    name=name,
                    google_id=google_id
                )
                db.add(user)
                db.commit()
                db.refresh(user)
                print(f"✅ [AUTH-SERVICE] Created new user by email: {email}")
            else:
                print(f"✅ [AUTH-SERVICE] Found existing user by email: {email}")
                # Update name if provided and different
                if name and user.name != name:
                    user.name = name
                    db.commit()
                    db.refresh(user)
            
            # Create a new session for this user
            session_id = f"session_{uuid.uuid4()}"
            session = UserSession(
                id=session_id,
                user_id=user.id,
                is_active=True,
                expires_at=datetime.now() + timedelta(hours=24)
            )
            db.add(session)
            db.commit()
            
            print(f"✅ [AUTH-SERVICE] Created session for user: {email} (session_id: {session_id})")
            
            return LoginResponse(
                success=True,
                session_id=session_id,
                user={
                    "id": user.id,
                    "email": user.email,
                    "name": user.name,
                    "google_id": user.google_id
                },
                message="Login successful by email"
            )
        except Exception as exc:
            db.rollback()
            print(f"❌ [AUTH-SERVICE] Email login error: {str(exc)}")
            return LoginResponse(
                success=False,
                session_id="",
                user=None,
                message=f"Email login failed: {str(exc)}"
            )

auth_service = AuthService() 