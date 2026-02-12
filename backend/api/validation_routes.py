"""
Validation Routes
API endpoints for data validation operations
"""
import os
import io
import gc
import json
import logging
import tempfile
from datetime import datetime
import pandas as pd
from fastapi import APIRouter, Form, HTTPException
from fastapi.responses import JSONResponse
from googleapiclient.http import MediaFileUpload

from services.auth_service import get_drive_service
from services.validation_service import (
    generate_validation_rules,
    apply_validation_rules,
    summarize_errors
)
from utils.file_utils import detect_and_cast_numeric
from utils.duplicate_detection import detect_duplicates
from utils.memory_utils import USER_STORE
from config.settings import CHUNK_SIZE
from utils.security import normalize_email, validate_short_text

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Validation"], prefix="/api")


@router.post("/get_validation_rules")
async def api_get_validation_rules(
    email: str = Form(...),
    filename: str = Form(...),
    local_path: str = Form(...)
):
    """Generate validation rules using Gemini"""
    email = normalize_email(email)
    filename = validate_short_text(filename, "filename", 255)
    local_path = validate_short_text(local_path, "local_path", 4096)

    # Get DataFrame from memory using email
    if email not in USER_STORE or "file_path" not in USER_STORE[email]:
        raise HTTPException(status_code=404, detail="No dataset loaded. Please upload a file first.")

    file_path = USER_STORE[email]["file_path"]
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, dtype=str)
        else:
            df = pd.read_excel(file_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file from disk: {e}")

    df = detect_and_cast_numeric(df)
    headers = list(df.columns)
    sample_size = min(len(df), 10)
    sample_rows = df.sample(n=sample_size).replace({float("nan"): None}).to_dict(orient="records")

    logger.info(f"[Gemini Input] Columns={headers}")
    rules = generate_validation_rules(headers, sample_rows)
    logger.info(f"[Gemini Output] Rules generated")

    # Ensure consistent return format
    if isinstance(rules, dict):
        flattened = []
        for col, lst in rules.items():
            for rule in lst:
                flattened.append({
                    "column": col,
                    "rule": rule.get("rule_id") or rule.get("rule"),
                    "description": rule.get("description", "")
                })
        rules = flattened

    return {"rules": rules, "headers": headers}


@router.post("/regenerate_rules")
async def api_regenerate_rules(
    email: str = Form(...),
    filename: str = Form(...),
    local_path: str = Form(...),
    edits_json: str = Form(...),
    current_headers_json: str = Form(None)
):
    """Refine validation rules based on user edits"""
    email = normalize_email(email)
    filename = validate_short_text(filename, "filename", 255)
    local_path = validate_short_text(local_path, "local_path", 4096)
    edits_json = validate_short_text(edits_json, "edits_json", 200000) or ""

    # Get DataFrame from memory
    if email not in USER_STORE or "file_path" not in USER_STORE[email]:
        raise HTTPException(status_code=404, detail="No dataset loaded in session.")

    file_path = USER_STORE[email]["file_path"]
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, dtype=str)
        else:
            df = pd.read_excel(file_path)
    except Exception:
        raise HTTPException(status_code=400, detail="Could not read source file")

    try:
        user_edits = json.loads(edits_json)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")
    
    original_headers = list(df.columns)
    active_headers = original_headers

    if current_headers_json:
        try:
            # Parse the headers received from the frontend (the ones NOT deleted)
            client_headers = json.loads(current_headers_json)
            
            # Filter the original file columns based on what the client sent
            active_headers = [h for h in original_headers if h in client_headers]
            logger.info(f"[RegenerateRules] Original Headers Count: {len(original_headers)}, Active Headers Count: {len(active_headers)}")
            logger.info(f"[RegenerateRules] Active Headers: {active_headers}")
        except Exception as e:
            # If parsing fails, fall back to original headers
            logger.warning(f"[RegenerateRules] Error loading client headers, using all: {e}")
            active_headers = original_headers
    
    df_filtered = df[active_headers]
    sample_rows = df_filtered.head(5).replace({float("nan"): None}).to_dict(orient="records")

    logger.info("[RegenerateRules] Sending user edits to Gemini...")
    new_rules = generate_validation_rules(active_headers, sample_rows, user_guidance=user_edits)

    if isinstance(new_rules, dict):
        flattened = []
        for col, lst in new_rules.items():
            for rule in lst:
                if col in active_headers: 
                    flattened.append({
                        "column": col,
                        "rule": rule.get("rule_id") or rule.get("rule"),
                        "description": rule.get("description", "")
                    })
        new_rules = flattened

    return {"rules": new_rules, "headers": active_headers}


@router.post("/run_validation")
async def api_run_validation(
    email: str = Form(...),
    filename: str = Form(...),
    local_path: str = Form(...),
    rules_json: str = Form(...),
):
    """
    Run validation on dataset with chunking for large files
    Optimized for memory efficiency
    """
    email = normalize_email(email)
    filename = validate_short_text(filename, "filename", 255)
    local_path = validate_short_text(local_path, "local_path", 4096)
    rules_json = validate_short_text(rules_json, "rules_json", 2000000) or ""

    # Get file path from memory
    if email not in USER_STORE or "file_path" not in USER_STORE[email]:
        raise HTTPException(status_code=400, detail="No dataset in memory.")

    file_path = USER_STORE[email]["file_path"]
    
    # Load dataframe from disk
    try:
        if file_path.endswith('.csv'):
            df = pd.read_csv(file_path, dtype=str)
        else:
            df = pd.read_excel(file_path)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Error reading file from disk: {e}")

    try:
        rules = json.loads(rules_json)
    except:
        raise HTTPException(status_code=400, detail="Invalid rules_json")

    total_rows = len(df)
    column_count = len(df.columns)

    logger.info(f"🔄 Starting validation for {total_rows} rows...")

    # Create temporary directory for chunked processing
    temp_dir = tempfile.mkdtemp()
    good_csv_path = os.path.join(temp_dir, "good_data.csv")
    bad_csv_path = os.path.join(temp_dir, "bad_data.csv")

    total_good = 0
    total_bad = 0

    # Process in chunks
    for start_idx in range(0, total_rows, CHUNK_SIZE):
        end_idx = min(start_idx + CHUNK_SIZE, total_rows)
        chunk = df.iloc[start_idx:end_idx].copy()

        logger.info(f"📊 Processing rows {start_idx} to {end_idx}...")

        # Apply validation rules on this chunk
        chunk_good, chunk_bad = apply_validation_rules(chunk, rules)

        # Update counts
        total_good += len(chunk_good)
        total_bad += len(chunk_bad)

        # Append to CSV files
        write_header = (start_idx == 0)

        if not chunk_good.empty:
            chunk_good.to_csv(good_csv_path, mode='a', index=False, header=write_header)

        if not chunk_bad.empty:
            chunk_bad.to_csv(bad_csv_path, mode='a', index=False, header=write_header)

        # Clear memory
        del chunk, chunk_good, chunk_bad
        gc.collect()

    logger.info("✅ Validation chunks processed. Calculating duplicates...")

    # Detect duplicates
    duplicates_df = detect_duplicates(df)

    # Clear main dataframe from memory
    del df
    gc.collect()

    # Generate summary
    summary = pd.DataFrame({
        "Metric": ["Total Rows", "Good Rows", "Bad Rows", "Good %", "Bad %", "Columns", "Rules", "Timestamp"],
        "Value": [
            total_rows, total_good, total_bad,
            f"{(total_good / total_rows * 100):.2f}%" if total_rows else "0.00%",
            f"{(total_bad / total_rows * 100):.2f}%" if total_rows else "0.00%",
            column_count, len(rules),
            datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        ]
    })

    # Calculate error frequency
    error_freq_df = pd.DataFrame(columns=["Error", "Frequency"])
    if total_bad > 0 and os.path.exists(bad_csv_path):
        try:
            bad_reasons = pd.read_csv(bad_csv_path, usecols=["_validation_reason"])
            error_freq_df = summarize_errors(bad_reasons)
            del bad_reasons
            gc.collect()
        except Exception:
            pass

    # Assemble final Excel file
    logger.info("💾 Assembling final Excel file...")
    final_excel_path = os.path.join(temp_dir, f"validation_result_{filename}.xlsx")

    with pd.ExcelWriter(final_excel_path, engine="openpyxl") as writer:
        # Good data
        if total_good > 0 and os.path.exists(good_csv_path):
            pd.read_csv(good_csv_path, dtype=str).to_excel(writer, "Good_Data", index=False)
        else:
            pd.DataFrame().to_excel(writer, "Good_Data", index=False)

        # Bad data
        if total_bad > 0 and os.path.exists(bad_csv_path):
            pd.read_csv(bad_csv_path, dtype=str).to_excel(writer, "Bad_Data", index=False)
        else:
            pd.DataFrame().to_excel(writer, "Bad_Data", index=False)

        # Other sheets
        (pd.DataFrame(rules) if rules else pd.DataFrame()).to_excel(writer, "Validation_Rules", index=False)
        summary.to_excel(writer, "Summary", index=False)
        error_freq_df.to_excel(writer, "Error_Frequency", index=False)
        duplicates_df.to_excel(writer, "Duplicates", index=False)

    # Upload to Google Drive
    logger.info("☁️ Uploading to Drive...")
    try:
        service = get_drive_service(email)
        media = MediaFileUpload(
            final_excel_path,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            resumable=True
        )

        metadata = {
            "name": f"validation_result_{filename}",
            "mimeType": "application/vnd.google-apps.spreadsheet"
        }

        created = service.files().create(
            body=metadata,
            media_body=media,
            fields="id,webViewLink,webContentLink"
        ).execute()

        file_id = created.get("id")
        web_link = created.get("webViewLink")

        # Set permissions
        try:
            service.permissions().create(
                fileId=file_id,
                body={"type": "anyone", "role": "reader"}
            ).execute()
            logger.info(f"✅ File permissions set: {file_id}")
        except Exception as perm_error:
            logger.warning(f"⚠️ Permission Error: {perm_error}")

        logger.info(f"✅ File uploaded to Drive: {web_link}")

    except Exception as e:
        logger.error(f"[Drive Upload Error] {e}")
        web_link = None
        file_id = None

    # Cleanup
    del media
    gc.collect()

    import shutil
    import time

    def safe_rmtree(path, retries=5, delay=1):
        for _ in range(retries):
            try:
                shutil.rmtree(path)
                return
            except PermissionError:
                time.sleep(delay)
        raise

    safe_rmtree(temp_dir)
    gc.collect()

    logger.info("🧹 File deleted successfully from disk")

    return {
        "workbook": {
            "id": file_id,
            "webViewLink": web_link,
            "downloadLink": f"https://drive.google.com/uc?export=download&id={file_id}" if file_id else None
        },
        "good_count": total_good,
        "bad_count": total_bad,
    }
