"""
Duplicate Detection Utilities
Functions for detecting exact and fuzzy duplicates in datasets
"""
import logging
import pandas as pd
from rapidfuzz import fuzz, process

logger = logging.getLogger(__name__)


def detect_duplicate_key_columns(df: pd.DataFrame) -> list:
    """
    Auto-detect columns likely to contain key business data (names, companies, etc.)
    
    Args:
        df: DataFrame to analyze
    
    Returns:
        list: Column names that are likely key columns
    """
    key_cols = []
    for col in df.columns:
        if df[col].dtype == object or pd.api.types.is_string_dtype(df[col]):
            values = df[col].dropna().astype(str)
            if values.empty:
                continue

            col_lower = col.lower()
            # Skip ID/serial/numeric-only columns
            if any(k in col_lower for k in ["id", "serial", "no", "count"]):
                continue
            if values.str.isdigit().all():
                continue
            if values.str.match(r"^\d{2}[-/]\d{2}[-/]\d{4}$").all():
                continue

            avg_len = values.str.len().mean()
            if avg_len < 3:
                continue

            unique_ratio = values.nunique() / len(values)
            if unique_ratio < 0.02:
                continue

            key_cols.append(col)

    logger.info(f"[Duplicates] Auto-detected key columns: {key_cols}")
    return key_cols


def detect_exact_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect exact duplicate rows
    
    Args:
        df: DataFrame to check
    
    Returns:
        DataFrame containing only exact duplicate rows
    """
    exact_dupes = df[df.duplicated(keep=False)]
    if not exact_dupes.empty:
        exact_dupes = exact_dupes.copy()
        exact_dupes["Duplicate_Type"] = "Exact"
        return exact_dupes
    return pd.DataFrame()


def detect_fuzzy_duplicates(df: pd.DataFrame, similarity_threshold: int = 85) -> pd.DataFrame:
    """
    Detect fuzzy duplicates using string similarity
    
    Args:
        df: DataFrame to check
        similarity_threshold: Minimum similarity score (0-100)
    
    Returns:
        DataFrame with fuzzy duplicate pairs
    """
    key_columns = detect_duplicate_key_columns(df)
    fuzzy_results = []

    for col in key_columns:
        vals = df[col].dropna().astype(str).unique().tolist()
        
        # Sort to enable neighbor comparison
        vals_sorted = sorted(vals)
        
        # Only compare adjacent items (huge optimization)
        for i in range(len(vals_sorted) - 1):
            val1 = vals_sorted[i]
            val2 = vals_sorted[i + 1]
            
            score = fuzz.token_sort_ratio(val1, val2)
            
            if score >= similarity_threshold:
                fuzzy_results.append({
                    "Column": col,
                    "Value1": val1,
                    "Value2": val2,
                    "Similarity": score,
                    "Duplicate_Type": "Fuzzy"
                })

    if fuzzy_results:
        return pd.DataFrame(fuzzy_results)
    return pd.DataFrame(columns=["Column", "Value1", "Value2", "Similarity", "Duplicate_Type"])


def detect_duplicates(df: pd.DataFrame, similarity_threshold: int = 85) -> pd.DataFrame:
    """
    Comprehensive duplicate detection (exact + fuzzy)
    
    Args:
        df: DataFrame to analyze
        similarity_threshold: Minimum similarity score for fuzzy matching
    
    Returns:
        DataFrame with all detected duplicates
    """
    duplicate_rows = []

    # Detect exact duplicates
    exact_dupes = detect_exact_duplicates(df)
    if not exact_dupes.empty:
        duplicate_rows.append(exact_dupes)

    # Detect fuzzy duplicates
    fuzzy_dupes = detect_fuzzy_duplicates(df, similarity_threshold)
    if not fuzzy_dupes.empty:
        duplicate_rows.append(fuzzy_dupes)

    if duplicate_rows:
        return pd.concat(duplicate_rows, ignore_index=True)
    else:
        return pd.DataFrame(columns=["Column", "Value1", "Value2", "Similarity", "Duplicate_Type"])
