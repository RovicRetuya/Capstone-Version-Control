"""The admin page's server side (/api/admin/*): accounts, daily check limits and more, for the DTI staff who run DeFaketive.

The admin side (the /admin page of this same app; there is no separate admin app) is apart from the shopping side. It has its
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
- Delete their OWN account (with their password), and never anyone else's: a shopper deletes their own account from
  Settings in the shopping app. The last admin can't delete itself.
- Change the three daily limits protections.py counts: new checks for the whole site, for each account, and for
  each internet connection guests use. A change counts at once and is kept in the `site_settings` table, so it
  outlives a restart; until one is saved, the numbers come from the environment (protections.Limits).
- Choose what the Products page offers: which "Filter by result" and "Order by" choices appear, which is
  picked first, and add options of their own (a minimum rating, a top price, a minimum review count, a marketplace,
  or an order by rating, price, reviews, date or name). Kept in the `ui_settings` table; everybody can read it (GET /api/products-filters).
- Read the problem reports people send from the site's "Report a problem" form, and mark each handled or open again.
- Change their own password.
- Read the "Forgot password" requests (password_requests.py), and answer one by setting a new password on that
  account. The new password is shown once and emailed to the address the person gave (when a mail account is set up).
- See the products the site has saved: name, marketplace, price, rating, result, reviews read, when saved.

    GET    /api/admin/me                   {admin: {id, name, email} | null}
    POST   /api/admin/login                {email, password}; only an admin account gets in
    POST   /api/admin/logout
    PUT    /api/admin/password             {current_password, new_password}
    GET    /api/admin/accounts?q=          every account, newest first; q searches names and emails
    POST   /api/admin/accounts             {name, email, password, admin?}: adds an account
    DELETE /api/admin/accounts/<id>      {current_password}: only your own id; refused for anyone else (403)
    GET    /api/admin/limits               the three limits, their defaults, and today's use of the site limit
    PUT    /api/admin/limits               {site, account, network}: whole numbers from 0 to 10,000
    GET    /api/admin/filters              the Products page's choices, and the starting ones
    PUT    /api/admin/filters              {show: {enabled, default}, sort: {enabled, default}, custom: [...]}
    GET    /api/products-filters           (no sign-in) the choices the Products page offers
    GET    /api/admin/reports?status=&category=&q=   the problem reports, newest first, with who sent each
    PUT    /api/admin/reports/<id>         {status: "new" | "done"}
    GET    /api/admin/password-requests?status=&q=   the Forgot password requests, newest first
    PUT    /api/admin/password-requests/<id>         {status: "new" | "done"}
    POST   /api/admin/password-requests/<id>/reset   sets a new password, emails it, marks the request done
    GET    /api/admin/products?q=&platform=          the saved products, newest first

The original app's own /api/admin/overview, database, lexicons and logs stay closed (protections.CLOSED_PATHS).
"""

from __future__ import annotations

import json
import re
import sqlite3
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Blueprint, current_app, g, jsonify, request, session

import password_requests
import problem_reports
import protections

blueprint = Blueprint("admin", __name__, url_prefix="/api/admin")
# What everybody may read: the choices the Products page offers (the admin sets them).
public_blueprint = Blueprint("product_choices", __name__, url_prefix="/api")

SCHEMA = """
CREATE TABLE IF NOT EXISTS agency_members (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    office TEXT NOT NULL, added_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS site_settings (
    name TEXT PRIMARY KEY, value INTEGER NOT NULL, updated_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS ui_settings (
    name TEXT PRIMARY KEY, value TEXT NOT NULL, updated_at TEXT NOT NULL
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
NO_REPORT_MESSAGE = "There is no such report."
LAST_ADMIN_MESSAGE = "You are the only admin. Add another admin account first, then you can delete this one."
OWN_ONLY_MESSAGE = "You can delete your own account only. People delete their own account from Settings."
ADMIN_RESET_MESSAGE = "An admin account's password can't be reset here. The admin changes it on the admin page."
NO_ACCOUNT_MESSAGE = "No account has that email, so there is no password to change."
PRODUCT_LIMIT = 500
LIMITS_MESSAGE = f"Each limit must be a whole number from 0 to {MAX_LIMIT:,}."


@contextmanager
def _connect(path: str | Path) -> Iterator[Any]:
    import accounts  # backend/accounts.py; server.py puts it on the path

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
        if row is None and connection.execute("SELECT 1 FROM agency_members").fetchone() is not None:
            # Another admin exists (the main one deleted its own account): the default login is not made again.
            return
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


# --- The Products page's choices -------------------------------------------------------------------------------------

# Every built-in choice the page can offer, by the names the screens use (src/lib/product-filters.ts has their labels).
FILTER_CHOICES = {
    "show": ("all", "attention", "safety", "caution", "clear", "unknown"),
    "sort": ("fewest", "most", "reviews"),
}
FILTER_DEFAULTS: dict[str, Any] = {
    "show": {"enabled": list(FILTER_CHOICES["show"]), "default": "all"},
    "sort": {"enabled": list(FILTER_CHOICES["sort"]), "default": "fewest"},
    "custom": [],
}
FILTERS_KEY = "product_filters"
FILTERS_MESSAGE = "Keep at least one choice in each list, and pick one of them to show first."

# Options the admin makes up. The page has to know how to apply each one, so the admin picks a kind and gives it a
# number (or a marketplace), a name, and, for an order, a direction. A custom option is in the `custom` list, and in a
# list's `enabled` by its id like any built-in one.
CUSTOM_ID = re.compile(r"^c[a-z0-9]{4,12}$")
MAX_CUSTOM = 20
LABEL_MAX = 40
# Filters: kind -> (lowest, highest) for a number, or the names a marketplace may have.
FILTER_KINDS: dict[str, Any] = {
    "min_rating": (1, 5),  # rated at least this many stars
    "max_price": (1, 10_000_000),  # priced at most this many pesos
    "min_reviews": (1, 1_000_000),  # at least this many reviews analyzed
    "marketplace": ("lazada", "shopee"),
}
# Orders: the thing to order by, and which way.
ORDER_FIELDS = ("rating", "price", "reviews", "checked", "name")
DIRECTIONS = ("asc", "desc")
CUSTOM_MESSAGE = "An option you added isn't valid: "


def _clean_custom_one(item: Any) -> tuple[dict[str, Any] | None, str]:
    """One admin-made option in the shape the page uses, or (None, why not)."""
    if not isinstance(item, dict):
        return None, "it is not an object."
    identifier, group, label, kind = item.get("id"), item.get("group"), item.get("label"), item.get("kind")
    if not isinstance(identifier, str) or not CUSTOM_ID.match(identifier):
        return None, "it has no valid id."
    if group not in ("show", "sort"):
        return None, "it belongs to no list."
    if not isinstance(label, str) or not 1 <= len(label.strip()) <= LABEL_MAX or not label.strip().isprintable():
        return None, f"its name must be 1 to {LABEL_MAX} characters."
    clean: dict[str, Any] = {"id": identifier, "group": group, "label": label.strip(), "kind": kind}
    if group == "sort":
        if kind not in ORDER_FIELDS or item.get("direction") not in DIRECTIONS:
            return None, "choose what to order by and which way."
        clean["direction"] = item["direction"]
        return clean, ""
    if kind not in FILTER_KINDS:
        return None, "choose what to filter by."
    value, allowed = item.get("value"), FILTER_KINDS[kind]
    if kind == "marketplace":
        if value not in allowed:
            return None, "choose Lazada or Shopee."
        clean["value"] = value
        return clean, ""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value != value:
        return None, "its number is missing."
    low, high = allowed
    if not low <= value <= high:
        return None, f"its number must be from {low:,} to {high:,}."
    clean["value"] = int(value) if kind == "min_reviews" else round(float(value), 1 if kind == "min_rating" else 2)
    return clean, ""


def check_filters(value: Any) -> tuple[dict[str, Any] | None, str]:
    """The choices in the shape the page uses (known names only, in the page's order), or (None, why not)."""
    if not isinstance(value, dict):
        return None, FILTERS_MESSAGE
    raw_custom = value.get("custom", [])
    if not isinstance(raw_custom, list) or len(raw_custom) > MAX_CUSTOM:
        return None, f"{CUSTOM_MESSAGE}at most {MAX_CUSTOM} can be added."
    custom: list[dict[str, Any]] = []
    for item in raw_custom:
        one, problem = _clean_custom_one(item)
        if one is None:
            return None, CUSTOM_MESSAGE + problem
        if any(other["id"] == one["id"] for other in custom):
            return None, CUSTOM_MESSAGE + "two share an id."
        custom.append(one)
    cleaned: dict[str, Any] = {}
    for group, built_in in FILTER_CHOICES.items():
        part = value.get(group)
        if not isinstance(part, dict) or not isinstance(part.get("enabled"), list):
            return None, FILTERS_MESSAGE
        known = [*built_in, *(one["id"] for one in custom if one["group"] == group)]
        asked = part["enabled"]
        if any(not isinstance(name, str) or name not in known for name in asked):
            return None, FILTERS_MESSAGE
        enabled = [name for name in known if name in asked]
        if not enabled or part.get("default") not in enabled:
            return None, FILTERS_MESSAGE
        cleaned[group] = {"enabled": enabled, "default": part["default"]}
    cleaned["custom"] = custom
    return cleaned, ""


def clean_filters(value: Any) -> dict[str, Any] | None:
    return check_filters(value)[0]


def saved_filters(path: str | Path) -> dict[str, Any]:
    """What the admin saved, or every choice with the usual starting ones when nothing (usable) is saved."""
    with _connect(path) as connection:
        row = connection.execute("SELECT value FROM ui_settings WHERE name = ?", (FILTERS_KEY,)).fetchone()
    if row is None:
        return FILTER_DEFAULTS
    try:
        return clean_filters(json.loads(row["value"])) or FILTER_DEFAULTS
    except ValueError:
        return FILTER_DEFAULTS


def save_filters(path: str | Path, filters: dict[str, Any]) -> None:
    with _connect(path) as connection:
        connection.execute(
            "INSERT INTO ui_settings(name, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(name) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (FILTERS_KEY, json.dumps(filters), _now()),
        )


# --- Routes ---------------------------------------------------------------------------------------------------------


def _source_word(source: Any) -> str:
    """How a product got here, in words. The stored value can be a file path on the server, which is not shown."""
    text = str(source or "")
    if text == "defaketive-extension":
        return "Extension"
    if text == "starter data":
        return "Starter set"
    return "Site scan" if text else ""


def saved_products(path: str | Path | None, query: str = "", platform: str = "") -> dict[str, Any]:
    """The saved products for the admin's list. Read only: the products database is opened so it cannot be written."""
    empty: dict[str, Any] = {"products": [], "total": 0, "platforms": {}, "shown": 0}
    if not path or not Path(path).exists():
        return empty
    where, values = ["1 = 1"], []
    platform = platform.strip().lower()[:30]
    if platform:
        where.append("lower(platform) = ?")
        values.append(platform)
    query = query.strip()[:100]
    if query:
        where.append("(name LIKE ? ESCAPE '\\' OR link LIKE ? ESCAPE '\\')")
        values.extend([_like(query)] * 2)
    try:
        connection = sqlite3.connect(f"{Path(path).resolve().as_uri()}?mode=ro", uri=True)
    except sqlite3.Error:
        return empty
    connection.row_factory = sqlite3.Row
    try:
        rows = connection.execute(
            "SELECT link, name, platform, price, rating, review_count, verdict_state, reviews_analyzed, reviews_listed, "
            f"source, updated_at FROM products WHERE {' AND '.join(where)} ORDER BY updated_at DESC LIMIT ?",
            (*values, PRODUCT_LIMIT),
        ).fetchall()
        total = connection.execute("SELECT COUNT(*) FROM products").fetchone()[0]
        platforms = {str(row[0] or "other"): row[1] for row in connection.execute("SELECT platform, COUNT(*) FROM products GROUP BY platform")}
    except sqlite3.Error:
        return empty
    finally:
        connection.close()
    return {
        "products": [
            {"link": row["link"], "name": row["name"] or "", "platform": row["platform"] or "", "price": row["price"],
             "rating": row["rating"], "review_count": row["review_count"], "result": row["verdict_state"] or "",
             "reviews_read": row["reviews_analyzed"], "reviews_listed": row["reviews_listed"],
             "source": _source_word(row["source"]), "saved": row["updated_at"] or ""}
            for row in rows
        ],
        "total": total,
        "platforms": platforms,
        "shown": len(rows),
    }


def install(webapp: Any, app: Any = None, products_db: str | Path | None = None) -> None:
    """Add the admin routes to the Flask app (backend/webapp.py), keep admin accounts out of the shopping app, use the saved limits."""
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
        """An admin may delete their own account (with their password), never anyone else's."""
        user, refused = admin()
        if refused:
            return refused
        if user_id != user["id"]:
            return refuse(OWN_ONLY_MESSAGE, 403)
        if len(admins(database())) < 2:
            return refuse(LAST_ADMIN_MESSAGE, 409)
        payload = request.get_json(silent=True)
        try:
            accounts.delete_user(database(), user["id"], payload.get("current_password") if isinstance(payload, dict) else None)
        except accounts.AccountError as error:
            return refuse(error.message, 403, fields={error.field: error.message})
        session.pop(SESSION_KEY, None)
        return jsonify({"deleted": True})

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

    @blueprint.get("/filters")
    def filters_answer() -> Any:
        _user, refused = admin()
        return refused or jsonify({"filters": saved_filters(database()), "defaults": FILTER_DEFAULTS})

    @blueprint.put("/filters")
    def change_filters() -> Any:
        _user, refused = admin()
        if refused:
            return refused
        cleaned, problem = check_filters(request.get_json(silent=True))
        if cleaned is None:
            return refuse(problem)
        save_filters(database(), cleaned)
        return jsonify({"filters": cleaned, "defaults": FILTER_DEFAULTS})

    @blueprint.get("/reports")
    def reports_answer() -> Any:
        """The problem reports people sent, newest first. ?status=new|done, ?category=, ?q= narrow them."""
        _user, refused = admin()
        if refused:
            return refused
        with _connect(database()) as connection:
            return jsonify(problem_reports.list_reports(
                connection, request.args.get("status", "all"), request.args.get("category", ""), request.args.get("q", "")))

    @blueprint.put("/reports/<int:report_id>")
    def change_report(report_id: int) -> Any:
        _user, refused = admin()
        if refused:
            return refused
        payload = request.get_json(silent=True)
        status = payload.get("status") if isinstance(payload, dict) else None
        if status not in problem_reports.STATUSES:
            return refuse("Mark a report new or done.")
        with _connect(database()) as connection:
            if not problem_reports.set_status(connection, report_id, status):
                return refuse(NO_REPORT_MESSAGE, 404)
        return jsonify({"id": report_id, "status": status})

    @blueprint.get("/password-requests")
    def password_requests_answer() -> Any:
        """The "Forgot password" requests, newest first. ?status=new|done, ?q= narrow them."""
        _user, refused = admin()
        if refused:
            return refused
        with _connect(database()) as connection:
            return jsonify(password_requests.list_requests(connection, request.args.get("status", "all"), request.args.get("q", "")))

    @blueprint.put("/password-requests/<int:request_id>")
    def change_password_request(request_id: int) -> Any:
        _user, refused = admin()
        if refused:
            return refused
        payload = request.get_json(silent=True)
        status = payload.get("status") if isinstance(payload, dict) else None
        if status not in password_requests.STATUSES:
            return refuse("Mark a request new or done.")
        with _connect(database()) as connection:
            if not password_requests.set_status(connection, request_id, status):
                return refuse(password_requests.NO_REQUEST_MESSAGE, 404)
        return jsonify({"id": request_id, "status": status})

    @blueprint.post("/password-requests/<int:request_id>/reset")
    def reset_password(request_id: int) -> Any:
        """Set a new password on the account the request is about, send it to the email the person gave, and mark it done.

        The new password is shown to the admin once (they can hand it over if no mail account is set up) and is
        never kept anywhere but as the account's stored password.
        """
        from werkzeug.security import generate_password_hash

        _user, refused = admin()
        if refused:
            return refused
        with _connect(database()) as connection:
            found = password_requests.get_request(connection, request_id)
            if found is None:
                return refuse(password_requests.NO_REQUEST_MESSAGE, 404)
            target = connection.execute("SELECT id, full_name, email FROM users WHERE email = ?", (found["email"].lower(),)).fetchone()
            if target is None:
                return refuse(NO_ACCOUNT_MESSAGE, 404)
            if connection.execute("SELECT 1 FROM agency_members WHERE user_id = ?", (target["id"],)).fetchone():
                return refuse(ADMIN_RESET_MESSAGE, 403)
            secret = password_requests.new_password()
            connection.execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(secret), target["id"]))
            password_requests.set_status(connection, request_id, "done")
            send_to, name = found["send_to"], target["full_name"]
        body = chr(10).join([
            f"Hello {name},", "",
            "The DeFaketive admin set a new password for your account:", "",
            f"    {secret}", "",
            "Sign in with it, then change it in Settings to one only you know.", "",
        ])
        emailed = problem_reports.send_mail(send_to, "Your new DeFaketive password", body, label=f"Password request {request_id}")
        return jsonify({"id": request_id, "password": secret, "emailed": emailed, "send_to": send_to, "name": name})

    @blueprint.get("/products")
    def products_answer() -> Any:
        """Every product the site has saved (scraped by the site or sent by the extension), newest first.

        ?q= searches the name and link; ?platform= narrows to one marketplace. Names, prices and counts only.
        """
        _user, refused = admin()
        if refused:
            return refused
        return jsonify(saved_products(products_db, request.args.get("q", ""), request.args.get("platform", "")))

    @public_blueprint.get("/products-filters")
    def products_filters() -> Any:
        return jsonify(saved_filters(database()))

    app.register_blueprint(blueprint)
    app.register_blueprint(public_blueprint)
