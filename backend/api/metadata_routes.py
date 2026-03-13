"""
Metadata Comparison Routes
---------------------------
Endpoints:
  GET /api/metadata/source-tables          — fetch all public tables from source PostgreSQL DB
  GET /api/metadata/target-objects         — fetch all objects from Conga API (proxied)
  GET /api/metadata/source-columns?table=  — fetch columns + data types for a source table
  GET /api/metadata/target-fields?object=  — fetch fields + data types for a target object
"""

import io
import logging
import time
import xml.etree.ElementTree as ET
from typing import Any

import pandas as pd
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
import psycopg2
from psycopg2 import sql as pgsql
import requests
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Metadata Comparison"], prefix="/api/metadata")

# --------------------------------------------------
# Source DB Configuration (PGSQL)
# --------------------------------------------------
DB_NAME = os.getenv("SOURCE_DB_NAME", "conga")
DB_HOST = os.getenv("SOURCE_DB_HOST", "172.16.138.15")
DB_PORT = int(os.getenv("SOURCE_DB_PORT", 5432))
USER = os.getenv("SOURCE_DB_USER", "forsys")
PASSWORD = os.getenv("SOURCE_DB_PASSWORD", "Forsys@123$")
SOURCE_DB_CONFIG = {
    "dbname": DB_NAME,
    "host": DB_HOST,
    "port": DB_PORT,
    "user": USER,
    "password": PASSWORD,
}

# --------------------------------------------------
# Conga API Configuration
# --------------------------------------------------
CONGA_BASE_URL = "https://preview-rls09.congacloud.com/api/schema/v1"
CONGA_BASE_2_URL = "https://preview-rls09.congacloud.com/api/metadata/v1"
CONGA_USER_ID = os.getenv("CONGA_USER_ID", "d1c3fad0-fb4f-0b5e-c79f-03c535e80e2a")
CONGA_CLIENT_ID = os.getenv("CONGA_CLIENT_ID", "fdaa232d-51c5-4559-afa9-195cb6bd4f59")
CONGA_CLIENT_SECRET = os.getenv("CONGA_CLIENT_SECRET", "JEDeDBP3$Z!2??10682eP25tB")


# --------------------------------------------------
# Conga Token Cache
# --------------------------------------------------
_token_cache: dict = {"token": "", "expires_at": 0.0}

def _get_conga_token() -> str:
    """Return a valid Conga bearer token, refreshing only when expired or within 60 s of expiry."""
    now = time.time()
    if _token_cache["token"] and now < _token_cache["expires_at"] - 60:
        return _token_cache["token"]

    url = "https://login-rlspreview.congacloud.com/api/v1/auth/connect/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": CONGA_CLIENT_ID,
        "client_secret": CONGA_CLIENT_SECRET,
        "user-id": CONGA_USER_ID,
    }
    response = requests.post(
        url,
        data=payload,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    response.raise_for_status()
    token_data = response.json()
    _token_cache["token"] = token_data.get("access_token", "")
    _token_cache["expires_at"] = now + token_data.get("expires_in", 300)
    granted_scopes = token_data.get("scope", "")
    logger.info("Conga token refreshed; expires_in=%s scope=%s", token_data.get("expires_in", 300), granted_scopes)
    return _token_cache["token"]


def _conga_headers() -> dict:
    """Return auth headers required by every Conga API call."""
    return {
        "Authorization": f"Bearer {_get_conga_token()}",
        "user-id": CONGA_USER_ID,
    }


# --------------------------------------------------
# Endpoints
# --------------------------------------------------
@router.get("/source-tables")
def get_source_tables():
    """Fetch all table names from the source PostgreSQL database (public schema)."""
    try:
        conn = psycopg2.connect(**SOURCE_DB_CONFIG)
        cur = conn.cursor()
        cur.execute(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {"tables": [row[0] for row in rows]}
    except psycopg2.OperationalError as exc:
        logger.error("Source DB connection failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"Database connection failed: {exc}")
    except Exception as exc:
        logger.exception("Failed to fetch source tables")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/target-objects")
def get_target_objects():
    """Proxy call to Conga API to fetch all available objects (avoids browser CORS issues)."""
    try:
        response = requests.get(
            f"{CONGA_BASE_URL}/objects",
            headers=_conga_headers(),
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()
        objects = [
            {
                "name": obj["Name"],
                "displayName": obj.get("DisplayName", obj["Name"]),
            }
            for obj in data.get("Data", [])
        ]
        return {"objects": objects}
    except requests.Timeout:
        logger.error("Conga API request timed out")
        raise HTTPException(status_code=504, detail="Conga API request timed out")
    except requests.HTTPError as exc:
        body = exc.response.text if exc.response is not None else ""
        logger.error("Conga API HTTP error %s: %s", exc.response.status_code if exc.response is not None else "?", body)
        raise HTTPException(status_code=502, detail=f"Conga API error {exc}: {body}")
    except requests.RequestException as exc:
        logger.error("Conga API request failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Conga API error: {exc}")
    except Exception as exc:
        logger.exception("Failed to fetch target objects")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/source-columns")
def get_source_columns(table: str = Query(..., description="Source table name")):
    """Fetch column names and data types for a given source table (public schema)."""
    try:
        conn = psycopg2.connect(**SOURCE_DB_CONFIG)
        cur = conn.cursor()
        cur.execute(
            "SELECT column_name, data_type "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = %s "
            "ORDER BY ordinal_position",
            (table,),
        )
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return {
            "table": table,
            "columns": [{"name": row[0], "dataType": row[1]} for row in rows],
        }
    except psycopg2.OperationalError as exc:
        logger.error("Source DB connection failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"Database connection failed: {exc}")
    except Exception as exc:
        logger.exception("Failed to fetch source columns")
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/dynamic-labels")
def get_dynamic_labels(table: str = Query(..., description="Source table name")):
    """
    Fetch a {apiName: fieldLabel} map for do_ columns by parsing the
    dynamicobjectlayoutxml stored in dynamicobjectconfig for the given table.
    Returns {"labels": {}} when no record exists or XML is missing.
    """
    try:
        conn = psycopg2.connect(**SOURCE_DB_CONFIG)
        cur = conn.cursor()
        cur.execute(
            "SELECT dynamicobjectlayoutxml FROM dynamicobjectconfig "
            "WHERE LOWER(dynamictablename) = LOWER(%s)",
            (table,),
        )
        row = cur.fetchone()
        cur.close()
        conn.close()

        if not row or not row[0]:
            return {"labels": {}}

        xml_str = row[0]
        try:
            root = ET.fromstring(xml_str)
        except ET.ParseError as exc:
            logger.warning("Failed to parse XML for table %s: %s", table, exc)
            return {"labels": {}}

        labels = {}
        for df in root.iter("dynamicFields"):
            api_el = df.find("apiName")
            label_el = df.find("fieldLabel")
            if api_el is not None and label_el is not None:
                api_name = (api_el.text or "").strip()
                field_label = (label_el.text or "").strip()
                if api_name:
                    labels[api_name] = field_label

        return {"labels": labels}
    except psycopg2.OperationalError as exc:
        logger.error("Source DB connection failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"Database connection failed: {exc}")
    except Exception as exc:
        logger.exception("Failed to fetch dynamic labels for table %s", table)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/target-fields-raw")
def get_target_fields_raw(object: str = Query(..., description="Target object name")):
    """Debug endpoint: returns the raw Conga API response so the structure can be inspected."""
    try:
        response = requests.get(
            f"{CONGA_BASE_2_URL}/objects/{object}",
            headers=_conga_headers(),
            timeout=15,
        )
        response.raise_for_status()
        return response.json()
    except requests.Timeout:
        raise HTTPException(status_code=504, detail="Conga API request timed out")
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Conga API error: {exc}")


def _extract_fields(raw: dict) -> list:
    """
    Extract normalised { name, displayName, dataType } list from the Conga metadata response.

    Confirmed response shape:
      {
        "Success": true,
        "Data": {
          "Name": "Account",
          "FieldMetadata": [
            { "FieldName": "Id", "DisplayName": "Id", "DataType": "Identifier", ... },
            { "FieldName": "Name", "DisplayName": "Name", "DataType": "String", ... },
            ...
          ]
        }
      }
    """
    data = raw.get("Data", {})
    if not isinstance(data, dict):
        logger.warning("Expected 'Data' to be a dict, got: %s", type(data))
        return []

    field_list = data.get("FieldMetadata", [])
    if not isinstance(field_list, list):
        logger.warning("Expected 'FieldMetadata' to be a list, got: %s", type(field_list))
        return []

    return [
        {
            "name": f.get("FieldName", ""),
            "displayName": f.get("DisplayName", f.get("FieldName", "")),
            "dataType": f.get("DataType", "Unknown"),
            "lookupObjectName": f.get("LookupObjectName"),
        }
        for f in field_list
        if isinstance(f, dict)
    ]


@router.get("/source-picklist")
def get_source_picklist(
    table: str = Query(..., description="Source table name"),
    column: str = Query(..., description="Source column name"),
):
    """
    1. Look up the FK referenced table for (table, column).
    2. Query SELECT {referenced_table}name FROM {referenced_table}.
    3. Return the list of display values.
    """
    try:
        conn = psycopg2.connect(**SOURCE_DB_CONFIG)
        cur = conn.cursor()

        # Step 1: find the FK referenced table / column
        cur.execute(
            """
            SELECT ccu.table_name AS referenced_table, ccu.column_name AS referenced_column
            FROM information_schema.table_constraints AS tc
            JOIN information_schema.key_column_usage AS kcu
                ON tc.constraint_name = kcu.constraint_name
                AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage AS ccu
                ON ccu.constraint_name = tc.constraint_name
                AND ccu.table_schema = tc.table_schema
            WHERE tc.table_name = %s
              AND kcu.column_name = %s
            """,
            (table, column),
        )
        fk_row = cur.fetchone()

        if not fk_row:
            cur.close()
            conn.close()
            return {"values": [], "info": "No foreign key found for this column"}

        referenced_table = fk_row[0]
        display_column = referenced_table + "name"

        # Step 2: fetch display values
        # referenced_table comes from information_schema so it is a trusted identifier
        cur.execute(f'SELECT "{display_column}" FROM "{referenced_table}"')  # noqa: S608
        rows = cur.fetchall()
        cur.close()
        conn.close()

        return {
            "values": [row[0] for row in rows if row[0] is not None],
            "referenced_table": referenced_table,
        }
    except psycopg2.OperationalError as exc:
        logger.error("Source DB connection failed: %s", exc)
        raise HTTPException(status_code=503, detail=f"Database connection failed: {exc}")
    except Exception as exc:
        logger.exception("Failed to fetch source picklist for %s.%s", table, column)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/target-picklist")
def get_target_picklist(
    object: str = Query(..., description="Target object name"),
    field: str = Query(..., description="Target field name"),
):
    """
    Call Conga dependency-fields API and return the PicklistEntries for the field.

    Response shape (relevant part):
      { "Data": { "PicklistMetadata": [ { "PicklistEntries": [ { "Value": "...", "DisplayText": "..." } ] } ] } }
    """
    try:
        response = requests.get(
            f"{CONGA_BASE_2_URL}/objects/{object}/fields/{field}/dependency-fields",
            headers=_conga_headers(),
            timeout=15,
        )
        response.raise_for_status()
        raw = response.json()

        picklist_metadata = raw.get("Data", {}).get("PicklistMetadata", [])
        values = []
        for pm in picklist_metadata:
            for entry in pm.get("PicklistEntries", []):
                if not entry.get("IsDeprecated", False):
                    values.append(
                        {
                            "value": entry.get("Value", ""),
                            "displayText": entry.get("DisplayText", entry.get("Value", "")),
                        }
                    )

        return {"values": values}
    except requests.Timeout:
        raise HTTPException(status_code=504, detail="Conga API request timed out")
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f"Conga API error: {exc}")
    except Exception as exc:
        logger.exception("Failed to fetch target picklist for %s.%s", object, field)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/target-fields")
def get_target_fields(object: str = Query(..., description="Target object name")):
    """Proxy call to Conga API to fetch fields and data types for a given object."""
    try:
        response = requests.get(
            f"{CONGA_BASE_2_URL}/objects/{object}",
            headers=_conga_headers(),
            timeout=15,
        )
        response.raise_for_status()
        raw = response.json()
        logger.info("Conga fields raw keys for %s: %s", object, list(raw.keys()))
        fields = _extract_fields(raw)
        return {"object": object, "fields": fields}
    except requests.Timeout:
        logger.error("Conga API request timed out for object: %s", object)
        raise HTTPException(status_code=504, detail="Conga API request timed out")
    except requests.RequestException as exc:
        logger.error("Conga API fields request failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Conga API error: {exc}")
    except Exception as exc:
        logger.exception("Failed to fetch target fields")
        raise HTTPException(status_code=500, detail=str(exc))


# --------------------------------------------------
# Excel Export
# --------------------------------------------------

class SessionData(BaseModel):
    sourceTable: str
    targetObject: str
    sourceColumns: list[dict[str, Any]]
    targetFields: list[dict[str, Any]]
    rowSelections: dict[str, str]
    picklistMappings: dict[str, dict[str, str]]
    dynamicLabels: dict[str, str] = {}
    dupCheckFields: list[str] = []


class ExportMappingRequest(BaseModel):
    sessions: list[SessionData]


def _header_cell(ws, row: int, col: int, value: str, fill: PatternFill) -> None:
    cell = ws.cell(row=row, column=col, value=value)
    cell.font = Font(bold=True, color="FFFFFF", size=10)
    cell.fill = fill
    cell.alignment = Alignment(horizontal="center", vertical="center")


def _get_fk_referenced_tables(table: str, uuid_columns: list[str]) -> dict[str, str]:
    """Query FK constraints to return {column_name: referenced_table} for the given uuid columns."""
    if not uuid_columns:
        return {}
    try:
        conn = psycopg2.connect(**SOURCE_DB_CONFIG)
        cur = conn.cursor()
        result: dict[str, str] = {}
        for col in uuid_columns:
            cur.execute(
                """
                SELECT ccu.table_name AS referenced_table
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.table_name = %s
                  AND kcu.column_name = %s
                """,
                (table, col),
            )
            row = cur.fetchone()
            if row:
                result[col] = row[0]
        cur.close()
        conn.close()
        return result
    except Exception:
        logger.exception("Failed to fetch FK referenced tables for %s", table)
        return {}


def _get_all_source_picklists(source_table: str, uuid_col_names: list[str]) -> dict[str, list[str]]:
    """
    For each uuid column in source_table, performs the FK lookup then fetches
    all display values — same logic as the /source-picklist endpoint but batched
    in a single DB connection.
    Returns {col_name: [value1, value2, ...]}; empty list when no FK or no values.
    """
    if not uuid_col_names:
        return {}
    try:
        conn = psycopg2.connect(**SOURCE_DB_CONFIG)
        cur = conn.cursor()
        result: dict[str, list[str]] = {}
        for col_name in uuid_col_names:
            # Step 1: FK lookup (identical query to /source-picklist endpoint)
            cur.execute(
                """
                SELECT ccu.table_name
                FROM information_schema.table_constraints AS tc
                JOIN information_schema.key_column_usage AS kcu
                    ON tc.constraint_name = kcu.constraint_name
                    AND tc.table_schema = kcu.table_schema
                JOIN information_schema.constraint_column_usage AS ccu
                    ON ccu.constraint_name = tc.constraint_name
                    AND ccu.table_schema = tc.table_schema
                WHERE tc.table_name = %s
                  AND kcu.column_name = %s
                """,
                (source_table, col_name),
            )
            fk_row = cur.fetchone()
            if not fk_row:
                result[col_name] = []
                continue
            ref_table = fk_row[0]
            display_col = ref_table + "name"
            # Step 2: fetch display values
            try:
                cur.execute(f'SELECT "{display_col}" FROM "{ref_table}"')  # noqa: S608
                rows = cur.fetchall()
                result[col_name] = [str(r[0]) for r in rows if r[0] is not None]
            except Exception:
                conn.rollback()  # reset aborted transaction so next columns can still be queried
                logger.warning(
                    "Skipping picklist for %s.%s — column '%s' not found in '%s'",
                    source_table, col_name, display_col, ref_table,
                )
                result[col_name] = []
        cur.close()
        conn.close()
        return result
    except Exception:
        logger.exception("Failed to fetch all source picklists for %s", source_table)
        return {}


def _get_all_target_picklists(target_object: str, picklist_fields: list[dict]) -> dict[str, list[str]]:
    """
    For each Picklist-type target field, call the Conga dependency-fields API
    and return {field_name: [displayText, ...]}; empty list on failure or no values.
    """
    if not picklist_fields:
        return {}
    result: dict[str, list[str]] = {}
    for field in picklist_fields:
        field_name = field["name"]
        try:
            response = requests.get(
                f"{CONGA_BASE_2_URL}/objects/{target_object}/fields/{field_name}/dependency-fields",
                headers=_conga_headers(),
                timeout=15,
            )
            response.raise_for_status()
            raw = response.json()
            values = []
            for pm in raw.get("Data", {}).get("PicklistMetadata", []):
                for entry in pm.get("PicklistEntries", []):
                    if not entry.get("IsDeprecated", False):
                        values.append(entry.get("DisplayText", entry.get("Value", "")))
            result[field_name] = values
        except Exception:
            logger.exception("Failed to fetch target picklist for %s.%s", target_object, field_name)
            result[field_name] = []
    return result


def _get_dependent_picklist_metadata(target_object: str) -> list[dict]:
    """
    Fetch DependentPicklistMetadata from the Conga object metadata API.
    Returns the list or [] when empty / on failure.
    """
    try:
        response = requests.get(
            f"{CONGA_BASE_2_URL}/objects/{target_object}",
            headers=_conga_headers(),
            timeout=15,
        )
        response.raise_for_status()
        return response.json().get("Data", {}).get("DependentPicklistMetadata", [])
    except Exception:
        logger.exception("Failed to fetch dependent picklist metadata for %s", target_object)
        return []


def _get_sample_records(table: str, columns: list[str]) -> dict[str, str]:
    """
    Fetch up to 100 rows from `table` in a single query and return the first
    non-null value per column as a string.  Falls back to "—" when all 100
    sampled rows are NULL for a column.
    """
    if not columns:
        return {}
    try:
        conn = psycopg2.connect(**SOURCE_DB_CONFIG)
        cur = conn.cursor()
        col_sql = pgsql.SQL(", ").join(pgsql.Identifier(c) for c in columns)
        query = pgsql.SQL("SELECT {cols} FROM {tbl} LIMIT 100").format(
            cols=col_sql,
            tbl=pgsql.Identifier(table),
        )
        cur.execute(query)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        result: dict[str, str] = {}
        for idx, col in enumerate(columns):
            sample = next(
                (
                    str(row[idx])
                    for row in rows
                    if row[idx] is not None and str(row[idx]).strip() != ""
                ),
                "—",
            )
            result[col] = sample
        return result
    except Exception:
        logger.exception("Failed to fetch sample records for table %s", table)
        return {}


def _get_column_stats(table: str, columns: list[str], dup_check_fields: list[str] | None = None) -> tuple[dict[str, dict], int]:
    """
    Load the source table into a pandas DataFrame and compute per-column stats:
      null       — count of NULL, empty string, or whitespace-only values
      non_null   — count of actual filled values
    Returns ({col_name: {"null": int, "non_null": int}}, composite_dup_count: int)
    composite_dup_count is the number of redundant duplicate rows across dup_check_fields
    (rows that are exact matches on all checked fields, excluding the first occurrence).
    """
    if not columns:
        return {}, 0
    try:
        conn = psycopg2.connect(**SOURCE_DB_CONFIG)
        df = pd.read_sql(f'SELECT * FROM "{table}"', conn)  # noqa: S608
        conn.close()
        result: dict[str, dict] = {}
        for col in columns:
            if col not in df.columns:
                result[col] = {"null": 0, "non_null": 0}
                continue
            s = df[col]
            is_missing = s.isna() | (s.astype(str).str.strip() == "")
            result[col] = {
                "null":     int(is_missing.sum()),
                "non_null": int((~is_missing).sum()),
            }
        # Composite duplicate count across dup_check_fields
        composite_dup_count = 0
        valid_dup_cols = [c for c in (dup_check_fields or []) if c in df.columns]
        if valid_dup_cols:
            composite_dup_count = int(df[valid_dup_cols].duplicated(keep="first").sum())
        return result, composite_dup_count
    except Exception:
        logger.exception("Failed to compute column stats for table %s", table)
        return {}, 0


def _check_null_columns(table: str, columns: list[str]) -> dict[str, bool]:
    """
    Return {col_name: has_nulls} for every column in one single batch query.

    Builds:  SELECT EXISTS(SELECT 1 FROM t WHERE c1 IS NULL),
                    EXISTS(SELECT 1 FROM t WHERE c2 IS NULL), ...
    EXISTS short-circuits on the first NULL found, keeping it fast on large tables.
    Column identifiers are quoted via psycopg2.sql — safe even with special chars.
    """
    if not columns:
        return {}
    try:
        conn = psycopg2.connect(**SOURCE_DB_CONFIG)
        cur = conn.cursor()
        parts = [
            pgsql.SQL("EXISTS(SELECT 1 FROM {tbl} WHERE {col} IS NULL OR TRIM({col}::text) = '')").format(
                tbl=pgsql.Identifier(table),
                col=pgsql.Identifier(col),
            )
            for col in columns
        ]
        query = pgsql.SQL("SELECT ") + pgsql.SQL(", ").join(parts)
        cur.execute(query)
        row = cur.fetchone()
        cur.close()
        conn.close()
        return {col: bool(val) for col, val in zip(columns, row)}
    except Exception:
        logger.exception("Failed to check null columns for table %s", table)
        return {}


# --------------------------------------------------
# Data-type compatibility helpers
# --------------------------------------------------

_TYPE_FAMILY: dict[str, str] = {
    # UUID / identifier
    "uuid": "uuid",
    "identifier": "uuid",
    # String family
    "text": "string",
    "varchar": "string",
    "character varying": "string",
    "char": "string",
    "character": "string",
    "name": "string",
    "string": "string",
    # Boolean
    "boolean": "boolean",
    "bool": "boolean",
    # Integer family
    "integer": "integer",
    "int": "integer",
    "int2": "integer",
    "int4": "integer",
    "int8": "integer",
    "bigint": "integer",
    "smallint": "integer",
    "long": "integer",
    # Numeric / decimal family
    "numeric": "numeric",
    "decimal": "numeric",
    "float": "numeric",
    "float4": "numeric",
    "float8": "numeric",
    "double precision": "numeric",
    "real": "numeric",
    "double": "numeric",
    "currency": "numeric",
    "money": "numeric",
    # Date only (no time component)
    "date": "date",
    # Datetime (date + time)
    "timestamp": "datetime",
    "timestamp without time zone": "datetime",
    "timestamp with time zone": "datetime",
    "timestamptz": "datetime",
    "datetime": "datetime",
    # Time only
    "time": "time",
    "time without time zone": "time",
    "time with time zone": "time",
    # JSON
    "json": "json",
    "jsonb": "json",
    # Conga-specific
    "picklist": "picklist",
    "lookup": "lookup",
}


def _data_type_match(src_dtype: str, tgt_dtype: str) -> str:
    """
    Return 'Yes', 'No', or 'N/A' for source ↔ target data-type compatibility.

    Rules:
      • uuid  ↔ Picklist  → Yes   (FK column maps to picklist values)
      • uuid  ↔ Lookup    → No
      • Same normalised family (case-insensitive) → Yes
        – covers boolean/Boolean, varchar/String, numeric/Decimal, date/Date, etc.
      • integer ↔ numeric cross-match → Yes
      • date  ↔ datetime (or vice-versa) → No  (granularity mismatch)
      • Everything else → No
    """
    if not src_dtype or not tgt_dtype or src_dtype == "N/A" or tgt_dtype == "N/A":
        return "N/A"
    src_norm = _TYPE_FAMILY.get(src_dtype.strip().lower(), src_dtype.strip().lower())
    tgt_norm = _TYPE_FAMILY.get(tgt_dtype.strip().lower(), tgt_dtype.strip().lower())

    if src_norm == "uuid" and tgt_norm == "picklist":
        return "Yes"
    if src_norm == "uuid" and tgt_norm == "lookup":
        return "No"
    if src_norm == tgt_norm:
        return "Yes"
    if src_norm in ("integer", "numeric") and tgt_norm in ("integer", "numeric"):
        return "Yes"
    return "No"


@router.get("/dependent-picklist-metadata")
def get_dependent_picklist_metadata(object: str = Query(...)):
    """
    Return DependentPicklistMetadata for a Conga target object.
    Used by the frontend to detect dependent picklist fields and build
    the 3-column configure modal.
    """
    data = _get_dependent_picklist_metadata(object)
    return {"dependentPicklistMetadata": data}


@router.post("/export-mapping")
def export_mapping(payload: ExportMappingRequest):
    """
    Generate an Excel workbook from one or more mapping sessions.

    Structure:
      Sheet 1         : Summary — one row per session
      Sheets 2…N      : One sheet per session (source → target field map)
      Last sheet      : Consolidated Picklist Mappings
    """
    wb = openpyxl.Workbook()

    fill_blue    = PatternFill("solid", fgColor="1453C6")
    fill_green   = PatternFill("solid", fgColor="1A7A3C")
    fill_summary = PatternFill("solid", fgColor="2A3F6F")

    # ── Sheet 1: Summary ──────────────────────────────────────────────────
    ws_sum = wb.active
    ws_sum.title = "Summary"

    sum_headers = [
        "#", "Source Table", "Target Object",
        "Source Field Count", "Src Record Count", "Target Field Count",
        "Field Mappings", "Picklist Mappings", "Duplicate Records",
    ]
    for ci, h in enumerate(sum_headers, 1):
        _header_cell(ws_sum, 1, ci, h, fill_summary)

    ws_sum.column_dimensions["A"].width = 6
    ws_sum.column_dimensions["B"].width = 28
    ws_sum.column_dimensions["C"].width = 28
    ws_sum.column_dimensions["D"].width = 20
    ws_sum.column_dimensions["E"].width = 18
    ws_sum.column_dimensions["F"].width = 20
    ws_sum.column_dimensions["G"].width = 18
    ws_sum.column_dimensions["H"].width = 20
    ws_sum.column_dimensions["I"].width = 20

    # Pre-fetch record counts for all sessions in one connection
    record_counts: dict[str, int] = {}
    try:
        conn = psycopg2.connect(**SOURCE_DB_CONFIG)
        cur = conn.cursor()
        for s in payload.sessions:
            cur.execute(
                pgsql.SQL("SELECT COUNT(*) FROM {tbl}").format(tbl=pgsql.Identifier(s.sourceTable))
            )
            record_counts[s.sourceTable] = cur.fetchone()[0]
        cur.close()
        conn.close()
    except Exception:
        logger.exception("Failed to fetch record counts for summary")

    for i, s in enumerate(payload.sessions, 1):
        field_count = sum(1 for v in s.rowSelections.values() if v)
        picklist_count = sum(
            1 for pm in s.picklistMappings.values() if pm
        )
        ws_sum.append([
            i, s.sourceTable, s.targetObject,
            len(s.sourceColumns), record_counts.get(s.sourceTable, "N/A"), len(s.targetFields),
            field_count, picklist_count,
        ])

    # Collected during per-session loop; back-filled into Summary column I after
    composite_dup_counts: list[int] = []

    # ── Per-session sheets ─────────────────────────────────────────────────
    pair_headers = [
        "#", "Source Table/Reference Table", "Source Field", "Custom Field",
        "Source Data Type", "Sample Record",
        "Target Table/Object", "Target Field", "Target Data Type",
        "Picklist Mapped", "Data Type Match",
    ]

    session_src_picklists: list[dict[str, list[str]]] = []

    for s in payload.sessions:
        # ── Shared DB lookups (reused by both Src Anlys and Mapping sheets) ──
        uuid_cols = [col["name"] for col in s.sourceColumns if col.get("dataType") == "uuid"]
        fk_map = _get_fk_referenced_tables(s.sourceTable, uuid_cols)
        all_col_names = [col["name"] for col in s.sourceColumns]
        stats_map, composite_dup_count = _get_column_stats(s.sourceTable, all_col_names, s.dupCheckFields)
        composite_dup_counts.append(composite_dup_count)
        sample_map = _get_sample_records(s.sourceTable, all_col_names)

        # ── Source Analysis sheet ────────────────────────────────────────────
        anlys_name = f"Src Anlys - {s.sourceTable}"[:31]
        ws_anlys = wb.create_sheet(title=anlys_name)

        anlys_headers = [
            "#", "Source Table/Reference Table", "Source Field", "Custom Field",
            "Source Data Type", "Sample Source Data", "Data Populated %",
        ]
        for ci, h in enumerate(anlys_headers, 1):
            _header_cell(ws_anlys, 1, ci, h, fill_blue)

        ws_anlys.column_dimensions["A"].width = 6
        ws_anlys.column_dimensions["B"].width = 26
        ws_anlys.column_dimensions["C"].width = 30
        ws_anlys.column_dimensions["D"].width = 14
        ws_anlys.column_dimensions["E"].width = 20
        ws_anlys.column_dimensions["F"].width = 26
        ws_anlys.column_dimensions["G"].width = 18

        for anlys_row, col in enumerate(s.sourceColumns, 2):
            col_name = col["name"]
            col_dtype = col["dataType"]
            is_custom = col_name.startswith("do_") and col_name in s.dynamicLabels
            display_name = s.dynamicLabels[col_name] if is_custom else col_name
            is_uuid = col_dtype == "uuid"
            src_table_obj = fk_map.get(col_name, s.sourceTable)
            col_stats = stats_map.get(col_name, {"null": 0, "non_null": 0})
            total = col_stats["null"] + col_stats["non_null"]
            populated_pct = round((col_stats["non_null"] / total) * 100, 2) if total > 0 else 0.0

            ws_anlys.cell(row=anlys_row, column=1, value=anlys_row - 1)
            ws_anlys.cell(row=anlys_row, column=2, value=src_table_obj)
            ws_anlys.cell(row=anlys_row, column=3, value=display_name)
            ws_anlys.cell(row=anlys_row, column=4, value="Yes" if is_custom else "No")
            ws_anlys.cell(row=anlys_row, column=5, value=col_dtype)
            ws_anlys.cell(row=anlys_row, column=6, value=sample_map.get(col_name, "—"))
            ws_anlys.cell(row=anlys_row, column=7, value=populated_pct)

        src_picklist_map = _get_all_source_picklists(s.sourceTable, uuid_cols)
        session_src_picklists.append(src_picklist_map)

        # ── Target Analysis sheet ────────────────────────────────────────────
        tgt_anlys_name = f"Tgt Anlys - {s.targetObject}"[:31]
        ws_tgt = wb.create_sheet(title=tgt_anlys_name)

        tgt_anlys_headers = [
            "#", "Target Table/Object", "Target Field", "Target Data Type",
        ]
        for ci, h in enumerate(tgt_anlys_headers, 1):
            _header_cell(ws_tgt, 1, ci, h, fill_blue)

        ws_tgt.column_dimensions["A"].width = 6
        ws_tgt.column_dimensions["B"].width = 26
        ws_tgt.column_dimensions["C"].width = 30
        ws_tgt.column_dimensions["D"].width = 20

        for tgt_row, tf in enumerate(s.targetFields, 2):
            tgt_dtype = tf.get("dataType", "")
            tgt_table_obj = tf.get("lookupObjectName") if tgt_dtype == "Lookup" else None
            ws_tgt.cell(row=tgt_row, column=1, value=tgt_row - 1)
            ws_tgt.cell(row=tgt_row, column=2, value=tgt_table_obj or s.targetObject)
            ws_tgt.cell(row=tgt_row, column=3, value=tf.get("displayName", tf["name"]))
            ws_tgt.cell(row=tgt_row, column=4, value=tgt_dtype)

        # ── Target Picklist sheet ────────────────────────────────────────────
        tgt_pl_name = f"Tgt Picklist - {s.targetObject}"[:31]
        ws_tgt_pl = wb.create_sheet(title=tgt_pl_name)

        tgt_pl_headers = ["Target Object", "Target Field", "Target Value"]
        for ci, h in enumerate(tgt_pl_headers, 1):
            _header_cell(ws_tgt_pl, 1, ci, h, fill_blue)

        ws_tgt_pl.column_dimensions["A"].width = 26
        ws_tgt_pl.column_dimensions["B"].width = 30
        ws_tgt_pl.column_dimensions["C"].width = 30

        picklist_tgt_fields = [tf for tf in s.targetFields if tf.get("dataType") == "Picklist"]
        tgt_picklist_map = _get_all_target_picklists(s.targetObject, picklist_tgt_fields)
        tgt_pl_row = 2
        for tf in picklist_tgt_fields:
            field_name = tf["name"]
            display_name = tf.get("displayName", field_name)
            values = tgt_picklist_map.get(field_name, [])
            if not values:
                ws_tgt_pl.cell(row=tgt_pl_row, column=1, value=s.targetObject)
                ws_tgt_pl.cell(row=tgt_pl_row, column=2, value=display_name)
                ws_tgt_pl.cell(row=tgt_pl_row, column=3, value="—")
                tgt_pl_row += 1
            else:
                for val in values:
                    ws_tgt_pl.cell(row=tgt_pl_row, column=1, value=s.targetObject)
                    ws_tgt_pl.cell(row=tgt_pl_row, column=2, value=display_name)
                    ws_tgt_pl.cell(row=tgt_pl_row, column=3, value=val)
                    tgt_pl_row += 1

        # ── Mapping sheet ────────────────────────────────────────────────────
        raw_name = f"{s.sourceTable} to {s.targetObject}"
        sheet_name = raw_name[:31]
        ws = wb.create_sheet(title=sheet_name)

        for ci, h in enumerate(pair_headers, 1):
            _header_cell(ws, 1, ci, h, fill_blue)

        ws.column_dimensions["A"].width = 6
        ws.column_dimensions["B"].width = 26
        ws.column_dimensions["C"].width = 30
        ws.column_dimensions["D"].width = 14  # Custom Field
        ws.column_dimensions["E"].width = 20  # Source Data Type
        ws.column_dimensions["F"].width = 26  # Sample Record
        ws.column_dimensions["G"].width = 26
        ws.column_dimensions["H"].width = 30
        ws.column_dimensions["I"].width = 20
        ws.column_dimensions["J"].width = 18
        ws.column_dimensions["K"].width = 16

        target_lookup: dict[str, dict] = {f["name"]: f for f in s.targetFields}

        row_num = 2
        serial = 1

        # Only mapped rows (source column has a target field selected)
        for col in s.sourceColumns:
            col_name: str = col["name"]
            target_field_name = s.rowSelections.get(col_name, "")
            if not target_field_name:
                continue

            col_dtype: str = col["dataType"]
            is_custom = col_name.startswith("do_") and col_name in s.dynamicLabels
            display_name = s.dynamicLabels[col_name] if is_custom else col_name

            is_uuid = col_dtype == "uuid"
            src_table_obj = fk_map.get(col_name, s.sourceTable)

            tf = target_lookup.get(target_field_name, {})
            target_display = tf.get("displayName", target_field_name)
            target_dtype   = tf.get("dataType", "")
            tgt_table_obj  = tf.get("lookupObjectName") if target_dtype == "Lookup" else None

            pm = s.picklistMappings.get(col_name, {})
            if not is_uuid:
                picklist_cell = "N/A"
            elif pm:
                picklist_cell = "Yes"
            else:
                picklist_cell = "No"

            ws.cell(row=row_num, column=1,  value=serial)
            ws.cell(row=row_num, column=2,  value=src_table_obj)
            ws.cell(row=row_num, column=3,  value=display_name)
            ws.cell(row=row_num, column=4,  value="Yes" if is_custom else "No")
            ws.cell(row=row_num, column=5,  value=col_dtype)
            ws.cell(row=row_num, column=6,  value=sample_map.get(col_name, "—"))
            ws.cell(row=row_num, column=7,  value=tgt_table_obj or s.targetObject)
            ws.cell(row=row_num, column=8,  value=target_display)
            ws.cell(row=row_num, column=9,  value=target_dtype)
            ws.cell(row=row_num, column=10, value=picklist_cell)
            ws.cell(row=row_num, column=11, value=_data_type_match(col_dtype, target_dtype))
            row_num += 1
            serial += 1

    # ── Back-fill Summary column I with composite duplicate counts ──────────
    for idx, dup_count in enumerate(composite_dup_counts, 2):  # row 2 onwards (row 1 = header)
        ws_sum.cell(row=idx, column=9, value=dup_count if dup_count > 0 else 0)

    # ── Last sheet: Picklist Mappings ──────────────────────────────────────
    ws_pl = wb.create_sheet(title="Picklist Mappings")
    pl_headers = [
        "Source Table", "Source Field", "Source Value",
        "Target Object", "Target Field", "Target Child Value", "Target Parent Value",
    ]
    for ci, h in enumerate(pl_headers, 1):
        _header_cell(ws_pl, 1, ci, h, fill_green)

    for col_letter, width in zip("ABCDEFG", [22, 26, 26, 22, 26, 26, 26]):
        ws_pl.column_dimensions[col_letter].width = width

    pl_row = 2
    for s, src_picklist_map in zip(payload.sessions, session_src_picklists):
        target_lookup = {f["name"]: f for f in s.targetFields}
        for col in s.sourceColumns:
            if col.get("dataType") != "uuid":
                continue
            col_name = col["name"]
            values = src_picklist_map.get(col_name, [])
            if not values:
                continue
            is_custom = col_name.startswith("do_") and col_name in s.dynamicLabels
            display_name = s.dynamicLabels[col_name] if is_custom else col_name
            target_field_name = s.rowSelections.get(col_name, "")
            tf = target_lookup.get(target_field_name, {})
            target_display = tf.get("displayName", target_field_name) if target_field_name else ""
            picklist_map = s.picklistMappings.get(col_name, {})
            for src_val in values:
                child_val = picklist_map.get(src_val, "")
                parent_key = f"__parent__{src_val}"
                # Dependent mapping: has a stored parent key
                if parent_key in picklist_map:
                    parent_val = picklist_map[parent_key]
                    tgt_parent = parent_val
                    tgt_child = child_val
                else:
                    # Standard (non-dependent) mapping
                    tgt_parent = ""
                    tgt_child = child_val
                ws_pl.cell(row=pl_row, column=1, value=s.sourceTable)
                ws_pl.cell(row=pl_row, column=2, value=display_name)
                ws_pl.cell(row=pl_row, column=3, value=src_val)
                ws_pl.cell(row=pl_row, column=4, value=s.targetObject)
                ws_pl.cell(row=pl_row, column=5, value=target_display)
                ws_pl.cell(row=pl_row, column=6, value=tgt_child)
                ws_pl.cell(row=pl_row, column=7, value=tgt_parent)
                pl_row += 1

    # ── Stream the workbook ────────────────────────────────────────────────
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="metadata_mapping.xlsx"'},
    )
