"""
QA Test Case Generator Service
---------------------------------
• Uses Gemini 2.5 Flash
• Acts as Senior QA Engineer & Test Architect
• Generates test cases in Given / When / Then (JSON output)
• Exports to Excel
• Supports follow-up generation

Supported document formats: .txt, .pdf, .docx
  – PDF  → native Gemini file upload (text + images preserved)
  – DOCX → text extraction + embedded image inline parts
  – TXT  → plain text embedded in prompt

Env var: GEMINI_API_KEY
"""

import gc
import json
import logging
import os
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from fastapi import HTTPException
import pandas as pd

logger = logging.getLogger(__name__)

from services.qa_requirement_service import (  # noqa: F401 — re-exported for routes
    _extract_docx_parts,
    _upload_csv_to_gemini,
    _upload_pdf_to_gemini,
    extract_document_text,
)
from services.gemini_token_service import gemini_token_service

MODEL_NAME = "gemini-2.5-flash"

# Absolute path — works regardless of working directory
EXPORT_DIR = Path(__file__).parent.parent / "exports"
EXPORT_DIR.mkdir(exist_ok=True)


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
_TC_ROLE = """Role: Act as a Senior QA Engineer and Test Architect on an Agile product team.

Task:
Generate comprehensive test cases from the provided requirements document."""

_TC_INSTRUCTIONS = """
Tasks:
• Clarify missing or ambiguous requirements (list assumptions)
• Generate comprehensive test cases covering:
  – Happy path
  – Negative
  – Edge & boundary
  – Non-functional
  – Cross-browser / device
  – Integration & data flow
  – Regression

Rules:
• Use Given / When / Then format for steps
• Think from real-world production usage
• Avoid duplicates
• Mark automation candidates realistically

CRITICAL OUTPUT RULES:
• Output MUST be valid JSON ONLY
• DO NOT include markdown, tables, or prose
• DO NOT include HTML
• Follow the exact JSON schema below

JSON Schema:
{
  "summary": "Short executive summary of coverage and assumptions",
  "test_cases": [
    {
      "id": "string",
      "test_type": "Happy Path | Negative | Edge | Non-Functional | Regression | Integration | Cross-Browser",
      "scenario": "string",
      "preconditions": "string",
      "steps": ["step 1", "step 2", "step 3"],
      "test_data": "string",
      "expected_result": "string",
      "priority": "High | Medium | Low",
      "automation_candidate": "Yes | No | Partial"
    }
  ]
}"""


def _build_focus_section(focus_query: Optional[str]) -> str:
    if not focus_query or not focus_query.strip():
        return ""
    return f"""
=====================
USER FOCUS / QUERY
=====================
The user has specified the following focus area or user story.
Prioritize generating test cases relevant to this scope:

  {focus_query.strip()}

"""


def build_main_prompt(document_content: str, focus_query: Optional[str] = None) -> str:
    """
    Prompt with document text embedded — used for TXT files.

    document_content is mandatory — the primary requirements source.
    focus_query is optional — injected as a top-level directive.
    """
    content_block = f"""
Requirements Document:
{document_content.strip()}
"""
    return f"""
{_TC_ROLE}
{_build_focus_section(focus_query)}
{_TC_INSTRUCTIONS}
{content_block}"""


def build_main_prompt_native(focus_query: Optional[str] = None) -> str:
    """
    Prompt WITHOUT embedded document — used when the document is supplied
    as a native Gemini file part (PDF) or inline image parts (DOCX).
    """
    return f"""
{_TC_ROLE}
{_build_focus_section(focus_query)}
{_TC_INSTRUCTIONS}

Generate test cases from the requirements document provided above (as file/image content).
"""


def build_followup_prompt(previous_output: str) -> str:
    return f"""
From the previous answer, generate ONLY missing:
• Edge cases
• Non-functional scenarios
• Regression scenarios

Rules:
• Do NOT repeat existing scenarios
• Use Given / When / Then format
• Continue ID numbering logically
• Use the same table structure

Output Columns:
ID | Test Type | Scenario | Preconditions | Steps | Test Data | Expected Result | Priority | Automation Candidate

Previous Test Cases:
{previous_output}
"""


# --------------------------------------------------
# JSON Utilities
# --------------------------------------------------
def safe_parse_json(text: str) -> dict:
    if not text:
        raise ValueError("Empty model response")

    cleaned = re.sub(r"^```json|```$", "", text.strip(), flags=re.MULTILINE)
    match = re.search(r"\{.*\}", cleaned, re.DOTALL)

    if not match:
        logger.error("No JSON object found in model response (first 200 chars): %s", text[:200])
        raise ValueError("No JSON found in model response")

    return json.loads(match.group())


# --------------------------------------------------
# Shared Excel Export Helper
# --------------------------------------------------
def _process_test_case_response(response_text: str) -> dict:
    """Parse model JSON output, write Excel, return API response dict."""
    logger.debug("Parsing model response (%d chars)", len(response_text))
    parsed = safe_parse_json(response_text)
    summary_text = parsed["summary"]
    test_cases = parsed["test_cases"]
    logger.info("Parsed %d test cases from model response", len(test_cases))

    df = pd.DataFrame([
        {
            "ID": tc["id"],
            "Test Type": tc["test_type"],
            "Scenario": tc["scenario"],
            "Preconditions": tc["preconditions"],
            "Steps": "\n".join(tc["steps"]),
            "Test Data": tc["test_data"],
            "Expected Result": tc["expected_result"],
            "Priority": tc["priority"],
            "Automation Candidate": tc["automation_candidate"],
        }
        for tc in test_cases
    ])

    total_rows = len(df)

    summary_df = pd.DataFrame({
        "Metric": ["Total Test Cases", "Generated At"],
        "Value": [total_rows, datetime.now().strftime("%Y-%m-%d %H:%M:%S")],
    })

    file_id = str(uuid.uuid4())
    excel_path = EXPORT_DIR / f"qa_test_cases_{file_id}.xlsx"

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="Test_Cases", index=False)
        summary_df.to_excel(writer, sheet_name="Summary", index=False)

    logger.info("Excel exported: %s (%d rows)", excel_path.name, total_rows)
    del df
    gc.collect()

    return {
        "summary": summary_text.strip().replace("*", ""),
        "download_url": f"/api/qa/test-cases/download/{excel_path.name}",
        "total_test_cases": total_rows,
    }


# --------------------------------------------------
# Service Functions
# --------------------------------------------------
async def generate_test_cases(document_content: str, focus_query: Optional[str] = None,user: Optional[str] = None) -> dict:
    """Text-only path — kept for backward compatibility."""
    logger.info(
        "generate_test_cases (text path): %d chars, focus_query=%s",
        len(document_content), bool(focus_query),
    )
    model, Redis_Key_Meta = await _get_model(user=user)
    prompt = build_main_prompt(document_content, focus_query=focus_query)
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
    logger.info("Model response received: %d chars", len(response.text))
    return _process_test_case_response(response.text)


async def generate_test_cases_from_bytes(
    filename: str,
    content: bytes,
    focus_query: Optional[str] = None,
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
        "generate_test_cases_from_bytes: filename=%s ext=%s size=%d bytes focus_query=%s",
        filename, ext, len(content), bool(focus_query),
    )

    if ext == "pdf":
        logger.info("PDF path → native Gemini file upload")
        file_ref = _upload_pdf_to_gemini(content)
        try:
            prompt = build_main_prompt_native(focus_query=focus_query)
            try:
                response = model.generate_content([file_ref, prompt])
            except google_exceptions.ResourceExhausted:
                if Redis_Key_Meta:
                    await gemini_token_service._handle_429(Redis_Key_Meta)
                raise HTTPException(status_code=429, detail="Too many requests. Please try again in a few minutes.")
            except google_exceptions.ServiceUnavailable:
                if Redis_Key_Meta:
                    await gemini_token_service._handle_503(Redis_Key_Meta)
                raise HTTPException(status_code=503, detail="Service unavailable. Please try again in a few minutes.")
            logger.info("PDF test case generation complete: %d chars in response", len(response.text))
        finally:
            try:
                genai.delete_file(file_ref.name)
                logger.debug("Deleted Gemini file: %s", file_ref.name)
            except Exception as exc:
                logger.warning("Could not delete Gemini file %s: %s", file_ref.name, exc)

    elif ext == "docx":
        logger.info("DOCX path → text + inline image parts")
        text, images = _extract_docx_parts(content)
        prompt = build_main_prompt_native(focus_query=focus_query)
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
        logger.info("DOCX test case generation complete: %d chars in response", len(response.text))

    elif ext == "csv":
        logger.info("CSV path → native Gemini Files API upload (text/csv)")
        file_ref = _upload_csv_to_gemini(content)
        try:
            prompt = build_main_prompt_native(focus_query=focus_query)
            try:
                response = model.generate_content([file_ref, prompt])
            except google_exceptions.ResourceExhausted:
                if Redis_Key_Meta:
                    await gemini_token_service._handle_429(Redis_Key_Meta)
                raise HTTPException(status_code=429, detail="Too many requests. Please try again in a few minutes.")
            except google_exceptions.ServiceUnavailable:
                if Redis_Key_Meta:
                    await gemini_token_service._handle_503(Redis_Key_Meta)
                raise HTTPException(status_code=503, detail="Service unavailable. Please try again in a few minutes.")
            logger.info("CSV test case generation complete: %d chars in response", len(response.text))
        finally:
            try:
                genai.delete_file(file_ref.name)
                logger.debug("Deleted Gemini CSV file: %s", file_ref.name)
            except Exception as exc:
                logger.warning("Could not delete Gemini CSV file %s: %s", file_ref.name, exc)

    else:
        logger.info("Fallback text path for extension '%s'", ext)
        text = content.decode("utf-8", errors="ignore")
        return await generate_test_cases(text, focus_query=focus_query, user=user)

    return _process_test_case_response(response.text)


def generate_followup_test_cases(previous_test_cases: str) -> dict:
    logger.info("generate_followup_test_cases: previous output %d chars", len(previous_test_cases))
    model = _get_model()
    prompt = build_followup_prompt(previous_test_cases)
    response = model.generate_content(prompt)
    logger.info("Follow-up test case generation complete: %d chars in response", len(response.text))
    return {"model": MODEL_NAME, "additional_test_cases": response.text}
