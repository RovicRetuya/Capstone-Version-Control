"""The "Report a problem" form: POST /api/problem-report.

Anyone may send a report, signed in or not. It is kept in the accounts database (table `problem_reports`) and the admin
reads it on the admin page (admin_api.py: GET /api/admin/reports), marking each one handled when it has been dealt
with. Without the admin page it can be read with:
    SELECT created_at, category, message, email, page, status FROM problem_reports ORDER BY id DESC;
Each connection may send a few reports an hour, so the form cannot be used to fill the database.

Each report is also emailed to REPORT_TO (DEFAKETIVE_REPORT_TO changes it). Sending needs a mail account, set with
DEFAKETIVE_SMTP_HOST, DEFAKETIVE_SMTP_USER and DEFAKETIVE_SMTP_PASSWORD (and DEFAKETIVE_SMTP_PORT, default 587, which
starts TLS; 465 uses SSL; DEFAKETIVE_SMTP_FROM, default the user). Without them nothing is emailed, the report is
still saved, and one line in the log says so.
"""

from __future__ import annotations

import logging
import os
import smtplib
import ssl
import threading
import time
from email.message import EmailMessage
from typing import Any

from flask import current_app, jsonify, request

import protections

CATEGORIES = ("wrong-result", "scan-problem", "display-bug", "account", "other")
MAX_MESSAGE = 2000
MIN_MESSAGE = 10
MAX_EMAIL = 200
MAX_PAGE = 300
PER_HOUR = 5
REPORT_TO = "23ur0560@psu.edu.ph"
LABELS = {"wrong-result": "A result looks wrong", "scan-problem": "A scan failed or got stuck",
          "display-bug": "Something looks or works broken", "account": "Sign in or account", "other": "Something else"}
log = logging.getLogger("defaketive.problem_reports")

SCHEMA = """
CREATE TABLE IF NOT EXISTS problem_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    category TEXT NOT NULL,
    message TEXT NOT NULL,
    email TEXT NOT NULL DEFAULT '',
    page TEXT NOT NULL DEFAULT '',
    user_id INTEGER,
    status TEXT NOT NULL DEFAULT 'new'
);
"""
STATUSES = ("new", "done")  # new: nobody has dealt with it yet; done: the admin marked it handled
LIST_LIMIT = 200


def ensure_schema(connection: Any) -> None:
    """The table, and its `status` column on a database that had the table before reports had a status."""
    connection.executescript(SCHEMA)
    if "status" not in {row[1] for row in connection.execute("PRAGMA table_info(problem_reports)")}:
        connection.execute("ALTER TABLE problem_reports ADD COLUMN status TEXT NOT NULL DEFAULT 'new'")


def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def list_reports(connection: Any, status: str = "all", category: str = "", query: str = "", limit: int = LIST_LIMIT) -> dict[str, Any]:
    """The newest reports first, with who sent each, and how many there are in all (whatever the filters)."""
    ensure_schema(connection)
    where, values = ["1 = 1"], []
    if status in STATUSES:
        where.append("r.status = ?")
        values.append(status)
    if category in CATEGORIES:
        where.append("r.category = ?")
        values.append(category)
    query = query.strip()[:100]
    if query:
        where.append("(r.message LIKE ? ESCAPE '\\' OR r.email LIKE ? ESCAPE '\\' OR r.page LIKE ? ESCAPE '\\' "
                     "OR u.full_name LIKE ? ESCAPE '\\' OR u.email LIKE ? ESCAPE '\\')")
        values.extend([_like(query)] * 5)
    rows = connection.execute(
        "SELECT r.id, r.created_at, r.category, r.message, r.email, r.page, r.status, r.user_id, "
        "u.full_name AS user_name, u.email AS user_email FROM problem_reports r LEFT JOIN users u ON u.id = r.user_id "
        f"WHERE {' AND '.join(where)} ORDER BY r.id DESC LIMIT ?",
        (*values, max(1, min(int(limit), LIST_LIMIT))),
    ).fetchall()
    counts = {name: 0 for name in STATUSES}
    for name, n in connection.execute("SELECT status, COUNT(*) FROM problem_reports GROUP BY status"):
        counts[name] = counts.get(name, 0) + n
    return {
        "reports": [
            {"id": row["id"], "created_at": row["created_at"], "category": row["category"],
             "label": LABELS.get(row["category"], row["category"]), "message": row["message"], "email": row["email"],
             "page": row["page"], "status": row["status"],
             "user": {"name": row["user_name"], "email": row["user_email"]} if row["user_id"] and row["user_email"] else None}
            for row in rows
        ],
        "counts": {**counts, "total": sum(counts.values())},
    }


def set_status(connection: Any, report_id: int, status: str) -> bool:
    """Mark one report handled or open again. False when there is no such report or no such status."""
    if status not in STATUSES:
        return False
    ensure_schema(connection)
    return bool(connection.execute("UPDATE problem_reports SET status = ? WHERE id = ?", (status, int(report_id))).rowcount)


TOO_SHORT = f"Please tell us a little more (at least {MIN_MESSAGE} characters)."
TOO_MANY = "You've sent a few reports already. Please try again in an hour."
SENT = "Thanks. Your report was sent."

_recent: dict[str, list[float]] = {}
_lock = threading.Lock()


def _allowed(key: str) -> bool:
    now = time.time()
    with _lock:
        hits = [t for t in _recent.get(key, []) if now - t < 3600]
        if len(hits) >= PER_HOUR:
            _recent[key] = hits
            return False
        hits.append(now)
        _recent[key] = hits
        if len(_recent) > 5000:
            for stale in [k for k, v in _recent.items() if not v or now - v[-1] >= 3600]:
                _recent.pop(stale, None)
    return True


def _clean(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit] if limit <= MAX_PAGE else str(value or "").strip()[:limit]


def email_report(report: dict[str, Any]) -> bool:
    """Send one report to the contact address. False (and a log line) when no mail account is set or sending fails."""
    host, user, password = (os.environ.get(f"DEFAKETIVE_SMTP_{name}", "") for name in ("HOST", "USER", "PASSWORD"))
    if not (host and user and password):
        log.warning("Problem report %s saved but not emailed: DEFAKETIVE_SMTP_HOST/USER/PASSWORD are not set.", report["id"])
        return False
    port = int(os.environ.get("DEFAKETIVE_SMTP_PORT", "587") or 587)
    message = EmailMessage()
    message["Subject"] = f"DeFaketive problem report: {LABELS.get(report['category'], report['category'])}"
    message["From"] = os.environ.get("DEFAKETIVE_SMTP_FROM") or user
    message["To"] = os.environ.get("DEFAKETIVE_REPORT_TO") or REPORT_TO
    if report["email"]:
        message["Reply-To"] = report["email"]
    kind = LABELS.get(report["category"], report["category"])
    sender = report["email"] or "no email given"
    who = "signed in" if report["user_id"] else "guest"
    message.set_content(
        chr(10).join([
            f"Report #{report['id']}",
            f"Type: {kind}",
            f"Page: {report['page'] or '-'}",
            f"From: {sender} ({who})",
            "",
            report["message"],
            "",
        ])
    )
    try:
        if port == 465:
            with smtplib.SMTP_SSL(host, port, timeout=20, context=ssl.create_default_context()) as server:
                server.login(user, password)
                server.send_message(message)
        else:
            with smtplib.SMTP(host, port, timeout=20) as server:
                server.starttls(context=ssl.create_default_context())
                server.login(user, password)
                server.send_message(message)
    except (OSError, smtplib.SMTPException) as problem:
        log.warning("Problem report %s saved but the email failed: %s", report["id"], problem)
        return False
    return True


def install(webapp: Any, app: Any = None) -> None:
    import accounts

    app = app or webapp.app

    @app.post("/api/problem-report")
    def problem_report() -> Any:
        payload = webapp._json_body()
        if payload is None:
            return jsonify({"error": "Send this request as JSON."}), 415
        category = str(payload.get("category") or "other")
        if category not in CATEGORIES:
            category = "other"
        message = _clean(payload.get("message"), MAX_MESSAGE)
        if len(message) < MIN_MESSAGE:
            return jsonify({"error": TOO_SHORT}), 400
        if not _allowed(protections.client_address()):
            return jsonify({"error": TOO_MANY}), 429
        user = webapp._current_user()
        with accounts._connect(str(current_app.config["ACCOUNTS_DB"])) as connection:
            ensure_schema(connection)
            report = {"category": category, "message": message, "email": _clean(payload.get("email"), MAX_EMAIL),
                      "page": _clean(payload.get("page"), MAX_PAGE), "user_id": user["id"] if user else None}
            report["id"] = connection.execute(
                "INSERT INTO problem_reports (category, message, email, page, user_id) VALUES (?, ?, ?, ?, ?)",
                (category, message, report["email"], report["page"], report["user_id"]),
            ).lastrowid
        # In the background, so the form answers at once however slow the mail server is.
        threading.Thread(target=email_report, args=(report,), daemon=True, name="defaketive-report-mail").start()
        return jsonify({"ok": True, "message": SENT}), 201
