"""
Validation Services
Handles data validation rules generation and application
"""
import os
import re
import json
import logging
import pandas as pd
import google.generativeai as genai
from google.api_core import exceptions as google_exceptions
from fastapi import HTTPException
from config.settings import GEMINI_API_KEY, GEMINI_MODEL_NAME
from utils.file_utils import normalize_value_for_rule

logger = logging.getLogger(__name__)

# Configure Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)


def apply_validation_rules(df: pd.DataFrame, rules: list) -> tuple:
    """
    Apply validation rules to dataframe and separate good/bad data
    
    Returns:
        tuple: (good_df, bad_df)
    """
    work = df.copy()
    work["_validation_status"] = "Good"
    work["_validation_reason"] = ""

    for idx, row in work.iterrows():
        errors = []
        for rule in rules:
            col = rule.get("column")
            expr = rule.get("rule")
            desc = rule.get("description", "Rule failed")

            if not col or col not in df.columns or not expr:
                continue

            value = normalize_value_for_rule(row[col])

            # Handle required fields
            if (value is None or str(value).strip() == "") and any(
                kw in desc.lower() for kw in ["required", "not empty", "non-empty"]
            ):
                errors.append(f"{col}: {desc}")
                continue

            try:
                # Safe eval with limited builtins
                safe_env = {
                    "value": value,
                    "re": re,
                    "isinstance": isinstance,
                    "int": int,
                    "float": float,
                    "str": str,
                    "len": len,
                    "bool": bool,
                    "any": any,
                    "all": all,
                }
                ok = bool(eval(expr, {"__builtins__": None}, safe_env))
                if not ok:
                    errors.append(f"{col}: {desc}")
            except Exception as e:
                logger.warning(f"[Eval Error] {col} -> {e} | Expr: {expr}")
                errors.append(f"{col}: Rule eval error")

        if errors:
            work.at[idx, "_validation_status"] = "Bad"
            work.at[idx, "_validation_reason"] = "; ".join(errors)

    good = work[work["_validation_status"] == "Good"].drop(
        columns=["_validation_status", "_validation_reason"]
    )
    bad = work[work["_validation_status"] == "Bad"].drop(
        columns=["_validation_status"]
    )
    return good, bad


async def generate_validation_rules(
    headers: list,
    sample_rows: list,
    user_guidance: dict = None,
    previous_rules: dict = None,
    user: str = None
) -> list:
    """
    Generate or refine validation rules using Gemini SDK
    
    Args:
        headers: List of column names
        sample_rows: Sample data rows
        user_guidance: Optional user edits/guidance
        previous_rules: Optional previous rules for refinement
    
    Returns:
        list: Validation rules
    """
    if not GEMINI_API_KEY:
        # Fallback to basic required rules
        return {h: [{"rule_id": "required", "type": "required", "description": "Must not be empty"}] for h in headers}

    prompt = f"""
You are an expert Data Quality Validator.
Given column names (and optionally sample data), generate Python boolean expressions for validating correct values.

CRITICAL INSTRUCTIONS FOR DATA TYPE DETECTION:

1. **Date Columns**: If you see values like "29-04-2001", "01/12/2023", "15-08-1995" these are DATE STRINGS (not numbers!)
   - Rule: `bool(re.fullmatch(r'^\\d{{{{1,2}}}}[-/]\\d{{{{1,2}}}}[-/]\\d{{{{2,4}}}}$', str(value)))`
   - Description: "Date must be in DD-MM-YYYY or DD/MM/YYYY format"
   - DO NOT use numeric checks like isinstance(value, int)!
   
2. **Phone Numbers**: Values like "+91-9876543210", "(123) 456-7890", "9876543210"
   - Rule: `bool(re.fullmatch(r'^\\+?[\\d\\s\\-\\(\\)]{{{{10,}}}}$', str(value)))`
   - Description: "Valid phone number format"
   - Keep as STRING validation, not numeric!
   
3. **Email Addresses**: Values containing "@" and "."
   - Rule: `('@' in str(value)) and ('.' in str(value))`
   - Description: "Valid email address format"
   
4. **Numeric IDs/Codes**: If column name contains "id", "code", "number" AND values are pure digits
   - Rule: `isinstance(value, (int, float)) or (isinstance(value, str) and str(value).isdigit())`
   - Description: "Must be a valid numeric ID"
   - Allow both numeric and string representation
   
5. **Money/Currency**: Values like 1000, 50000 in columns like "salary", "income", "price"
   - Rule: `isinstance(value, (int, float)) and value >= 0`
   - Description: "Must be a positive number"
   
6. **Text Fields**: Names, addresses, descriptions, cities
   - Rule: `isinstance(value, str) and len(value.strip()) > 0`
   - Description: "Must not be empty"

🔹 Each rule must be directly executable in Python with the variable name `value`.
🔹 Output **only** a valid JSON array — no extra text.
🔹 IMPORTANT: Look at the ACTUAL values in samples to determine type - if you see "29-04-2001", it's a DATE STRING not a number!

Example expected output:
[
  {{"column": "email_address", "rule": "('@' in str(value)) and ('.' in str(value))", "description": "Valid email address format"}},
  {{"column": "date_of_birth", "rule": "bool(re.fullmatch(r'^\\d{{{{1,2}}}}[-/]\\d{{{{1,2}}}}[-/]\\d{{{{2,4}}}}$', str(value)))", "description": "Date must be in DD-MM-YYYY format"}},
  {{"column": "phone", "rule": "bool(re.fullmatch(r'^\\+?[\\d\\s\\-\\(\\)]{{{{10,}}}}$', str(value)))", "description": "Valid phone number"}},
  {{"column": "age", "rule": "isinstance(value, (int, float)) and 0 <= value <= 150", "description": "Age must be between 0 and 150"}}
]

Columns:
{', '.join(headers)}

Sample rows (USE THESE to determine actual data types):
{json.dumps(sample_rows, indent=2, default=str)}
"""

    if previous_rules and user_guidance:
        prompt += f"""

Previous rules:
{json.dumps(previous_rules, indent=2, default=str)}

User provided these edits:
{json.dumps(user_guidance, indent=2, default=str)}

Please refine and regenerate improved JSON rules accordingly.
"""
    elif user_guidance:
        prompt += f"""

User edits:
{json.dumps(user_guidance, indent=2, default=str)}
"""

    try:
        from services.gemini_token_service import gemini_token_service
        Redis_Key_Meta, Redis_Key = await gemini_token_service._get_available_api_key()
        if Redis_Key:
            try:
                genai.configure(api_key=Redis_Key)
                model = genai.GenerativeModel("gemini-2.5-flash")
                logger.info(f"✅ Gemini configured with model with Redis Key: gemini-2.5-flash")
            except Exception as e:
                model = None
                logger.error(f"❌ Failed to configure Gemini: {e}")
        else:
            Redis_Key_Meta = None
            model = None
            logger.warning("⚠️ GEMINI_API_KEY not set — LLM calls will use hybrid fallback")
        logger.info(f"✅ Gemini model Sending Propmt with Redis Key: gemini-2.5-flash")
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
        logger.info(f"✅ Response received model with Redis Key: gemini-2.5-flash")
        text = response.text.strip()
        logger.info(f"✅ Gemini response with Redis Key: {Redis_Key} and user: {user}")

        # Extract JSON content
        match = re.search(r"\[[\s\S]*\]", text)
        if not match:
            logger.warning("[Gemini SDK] No valid JSON detected")
            return {h: [{"rule_id": "required", "type": "required", "description": "Must not be empty"}] for h in headers}

        raw_json = match.group(0).strip()
        raw_json = raw_json.strip("```json").strip("```").strip()

        try:
            rules = json.loads(raw_json)
        except json.JSONDecodeError:
            closing_index = raw_json.find("]") + 1
            rules = json.loads(raw_json[:closing_index])

        return rules

    except Exception as e:
        logger.error(f"[Gemini SDK Error] {e}")
        return {h: [{"rule_id": "required", "type": "required", "description": "Must not be empty"}] for h in headers}


def summarize_errors(bad_df: pd.DataFrame) -> pd.DataFrame:
    """
    Summarize validation errors by frequency
    
    Args:
        bad_df: DataFrame with _validation_reason column
    
    Returns:
        DataFrame with error frequency summary
    """
    if "_validation_reason" not in bad_df.columns or bad_df.empty:
        return pd.DataFrame(columns=["Error", "Frequency"])

    error_list = []
    for reason in bad_df["_validation_reason"].dropna():
        error_list.extend(reason.split("; "))

    if not error_list:
        return pd.DataFrame(columns=["Error", "Frequency"])

    from collections import Counter
    error_counts = Counter(error_list)

    return pd.DataFrame([
        {"Error": err, "Frequency": count}
        for err, count in error_counts.most_common()
    ])
