"""
Governance Overdue Alert Scheduler
Runs daily and emails project owners when phase records are past their planned date
without an actual date filled and without a terminal status.
"""
import os
import sys
import logging
import smtplib
import ssl
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

# ─── Resolved paths ───────────────────────────────────────────────────────────
_PM_AGENT_PATH = Path(__file__).parent.parent / "pm_agent"
_PM_AGENT_DIR = str(_PM_AGENT_PATH)
if _PM_AGENT_DIR not in sys.path:
    sys.path.insert(0, _PM_AGENT_DIR)

from pm_agent.models import SessionLocal, GovernanceProject, GovernanceProjectPhase  # type: ignore[import-untyped]

# ─── Statuses that are considered "done" — skip these ─────────────────────────
TERMINAL_STATUSES = {"under review", "signed off"}

# ─── Email config from environment ────────────────────────────────────────────
SMTP_HOST     = os.getenv("SMTP_HOST", "")
SMTP_PORT     = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER     = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
MAIL_FROM     = os.getenv("MAIL_FROM", SMTP_USER)
# Comma-separated CC list — user will fill these in later
CC_EMAILS     = [e.strip() for e in os.getenv("GOVERNANCE_CC_EMAILS", "").split(",") if e.strip()]


def _parse_date(val: str | None) -> date | None:
    """Try common date formats and return a date object, or None."""
    if not val:
        return None
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(val.strip(), fmt).date()
        except ValueError:
            continue
    return None


def _build_html_body(project_name: str, project_type: str, overdue_rows: list) -> str:
    rows_html = ""
    for r in overdue_rows:
        days_over = (date.today() - r["planned_date"]).days
        rows_html += f"""
        <tr>
          <td style="padding:8px 12px;border:1px solid #dde3f0;">{r['phase'] or '—'}</td>
          <td style="padding:8px 12px;border:1px solid #dde3f0;">{r['subphase'] or '—'}</td>
          <td style="padding:8px 12px;border:1px solid #dde3f0;">{r['planned_date'].strftime('%d %b %Y')}</td>
          <td style="padding:8px 12px;border:1px solid #dde3f0;color:#c0392b;font-weight:600;">{days_over} day(s)</td>
          <td style="padding:8px 12px;border:1px solid #dde3f0;">{r['status'] or 'Not Started'}</td>
        </tr>"""

    return f"""
    <html><body style="font-family:Arial,sans-serif;color:#1a2b50;">
      <p>Hi,</p>
      <p>The following phases in project <strong>{project_name}</strong>
         ({project_type}) are <span style="color:#c0392b;font-weight:600;">overdue</span>
         — their planned date has passed without an actual completion date.</p>
      <table style="border-collapse:collapse;width:100%;margin-top:12px;">
        <thead>
          <tr style="background:#1453c6;color:white;">
            <th style="padding:10px 12px;text-align:left;">Phase</th>
            <th style="padding:10px 12px;text-align:left;">Sub-Phase</th>
            <th style="padding:10px 12px;text-align:left;">Planned Date</th>
            <th style="padding:10px 12px;text-align:left;">Days Overdue</th>
            <th style="padding:10px 12px;text-align:left;">Status</th>
          </tr>
        </thead>
        <tbody>{rows_html}</tbody>
      </table>
      <p style="margin-top:20px;">Please review and update the project status accordingly.</p>
      <p style="color:#6b7a9d;font-size:0.85rem;">This is an automated alert from the Data Project Governance system.</p>
    </body></html>
    """


def _send_email(to: str, subject: str, html_body: str):
    if not SMTP_HOST or not SMTP_USER or not SMTP_PASSWORD:
        logger.warning("SMTP not configured — skipping email to %s", to)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = MAIL_FROM
    msg["To"]      = to
    if CC_EMAILS:
        msg["Cc"] = ", ".join(CC_EMAILS)

    msg.attach(MIMEText(html_body, "html"))

    recipients = [to] + CC_EMAILS
    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.ehlo()
            server.starttls(context=context)
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.sendmail(MAIL_FROM, recipients, msg.as_string())
        logger.info("Overdue alert sent to %s (cc: %s) for subject: %s", to, CC_EMAILS, subject)
    except Exception:
        logger.exception("Failed to send overdue alert email to %s", to)


def check_overdue_phases():
    """
    Query all governance phase records that are:
      - Not in a terminal status (Under Review / Signed Off)
      - Missing an actual date
      - Planned date was at least 1 day ago
    Group by project and send one email per project to the project owner.
    """
    today = date.today()
    db = SessionLocal()
    try:
        phases = (
            db.query(GovernanceProjectPhase, GovernanceProject)
            .join(GovernanceProject, GovernanceProjectPhase.project_id == GovernanceProject.id)
            .filter(
                (GovernanceProjectPhase.actual_date.is_(None)) |
                (GovernanceProjectPhase.actual_date == "")
            )
            .filter(
                GovernanceProjectPhase.planned_date.isnot(None) &
                (GovernanceProjectPhase.planned_date != "")
            )
            .all()
        )

        # Group overdue rows by project
        project_map: dict[str, dict] = {}
        logger.info("Found phases: %d", len(phases))
        for phase, project in phases:
            # Skip terminal statuses
            if (phase.status or "").strip().lower() in TERMINAL_STATUSES:
                continue

            planned = _parse_date(phase.planned_date)
            if planned is None:
                continue

            # Must be at least 1 full day past planned date
            if (today - planned).days < 1:
                continue

            pid = project.id
            if pid not in project_map:
                project_map[pid] = {
                    "project_name": project.project_name,
                    "project_type": project.project_type,
                    "user_email":   project.user_email,
                    "rows": [],
                }
            project_map[pid]["rows"].append({
                "phase":        phase.phase,
                "subphase":     phase.subphase,
                "planned_date": planned,
                "status":       phase.status,
            })

        if not project_map:
            logger.info("Governance overdue check: no overdue records found.")
            return

        for pid, data in project_map.items():
            n = len(data["rows"])
            subject = f"[Overdue] {data['project_name']} — {n} phases{'s' if n > 1 else ''} past planned date"
            html    = _build_html_body(data["project_name"], data["project_type"], data["rows"])
            _send_email(data["user_email"], subject, html)

        logger.info("Governance overdue check complete. Emails sent for %d project(s).", len(project_map))

    except Exception:
        logger.exception("Error during governance overdue check.")
    finally:
        db.close()


# ─── Scheduler singleton ──────────────────────────────────────────────────────

scheduler = AsyncIOScheduler()


def start_scheduler():
    """Start the daily overdue check. Runs every day at 09:00 server time."""
    scheduler.add_job(
        check_overdue_phases,
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=0),
        id="governance_overdue_check",
        name="Governance Overdue Phase Alert",
        replace_existing=True,
        misfire_grace_time=3600,   # run even if server was down for up to 1 hour
    )
    scheduler.start()
    logger.info("Governance overdue scheduler started — runs every Monday at 09:00.")


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("Governance overdue scheduler stopped.")