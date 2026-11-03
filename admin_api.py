"""The admin app's server side: accounts and daily check limits, for the DTI staff who run DeFaketive.

The admin side (the /admin page of the app) is apart from the shopping side. It has its
own sign-in, kept in the session as `admin_id`, never as the shopping app's `user_id`, so signing in to one never
signs in to the other.

Who is an admin. The main admin, ADMIN_EMAIL (Admin@defake.com), is made in the accounts database when the server
starts (ensure_admin), with the one-time password ADMIN_PASSWORD if it does not exist yet. Only an admin can make
another admin: by adding an account with the admin role in the admin page. Nobody becomes an admin by signing up, and
no existing account is promoted.

Admin accounts are admin-only. The shopping app's sign-in refuses it (with the right password: a wrong one is
counted as usual), and a shopping-app session of the account ends on its next request.

What the admin can do, and what not.
- See every account: name, email, when it joined, how many products are in its History and Wishlist, and how many
  checks it started today. Never a password or its hash, and never which products.
- Add an account (name, email, password), as a shopper or as another admin.
- NOT delete an account. The admin cannot delete anyone's account (not even a shopper's): DELETE below always refuses.
  A person deletes their own account from Settings in the shopping app.
- Change the three daily limits protections.py counts: new checks for the whole site, for each account, and for
  each internet connection guests use. A change counts at once and is kept in the `site_settings` table, so it
  outlives a restart; until one is saved, the numbers come from the environment (protections.Limits).
- Change their own password.

    GET    /api/admin/me                   {admin: {id, name, email} | null}
    POST   /api/admin/login                {email, password}; only an admin account gets in
    POST   /api/admin/logout
    PUT    /api/admin/password             {current_password, new_password}
    GET    /api/admin/accounts?q=          every account, newest first; q searches names and emails
    POST   /api/admin/accounts             {name, email, password, admin?}: adds an account
    DELETE /api/admin/accounts/<id>      always refused (403): the admin cannot delete accounts
    GET    /api/admin/limits               the three limits, their defaults, and today's use of the site limit
    PUT    /api/admin/limits               {site, account, network}: whole numbers from 0 to 10,000

The original app's own /api/admin/overview, database, lexicons and logs stay closed (protections.CLOSED_PATHS).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, g, jsonify, request, session

import protections

blueprint = Blueprint("admin", __name__, url_prefix="/api/admin")

SCHEMA = """
CREATE TABLE IF NOT EXISTS agency_members (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    office TEXT NOT NULL, added_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS site_settings (
    name TEXT PRIMARY KEY, value INTEGER NOT NULL, updated_at TEXT NOT NULL
);
"""

OFFICE = "DTI"
# The main admin. The email is compared in lower case, like every account's, so "Admin@defake.com" signs in.
ADMIN_EMAIL = "admin@defake.com"
# The first version of this admin used this email; its account is renamed (ensure_admin) rather than left behind.
LEGACY_ADMIN_EMAIL = "admin@defake"
ADMIN_NAME = "Administrator"
ADMIN_PASSWORD = "Admin@defake.com"
SESSION_KEY = "admin_id"
# The limits an admin may change: the name on the protections.limits object, and in site_settings.
LIMIT_NAMES = ("site", "account", "network")
MAX_LIMIT = 10_000
MAX_ACCOUNTS = 1000

SIGN_IN_MESSAGE = "Sign in with your admin account."
WRONG_MESSAGE = "Email or password is incorrect."
TOO_MANY_MESSAGE = "Too many tries. Wait a few minutes, then try again."
NOT_ADMIN_MESSAGE = "This account is not an admin. Shoppers use the main DeFaketive app."
ROLE_REMOVED_MESSAGE = "Your admin session ended, so you were signed out."
ADMIN_ONLY_MESSAGE = "This is an admin account. It can only be used in the DeFaketive admin app."
DELETE_REFUSED_MESSAGE = "The admin page can't delete accounts. People delete their own account from Settings."
LIMITS_MESSAGE = f"Each limit must be a whole number from 0 to {MAX_LIMIT:,}."


@contextmanager
def _connect(path: str | Path) -> Iterator[Any]:
    import accounts  # the original app's; server.py puts it on the path

    # The accounts module makes its own tables first and turns foreign keys on, so deleting an account removes its
    # admin row, History and Wishlist too.
    with accounts._connect(path) as connection:
        connection.executescript(SCHEMA)
        yield connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# --- Who is an admin ------------------------------------------------------------------------------------------------


def user_by_email(path: str | Path, email: str) -> dict[str, Any] | None:
    with _connect(path) as connection:
        row = connection.execute("SELECT id, full_name, email FROM users WHERE email = ?", (email.strip().lower(),)).fetchone()
    return {"id": row["id"], "name": row["full_name"], "email": row["email"]} if row else None


def is_admin(path: str | Path, user_id: Any) -> bool:
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        return False
    with _connect(path) as connection:
        return connection.execute("SELECT 1 FROM agency_members WHERE user_id = ?", (user_id,)).fetchone() is not None


def ensure_admin(path: str | Path) -> None:
    """Make sure the main admin exists and is an admin. A password someone has changed is left as it is."""
    from werkzeug.security import generate_password_hash

    with _connect(path) as connection:
        row = connection.execute("SELECT id FROM users WHERE email = ?", (ADMIN_EMAIL,)).fetchone()
        legacy = connection.execute("SELECT id FROM users WHERE email = ?", (LEGACY_ADMIN_EMAIL,)).fetchone()
        if row is None and legacy is not None:
            connection.execute(
                "UPDATE users SET email = ?, password_hash = ? WHERE id = ?",
                (ADMIN_EMAIL, generate_password_hash(ADMIN_PASSWORD), legacy["id"]),
            )
            row = legacy
        if row is None:
            # Made here, not through sign-up, so nobody can sign up with this email first.
            cursor = connection.execute(
                "INSERT INTO users(full_name, email, password_hash, created_at) VALUES (?, ?, ?, ?)",
                (ADMIN_NAME, ADMIN_EMAIL, generate_password_hash(ADMIN_PASSWORD), _now()),
            )
            admin_id = cursor.lastrowid
        else:
            admin_id = row["id"]
        connection.execute(
            "INSERT INTO agency_members(user_id, office, added_at) VALUES (?, ?, ?) ON CONFLICT(user_id) DO NOTHING",
            (admin_id, OFFICE, _now()),
        )


def add_admin(path: str | Path, user_id: int) -> None:
    with _connect(path) as connection:
        connection.execute(
            "INSERT INTO agency_members(user_id, office, added_at) VALUES (?, ?, ?) ON CONFLICT(user_id) DO NOTHING",
            (int(user_id), OFFICE, _now()),
        )


def admins(path: str | Path) -> list[dict[str, Any]]:
    with _connect(path) as connection:
        rows = connection.execute(
            "SELECT users.id, users.full_name, users.email, agency_members.added_at "
            "FROM agency_members JOIN users ON users.id = agency_members.user_id ORDER BY agency_members.added_at"
        ).fetchall()
    return [{"id": row["id"], "name": row["full_name"], "email": row["email"], "added_at": row["added_at"]} for row in rows]


# --- Accounts -------------------------------------------------------------------------------------------------------


def _like(text: str) -> str:
    return "%" + text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"


def account_list(path: str | Path, query: str = "", day: str = "") -> dict[str, Any]:
    """Every account (newest first, at most MAX_ACCOUNTS), with how many there are and how many are admins."""
    where, values = "", []
    if query.strip():
        where = "WHERE users.full_name LIKE ? ESCAPE '\\' OR users.email LIKE ? ESCAPE '\\'"
        values = [_like(query.strip())] * 2
    with _connect(path) as connection:
        rows = connection.execute(
            f"""SELECT users.id, users.full_name, users.email, users.created_at,
                       agency_members.user_id IS NOT NULL AS admin,
                       (SELECT COUNT(*) FROM user_activity WHERE user_id = users.id AND opened_at > 0) AS history,
                       (SELECT COUNT(*) FROM user_wishlist WHERE user_id = users.id) AS wishlist,
                       COALESCE((SELECT used FROM guest_scans WHERE guest_key = 'account:' || users.id AND day = ?), 0)
                           AS checks_today
                FROM users LEFT JOIN agency_members ON agency_members.user_id = users.id
                {where} ORDER BY users.created_at DESC, users.id DESC LIMIT ?""",
            [day, *values, MAX_ACCOUNTS],
        ).fetchall()
        total = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        admin_count = connection.execute(
            "SELECT COUNT(*) FROM agency_members JOIN users ON users.id = agency_members.user_id"
        ).fetchone()[0]
    return {
        "accounts": [
            {"id": row["id"], "name": row["full_name"], "email": row["email"], "joined": row["created_at"],
             "admin": bool(row["admin"]), "history": row["history"], "wishlist": row["wishlist"],
             "checks_today": row["checks_today"]}
            for row in rows
        ],
        "total": total,
        "admins": admin_count,
    }


# --- Daily limits ---------------------------------------------------------------------------------------------------


def saved_limits(path: str | Path) -> dict[str, int]:
    with _connect(path) as connection:
        rows = connection.execute("SELECT name, value FROM site_settings").fetchall()
    return {row["name"]: int(row["value"]) for row in rows if row["name"] in LIMIT_NAMES}


def apply_saved_limits(path: str | Path) -> None:
    """Put the limits an admin saved on protections.limits, over the environment's numbers."""
    for name, value in saved_limits(path).items():
        setattr(protections.limits, name, value)


def save_limits(path: str | Path, values: dict[str, int]) -> None:
    now = _now()
    with _connect(path) as connection:
        connection.executemany(
            "INSERT INTO site_settings(name, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            [(name, value, now) for name, value in values.items()],
        )
    for name, value in values.items():
        setattr(protections.limits, name, value)


def _whole_number(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= MAX_LIMIT:
        return None
    return value


# --- Routes ---------------------------------------------------------------------------------------------------------


def install(webapp: Any, app: Any = None) -> None:
    """Add the admin routes to the original app, keep admin accounts out of the shopping app, use the saved limits."""
    import accounts

    app = app or webapp.app
    defaults = {name: getattr(protections.Limits(), name) for name in LIMIT_NAMES}
    ensure_admin(app.config["ACCOUNTS_DB"])
    apply_saved_limits(app.config["ACCOUNTS_DB"])

    def database() -> str:
        return str(current_app.config["ACCOUNTS_DB"])

    def refuse(message: str, status: int = 400, **extra: Any) -> Any:
        return jsonify({"error": message, **extra}), status

    def signed_in_admin() -> dict[str, Any] | None:
        user = accounts.get_user(database(), session[SESSION_KEY]) if SESSION_KEY in session else None
        if user is None or not is_admin(database(), user["id"]):
            return None
        return user

    def admin() -> tuple[dict[str, Any] | None, Any]:
        """The signed-in admin, or the answer to give instead."""
        if SESSION_KEY not in session:
            return None, refuse(SIGN_IN_MESSAGE, 401, sign_in=True)
        user = signed_in_admin()
        if user is None:
            # Deleted, or no longer an admin: this admin session ends.
            session.pop(SESSION_KEY, None)
            return None, refuse(ROLE_REMOVED_MESSAGE, 401, sign_in=True)
        return user, None

    @app.before_request
    def doors() -> Any:
        path = request.path
        if not path.startswith("/api/"):
            return None
        if path.startswith("/api/admin/"):
            return None
        # Admin accounts are admin-only: the shopping app's sign-in refuses one (with its right password; a wrong one
        # goes on to the original, which counts it).
        if path in ("/api/auth/login", "/api/auth/signup") and request.method == "POST":
            # The original's sign-in empties the session; an admin signed in on the same computer stays signed in.
            if SESSION_KEY in session:
                g.admin_id = session[SESSION_KEY]
            payload = request.get_json(silent=True)
            if path == "/api/auth/login" and isinstance(payload, dict):
                found = user_by_email(database(), str(payload.get("email") or ""))
                if found and is_admin(database(), found["id"]) and accounts.authenticate(
                    database(), found["email"], payload.get("password")
                ):
                    return refuse(ADMIN_ONLY_MESSAGE, 403, admin_only=True)
            return None
        # A shopping-app session of an account that is an admin now ends.
        if "user_id" in session and is_admin(database(), session["user_id"]):
            session.pop("user_id", None)
        return None

    @app.after_request
    def keep_admin_session(response: Any) -> Any:
        admin_id = g.pop("admin_id", None)
        if admin_id is not None and SESSION_KEY not in session:
            session[SESSION_KEY] = admin_id
        return response

    def me_answer(user: dict[str, Any] | None) -> dict[str, Any]:
        return {"admin": {"id": user["id"], "name": user["name"], "email": user["email"]} if user else None}

    @blueprint.get("/me")
    def me() -> Any:
        user = signed_in_admin()
        if user is None and SESSION_KEY in session:
            # Deleted, or no longer an admin: this admin session ends, and the app says why.
            session.pop(SESSION_KEY, None)
            return jsonify({**me_answer(None), "notice": ROLE_REMOVED_MESSAGE})
        return jsonify(me_answer(user))

    @blueprint.post("/login")
    def login() -> Any:
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return refuse(WRONG_MESSAGE)
        email = str(payload.get("email") or "").strip().lower()
        # Counted apart from the shopping app's tries, with the same rule (5 wrong in 15 minutes).
        key = f"admin:{email}"
        if len(webapp._recent_failures(key)) >= webapp.LOGIN_FAILURE_LIMIT:
            return refuse(TOO_MANY_MESSAGE, 429)
        user = accounts.authenticate(database(), email, payload.get("password"))
        if user is None:
            with webapp._lock:
                webapp._login_failures.setdefault(key, []).append(time.monotonic())
            return refuse(WRONG_MESSAGE, 401)
        with webapp._lock:
            webapp._login_failures.pop(key, None)
        if not is_admin(database(), user["id"]):
            return refuse(NOT_ADMIN_MESSAGE, 403, not_admin=True)
        session[SESSION_KEY] = user["id"]
        session.permanent = True
        return jsonify(me_answer(user))

    @blueprint.post("/logout")
    def logout() -> Any:
        session.pop(SESSION_KEY, None)
        return jsonify(me_answer(None))

    @blueprint.put("/password")
    def password() -> Any:
        user, refused = admin()
        if refused:
            return refused
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict) or not payload.get("new_password"):
            return refuse("Enter a new password.", 400, fields={"new_password": "Enter a new password."})
        try:
            accounts.update_user(database(), user["id"], payload.get("current_password"),
                                 new_password=payload.get("new_password"))
        except accounts.AccountError as error:
            status = 403 if isinstance(error, accounts.WrongPassword) else 400
            return refuse(error.message, status, fields={error.field: error.message})
        return jsonify({"changed": True})

    @blueprint.get("/accounts")
    def account_rows() -> Any:
        user, refused = admin()
        if refused:
            return refused
        found = account_list(database(), str(request.args.get("q") or "")[:200], accounts.manila_day())
        for row in found["accounts"]:
            row["you"] = row["id"] == user["id"]
            row["main"] = row["email"] == ADMIN_EMAIL
        return jsonify(found)

    @blueprint.post("/accounts")
    def add_account() -> Any:
        _user, refused = admin()
        if refused:
            return refused
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return refuse("Enter a name, an email and a password.")
        if "admin" in payload and not isinstance(payload["admin"], bool):
            return refuse("Say whether the account should be an admin.")
        errors = {}
        for field, check in (
            ("name", lambda: accounts._clean_name(payload.get("name"))),
            ("email", lambda: accounts._clean_email(payload.get("email"))),
            ("password", lambda: accounts._check_new_password(payload.get("password"))),
        ):
            try:
                check()
            except accounts.AccountError as error:
                errors[field] = error.message
        if errors:
            return refuse(next(iter(errors.values())), 400, fields=errors)
        try:
            created = accounts.create_user(database(), payload["name"], payload["email"], payload["password"])
        except accounts.EmailTaken as error:
            return refuse(error.message.replace(" Sign in instead.", ""), 409, fields={"email": error.message})
        if payload.get("admin"):
            add_admin(database(), created["id"])
        return jsonify({"id": created["id"], "name": created["name"], "email": created["email"],
                        "admin": bool(payload.get("admin"))}), 201

    @blueprint.delete("/accounts/<int:user_id>")
    def delete(user_id: int) -> Any:
        # Kept as a route, so the answer says why, but nothing is deleted: the admin has no permission to.
        _user, refused = admin()
        if refused:
            return refused
        return refuse(DELETE_REFUSED_MESSAGE, 403)

    def limits_answer() -> dict[str, Any]:
        used = accounts.guest_scans_used(database(), protections.SITE_KEY, accounts.manila_day())
        return {
            "limits": {name: getattr(protections.limits, name) for name in LIMIT_NAMES},
            "defaults": defaults,
            "site_used_today": used,
            "max": MAX_LIMIT,
        }

    @blueprint.get("/limits")
    def limits() -> Any:
        _user, refused = admin()
        return refused or jsonify(limits_answer())

    @blueprint.put("/limits")
    def change_limits() -> Any:
        _user, refused = admin()
        if refused:
            return refused
        payload = request.get_json(silent=True)
        if not isinstance(payload, dict):
            return refuse(LIMITS_MESSAGE)
        values = {name: _whole_number(payload.get(name)) for name in LIMIT_NAMES}
        if any(value is None for value in values.values()):
            return refuse(LIMITS_MESSAGE)
        save_limits(database(), values)  # type: ignore[arg-type]
        return jsonify(limits_answer())

    app.register_blueprint(blueprint)
