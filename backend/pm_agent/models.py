import os
import uuid
from dotenv import load_dotenv

from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    Text,
    Boolean,
    JSON,
    ForeignKey,
    UniqueConstraint,
    LargeBinary,
    create_engine,
)
from sqlalchemy.sql import func
from sqlalchemy.orm import declarative_base, sessionmaker


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL is not set")

engine_kwargs = {
    "pool_pre_ping": True,
    "pool_recycle": 300,
}

if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
else:
    engine_kwargs["connect_args"] = {"connect_timeout": 10}

engine = create_engine(DATABASE_URL, **engine_kwargs)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """Dependency to get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True)
    name = Column(String)
    google_id = Column(String, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Session(Base):
    __tablename__ = "sessions"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(Integer, index=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True))

class Document(Base):
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, index=True)
    feature = Column(String, nullable=False)
    prompt = Column(Text, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())

class Workspace(Base):
    __tablename__ = "workspaces"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    description = Column(Text)
    is_default = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

class Feedback(Base):
    __tablename__ = "feedback"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Basic Information
    name = Column(String)
    email = Column(String)
    
    # Sprint Planning Feedback
    clarity_of_sprint_goals = Column(String)  # Rating: 1-5
    workload_distribution = Column(String)   # Rating: 1-5
    plan_alignment_sow = Column(String)      # Yes/No/Partial
    suggestions_sprint_planning = Column(Text)
    
    # Risk Assessment Feedback
    risks_clear = Column(String)            # Yes/No
    mitigation_practical = Column(String)   # Yes/No
    suggestions_risk_assessment = Column(Text)
    
    # Overall Feedback
    overall_sprint_planning_rating = Column(String)  # Rating: 1-5
    overall_risk_assessment_rating = Column(String)  # Rating: 1-5
    
    # Additional Comments
    additional_comments = Column(Text)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(String, index=True)  # Store user email

class UploadedFile(Base):
    __tablename__ = "uploaded_files"
    
    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # pdf, docx, txt, etc.
    file_path = Column(String, nullable=False)  # Path where file is stored
    uploaded_by = Column(String, index=True)  # User email or username
    upload_time = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String, default="Uploaded")  # Uploaded, Processing, Processed, Error
    extracted_text = Column(Text)  # Extracted text content from the file
    indexing_status = Column(String, default="pending_index")  # pending_index, indexed, error
    file_hash = Column(String, index=True, nullable=True) 
    expires_at = Column(DateTime(timezone=True), nullable=True)
    

class MandatoryFile(Base):
    __tablename__ = "mandatory_files"
    
    id = Column(Integer, primary_key=True, index=True)
    file_name = Column(String, nullable=False)
    file_type = Column(String, nullable=False)  # pdf, docx, txt, xlsx, etc.
    file_path = Column(String, nullable=True)  # Legacy: Path where file was stored on disk (deprecated, kept for backward compatibility)
    file_content = Column(LargeBinary, nullable=True)  # File content stored in database
    file_size = Column(Integer)  # File size in bytes
    uploaded_by = Column(String, index=True)  # User email or username
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    description = Column(String)  # Optional description
    is_active = Column(Boolean, default=True)  # For soft delete
    extracted_text = Column(Text)  # Extracted text content from the file (for search/indexing)

class ProjectKnowledgeBaseFile(Base):
    __tablename__ = "project_knowledge_base_files"
    
    id = Column(Integer, primary_key=True, index=True)
    user_email = Column(String, nullable=False, index=True)  # User email who selected the file
    mandatory_file_id = Column(Integer, ForeignKey("mandatory_files.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Ensure unique combination of user and file
    __table_args__ = (
        UniqueConstraint('user_email', 'mandatory_file_id', name='uq_user_file'),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    chat_id = Column(String, index=True, nullable=False)
    user_email = Column(String, index=True)
    role = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Conversation(Base):
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(String, unique=True, index=True, nullable=False)
    chat_id = Column(String, index=True, nullable=False)
    user_email = Column(String, index=True)
    project_id = Column(String, index=True, nullable=True)  # Foreign key to projects.id
    conversation_json = Column(JSON, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Project(Base):
    __tablename__ = "projects"
    
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    user_email = Column(String, index=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class UserUploadedFile(Base):
    __tablename__ = "user_uploaded_files"

    id = Column(Integer, primary_key=True, index=True)

    user_email = Column(String, index=True, nullable=False)

    # Either uploaded_files.id OR mandatory_files.id
    file_id = Column(Integer, nullable=False)

    file_source = Column(String, nullable=False)
    # values:
    # 'chat_upload'  -> uploaded_files
    # 'gdrive_upload' -> mandatory_files

    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=False)

    is_active = Column(Boolean, default=True)


class GovernanceProject(Base):
    __tablename__ = "governance_projects"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_email = Column(String, index=True, nullable=False)
    project_name = Column(String, nullable=False)
    project_type = Column(String, nullable=False)  # DI or DM
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class GovernanceProjectPhase(Base):
    __tablename__ = "governance_project_phases"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String, ForeignKey("governance_projects.id", ondelete="CASCADE"), nullable=False, index=True)
    phase = Column(String, nullable=True)
    subphase = Column(String, nullable=True)
    gate_check = Column(String, nullable=True)
    status = Column(String, nullable=True)
    comments = Column(Text, nullable=True)
    planned_date = Column(String, nullable=True)
    actual_date = Column(String, nullable=True)
    document_link = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


