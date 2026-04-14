"""
QA Requirement Analysis Service
---------------------------------
• Uses Gemini 2.5 Flash
• Acts as Senior Business Analyst & Requirements Architect (15+ yrs)
• Analyzes requirement documents
• Produces structured, actionable outputs

Supported document formats: .txt, .pdf, .docx
  – PDF  → native Gemini file upload (text + images preserved)
  – DOCX → text extraction + embedded image inline parts
  – TXT  → plain text embedded in prompt

Env var: GEMINI_API_KEY
"""

import io
import logging
import os
import tempfile
import time
from typing import List, Optional, Tuple

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from fastapi import HTTPException
from services.gemini_token_service import gemini_token_service

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-2.5-flash"

# MIME types supported as inline image data by Gemini
_SUPPORTED_IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}


# --------------------------------------------------
# Document Text Extraction (text-only fallback)
# --------------------------------------------------
def extract_document_text(filename: str, content: bytes) -> str:
    """
    Extract plain text from uploaded requirement documents.
    Supported: .txt, .pdf, .docx (and anything UTF-8 decodable as fallback).
    Used as a lightweight text-only fallback when native upload is not needed.
    """
    ext = filename.lower().rsplit(".", 1)[-1]
    logger.debug("extract_document_text: filename=%s ext=%s size=%d bytes", filename, ext, len(content))

    if ext == "txt":
        text = content.decode("utf-8", errors="ignore")
        logger.info("Extracted TXT: %d chars from %s", len(text), filename)
        return text

    if ext == "pdf":
        try:
            import PyPDF2
            reader = PyPDF2.PdfReader(io.BytesIO(content))
            pages = [page.extract_text() or "" for page in reader.pages]
            text = "\n".join(pages).strip()
            logger.info("Extracted PDF text: %d pages, %d chars from %s", len(pages), len(text), filename)
            return text
        except ImportError:
            raise RuntimeError("PyPDF2 is required for PDF parsing: pip install PyPDF2")

    if ext == "docx":
        try:
            import docx
            doc = docx.Document(io.BytesIO(content))
            text = "\n".join(p.text for p in doc.paragraphs).strip()
            logger.info("Extracted DOCX text: %d chars from %s", len(text), filename)
            return text
        except ImportError:
            raise RuntimeError("python-docx is required for DOCX parsing: pip install python-docx")

    # Fallback — try raw UTF-8 decode for any other text-like format
    text = content.decode("utf-8", errors="ignore")
    logger.warning("Unknown extension '%s' for %s — decoded as UTF-8 (%d chars)", ext, filename, len(text))
    return text


# --------------------------------------------------
# Native Gemini upload helpers
# --------------------------------------------------
def _upload_pdf_to_gemini(content: bytes):
    """
    Write PDF bytes to a temp file, upload to Gemini Files API, wait until ACTIVE.
    The caller is responsible for calling genai.delete_file() in a finally block.
    """
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(content)
            tmp_path = f.name
        logger.debug("PDF written to temp file: %s (%d bytes)", tmp_path, len(content))

        logger.info("Uploading PDF to Gemini Files API (%d bytes)…", len(content))
        file_ref = genai.upload_file(tmp_path, mime_type="application/pdf")
        logger.info("Upload complete — Gemini file name: %s, state: %s", file_ref.name, file_ref.state.name)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
            logger.debug("Temp file deleted: %s", tmp_path)

    # Poll until ACTIVE (timeout 60 s)
    max_wait, waited = 60, 0
    while file_ref.state.name == "PROCESSING" and waited < max_wait:
        logger.debug("Gemini file %s still PROCESSING — waited %ds", file_ref.name, waited)
        time.sleep(2)
        waited += 2
        file_ref = genai.get_file(file_ref.name)

    if file_ref.state.name != "ACTIVE":
        logger.error(
            "Gemini file %s did not become ACTIVE after %ds (state=%s)",
            file_ref.name, waited, file_ref.state.name,
        )
        try:
            genai.delete_file(file_ref.name)
        except Exception:
            pass
        raise RuntimeError(
            f"Gemini file upload did not become ACTIVE (state={file_ref.state.name})"
        )

    logger.info("Gemini file %s is ACTIVE after %ds", file_ref.name, waited)
    return file_ref


def _upload_csv_to_gemini(content: bytes):
    """
    Write CSV bytes to a temp file, upload to Gemini Files API as text/csv, wait until ACTIVE.
    The caller is responsible for calling genai.delete_file() in a finally block.
    """
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(content)
            tmp_path = f.name
        logger.debug("CSV written to temp file: %s (%d bytes)", tmp_path, len(content))

        logger.info("Uploading CSV to Gemini Files API (%d bytes)…", len(content))
        file_ref = genai.upload_file(tmp_path, mime_type="text/csv")
        logger.info("Upload complete — Gemini file name: %s, state: %s", file_ref.name, file_ref.state.name)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.unlink(tmp_path)
            logger.debug("Temp file deleted: %s", tmp_path)

    # Poll until ACTIVE (timeout 60 s)
    max_wait, waited = 60, 0
    while file_ref.state.name == "PROCESSING" and waited < max_wait:
        logger.debug("Gemini CSV file %s still PROCESSING — waited %ds", file_ref.name, waited)
        time.sleep(2)
        waited += 2
        file_ref = genai.get_file(file_ref.name)

    if file_ref.state.name != "ACTIVE":
        logger.error(
            "Gemini CSV file %s did not become ACTIVE after %ds (state=%s)",
            file_ref.name, waited, file_ref.state.name,
        )
        try:
            genai.delete_file(file_ref.name)
        except Exception:
            pass
        raise RuntimeError(
            f"Gemini CSV file upload did not become ACTIVE (state={file_ref.state.name})"
        )

    logger.info("Gemini CSV file %s is ACTIVE after %ds", file_ref.name, waited)
    return file_ref


def _extract_docx_parts(content: bytes) -> Tuple[str, List[Tuple[str, bytes]]]:
    """
    Extract (text, [(mime_type, image_bytes)]) from a DOCX file.
    Only image types supported as Gemini inline data are included.
    """
    try:
        import docx
    except ImportError:
        raise RuntimeError("python-docx is required for DOCX parsing: pip install python-docx")

    doc = docx.Document(io.BytesIO(content))
    text = "\n".join(p.text for p in doc.paragraphs).strip()
    logger.info("DOCX text extracted: %d chars", len(text))

    images: List[Tuple[str, bytes]] = []
    for rel in doc.part.rels.values():
        if "image" in rel.reltype:
            part = rel.target_part
            if part.content_type in _SUPPORTED_IMAGE_TYPES:
                images.append((part.content_type, part.blob))

    logger.info("DOCX embedded images found: %d (supported types only)", len(images))
    return text, images


# --------------------------------------------------
# Lazy model init — does NOT raise at import time
# --------------------------------------------------
async def _get_model(user: Optional[str] = None):
    Redis_Key_Meta, Redis_Key = await gemini_token_service._get_available_api_key()
    GEMINI_KEY = os.getenv("GEMINI_API_KEY", "").strip()
    if Redis_Key:
        try:
            genai.configure(api_key=Redis_Key)
            logger.info(f"✅ Gemini configured with Redis Key: {Redis_Key}")
        except Exception as e:
            logger.error(f"❌ Failed to configure Gemini: {e}")
    elif GEMINI_KEY:
        Redis_Key_Meta = None
        try:
            genai.configure(api_key=GEMINI_KEY)
            logger.info(f"✅ Gemini configured with model with GEMINI_KEY: {GEMINI_KEY[:4]}***")
        except Exception as e:
            logger.error(f"❌ Failed to configure Gemini: {e}")
            logger.warning("⚠️ GEMINI_API_KEY not set — LLM calls will use hybrid fallback")
    else:
        raise RuntimeError("GEMINI_API_KEY environment variable not set")
    return genai.GenerativeModel(MODEL_NAME), Redis_Key_Meta


# --------------------------------------------------
# Prompt Builders
# --------------------------------------------------
_ANALYSIS_STEPS = """
=====================
STEP 1: Document Summary
=====================
• Provide a one-paragraph executive summary describing:
  – Document purpose
  – Scope
  – Business objectives
• Identify:
  – Target users
  – Business domain
  – High-level solution overview

=====================
STEP 2: Requirements Extraction
=====================
Extract and structure requirements under the following headings:

1. Functional Requirements
   – Clearly numbered (FR-01, FR-02…)
   – Written in "The system shall..." format

2. Non-Functional Requirements
   – Performance
   – Security
   – Usability & Accessibility
   – Scalability
   – Reliability & Availability

3. Business Rules
   – Validations
   – Workflows
   – Calculations
   – Approval rules

4. Data Requirements
   – Core entities
   – Key attributes
   – Relationships
   – Data retention considerations

5. Integration Requirements
   – External systems
   – APIs
   – Data exchange direction
   – Frequency and failure handling

6. UI / UX Requirements
   – Key screens
   – User flows
   – Role-based access
   – Accessibility (WCAG considerations)

=====================
STEP 3: Gaps & Risks
=====================
• Missing or ambiguous requirements
• Conflicting requirements
• Technical or architectural risks
• Clarification questions (MAXIMUM 5, high-impact only)

=====================
STEP 4: Testability Analysis
=====================
For EACH functional requirement:
• Testable: Yes / No / Partially
• Provide brief justification

Rules:
• Be concise but enterprise-grade
• Avoid assumptions unless explicitly stated
• Use structured bullet points and tables where appropriate
• Do NOT invent requirements not implied by the document
"""

_ANALYSIS_ROLE = """Role:
You are a Senior Business Analyst and Requirements Architect with 15+ years of experience
in enterprise and product-based software systems.

Task:
Analyze the attached document to identify complete, clear, and actionable software
requirements suitable for development, QA, and stakeholder validation."""


def _build_query_section(query: Optional[str]) -> str:
    if not query or not query.strip():
        return ""
    return f"""
=====================
USER FOCUS / QUERY
=====================
The user has highlighted the following specific area or question.
Prioritize this lens throughout every step of your analysis:

  {query.strip()}

"""


def build_analysis_prompt(document_text: str, query: Optional[str] = None) -> str:
    """Prompt with document text embedded — used for TXT files."""
    return f"""
{_ANALYSIS_ROLE}
{_build_query_section(query)}
{_ANALYSIS_STEPS}
=====================
DOCUMENT TO ANALYZE
=====================
{document_text}
"""


def build_analysis_prompt_native(query: Optional[str] = None) -> str:
    """
    Prompt WITHOUT embedded document text — used when the document is supplied
    as a native Gemini file part (PDF) or inline image parts (DOCX).
    The model reads the document directly from the multipart content list.
    """
    return f"""
{_ANALYSIS_ROLE}
{_build_query_section(query)}
{_ANALYSIS_STEPS}
Analyze the document provided above (as file/image content) following all steps.
"""


def build_followup_prompt(previous_output: str) -> str:
    return f"""
From the previous requirement analysis, perform a deeper second-pass review.

Tasks:
• Identify any additional hidden gaps or risks
• Refine clarification questions (still max 5)
• Improve testability justifications where weak
• Highlight requirements that are NOT implementation-ready

Do NOT repeat previously listed requirements unless refining them.

Previous Analysis:
{previous_output}
"""


# --------------------------------------------------
# Service Functions
# --------------------------------------------------
async def analyze_requirements(document_text: str, user_prompt: Optional[str] = None,  user: Optional[str] = None) -> dict:
    """Text-only path — kept for backward compatibility."""
    logger.info(
        "analyze_requirements (text path): %d chars, focus_query=%s",
        len(document_text), bool(user_prompt),
    )
    model, Redis_Key_Meta = await _get_model(user=user)
    prompt = build_analysis_prompt(document_text, query=user_prompt)
    try:
        response = model.generate_content(prompt)
    except google_exceptions.ResourceExhausted:
        if Redis_Key_Meta:
            await gemini_token_service._handle_429(Redis_Key_Meta)
        raise HTTPException(status_code=429, detail="Too many requests. Please try again in a few minutes.")
    except google_exceptions.ServiceUnavailable:
        if Redis_Key_Meta:
            await gemini_token_service._handle_503(Redis_Key_Meta)
        raise HTTPException(status_code=503, detail="Service unavailable. Please try again in a few minutes.")
    logger.info("Requirement analysis complete: %d chars in response", len(response.text))
    return {"model": MODEL_NAME, "analysis": response.text}


async def analyze_requirements_from_bytes(
    filename: str,
    content: bytes,
    user_prompt: Optional[str] = None,
    user: Optional[str] = None
) -> dict:
    """
    Dispatch by file extension:
      • PDF  → native Gemini file upload (text + images preserved)
      • DOCX → text + inline embedded images
      • TXT / other → plain text embedded in prompt
    """
    model, Redis_Key_Meta = await _get_model(user=user)
    ext = filename.lower().rsplit(".", 1)[-1]
    logger.info(
        "analyze_requirements_from_bytes: filename=%s ext=%s size=%d bytes focus_query=%s",
        filename, ext, len(content), bool(user_prompt),
    )

    if ext == "pdf":
        logger.info("PDF path → native Gemini file upload")
        file_ref = _upload_pdf_to_gemini(content)
        try:
            prompt = build_analysis_prompt_native(query=user_prompt)
            try:
                response = model.generate_content([file_ref, prompt])
            except google_exceptions.ResourceExhausted:
                if Redis_Key_Meta:
                    await gemini_token_service._handle_429(Redis_Key_Meta)
                raise
            except google_exceptions.ServiceUnavailable:
                if Redis_Key_Meta:
                    await gemini_token_service._handle_503(Redis_Key_Meta)
                raise
            logger.info("PDF analysis complete: %d chars in response", len(response.text))
        finally:
            try:
                genai.delete_file(file_ref.name)
                logger.debug("Deleted Gemini file: %s", file_ref.name)
            except Exception as exc:
                logger.warning("Could not delete Gemini file %s: %s", file_ref.name, exc)

    elif ext == "docx":
        logger.info("DOCX path → text + inline image parts")
        text, images = _extract_docx_parts(content)
        prompt = build_analysis_prompt_native(query=user_prompt)
        parts: list = [prompt, text]
        parts += [{"mime_type": mime, "data": img_bytes} for mime, img_bytes in images]
        logger.info("Sending %d parts to Gemini (text + %d images)", len(parts), len(images))
        try:
            response = model.generate_content(parts)
        except google_exceptions.ResourceExhausted:
            if Redis_Key_Meta:
                await gemini_token_service._handle_429(Redis_Key_Meta)
            raise HTTPException(status_code=429, detail="Too many requests. Please try again in a few minutes.")
        except google_exceptions.ServiceUnavailable:
            if Redis_Key_Meta:
                await gemini_token_service._handle_503(Redis_Key_Meta)
            raise HTTPException(status_code=503, detail="Service unavailable. Please try again in a few minutes.")
        logger.info("DOCX analysis complete: %d chars in response", len(response.text))

    elif ext == "csv":
        logger.info("CSV path → native Gemini Files API upload (text/csv)")
        file_ref = _upload_csv_to_gemini(content)
        try:
            prompt = build_analysis_prompt_native(query=user_prompt)
            try:
                response = model.generate_content([file_ref, prompt])
            except google_exceptions.ResourceExhausted:
                if Redis_Key_Meta:
                    await gemini_token_service._handle_429(Redis_Key_Meta)
                raise
            except google_exceptions.ServiceUnavailable:
                if Redis_Key_Meta:
                    await gemini_token_service._handle_503(Redis_Key_Meta)
                raise
            logger.info("CSV analysis complete: %d chars in response", len(response.text))
        finally:
            try:
                genai.delete_file(file_ref.name)
                logger.debug("Deleted Gemini CSV file: %s", file_ref.name)
            except Exception as exc:
                logger.warning("Could not delete Gemini CSV file %s: %s", file_ref.name, exc)

    else:
        logger.info("Fallback text path for extension '%s'", ext)
        text = content.decode("utf-8", errors="ignore")
        return await analyze_requirements(text, user_prompt=user_prompt,user=user)

    return {"model": MODEL_NAME, "analysis": response.text}


def followup_requirements(previous_analysis: str) -> dict:
    logger.info("followup_requirements: previous analysis %d chars", len(previous_analysis))
    model = _get_model()
    prompt = build_followup_prompt(previous_analysis)
    response = model.generate_content(prompt)
    logger.info("Follow-up analysis complete: %d chars in response", len(response.text))
    return {"model": MODEL_NAME, "refined_analysis": response.text}
