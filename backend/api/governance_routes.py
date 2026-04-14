"""
Governance Project Routes
CRUD endpoints for Data Governance projects and their phase records.
Uses the shared PostgreSQL DB defined in backend/pm_agent/models.py.
"""
import io
import os
import sys
import ssl
import uuid
import logging
import smtplib
import threading
from pathlib import Path
from typing import Optional, List
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import quote

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session
from openpyxl import load_workbook
from openpyxl.styles import Font
import os

# Resolve pm_agent models from the sibling directory
_PM_AGENT_PATH = Path(__file__).parent.parent / "pm_agent"

# Load pm_agent .env so DATABASE_URL is available before importing models
from dotenv import load_dotenv
load_dotenv(_PM_AGENT_PATH / ".env")

try:
    from pm_agent.models import SessionLocal, GovernanceProject, GovernanceProjectPhase, Base, engine  # type: ignore[import-untyped]
except Exception as _import_err:
    raise RuntimeError(
        f"governance_routes: failed to import pm_agent models. "
        f"Ensure DATABASE_URL is set and pm_agent/.env exists. Error: {_import_err}"
    ) from _import_err

from services.gdrive_service import upload_bytes_to_folder, create_shareable_link

logger = logging.getLogger(__name__)

# Ensure tables exist on startup
try:
    Base.metadata.create_all(
        bind=engine,
        tables=[GovernanceProject.__table__, GovernanceProjectPhase.__table__]
    )
except Exception as _e:
    logger.warning("governance_routes: could not run create_all on startup: %s", _e)

# Add new columns to existing tables if they don't exist yet
try:
    with engine.connect() as _conn:
        for _col, _type in [("subphase", "VARCHAR"), ("gate_check", "VARCHAR"), ("comments", "TEXT"), ("actual_date", "VARCHAR")]:
            try:
                _conn.execute(text(f"ALTER TABLE governance_project_phases ADD COLUMN {_col} {_type}"))
                _conn.commit()
            except Exception:
                _conn.rollback()
except Exception as _e:
    logger.warning("governance_routes: could not run column migrations on startup: %s", _e)

try:
    with engine.connect() as _conn:
        try:
            _conn.execute(text("ALTER TABLE governance_projects ADD COLUMN is_active BOOLEAN DEFAULT TRUE"))
            _conn.commit()
            logger.info("governance_routes: added is_active column to governance_projects")
        except Exception:
            _conn.rollback()
except Exception as _e:
    logger.warning("governance_routes: could not add is_active column: %s", _e)

# Templates live in the frontend's public/templates folder
_TEMPLATES_DIR = Path(__file__).parent.parent.parent / "dataAgent" / "frontend" / "public" / "templates"

router = APIRouter(tags=["Governance"], prefix="/api/governance")

# Super admin emails from env (comma-separated)
_SUPER_ADMINS = {
    e.strip().lower()
    for e in os.getenv("GOVERNANCE_SUPER_ADMINS", "").split(",")
    if e.strip()
}

def _is_super_admin(email: str) -> bool:
    return email.strip().lower() in _SUPER_ADMINS


def _notify_super_admins_new_project(project_name: str, project_type: str, created_by: str):
    """Send a notification email to all super admins when a new project is created."""
    if not _SUPER_ADMINS:
        return
    smtp_host     = os.getenv("SMTP_HOST", "")
    smtp_port     = int(os.getenv("SMTP_PORT", "587"))
    smtp_user     = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    mail_from     = os.getenv("MAIL_FROM", smtp_user)

    if not smtp_host or not smtp_user or not smtp_password:
        logger.warning("SMTP not configured — skipping new project notification.")
        return

    type_label = "Data Integration" if project_type == "DI" else "Data Migration"
    subject = f"[New Project] {project_name} ({type_label}) created by {created_by}"
    html_body = f"""
    <html><body style="font-family:Arial,sans-serif;color:#1a2b50;">
      <p>Hi,</p>
      <p>A new data governance project has been created:</p>
      <table style="border-collapse:collapse;margin-top:12px;">
        <tr>
          <td style="padding:8px 16px;border:1px solid #dde3f0;font-weight:600;background:#f4f7ff;">Project Name</td>
          <td style="padding:8px 16px;border:1px solid #dde3f0;">{project_name}</td>
        </tr>
        <tr>
          <td style="padding:8px 16px;border:1px solid #dde3f0;font-weight:600;background:#f4f7ff;">Project Type</td>
          <td style="padding:8px 16px;border:1px solid #dde3f0;">{type_label}</td>
        </tr>
        <tr>
          <td style="padding:8px 16px;border:1px solid #dde3f0;font-weight:600;background:#f4f7ff;">Created By</td>
          <td style="padding:8px 16px;border:1px solid #dde3f0;">{created_by}</td>
        </tr>
      </table>
      <p style="color:#6b7a9d;font-size:0.85rem;margin-top:20px;">
        This is an automated notification from the Data Project Governance system.
      </p>
    </body></html>
    """

    def _send():
        try:
            cc_list = list(_SUPER_ADMINS)
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = mail_from
            msg["To"]      = created_by
            if cc_list:
                msg["Cc"] = ", ".join(cc_list)
            msg.attach(MIMEText(html_body, "html"))
            recipients = [created_by] + cc_list
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(smtp_user, smtp_password)
                server.sendmail(mail_from, recipients, msg.as_string())
            logger.info("New project notification sent to %s (cc: %s) for: %s", created_by, cc_list, project_name)
        except Exception:
            logger.exception("Failed to send new project notification.")

    threading.Thread(target=_send, daemon=True).start()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()




# Test trigger endpoints (for manual testing only)
@router.post("/test-overdue-check")
def trigger_overdue_check():
    """Manually trigger the overdue check — for testing only."""
    try:
        from api.governance_scheduler import check_overdue_phases
        check_overdue_phases()
        return {"status": "ok", "message": "Overdue check ran. Check server logs and your inbox."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/test-incomplete-check")
def trigger_incomplete_check():
    """Manually trigger the hourly incomplete-project reminder — for testing only."""
    try:
        from api.governance_scheduler import check_incomplete_projects
        check_incomplete_projects()
        return {"status": "ok", "message": "Incomplete-project check ran. Check server logs and your inbox."}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ─── Pydantic Schemas ─────────────────────────────────────────────────────────

class ProjectPayload(BaseModel):
    user_email: str
    project_name: str
    project_type: str


class PhaseRecord(BaseModel):
    id: Optional[str] = None
    phase: Optional[str] = None
    subphase: Optional[str] = None
    gate_check: Optional[str] = None
    status: Optional[str] = None
    comments: Optional[str] = None
    planned_date: Optional[str] = None
    actual_date: Optional[str] = None
    document_link: Optional[str] = None


class BulkPhasesPayload(BaseModel):
    phases: List[PhaseRecord]


# ─── Helpers ──────────────────────────────────────────────────────────────────

def project_to_dict(p: GovernanceProject) -> dict:
    return {
        "id": p.id,
        "user_email": p.user_email,
        "project_name": p.project_name,
        "project_type": p.project_type,
        "is_active": p.is_active if p.is_active is not None else True,
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
    }


def phase_to_dict(p: GovernanceProjectPhase) -> dict:
    return {
        "id": p.id,
        "project_id": p.project_id,
        "phase": p.phase,
        "subphase": p.subphase,
        "gate_check": p.gate_check,
        "status": p.status,
        "comments": p.comments,
        "planned_date": p.planned_date,
        "actual_date": p.actual_date,
        "document_link": p.document_link,
    }


def _find_header_row(ws, keywords=None) -> tuple:
    """
    Scan the worksheet for the header row.
    Returns (row_index, {normalised_header: column_index}) or (None, {}).
    Normalises by lowercasing and stripping whitespace.
    """
    if keywords is None:
        keywords = {"phase", "status", "planned date", "document link"}
    for row in ws.iter_rows():
        row_map = {}
        for cell in row:
            if cell.value:
                norm = str(cell.value).strip().lower()
                if norm in keywords:
                    row_map[norm] = cell.column
        if len(row_map) >= 2:          # at least 2 matching headers → this is the header row
            return row[0].row, row_map
    return None, {}


def _extract_status_from_validation(ws) -> List[str]:
    """
    Read the data validation on the status column and return its allowed values.
    Handles both inline lists ("v1,v2,v3") and named-range references.
    """
    for dv in ws.data_validations.dataValidation:
        if dv.type != "list":
            continue
        formula = (dv.formula1 or "").strip().strip('"')
        if not formula:
            continue

        # Inline list: "Not Started,In Progress,Complete"
        if "!" not in formula and "$" not in formula:
            return [v.strip() for v in formula.split(",") if v.strip()]

        # Range reference: Sheet2!$A$1:$A$10  — read from workbook
        try:
            if "!" in formula:
                sheet_name, cell_range = formula.split("!", 1)
                sheet_name = sheet_name.strip("'")
            else:
                sheet_name = ws.title
                cell_range = formula

            ref_ws = ws.parent[sheet_name]
            values = []
            for row in ref_ws[cell_range]:
                for cell in (row if hasattr(row, "__iter__") else [row]):
                    if cell.value:
                        values.append(str(cell.value).strip())
            if values:
                return values
        except Exception:
            pass

    return []


def _build_filled_workbook(project: GovernanceProject, phases, templates_dir: Path) -> bytes:
    """
    Opens the governance template for the project's type, fills in the phase data
    from the supplied phases list, and returns the workbook as xlsx bytes.
    """
    def _norm(*parts):
        return tuple((p or "").strip().lower() for p in parts)

    # Key by (phase, subphase) — gate_check is informational only, not user-editable
    record_map = {_norm(p.phase, p.subphase): p for p in phases}

    template_path = templates_dir / f"governance_template_{project.project_type}.xlsx"
    if not template_path.exists():
        template_path = templates_dir / "governance_template.xlsx"
    if not template_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"Template file not found. Place governance_template_{project.project_type}.xlsx "
                f"(or governance_template.xlsx) in dataAgent/frontend/public/templates/."
            ),
        )

    wb = load_workbook(str(template_path))
    ws = wb[project.project_type] if project.project_type in wb.sheetnames else wb.active

    all_keywords = {"phase", "sub-phase", "gate check/review session", "status", "planned date", "actual date", "comments", "document link"}
    header_row_idx, col_map = _find_header_row(ws, keywords=all_keywords)
    if header_row_idx is None:
        raise HTTPException(status_code=422, detail="Could not find column headers in template.")

    phase_col        = col_map.get("phase")
    subphase_col     = col_map.get("sub-phase")
    gate_check_col   = col_map.get("gate check/review session")
    status_col       = col_map.get("status")
    planned_date_col = col_map.get("planned date")
    actual_date_col  = col_map.get("actual date")
    comments_col     = col_map.get("comments")
    doc_link_col     = col_map.get("document link")

    if phase_col is None:
        buffer = io.BytesIO()
        wb.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()

    current_phase = ""
    current_subphase = ""

    for row_idx in range(header_row_idx + 1, ws.max_row + 1):
        def _val(col, row_idx=row_idx):
            if col is None:
                return ""
            v = ws.cell(row=row_idx, column=col).value
            return str(v).strip() if v else ""

        p  = _val(phase_col)
        sp = _val(subphase_col)
        gc = _val(gate_check_col)

        # Skip completely blank rows
        if not p and not sp and not gc:
            continue

        if p:
            current_phase = p
        if sp:
            current_subphase = sp

        record = record_map.get(_norm(current_phase, current_subphase))
        if record is None:
            continue

        if status_col and record.status:
            ws.cell(row=row_idx, column=status_col).value = record.status
        if planned_date_col and record.planned_date:
            ws.cell(row=row_idx, column=planned_date_col).value = record.planned_date
        if actual_date_col and record.actual_date:
            ws.cell(row=row_idx, column=actual_date_col).value = record.actual_date
        if comments_col and record.comments:
            ws.cell(row=row_idx, column=comments_col).value = record.comments
        if doc_link_col and record.document_link:
            ws.cell(row=row_idx, column=doc_link_col).value = record.document_link

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()


# ─── Picklist endpoint ────────────────────────────────────────────────────────

@router.get("/templates/{project_type}/picklists")
def get_template_picklists(project_type: str):
    """
    Opens the governance template for the given project type and extracts:
    - Distinct Phase values from the Phase column
    - Distinct Subphase values from the Subphase column
    - Distinct Gate Check/Review Session values from that column
    - Status allowed values from the cell data validation on that column
    """
    template_path = _TEMPLATES_DIR / f"governance_template_{project_type}.xlsx"
    if not template_path.exists():
        template_path = _TEMPLATES_DIR / "governance_template.xlsx"
    if not template_path.exists():
        raise HTTPException(status_code=404, detail="Template not found.")

    wb = load_workbook(str(template_path), data_only=True)
    ws = wb[project_type] if project_type in wb.sheetnames else wb.active

    all_keywords = {"phase", "sub-phase", "gate check/review session", "status", "planned date", "document link"}
    header_row_idx, col_map = _find_header_row(ws, keywords=all_keywords)

    if header_row_idx is None:
        return {"phases": [], "subphases_by_phase": {}, "gate_checks_by_subphase": {}, "statuses": []}

    phase_col      = col_map.get("phase")
    subphase_col   = col_map.get("sub-phase")
    gate_check_col = col_map.get("gate check/review session")
    status_col     = col_map.get("status")

    phases = []
    seen_phases = set()
    subphases_by_phase: dict = {}          # { phase: [subphase, ...] }
    gate_checks_by_subphase: dict = {}     # { subphase: [gate_check, ...] }
    template_rows: list = []               # flat ordered list for pre-population

    current_phase = ""
    current_subphase = ""

    for row_idx in range(header_row_idx + 1, ws.max_row + 1):
        def _val(col, row_idx=row_idx):
            if col is None:
                return ""
            v = ws.cell(row=row_idx, column=col).value
            return str(v).strip() if v else ""

        p  = _val(phase_col)
        sp = _val(subphase_col)
        gc = _val(gate_check_col)

        # Update running context (cells may be blank on continuation rows)
        if p:
            current_phase = p
            if p not in seen_phases:
                phases.append(p)
                seen_phases.add(p)
            if p not in subphases_by_phase:
                subphases_by_phase[p] = []

        if sp and current_phase:
            current_subphase = sp
            bucket = subphases_by_phase.setdefault(current_phase, [])
            if sp not in bucket:
                bucket.append(sp)
            if sp not in gate_checks_by_subphase:
                gate_checks_by_subphase[sp] = []

        if gc and current_subphase:
            bucket = gate_checks_by_subphase.setdefault(current_subphase, [])
            if gc not in bucket:
                bucket.append(gc)

        # Collect a flat row for pre-population (only rows with actual data)
        if current_phase and (p or sp or gc):
            template_rows.append({
                "phase": current_phase,
                "subphase": current_subphase,
                "gate_check": gc,
            })

    # Status comes from data validation
    statuses = []
    if status_col:
        statuses = _extract_status_from_validation(ws)

    return {
        "phases": phases,
        "subphases_by_phase": subphases_by_phase,
        "gate_checks_by_subphase": gate_checks_by_subphase,
        "statuses": statuses,
        "template_rows": template_rows,
    }


# ─── Project endpoints ────────────────────────────────────────────────────────

@router.get("/is-super-admin")
def check_super_admin(email: str = Query(...)):
    return {"is_super_admin": _is_super_admin(email)}


@router.get("/projects")
def list_projects(email: str = Query(...), db: Session = Depends(get_db)):
    if _is_super_admin(email):
        projects = (
            db.query(GovernanceProject)
            .order_by(GovernanceProject.created_at.desc())
            .all()
        )
    else:
        projects = (
            db.query(GovernanceProject)
            .filter(GovernanceProject.user_email == email)
            .order_by(GovernanceProject.created_at.desc())
            .all()
        )
    return [project_to_dict(p) for p in projects]


@router.post("/projects", status_code=201)
def create_project(payload: ProjectPayload, db: Session = Depends(get_db)):
    project = GovernanceProject(
        id=str(uuid.uuid4()),
        user_email=payload.user_email,
        project_name=payload.project_name,
        project_type=payload.project_type,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    _notify_super_admins_new_project(project.project_name, project.project_type, project.user_email)
    return project_to_dict(project)


@router.put("/projects/{project_id}")
def update_project(project_id: str, payload: ProjectPayload, db: Session = Depends(get_db)):
    project = (
        db.query(GovernanceProject)
        .filter(GovernanceProject.id == project_id, GovernanceProject.user_email == payload.user_email)
        .first()
    )
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    project.project_name = payload.project_name
    project.project_type = payload.project_type
    project.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(project)
    return project_to_dict(project)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: str, email: str = Query(...), db: Session = Depends(get_db)):
    query = db.query(GovernanceProject).filter(GovernanceProject.id == project_id)
    if not _is_super_admin(email):
        query = query.filter(GovernanceProject.user_email == email)
    project = query.first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    db.delete(project)
    db.commit()


@router.patch("/projects/{project_id}/toggle-status")
def toggle_project_status(
    project_id: str,
    email: str = Query(...),
    db: Session = Depends(get_db),
):
    if not _is_super_admin(email):
        raise HTTPException(status_code=403, detail="Super admin access required.")
    project = db.query(GovernanceProject).filter(GovernanceProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    current = project.is_active if project.is_active is not None else True
    project.is_active = not current
    db.commit()
    db.refresh(project)
    return {"id": project.id, "is_active": project.is_active}


# ─── Mail to owner ────────────────────────────────────────────────────────────

class MailOwnerPayload(BaseModel):
    email: str      # super admin's email (for auth check)
    message: str    # custom body text from popup


@router.post("/projects/{project_id}/mail-owner")
def mail_project_owner(project_id: str, payload: MailOwnerPayload, db: Session = Depends(get_db)):
    if not _is_super_admin(payload.email):
        raise HTTPException(status_code=403, detail="Super admin access required.")

    project = db.query(GovernanceProject).filter(GovernanceProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    owner_email  = project.user_email
    project_name = project.project_name
    status_label = "Active" if (project.is_active is None or project.is_active) else "Inactive"
    message_text = payload.message

    smtp_host     = os.getenv("SMTP_HOST", "")
    smtp_port     = int(os.getenv("SMTP_PORT", "587"))
    smtp_user     = os.getenv("SMTP_USER", "")
    smtp_password = os.getenv("SMTP_PASSWORD", "")
    mail_from     = os.getenv("MAIL_FROM", smtp_user)

    if not smtp_host or not smtp_user or not smtp_password:
        raise HTTPException(status_code=503, detail="SMTP not configured on the server.")

    subject   = f"{project_name} - {status_label}"
    cc_list   = list(_SUPER_ADMINS)
    body_html = f"""
    <html><body style="font-family:Arial,sans-serif;color:#1a2b50;line-height:1.6;">
      <p>Dear Project Manager,</p>
      <p>{message_text.replace(chr(10), '<br>')}</p>
      <p style="margin-top:24px;">Kind regards,<br><strong>COE</strong></p>
    </body></html>
    """

    def _send():
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"]    = mail_from
            msg["To"]      = owner_email
            if cc_list:
                msg["Cc"] = ", ".join(cc_list)
            msg.attach(MIMEText(body_html, "html"))
            recipients = [owner_email] + cc_list
            context = ssl.create_default_context()
            with smtplib.SMTP(smtp_host, smtp_port) as server:
                server.ehlo()
                server.starttls(context=context)
                server.login(smtp_user, smtp_password)
                server.sendmail(mail_from, recipients, msg.as_string())
            logger.info("Mail to owner sent: project=%s to=%s", project_name, owner_email)
        except Exception:
            logger.exception("Failed to send mail-to-owner for project %s", project_name)

    threading.Thread(target=_send, daemon=True).start()
    return {"status": "ok", "message": "Email queued."}


# ─── Phase endpoints ──────────────────────────────────────────────────────────

@router.get("/projects/{project_id}/phases")
def list_phases(project_id: str, db: Session = Depends(get_db)):
    phases = (
        db.query(GovernanceProjectPhase)
        .filter(GovernanceProjectPhase.project_id == project_id)
        .order_by(GovernanceProjectPhase.created_at)
        .all()
    )
    return [phase_to_dict(p) for p in phases]


@router.post("/projects/{project_id}/phases/bulk", status_code=200)
def bulk_save_phases(project_id: str, payload: BulkPhasesPayload, db: Session = Depends(get_db)):
    project = db.query(GovernanceProject).filter(GovernanceProject.id == project_id).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    db.query(GovernanceProjectPhase).filter(GovernanceProjectPhase.project_id == project_id).delete()

    now = datetime.now(timezone.utc)
    for record in payload.phases:
        phase = GovernanceProjectPhase(
            id=record.id or str(uuid.uuid4()),
            project_id=project_id,
            phase=record.phase,
            subphase=record.subphase,
            gate_check=record.gate_check,
            status=record.status,
            comments=record.comments,
            planned_date=record.planned_date,
            actual_date=record.actual_date,
            document_link=record.document_link,
            created_at=now,
            updated_at=now,
        )
        db.add(phase)

    db.commit()
    return {"message": "Phases saved.", "count": len(payload.phases)}


# ─── Download filled template ─────────────────────────────────────────────────

@router.get("/projects/{project_id}/download")
def download_filled_template(project_id: str, email: str = Query(...), db: Session = Depends(get_db)):
    """
    Opens the governance template for the project's type, fills in the phase data
    from the DB, and streams the filled workbook as an xlsx download.
    """
    query = db.query(GovernanceProject).filter(GovernanceProject.id == project_id)
    if not _is_super_admin(email):
        query = query.filter(GovernanceProject.user_email == email)
    project = query.first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    phases = (
        db.query(GovernanceProjectPhase)
        .filter(GovernanceProjectPhase.project_id == project_id)
        .all()
    )

    xlsx_bytes = _build_filled_workbook(project, phases, _TEMPLATES_DIR)

    filename = f"{project.project_name}_{project.project_type}.xlsx"
    encoded_name = quote(filename)

    return StreamingResponse(
        io.BytesIO(xlsx_bytes),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename=\"{filename}\"; filename*=UTF-8''{encoded_name}"
        },
    )


# ─── Upload filled template to Google Drive ───────────────────────────────────

@router.post("/projects/{project_id}/upload-to-drive")
def upload_to_drive(project_id: str, email: str = Query(...), db: Session = Depends(get_db)):
    """
    Builds the filled workbook (same as /download) and uploads it to the user's
    Google Drive. Returns a shareable link.
    """
    query = db.query(GovernanceProject).filter(GovernanceProject.id == project_id)
    if not _is_super_admin(email):
        query = query.filter(GovernanceProject.user_email == email)
    project = query.first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    phases = (
        db.query(GovernanceProjectPhase)
        .filter(GovernanceProjectPhase.project_id == project_id)
        .all()
    )

    xlsx_bytes = _build_filled_workbook(project, phases, _TEMPLATES_DIR)

    filename = f"{project.project_name}_{project.project_type}.xlsx"

    uploaded = upload_bytes_to_folder(
        folder_id=None,
        filename=filename,
        data_bytes=xlsx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        email=email,
    )

    file_url = create_shareable_link(uploaded["id"], email)

    logger.info("Governance file uploaded to Drive for %s: %s", email, filename)

    return {"file_url": file_url, "filename": filename}