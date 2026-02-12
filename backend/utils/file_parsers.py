import json
import csv
import io
from typing import Any, Dict, List

import pandas as pd


def parse_uploaded_file(
    filename: str,
    file_bytes: bytes
) -> Dict[str, Any]:
    """
    Detect file type (json / csv / xlsx) and
    return normalized JSON for LLM mapping
    """

    ext = filename.lower().split(".")[-1]

    if ext == "json":
        return json.loads(file_bytes.decode("utf-8"))

    if ext == "csv":
        return _parse_csv(file_bytes)

    if ext in ("xlsx", "xls"):
        return _parse_excel(file_bytes)

    raise ValueError(f"Unsupported file type: .{ext}")


def _parse_csv(file_bytes: bytes) -> Dict[str, Any]:
    text = file_bytes.decode("utf-8")
    reader = csv.DictReader(io.StringIO(text))

    rows = list(reader)
    if not rows:
        raise ValueError("CSV file is empty")

    return {
        "rows": rows,
        "columns": list(rows[0].keys())
    }


def _parse_excel(file_bytes: bytes) -> Dict[str, Any]:
    df = pd.read_excel(io.BytesIO(file_bytes))

    if df.empty:
        raise ValueError("Excel file is empty")

    return {
        "rows": df.to_dict(orient="records"),
        "columns": list(df.columns)
    }
