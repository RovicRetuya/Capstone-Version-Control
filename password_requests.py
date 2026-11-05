"""The "Forgot password" form: POST /api/password-request.

Anyone may ask. The person gives the name and email on the account, the last password they remember, and the email the
new password should be sent to. The request is kept in the accounts database (table `password_requests`) and the admin
reads it on the admin page (admin_api.py: GET /api/admin/password-requests), then sets a new password for the account.

The remembered password is never kept. The server compares it with the account's stored password once, while the
request is made, and keeps only the answer (matched or not) so the admin can tell the real owner from a stranger. A
password typed into this form is not written to the database, the log or an email.

The form answers the same way whether or not an account exists, so it can't be used to find out who has one.
Each connection may send a few requests an hour.
"""

from __future__ import annotations

import secrets
import string
import threading
import time
from typing import Any

from flask import current_app, jsonify

import protections

STATUSES = ("new", "done")
MAX_NAME = 120
MAX_EMAIL = 254
MAX_PASSWORD = 200
PER_HOUR = 5
LIST_LIMIT = 200
TEMP_LENGTH = 12
SENT = "Thanks. Your request was sent to the admin. They will set a new password and send it to the email you gave."
TOO_MANY = "You've sent a few requests already. Please try again in an hour."
NO_REQUEST_MESSAGE = "There is no such request."

SCHEMA = """
CREATE TABLE IF NOT EXISTS password_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    send_to TEXT NOT NULL,
    user_id INTEGER,
    name_matches INTEGER NOT NULL DEFAULT 0,
    password_matched INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'new',
    handled_at TEXT
);
"""

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


def ensure_schema(connection: Any) -> None:
    connection.executescript(SCHEMA)


def _clean(value: Any, limit: int) -> str:
    return " ".join(str(value or "").split())[:limit]


def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def new_password() -> str:
    """A password for the admin to hand over: letters and digits, no look-alikes, with at least one of each."""
    letters = "".join(c for c in string.ascii_letters if c not in "IlOo")
    digits = "".join(c for c in string.digits if c not in "01")
    while True:
        text = "".join(secrets.choice(letters + digits) for _ in range(TEMP_LENGTH))
        if any(c in digits for c in text) and any(c in letters for c in text):
            return text


def record(connection: Any, name: str, email: str, last_password: str, send_to: str) -> int:
    """Save one request. Compares the remembered password with the account's, and keeps only whether it matched."""
    from werkzeug.security import check_password_hash

    ensure_schema(connection)
    row = connection.execute("SELECT id, full_name, password_hash FROM users WHERE email = ?", (email.lower(),)).fetchone()
    matched = bool(row and last_password and check_password_hash(row["password_hash"], last_password))
    same_name = bool(row and row["full_name"].casefold() == name.casefold())
    return connection.execute(
        "INSERT INTO password_requests (name, email, send_to, user_id, name_matches, password_matched) VALUES (?, ?, ?, ?, ?, ?)",
        (name, email, send_to, row["id"] if row else None, int(same_name), int(matched)),
    ).lastrowid


def list_requests(connection: Any, status: str = "all", query: str = "", limit: int = LIST_LIMIT) -> dict[str, Any]:
    ensure_schema(connection)
    where, values = ["1 = 1"], []
    if status in STATUSES:
        where.append("r.status = ?")
        values.append(status)
    query = query.strip()[:100]
    if query:
        where.append("(r.name LIKE ? ESCAPE '\\' OR r.email LIKE ? ESCAPE '\\' OR r.send_to LIKE ? ESCAPE '\\')")
        values.extend([_like(query)] * 3)
    rows = connection.execute(
        "SELECT r.id, r.created_at, r.name, r.email, r.send_to, r.user_id, r.name_matches, r.password_matched, r.status, "
        "r.handled_at, u.full_name AS account_name FROM password_requests r LEFT JOIN users u ON u.id = r.user_id "
        f"WHERE {' AND '.join(where)} ORDER BY r.id DESC LIMIT ?",
        (*values, max(1, min(int(limit), LIST_LIMIT))),
    ).fetchall()
    counts = {name: 0 for name in STATUSES}
    for name, n in connection.execute("SELECT status, COUNT(*) FROM password_requests GROUP BY status"):
        counts[name] = counts.get(name, 0) + n
    return {
        "requests": [
            {"id": row["id"], "created_at": row["created_at"], "name": row["name"], "email": row["email"],
             "send_to": row["send_to"], "status": row["status"], "handled_at": row["handled_at"],
             "account_found": row["account_name"] is not None, "name_matches": bool(row["name_matches"]),
             "password_matched": bool(row["password_matched"])}
            for row in rows
        ],
        "counts": {**counts, "total": sum(counts.values())},
    }


def get_request(connection: Any, request_id: int) -> Any:
    ensure_schema(connection)
    return connection.execute("SELECT * FROM password_requests WHERE id = ?", (int(request_id),)).fetchone()


def set_status(connection: Any, request_id: int, status: str) -> bool:
    if status not in STATUSES:
        return False
    ensure_schema(connection)
    handled = "datetime('now')" if status == "done" else "NULL"
    return bool(connection.execute(
        f"UPDATE password_requests SET status = ?, handled_at = {handled} WHERE id = ?", (status, int(request_id))
    ).rowcount)


def install(webapp: Any, app: Any = None) -> None:
    import accounts

    app = app or webapp.app

    @app.post("/api/password-request")
    def password_request() -> Any:
        payload = webapp._json_body()
        if payload is None:
            return jsonify({"error": "Send this request as JSON."}), 415
        name = _clean(payload.get("name"), MAX_NAME)
        email = _clean(payload.get("email"), MAX_EMAIL)
        send_to = _clean(payload.get("send_to"), MAX_EMAIL)
        last = str(payload.get("last_password") or "")[:MAX_PASSWORD]
        errors: dict[str, str] = {}
        if not name:
            errors["name"] = "Enter the name on the account."
        for field, value, missing in (("email", email, "Enter the email on the account."),
                                      ("send_to", send_to, "Enter the email to send the new password to.")):
            try:
                accounts._clean_email(value)
            except accounts.AccountError:
                errors[field] = missing if not value else "Enter a valid email address, like you@example.com."
        if errors:
            return jsonify({"error": next(iter(errors.values())), "fields": errors}), 400
        if not _allowed(protections.client_address()):
            return jsonify({"error": TOO_MANY}), 429
        with accounts._connect(str(current_app.config["ACCOUNTS_DB"])) as connection:
            record(connection, name, email, last, send_to.lower())
        return jsonify({"ok": True, "message": SENT}), 201
