"""
File Upload Routes
Endpoints for uploading local files
"""
import io
import os
import gc
import json
import logging
import pathlib
import shutil
import tempfile
import pandas as pd
from datetime import datetime
from fastapi import APIRouter, Form, UploadFile, File, HTTPException

from services.auth_service import make_session_token
from utils.file_utils import detect_and_cast_numeric
from utils.memory_utils import USER_STORE
from utils.security import normalize_email, validate_short_text

logger = logging.getLogger(__name__)

router = APIRouter(tags=["File Upload"], prefix="/api")


@router.post("/upload_local")
async def api_upload_local(email: str = Form(...), file: UploadFile = File(...)):
    """
    ✅ Optimized Upload: Saves file directly to Disk (Temp folder).
    Does NOT load the whole file into RAM. Safe for large files.
    """
    email = normalize_email(email)
    if email not in USER_STORE:
        USER_STORE.setdefault(email, {})
    
    filename = file.filename
    filename = validate_short_text(filename, "filename", max_len=255)
    filename_lower = filename.lower()
    
    # 1. Create a Temp File on Disk
    # 'delete=False' means the file stays until we manually remove it
    suffix = pathlib.Path(filename).suffix
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    temp_path = temp_file.name  # e.g., /tmp/tmp8475.csv

    try:
        # 2. Stream content from Upload to Disk (RAM Safe)
        with temp_file as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        logger.info(f"✅ File saved to disk at: {temp_path}")
        
        # 3. Store ONLY the PATH in memory (Not the heavy DataFrame)
        USER_STORE[email]["file_path"] = temp_path
        USER_STORE[email]["filename"] = filename
        
        # Clear any old dataframe from RAM to free space
        if "dataframe" in USER_STORE[email]:
            del USER_STORE[email]["dataframe"]
        
        gc.collect()

        # 4. Generate Preview (Read only first 5 rows)
        try:
            if filename_lower.endswith(".csv"):
                try:
                    df_preview = pd.read_csv(temp_path, nrows=5, dtype=str)
                except:
                    df_preview = pd.read_csv(temp_path, nrows=5, sep=None, engine='python', dtype=str)
                    
            elif filename_lower.endswith(".json"):
                with open(temp_path, 'r') as f:
                    try:
                        data = json.load(f)
                        if isinstance(data, list):
                            df_preview = pd.DataFrame(data[:5])
                        else:
                            df_preview = pd.DataFrame([data])
                    except:
                        df_preview = pd.DataFrame()
                        
            elif filename_lower.endswith((".xls", ".xlsx", ".xlsm")):
                df_preview = pd.read_excel(temp_path, nrows=5, dtype=str)
            else:
                raise Exception("Unsupported file format")
                
        except Exception as read_err:
            logger.warning(f"⚠️ Preview generation failed: {read_err}")
            df_preview = pd.DataFrame(columns=["Error"])

    except Exception as e:
        logger.exception(f"Failed to save file: {e}")
        # Cleanup if failed
        if os.path.exists(temp_path):
            os.remove(temp_path)
        raise HTTPException(status_code=400, detail=f"Failed to save file: {e}")

    # Create session token
    session_token = make_session_token(email, filename)
    USER_STORE[email]["last_session_token"] = session_token
    
    # Prepare preview for frontend
    preview = df_preview.replace({float("inf"): None, float("-inf"): None}).fillna("").to_dict(orient="records")
    
    return {
        "name": filename, 
        "preview": preview, 
        "local_path": session_token
    }


@router.post("/upload_mapping_file")
async def api_upload_mapping_file(
    email: str = Form(...),
    file: UploadFile = File(...),
    file_type: str = Form(...)  # "source" or "target"
):
    """
    Upload mapping file (source or target) for field mapping feature
    """
    email = normalize_email(email)
    file_type = validate_short_text(file_type, "file_type", max_len=20)
    if file_type not in {"source", "target"}:
        raise HTTPException(status_code=400, detail="file_type must be 'source' or 'target'")

    if email not in USER_STORE:
        USER_STORE[email] = {}
    
    if "mapping_files" not in USER_STORE[email]:
        USER_STORE[email]["mapping_files"] = {}
    
    contents = await file.read()
    filename = file.filename
    filename = validate_short_text(filename, "filename", max_len=255)
    filename_lower = filename.lower()

    try:
        if filename_lower.endswith(".csv"):
            try:
                df = pd.read_csv(io.BytesIO(contents), sep=None, engine="python", dtype=str)
            except:
                df = pd.read_csv(io.BytesIO(contents), dtype=str)
        
        elif filename_lower.endswith(".json"):
            json_data = json.load(io.BytesIO(contents))
            if isinstance(json_data, dict):
                df = pd.DataFrame([json_data])
            else:
                df = pd.DataFrame(json_data)

        elif filename_lower.endswith((".xls", ".xlsx", ".xlsm")):
            df = pd.read_excel(io.BytesIO(contents))

        else:
            raise Exception(f"Unsupported file format: {pathlib.Path(filename).suffix}")

    except Exception as e:
        logger.exception(f"Failed to parse mapping file: {e}")
        raise HTTPException(status_code=400, detail=f"Failed to read file: {e}")

    # Cast numeric columns
    df = detect_and_cast_numeric(df)

    # Store in mapping-specific structure with file_type key
    USER_STORE[email]["mapping_files"][file_type] = {
        "dataframe": df,
        "filename": filename,
        "uploaded_at": datetime.utcnow().isoformat(),
        "file_id": None
    }

    logger.info(f"✅ Mapping {file_type} file uploaded: {filename} for {email}")
    logger.info(f"📊 Shape: {df.shape}, Columns: {list(df.columns)}")
    
    # Create session token
    session_token = make_session_token(email, filename)
    
    # Generate preview
    preview = df.head(5).replace({
        float("inf"): None, 
        float("-inf"): None
    }).fillna("").to_dict(orient="records")
    
    return {
        "name": filename,
        "preview": preview,
        "local_path": session_token,
        "file_type": file_type,
        "columns": list(df.columns),
        "row_count": len(df)
    }
