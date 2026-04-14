# mapping_services.py — COMPLETE FILE
# Handles field mapping between source and target systems using LLM + hybrid approaches
# Supports Google Drive files, Local uploads, and In-Memory Sessions

import os
import io
import re
import json
import logging
import base64
from datetime import datetime, time
from difflib import SequenceMatcher
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from typing import Any, Dict, List, Optional, Tuple
from functools import lru_cache
from dotenv import load_dotenv

# ✅ IMPORT SHARED STORE (Crucial for finding uploaded files)
from store import USER_STORE

import pandas as pd
from fastapi import APIRouter, HTTPException, Form , Header
import google.generativeai as genai

from services.gdrive_service import find_file_by_id,download_file_bytes,upload_mapping_to_gdrive

# Load environment variables from .env file
load_dotenv()

# ==================== CONFIGURATION ====================
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mapping_router = APIRouter(tags=["Mapping"])

# Constants
DEFAULT_HOST_SYSTEM = "Host System"
DEFAULT_TARGET_SYSTEM = "Target System"
DEFAULT_LLM_TIMEOUT = 200.0  # Increased timeout for large files
DEFAULT_SIMILARITY_THRESHOLD = 0.4
SEMANTIC_WEIGHT = 0.65
STRING_WEIGHT = 0.35
MAX_EXECUTOR_WORKERS = 4

# Gemini Setup
GEMINI_KEY = os.getenv("GEMINI_MAPPING_API_KEY", "").strip()
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if GEMINI_KEY:
    try:
        genai.configure(api_key=GEMINI_KEY)
        gemini_model = genai.GenerativeModel(GEMINI_MODEL_NAME)
        logger.info(f"✅ Gemini configured with model: {GEMINI_MODEL_NAME}")
    except Exception as e:
        gemini_model = None
        logger.error(f"❌ Failed to configure Gemini: {e}")
else:
    gemini_model = None
    logger.warning("⚠️ GEMINI_API_KEY not set — LLM calls will use hybrid fallback")

# ==================== SYNONYM MAP ====================
SYNONYM_MAP = {
    "client": ["customer", "user", "account"],
    "customer": ["client", "user", "account"],
    "addr": ["address", "location", "street"],
    "invoice": ["billing", "bill"],
    "billing": ["invoice", "bill"],
    "ship": ["shipping", "delivery"],
    "phone": ["contact", "contact_no", "phone_number", "mobile", "telephone"],
    "dob": ["date_of_birth", "birth_date", "birthdate"],
    "salary": ["income", "annual_income", "yearly_salary", "compensation"],
    "reward": ["loyalty", "points", "reward_balance", "rewards"],
    "lang": ["language", "preferred_language", "lang_pref", "locale"],
    "joined": ["registration", "joined_on", "signup_date", "created_date"],
    "job": ["occupation", "job_title", "profession", "position"],
    "last_order": ["last_purchase", "last_order_date", "last_purchase_date"],
    "email": ["mail", "email_address", "e_mail"],
    "id": ["identifier", "unique_id", "code"],
    "status": ["state", "condition"],
    "qty": ["quantity", "amount", "count"],
    "desc": ["description", "details"],
}

# ==================== OPTIONAL ENHANCEMENTS ====================
# We wrap these in try-except to ensure the app runs even if libraries are missing
try:
    from sentence_transformers import SentenceTransformer, util as st_util
    ST_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
    logger.info("✅ Sentence Transformers loaded")
except Exception as e:
    ST_MODEL = None
    logger.warning(f"⚠️ sentence-transformers not available: {e}")

try:
    from rapidfuzz import fuzz
    logger.info("✅ RapidFuzz loaded")
except Exception:
    fuzz = None
    logger.warning("⚠️ rapidfuzz not available, using SequenceMatcher fallback")

# ==================== EXECUTOR FOR TIMEOUT ====================
_EXECUTOR = ThreadPoolExecutor(max_workers=MAX_EXECUTOR_WORKERS)


# ==================== FILE & TOKEN UTILITIES (FIXED) ====================

def is_local_file(file_path: str) -> bool:
    """Check if the provided path is a local physical file"""
    if not file_path: return False
    try:
        return os.path.exists(file_path) and os.path.isfile(file_path)
    except Exception:
        return False

def is_session_token(token: str) -> bool:
    """
    ✅ Checks if the string is a base64 encoded session token.
    Logic: It must decode successfully and contain the '||' delimiter.
    """
    if not token or len(token) < 20: 
        return False
    try:
        decoded = base64.urlsafe_b64decode(token).decode("utf-8")
        return "||" in decoded
    except Exception:
        return False

def get_data_from_memory(token: str, file_type: Optional[str] = None) -> Any:
    """
    ✅ Retrieves DataFrame from USER_STORE based on token and file_type
    
    Args:
        token: Session token containing email||filename||timestamp
        file_type: "source" or "target" for mapping files
    
    Returns:
        List of dicts (JSON-ready data) or None
    """
    try:
        decoded = base64.urlsafe_b64decode(token).decode("utf-8")
        parts = decoded.split("||")
        if len(parts) < 3:
            logger.error("❌ Invalid token format")
            return None
            
        email, filename, timestamp = parts[0], parts[1], parts[2]
        
        logger.info(f"🔍 Looking up memory data for: {email} | File: {filename} | Type: {file_type}")

        if email not in USER_STORE:
            logger.error(f"❌ User {email} not found in USER_STORE.")
            return None
            
        user_data = USER_STORE[email]
        print(user_data)

        # ✅ Priority 1: Check mapping_files if file_type provided
        if file_type and "mapping_files" in user_data:
            if file_type in user_data["mapping_files"]:
                df = user_data["mapping_files"][file_type]["dataframe"]
                logger.info(f"✅ Found mapping {file_type} file: {user_data['mapping_files'][file_type]['filename']}")
                return df.to_dict(orient="records")
            else:
                logger.error(f"❌ Mapping {file_type} file not found")
                return None
        
        # ✅ Priority 2: Fallback to regular dataframe (for profiling)
        if "dataframe" not in user_data:
            logger.error("❌ No dataframe found in user session.")
            return None

        df = user_data["dataframe"]
        logger.info(f"✅ Found profiling dataframe: {filename}")
        return df.to_dict(orient="records")
        
    except Exception as e:
        logger.exception(f"❌ Error in get_data_from_memory: {e}")
        return None
    
# def get_data_from_memory(token: str) -> Any:
#     """
#     ✅ Decodes token and retrieves DataFrame from the Shared USER_STORE.
#     """
#     try:
#         decoded = base64.urlsafe_b64decode(token).decode("utf-8")
#         parts = decoded.split("||")
#         if len(parts) < 3:
#             return None
            
#         email, filename, timestamp = parts[0], parts[1], parts[2]
        
#         logger.info(f"🔍 Looking up memory data for: {email} | File: {filename}")

#         if email not in USER_STORE:
#             logger.error(f"❌ User {email} not found in USER_STORE.")
#             return None
            
#         user_data = USER_STORE[email]

#         # if "raw_json" in user_data:
#         #     logger.info(f"✅ Returning RAW JSON for {filename}")
#         #     return user_data["raw_json"]
        
#         if "dataframe" not in user_data:
#             logger.error("❌ No dataframe found in user session.")
#             return None

#         df = user_data["dataframe"]
#         # Convert to list of dicts for JSON processing
#         print(df)
#         print(df.to_dict(orient="records"))
#         return df.to_dict(orient="records")

#     except Exception as e:
#         logger.error(f"❌ Failed to retrieve data from token: {e}")
#         return None


# ==================== SIMILARITY UTILITIES ====================
@lru_cache(maxsize=1000)
def get_synonyms(token: str) -> set:
    """Get all synonyms for a token (cached)"""
    synonyms = {token}
    for canonical, syns in SYNONYM_MAP.items():
        if token == canonical or token in syns:
            synonyms.update([canonical] + syns)
    return synonyms

def synonym_boost_score(src_tokens: List[str], tgt_tokens: List[str]) -> float:
    """Boost score if synonyms match"""
    boost = 0.0
    for s in src_tokens:
        src_syns = get_synonyms(s)
        for t in tgt_tokens:
            if t in src_syns:
                boost += 0.15
    return min(boost, 0.4)

@lru_cache(maxsize=10000)
def compute_string_similarity(a: str, b: str) -> float:
    """Compute string similarity using rapidfuzz or SequenceMatcher (cached)"""
    a_lower, b_lower = (a or "").lower(), (b or "").lower()
    if fuzz:
        try:
            return fuzz.token_set_ratio(a_lower, b_lower) / 100.0
        except Exception as e:
            logger.debug(f"Fuzz error: {e}")
    return SequenceMatcher(None, a_lower, b_lower).ratio()

def compute_semantic_similarity_batch(list_a: List[str], list_b: List[str]) -> Dict[Tuple[int, int], float]:
    """Compute semantic similarity between two lists of strings"""
    if ST_MODEL is None:
        return {
            (i, j): compute_string_similarity(a, b)
            for i, a in enumerate(list_a)
            for j, b in enumerate(list_b)
        }
    
    try:
        emb_a = ST_MODEL.encode(list_a, convert_to_tensor=True, show_progress_bar=False)
        emb_b = ST_MODEL.encode(list_b, convert_to_tensor=True, show_progress_bar=False)
        cos = st_util.cos_sim(emb_a, emb_b)
        return {(i, j): float(cos[i][j]) for i in range(len(list_a)) for j in range(len(list_b))}
    except Exception as e:
        logger.error(f"Semantic similarity error: {e}")
        return {
            (i, j): compute_string_similarity(a, b)
            for i, a in enumerate(list_a)
            for j, b in enumerate(list_b)
        }


# ==================== JSON UTILITIES ====================
def safe_json_parse(text: str) -> Any:
    """Safely parse JSON with multiple fallback strategies"""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    
    patterns = [
        r"```json\s*([\s\S]*?)\s*```",
        r"(\{[\s\S]*\}|\[[\s\S]*\])",
    ]
    
    for pattern in patterns:
        match = re.search(pattern, text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                continue
    
    raise json.JSONDecodeError(f"Could not parse JSON from text", text, 0)

def extract_json_content_from_file_local(file_path: str) -> Any:
    """Read and parse JSON from local file"""
    try:
        logger.info(f"Reading local file: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()
        return safe_json_parse(text)
    except Exception as e:
        logger.error(f"⚠️ Error reading local file {file_path}: {e}")
        raise

def extract_json_content_from_file(file_id: str, email: str , access_token: Optional[str] = None) -> Any:
    """Download and parse JSON from Google Drive file"""
    try:
        logger.info(f"Downloading from Google Drive: {file_id}")
        data = download_file_bytes(file_id ,email , access_token)
        text = data.decode("utf-8", errors="ignore")
        return safe_json_parse(text)
    except Exception as e:
        logger.error(f"⚠️ Error extracting JSON from Drive: {e}")
        raise

def extract_all_leaf_paths_from_json(obj: Any, prefix: str = "", max_depth: int = 10) -> List[str]:
    """Extract all leaf JSON paths from nested object"""
    if max_depth <= 0:
        return [prefix] if prefix else []
    
    out = []

    if isinstance(obj, dict):
        if not obj:
            out.append(prefix)
        for k, v in obj.items():
            full = f"{prefix}.{k}" if prefix else k
            out.extend(extract_all_leaf_paths_from_json(v, full, max_depth - 1))
    elif isinstance(obj, list):
        if not obj:
            out.append(prefix)
        elif isinstance(obj[0], (dict, list)):
            # Analyze only the first item of a list to deduce schema
            out.extend(extract_all_leaf_paths_from_json(obj[0], prefix, max_depth - 1))
        else:
            out.append(prefix)
    else:
        out.append(prefix)
    
    return out


# ==================== HYBRID FALLBACK MAPPER ====================
def tokenize_field(field: str) -> List[str]:
    """Tokenize field name for comparison"""
    return re.findall(r"[A-Za-z0-9]+", field.lower())


# def hybrid_smart_map(
#     fields_src: List[str],
#     fields_tgt: List[str],
#     sem_weight: float = SEMANTIC_WEIGHT,
#     str_weight: float = STRING_WEIGHT,
#     threshold: float = DEFAULT_SIMILARITY_THRESHOLD
# ) -> List[Dict[str, Any]]:
#     """Hybrid mapping using semantic + string similarity + synonym boosting"""
#     if not fields_src:
#         logger.warning("No source fields provided")
#         return []
    
#     if not fields_tgt:
#         logger.warning("No target fields provided")
#         return [{"source_field": s, "target_field": "N/A", "score": 0.0} for s in fields_src]

#     sem_scores = compute_semantic_similarity_batch(fields_src, fields_tgt)
#     tokenized_src = [tokenize_field(s) for s in fields_src]
#     tokenized_tgt = [tokenize_field(t) for t in fields_tgt]
    
#     mappings = []
#     for i, s in enumerate(fields_src):
#         best_score, best_tgt = 0.0, None
        
#         for j, t in enumerate(fields_tgt):
#             sem = sem_scores.get((i, j), 0)
#             strsim = compute_string_similarity(s, t)
#             syn_boost = synonym_boost_score(tokenized_src[i], tokenized_tgt[j])
#             score = sem_weight * sem + str_weight * strsim + syn_boost
            
#             if score > best_score:
#                 best_score, best_tgt = score, t
        
#         mappings.append({
#             "source_field": s,
#             "target_field": best_tgt if best_score >= threshold else "N/A",
#             "score": round(best_score, 4)
#         })
    
#     logger.info(f"Hybrid mapping completed: {len(mappings)} mappings generated")
#     return mappings

def hybrid_smart_map(fields_src, fields_tgt, sem_weight=0.65, str_weight=0.35, threshold=0.4):
    """
    fields_src and fields_tgt are lists of string paths (or strings).
    Returns list of {"source_field", "target_field", "score"}.
    """
    if not fields_src:
        return []
    if not fields_tgt:
        return [{"source_field": s, "target_field": "N/A", "score": 0.0} for s in fields_src]

    sem_scores = compute_semantic_similarity_batch(fields_src, fields_tgt)
    tokenized_src = [re.findall(r"[A-Za-z0-9]+", s.lower()) for s in fields_src]
    tokenized_tgt = [re.findall(r"[A-Za-z0-9]+", t.lower()) for t in fields_tgt]
    mappings = []
    for i, s in enumerate(fields_src):
        best_score, best_tgt = 0.0, None
        for j, t in enumerate(fields_tgt):
            sem = sem_scores.get((i, j), 0)
            strsim = compute_string_similarity(s, t)
            syn_boost = synonym_boost_score(tokenized_src[i], tokenized_tgt[j])
            score = sem_weight * sem + str_weight * strsim + syn_boost
            if score > best_score:
                best_score, best_tgt = score, t
        if best_score >= threshold:
            mappings.append({"source_field": s, "target_field": best_tgt, "score": round(best_score, 4)})
        else:
            mappings.append({"source_field": s, "target_field": "N/A", "score": round(best_score, 4)})
    return mappings


# ==================== LLM UTILITIES ====================
# def build_mapping_prompt(host_fields: Any, target_fields: Any, host_system: str, target_system: str) -> str:
#     """Build the enhanced LLM prompt for field mapping"""
    
#     # Truncate if too large to prevent token limits
#     host_preview = host_fields[:15] if isinstance(host_fields, list) else host_fields
#     target_preview = target_fields[:15] if isinstance(target_fields, list) else target_fields

#     src_str = json.dumps(host_preview, indent=2, ensure_ascii=False)
#     tgt_str = json.dumps(target_preview, indent=2, ensure_ascii=False)

#     return f"""You are an expert **Data Integration and Schema Mapping Architect**.
    
#     Context:
#     Host System: {host_system}
#     Target System: {target_system}

#     Host Data Sample:
#     {src_str}

#     Target Data Sample:
#     {tgt_str}

#     Objective:
#     Map every field from the Host system to the Target system.
    
#     Output Format:
#     Return ONLY a JSON Array.
#     [
#       {{
#         "Source Field (JSON Path)": "Field_Name",
#         "Source System": "{host_system}",
#         "Source Data Type": "string",
#         "Sample Source Value": "Example",
#         "Transformation / Logic": "Direct Mapping",
#         "Target Field (API Name)": "Mapped_Field_Name",
#         "Target System": "{target_system}",
#         "Target Data Type": "string",
#         "Sample Target Value": "Example",
#         "Comments / Notes": "Reasoning"
#       }}
#     ]
#     """

# def build_mapping_prompt(host_fields: Any, target_fields: Any, host_system: str, target_system: str) -> str:
#     """Build the enhanced LLM prompt for field mapping"""
    
#     # Truncate if too large to prevent token limits
#     host_preview = host_fields[:15] if isinstance(host_fields, list) else host_fields
#     target_preview = target_fields[:15] if isinstance(target_fields, list) else target_fields

#     src_str = json.dumps(host_preview, indent=2, ensure_ascii=False)
#     tgt_str = json.dumps(target_preview, indent=2, ensure_ascii=False)

#     return f"""You are an expert **Data Integration and Schema Mapping Architect**.
    
#     Context:
#     Host System: {host_system}
#     Target System: {target_system}

#     Host Data Sample:
#     {src_str}

#     Target Data Sample:
#     {tgt_str}

#     Objective:
#     Map every field from the Host system to the Target system.
    
#     Output Format:
#     Return ONLY a JSON Array.
#     [
#       {{
#         "Source Field (JSON Path)": "Field_Name",
#         "Source System": "{host_system}",
#         "Source Data Type": "string",
#         "Sample Source Value": "Example",
#         "Transformation / Logic": "Direct Mapping",
#         "Target Field (API Name)": "Mapped_Field_Name",
#         "Target System": "{target_system}",
#         "Target Data Type": "string",
#         "Sample Target Value": "Example",
#         "Comments / Notes": "Reasoning"
#       }}
#     ]
#     """

def build_mapping_prompt(host_fields: Any, target_fields: Any, host_system: str, target_system: str) -> str:
    """Build the enhanced LLM prompt for field mapping"""
    # def standardize_to_single_json(data):
    #     # Case 1: Idi List ayithe (Local File)
    #     if isinstance(data, list):
    #         if len(data) > 0:
    #             # List ni "Single Dictionary" ga convert chestunnam
    #             # Key: "schema_sample", Value: First Row
    #             return {"file_schema_sample": data[0]}
    #         else:
    #             return {} # Empty Dict
        
    #     # Case 2: Idi already Dictionary ayithe (Drive File)
    #     # Direct ga return chestunnam
    #     return data

    # # --- APPLY LOGIC ---
    # # Ippudu host_data mariyu target_data RENDU kooda Single JSON Objects eh!
    # # No more lists.
    # host_final = standardize_to_single_json(host_fields)
    # target_final = standardize_to_single_json(target_fields)

    # # --- CONVERT TO STRING ---
    # src_str = json.dumps(host_final, indent=2, ensure_ascii=False)
    # tgt_str = json.dumps(target_final, indent=2, ensure_ascii=False)
    # def get_schema_sample(data):
    #     """Extracts a single representative dictionary (first record) from a list"""
    #     if isinstance(data, list):
    #         if len(data) > 0:
    #             # Return the first item (contains keys + sample values)
    #             return data[0]
    #         else:
    #             return {}
    #     return data  # If it's already a dict

    # # --- PREPARE DATA ---
    # # We only send the SCHEMA (1st record) to the LLM, not the full file.
    # # This fixes the "Missing Sample Value" issue.
    # host_sample = get_schema_sample(host_fields)
    # target_sample = get_schema_sample(target_fields)

    src_str = json.dumps(host_fields, indent=2, ensure_ascii=False)
    tgt_str = json.dumps(target_fields, indent=2, ensure_ascii=False)

    print("=====================================================================")
    print(src_str)
    print("========================================================================")
    print(tgt_str)

    return f"""
You are an expert **Data Integration and Schema Mapping Architect** specializing in enterprise data systems (ERP, CRM, Billing, HRMS, etc.).
You must deeply analyze and map fields between two system payloads.

---

### CONTEXT

**Host System:** {host_system}  
**Target System:** {target_system}

You are given two full JSON payloads — one from the Host system (source) and one from the Target system (destination).  

**HOST JSON:**
{src_str}

**TARGET JSON:**
{tgt_str}

---

### OBJECTIVE

Perform a **deep recursive analysis** of both JSON payloads and generate a **Field Mapping Specification** that shows how each source field maps to the destination system field.

You must:
- Traverse nested objects and arrays recursively.
- Detect each leaf field (like `ORDER.ORDER_STATUS.ORACLE_ORDER_NUMBER`).
- Match each host field to the most appropriate target field based on name similarity, semantics, and context.

---

### MAPPING OUTPUT RULES

For **each field in the HOST JSON**, create one JSON object in the output array containing:

- **"Source Field (JSON Path)"** → full path of the field in the HOST JSON (e.g., `ORDER.ORDER_STATUS.ORACLE_ORDER_NUMBER`)
- **"Source System"** → `{host_system}`
- **"Source Data Type"** →  
  Predict the correct data type (`string`, `integer`, `float`, `boolean`, `date`, `datetime`, `object`, or `array`)  
  based on the field name and/or its sample value.  
  If `{host_system}` is known (e.g., Oracle ERP, SAP, Workday), use realistic system-specific data typing conventions.  
  Never leave this field blank — always infer a best guess.
- **"Sample Source Value"** →  
  Provide a realistic example value consistent with the detected data type.  
  If `{host_system}` is known, generate realistic example data (e.g., for Oracle ERP use "12345" or "Cancelled", for Workday use "2024-10-25").  
  If not known, use domain-appropriate sample data (e.g., string → "Example", number → 1234).
- **"Transformation / Logic"** →  
  Describe how the source value should be transformed before mapping (e.g., "Direct Mapping", "Conditional Mapping", "Lookup to Reference Table", "Translate Status", "Static Value Assignment", etc.).  
  If not applicable, use `"Direct Mapping"`.
- **"Target Field (API Name)"** →  
  Name of the target field that best matches, or `"N/A"` if no suitable field found.
- **"Target System"** → `{target_system}`
- **"Target Data Type"** →  
  Predict or infer the correct data type for the target field.  
  Use conventions if `{target_system}` is known (e.g., Salesforce `__c` fields → string/ID, SAP IDs → integer).  
  Never leave this field blank — always fill a best guess.
- **"Sample Target Value"** →  
  Provide a realistic example value that aligns with the predicted data type and system conventions.
- **"Comments / Notes"** →  
  Explain the mapping logic in one line (why it maps this way, or what transformation applies).

---

### ADDITIONAL REQUIREMENTS

1. Every HOST field must appear **exactly once**.
2. If no clear target match exists, set `"Target Field (API Name)"` = `"N/A"` but still fill `"Target Data Type"` and `"Sample Target Value"` with predicted realistic placeholders.
3. Prefer semantic and contextual matches over pure name similarity.
4. Use your internal understanding of common system fields to enrich sample values and types.
5. Return **only a valid JSON array** of objects — no markdown, no extra text.

---

### EXAMPLE OUTPUT (Structure Only)

[
  {{
    "Source Field (JSON Path)": "ORDER.ORDER_STATUS.ORACLE_ORDER_NUMBER",
    "Source System": "{host_system}",
    "Source Data Type": "string",
    "Sample Source Value": "ORD-12345",
    "Transformation / Logic": "Direct Mapping",
    "Target Field (API Name)": "APTS_Oracle_Order_Number__c",
    "Target System": "{target_system}",
    "Target Data Type": "string",
    "Sample Target Value": "ORD-98765",
    "Comments / Notes": "Oracle Order Number mapped directly to Salesforce Order Number field"
  }},
  {{
    "Source Field (JSON Path)": "ORDER.ORDER_STATUS.ATTRIBUTE1",
    "Source System": "{host_system}",
    "Source Data Type": "string",
    "Sample Source Value": "Cancelled in Oracle",
    "Transformation / Logic": "Translation Mapping",
    "Target Field (API Name)": "Apttus_Config2__Status__c",
    "Target System": "{target_system}",
    "Target Data Type": "string",
    "Sample Target Value": "Cancelled",
    "Comments / Notes": "Translate status values between Oracle and Salesforce"
  }}
]

Return **only the JSON array** — nothing else.
"""


def _run_gemini_sync(model,prompt: str) -> str:
    """Call Gemini synchronously"""
    if model is None:
        raise RuntimeError("No Gemini model configured")
    
    resp = model.generate_content([prompt])
    
    if hasattr(resp, "text") and resp.text:
        return resp.text
    if hasattr(resp, "candidates") and resp.candidates:
        try:
            parts = resp.candidates[0].content.parts
            if parts and hasattr(parts[0], "text"):
                return parts[0].text
        except (IndexError, AttributeError) as e:
            logger.error(f"Error extracting text from response: {e}")
    
    raise ValueError("Empty or invalid response from Gemini")


def run_gemini_with_timeout(model,prompt: str, timeout_seconds: float = DEFAULT_LLM_TIMEOUT) -> str:
    """Run Gemini with timeout"""
    if model is None:
        raise RuntimeError("Gemini not configured")
    
    future = _EXECUTOR.submit(_run_gemini_sync,model, prompt)
    try:
        return future.result(timeout=timeout_seconds)
    except FutureTimeout:
        future.cancel()
        raise TimeoutError(f"LLM request timed out after {timeout_seconds}s")


def normalize_llm_mapping_response(parsed: Any, host_system: str, target_system: str) -> List[Dict[str, Any]]:
    """Normalize LLM response to standard format"""
    if isinstance(parsed, dict) and "mapping" in parsed:
        parsed = parsed["mapping"]
    
    if not isinstance(parsed, list):
             raise ValueError("LLM returned non-list structure")

    normalized = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        
        # Handle multiple possible field names (LLMs can be inconsistent)
        src_path = (item.get("Source Field (JSON Path)") or item.get("source") or item.get("Source") or "")
        src_data_type = item.get("Source Data Type") or item.get("source_data_type") or ""
        src_sample = item.get("Sample Source Value", "")
        transformation = item.get("Transformation / Logic", item.get("transformation", "Direct Mapping"))
        tgt_field = (item.get("Target Field (API Name)") or item.get("Target Field") or item.get("target") or "N/A")
        tgt_data_type = item.get("Target Data Type", "")
        tgt_sample = item.get("Sample Target Value", "")
        comments = item.get("Comments / Notes", item.get("Comments", ""))

        normalized.append({
            "source": src_path,
            "target": tgt_field or "N/A",
            "details": {
                "source_system": host_system,
                "target_system": target_system,
                "source_data_type": src_data_type,
                "source_sample": src_sample,
                "transformation": transformation,
                "target_data_type": tgt_data_type,
                "target_sample": tgt_sample,
                "notes": comments,
            }
        })

    return normalized


async def llm_field_mapping(
    host_fields: Any,
    target_fields: Any,
    host_system: str,
    target_system: str,
    llm_timeout: float = DEFAULT_LLM_TIMEOUT,
    user: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Try LLM first, fallback to hybrid if it fails"""
    # if gemini_model is None:
    #     logger.warning("⚠️ LLM not configured — using hybrid fallback")
    #     return _fallback_to_hybrid(host_fields, target_fields)
    model = None

    prompt = build_mapping_prompt(host_fields, target_fields, host_system, target_system)

    try:
        from services.gemini_token_service import gemini_token_service
        from google.api_core import exceptions as google_exceptions
        Redis_Key_Meta, Redis_Key = await gemini_token_service._get_available_api_key()
        if Redis_Key:
            try:
                genai.configure(api_key=Redis_Key)
                model = genai.GenerativeModel(GEMINI_MODEL_NAME)
                logger.info(f"✅ Gemini configured with model with Redis Key: {GEMINI_MODEL_NAME}")
            except Exception as e:
                model = None
                logger.error(f"❌ Failed to configure Gemini: {e}")
        elif GEMINI_KEY:
            Redis_Key_Meta = None
            try:
                genai.configure(api_key=GEMINI_KEY)
                model = genai.GenerativeModel(GEMINI_MODEL_NAME)
                logger.info(f"✅ Gemini configured with model with GEMINI_KEY: {GEMINI_MODEL_NAME}")
            except Exception as e:
                model = None
                logger.error(f"❌ Failed to configure Gemini: {e}")
                logger.warning("⚠️ GEMINI_API_KEY not set — LLM calls will use hybrid fallback")
        else:
            logger.warning("⚠️ No Gemini key available — using hybrid fallback")
            return _fallback_to_hybrid(host_fields, target_fields)

        try:
            text = run_gemini_with_timeout(model, prompt, timeout_seconds=llm_timeout)
        except google_exceptions.ResourceExhausted as e:
            if Redis_Key_Meta:
                await gemini_token_service._handle_429(Redis_Key_Meta)
            raise HTTPException(status_code=429, detail="Too many requests. Please try again in a few minutes.")
        except google_exceptions.ServiceUnavailable as e:
            if Redis_Key_Meta:
                await gemini_token_service._handle_503(Redis_Key_Meta)
            raise HTTPException(status_code=503, detail="Service unavailable. Please try again in a few minutes.")

        logger.info(f"🔍 RAW GEMINI RESPONSE (first 500 chars): {text[:500]}")
        if not text:
            raise ValueError("Empty response from Gemini")

        # Remove markdown code blocks
        text = text.replace("```json", "").replace("```", "").strip()
        
        # Find JSON array
        match = re.search(r"(\[[\s\S]*\])", text)
        if not match:
            # Fallback: try to find just a JSON object
            match = re.search(r"(\{[\s\S]*\})", text)
            if not match:
                 raise ValueError(f"No JSON found in Gemini response")

        parsed = json.loads(match.group(0))
        if parsed:
            logger.info(f"🔍 FIRST PARSED ITEM KEYS: {list(parsed[0].keys())}")
            logger.info(f"🔍 FIRST ITEM: {json.dumps(parsed[0], indent=2)}")
        normalized = normalize_llm_mapping_response(parsed, host_system, target_system)
        

        source_fields_from_data = extract_all_leaf_paths_from_json(host_fields)
        mapped_sources = {m["source"] for m in normalized}
       
        if not normalized:
            raise ValueError("Gemini returned empty mapping")

        logger.info(f"✅ LLM mapping completed: {len(normalized)} mappings")
        return normalized

    except Exception as e:
        logger.warning(f"⚠️ LLM failed ({e.__class__.__name__}: {e}), falling back to hybrid")
        print("⚠️ Gemini failed or timed out, falling back to hybrid:", e)
        # Use hybrid fallback. Need host/target lists of leaf paths
        if isinstance(host_fields, dict):
            host_paths = extract_all_leaf_paths_from_json(host_fields)
        elif isinstance(host_fields, list):
            host_paths = []
            for h in host_fields:
                if isinstance(h, dict):
                    host_paths.extend(extract_all_leaf_paths_from_json(h))
        else:
            host_paths = [str(host_fields)]
        if isinstance(target_fields, dict):
            target_paths = extract_all_leaf_paths_from_json(target_fields)
        else:
            target_paths = [str(target_fields)]
        hybrid = hybrid_smart_map(host_paths, target_paths)
        return [{"source": m["source_field"], "target": m["target_field"]} for m in hybrid]


def _fallback_to_hybrid(host_fields: Any, target_fields: Any) -> List[Dict[str, Any]]:
    """Fallback to hybrid mapping"""
    host_paths = extract_all_leaf_paths_from_json(host_fields) if isinstance(host_fields, (dict, list)) else [str(host_fields)]
    target_paths = extract_all_leaf_paths_from_json(target_fields) if isinstance(target_fields, (dict, list)) else [str(target_fields)]
    
    hybrid = hybrid_smart_map(host_paths, target_paths)
    
    return [
        {
            "source": m["source_field"],
            "target": m["target_field"],
            "details": {"score": m["score"], "method": "hybrid"}
        }
        for m in hybrid
    ]


# ==================== API ENDPOINTS (FIXED LOGIC) ====================

@mapping_router.post("/smart_mapping_with_files")
async def smart_mapping_with_files(
    email: str = Form(...),
    host_file_id: str = Form(...),
    target_file_id: str = Form(...),
    host_file_type: str = Form(...),    
    target_file_type: str = Form(...),
    host_system: str = Form(DEFAULT_HOST_SYSTEM),
    target_system: str = Form(DEFAULT_TARGET_SYSTEM),
    authorization: Optional[str] = Header(None)
):
    """
    Smart mapping with files from Google Drive OR In-Memory Session OR Local Path
    """
    try:
        # ✅ ADD: Extract token
        access_token = None
        if authorization and authorization.startswith("Bearer "):
            access_token = authorization.replace("Bearer ", "").strip()
            logger.info(f"🔑 Token received for {email}")
        else:
            raise HTTPException(
                status_code=401,
                detail="❌ No credentials found. User must login first via /login endpoint."
            )
        
        logger.info(f"📥 Starting mapping for user: {email}")
        print("DEBUG CHECK ---> Host ID:", host_file_id)
        print("DEBUG CHECK ---> Target ID:", target_file_id)

        # Check if strings are identical
        if host_file_id == target_file_id:
             print("❌ ERROR: two host_file and target_files are same")
        else:
              print("✅ OK: Tokens different ga unnayi.")
        
        # ==================== HANDLE HOST FILE ====================
        # 1. Check if it's an In-Memory Token
        if is_session_token(host_file_id):
            logger.info("✅ Host file: IN-MEMORY SESSION")
            host_fields = get_data_from_memory(host_file_id,file_type=host_file_type)
            print(f"source in smart_mapping :- {host_fields} | Type: Source")
            if host_fields is None:
                 raise HTTPException(status_code=404, detail="Host file session expired or not found. Please re-upload.")
            
            # Extract filename from token
            try:
                decoded = base64.urlsafe_b64decode(host_file_id).decode("utf-8")
                fname = decoded.split("||")[1]
            except:
                fname = "host_upload.json"
            host_file = {"id": "local", "name": fname}
            
        # 2. Check if it's a physical local file (Legacy/Dev usage)
        elif is_local_file(host_file_id):
            logger.info("✅ Host file: LOCAL DISK")
            with open(host_file_id, 'r') as f:
                host_fields = json.load(f)
            host_file = {"id": host_file_id, "name": os.path.basename(host_file_id)}
            
            
        # 3. Assume Google Drive
        else:
            logger.info("✅ Host file: GOOGLE DRIVE")
            host_file = find_file_by_id(host_file_id, email,access_token)
            if not host_file:
                raise HTTPException(status_code=404, detail=f"Host file not found in Drive: {host_file_id}")
            host_fields = extract_json_content_from_file(host_file_id, email,access_token)

        # ==================== HANDLE TARGET FILE ====================
        # 1. Check if it's an In-Memory Token
        if is_session_token(target_file_id):
            logger.info("✅ Target file: IN-MEMORY SESSION")
            target_fields = get_data_from_memory(target_file_id,file_type=target_file_type)
            print(f"source in smart_mapping :- {host_fields} | Type: target")
            if target_fields is None:
                 raise HTTPException(status_code=404, detail="Target file session expired. Please re-upload.")
            
            try:
                decoded = base64.urlsafe_b64decode(target_file_id).decode("utf-8")
                fname = decoded.split("||")[1]
            except:
                fname = "target_upload.json"
            target_file = {"id": "local", "name": fname}

        # 2. Physical Local File
        elif is_local_file(target_file_id):
            logger.info("✅ Target file: LOCAL DISK")
            with open(target_file_id, 'r') as f:
                target_fields = json.load(f)
            target_file = {"id": target_file_id, "name": os.path.basename(target_file_id)}
            
            
        # 3. Google Drive
        else:
            logger.info("✅ Target file: GOOGLE DRIVE")
            target_file = find_file_by_id(target_file_id, email,access_token)
            if not target_file:
                raise HTTPException(status_code=404, detail=f"Target file not found in Drive: {target_file_id}")
            target_fields = extract_json_content_from_file(target_file_id, email,access_token)

        logger.info(f"📄 Processing: {host_file['name']} -> {target_file['name']}")

        # ==================== PERFORM MAPPING ====================
        mapping = llm_field_mapping(host_fields, target_fields, host_system, target_system, llm_timeout=200.0)

        # ==================== UPLOAD RESULT ====================
        parent_id = None
        if "parents" in host_file and host_file["parents"]:
             parent_id = host_file["parents"][0]
        
        host_base_name = os.path.splitext(host_file['name'])[0]
        target_base_name = os.path.splitext(target_file['name'])[0]

        upload_resp = upload_mapping_to_gdrive(
            mapping, 
            host_file, 
            target_file, 
            None, 
            parent_id, 
            host_base_name,
            target_base_name,
            email ,
            access_token,
            source_data=host_fields,    
            target_data=target_fields
        )

        logger.info(f"✅ Mapping complete. Upload Response keys: {upload_resp.keys() if upload_resp else 'None'}")

        # ✅ FIX: Handle the URL return properly (webViewLink vs file_url)
        final_url = upload_resp.get("webViewLink") or upload_resp.get("file_url") or upload_resp.get("alternateLink")

        return {
            "status": "success",
            "mapping_count": len(mapping),
            "mapping": mapping,
            "host_file": {"id": host_file.get("id"), "name": host_file.get("name")},
            "target_file": {"id": target_file.get("id"), "name": target_file.get("name")},
            "file_url": final_url,
            "preview": json.dumps(mapping[:10], indent=2, ensure_ascii=False)
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"❌ [Mapping Error] {e}")
        raise HTTPException(status_code=500, detail=str(e))


@mapping_router.get("/test_mapping")
async def test_mapping():
    """Test endpoint to verify mapping service is working"""
    return {
        "status": "Mapping service is running",
        "timestamp": datetime.now().isoformat(),
        "configuration": {
            "llm_configured": gemini_model is not None,
            "llm_model": GEMINI_MODEL_NAME if gemini_model else None,
            "semantic_model": ST_MODEL is not None,
            "fuzzy_matching": fuzz is not None,
        }
    }


@mapping_router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "mapping_service",
        "timestamp": datetime.now().isoformat()
    }