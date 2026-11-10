"""What keeps the app safe once people outside the team can reach it. server.py installs all of it.

The original app (imported, not edited) was written for one PC and the people sitting at it. Opened to the
public, these were measured on 15 Oct 2026 on a copy of the real database:

1. Closed routes. Older routes that the new screens never call answered anyone without signing in:
   /api/upload added any product to the shared database (and so to everyone's "Similar products"),
   /api/evaluation ran the review model over an uploaded file of up to 10 MB, /api/survey stored anything sent
   to it, and /api/admin/overview|database|lexicons|logs and /api/export/* gave out the scan logs, the word lists and review text. They now
   answer 404. DEFAKETIVE_OLD_ROUTES=1 opens them again (the original's own page on port 5000 uses them).

2. Daily limits that hold. A guest's 3 free scans were counted per browser cookie, so clearing cookies gave 3
   more; an account (made in seconds, no email check) had no limit at all. On top of the original's cookie count:
   guests share a daily limit per internet connection (DEFAKETIVE_NETWORK_DAILY_SCANS, 10: phone networks put
   many people behind one address), each account has one (DEFAKETIVE_ACCOUNT_DAILY_SCANS, 10) and so does the
   whole site (DEFAKETIVE_SITE_DAILY_SCANS, 100), which also keeps the load on Lazada small. They are counted in
   the original's own guest_scans table; a connection is stored only as a scrambled key, and rows older than a
   week are removed.

3. One Chrome at a time. Every scan used to start its own Chrome at once, so ten people pressing Check meant ten
   browsers. Scans now wait their turn and say how many are ahead. With DEFAKETIVE_MAX_ACTIVE_SCANS (6) running
   or waiting, a new one is turned away with "busy, try again in a few minutes".

4. No copy per visitor. Every new browser session (every request without a cookie, from a crawler too) got its
   own copy of the newest scan file, kept for good, and wrote that file into the database again: 200 such
   visits cost 65 MB and 78 s. A session now starts empty (every saved report is served from the shared pool
   anyway) and session catalogs are forgotten when idle or when there are too many.

5. No reviewer names. Each report the server sent carried every reviewer's Lazada name (175 of 182 saved
   reports had them), though no screen shows one. They are removed from every report sent. The database keeps
   them; only what leaves the server changes.

6. Public wording (only when serve.py runs the app for the public). A visitor cannot answer a Lazada check in a
   Chrome window on the scanning PC, so the progress messages say a team member has to clear it, and the job
   carries `needs_team` so the screens word their notice that way.
"""

from __future__ import annotations

import hashlib
import os
import sqlite3
import threading
import time
from collections.abc import Callable
from contextlib import closing
from datetime import datetime, timedelta, timezone
from typing import Any

from flask import Flask, Response, current_app, g, jsonify, request

# The original's admin routes by name: /api/admin/ itself now holds the admin page's own routes (admin_api.py).
CLOSED_PATHS = frozenset({
    "/api/upload", "/api/evaluation", "/api/survey",
    "/api/admin/overview", "/api/admin/database", "/api/admin/lexicons", "/api/admin/logs",
})
CLOSED_PREFIXES = ("/api/export/",)
# Requests that start a new check, and so count against the daily limits: a live scan, and reviews an extension
# collected (extension_api.py). /api/search only counts when it asks for a live scan.
COUNTED_PATHS = frozenset({"/api/search", "/api/extension/check"})
# Routes whose answer holds a product with its reviews.
REPORT_PATHS = frozenset({"/api/products/detail", "/api/saved/detail"})
# Review fields that name a person.
PERSONAL_REVIEW_FIELDS = ("author",)

SITE_KEY = "site"
SCAN_THREAD_PREFIX = "defaketive-scrape-"

SITE_LIMIT_MESSAGE = "DeFaketive has reached today's limit of new checks. Saved reports still open. Try again tomorrow."
ACCOUNT_LIMIT_MESSAGE = "You've used today's {limit} checks. You can still open saved reports. New checks are available tomorrow."
NETWORK_LIMIT_MESSAGE = (
    "Too many free checks were started from this internet connection today. "
    "Sign in or create a free account to keep checking."
)
BUSY_MESSAGE = "DeFaketive is busy with other checks right now. Please try again in a few minutes."

# What the progress panel says, for the public, when the scanner's Chrome window needs a person (serve.py).
PUBLIC_LOGIN_MESSAGE = (
    "Lazada asked our scanner to log in again. Someone from our team has to do this at the scanning computer. "
    "If it isn't done within 10 minutes, this check stops and you can try again later."
)
PUBLIC_CHECK_MESSAGE = (
    "Lazada asked for a security check. Someone from our team has to clear it at the scanning computer. "
    "If it isn't cleared within 10 minutes, this check stops and you can try again later."
)
PUBLIC_REVIEWS_HELD_MESSAGE = (
    "Lazada is not showing this product's reviews yet, perhaps because of a security check. Someone from our team "
    "has to look at the scanning computer. If it isn't cleared within 10 minutes, this check stops."
)


def _setting(name: str, default: int) -> int:
    try:
        return max(0, int(os.environ.get(name, default)))
    except ValueError:
        return default


class Limits:
    """The numbers, read when the app starts. The admin page changes site, account and network on the object
    (admin_api.py keeps them), and so do tests."""

    def __init__(self) -> None:
        self.site = _setting("DEFAKETIVE_SITE_DAILY_SCANS", 100)
        self.account = _setting("DEFAKETIVE_ACCOUNT_DAILY_SCANS", 10)
        self.network = _setting("DEFAKETIVE_NETWORK_DAILY_SCANS", 10)
        self.active_scans = max(1, _setting("DEFAKETIVE_MAX_ACTIVE_SCANS", 6))
        # Chrome windows at the same time. One: each needs about half a gigabyte, and Lazada sees one shopper.
        self.parallel_scans = max(1, _setting("DEFAKETIVE_PARALLEL_SCANS", 1))
        self.session_catalogs = max(10, _setting("DEFAKETIVE_SESSION_CATALOGS", 2000))
        self.session_idle_seconds = max(60, _setting("DEFAKETIVE_SESSION_IDLE_SECONDS", 2 * 60 * 60))


limits = Limits()


# --- 4. Session catalogs --------------------------------------------------------------------------------------


class SessionCatalogs(dict):
    """The original's per-session catalogs, forgotten when idle or when there are too many.

    The original reads and writes `_catalogs` only while holding its lock, so this needs no lock of its own.
    Empty catalogs (visitors who never scanned, crawlers) go first; a catalog holding a scan goes only when it is
    the oldest of those left or has been idle for `session_idle_seconds`.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._used: dict[str, float] = {key: time.monotonic() for key in self}

    def __getitem__(self, key: str) -> Any:
        value = super().__getitem__(key)
        self._used[key] = time.monotonic()
        return value

    def __setitem__(self, key: str, value: Any) -> None:
        super().__setitem__(key, value)
        self._used[key] = time.monotonic()
        self.prune(keep=key)

    def __delitem__(self, key: str) -> None:
        super().__delitem__(key)
        self._used.pop(key, None)

    def pop(self, key: str, *default: Any) -> Any:
        self._used.pop(key, None)
        return super().pop(key, *default)

    def prune(self, keep: str | None = None) -> None:
        now = time.monotonic()
        for key in [k for k, used in self._used.items() if k != keep and now - used > limits.session_idle_seconds]:
            del self[key]
        excess = len(self) - limits.session_catalogs
        if excess <= 0:
            return
        oldest = sorted((k for k in self._used if k != keep), key=self._used.__getitem__)
        empty_first = [k for k in oldest if not dict.__getitem__(self, k)] + [k for k in oldest if dict.__getitem__(self, k)]
        for key in empty_first[:excess]:
            del self[key]


# --- 5. Reviewer names ----------------------------------------------------------------------------------------


def without_names(product: Any) -> Any:
    """A copy of a product whose reviews name nobody. Never alters the product it was given."""
    if not isinstance(product, dict) or not isinstance(product.get("comments"), list):
        return product
    comments = [
        {key: value for key, value in review.items() if key not in PERSONAL_REVIEW_FIELDS}
        if isinstance(review, dict)
        else review
        for review in product["comments"]
    ]
    return {**product, "comments": comments}


# --- 2 and 3. Limits and the scan queue -----------------------------------------------------------------------


def client_address() -> str:
    """The visitor's internet address.

    Behind a proxy on this same computer (Caddy on the live server, cloudflared on a PC) every request comes from
    the proxy, which names the real visitor in CF-Connecting-IP (Caddy sets it itself: deploy/Caddyfile). That
    header is believed only when DEFAKETIVE_PROXY=cloudflare (serve.py --proxy cloudflare) and the request really
    came from this computer; otherwise anyone could pick their own address.
    """
    remote = request.remote_addr or ""
    if os.environ.get("DEFAKETIVE_PROXY") == "cloudflare" and remote in {"127.0.0.1", "::1"}:
        return request.headers.get("CF-Connecting-IP", "").strip() or remote
    return remote


def network_key(secret: str, address: str) -> str:
    """A connection's key in the database: scrambled with the app's secret, so the address itself is not kept."""
    return "network:" + hashlib.sha256(f"{secret}|{address}".encode("utf-8")).hexdigest()[:24]


def _opening_message(job: dict[str, Any]) -> str:
    return f"Opening {str(job.get('platform') or 'lazada').title()} and collecting public reviews…"


class ScanQueue:
    """Lets `parallel` jobs at a time do the heavy part (a scan's Chrome window, or an analysis); the others wait
    their turn, oldest first, and their message says how many are ahead.

    A job is known by its thread's name ("defaketive-scrape-<job id>", as the original names scan threads).
    `starting` words the message for the moment a job's turn comes.
    """

    def __init__(self, jobs: dict[str, dict[str, Any]], lock: Any, parallel: Callable[[], int] | None = None,
                 starting: Callable[[dict[str, Any]], str] = _opening_message) -> None:
        self.jobs = jobs
        self.lock = lock
        self.parallel = parallel or (lambda: limits.parallel_scans)
        self.starting = starting
        self.condition = threading.Condition()
        self.waiting: list[str] = []
        self.running = 0

    def _say(self, job_id: str, message: str) -> None:
        with self.lock:
            job = self.jobs.get(job_id)
            if job is not None and job.get("state") == "running":
                job["message"] = message

    def _tell_positions(self) -> None:
        for place, job_id in enumerate(self.waiting):
            ahead = self.running + place
            self._say(job_id, f"Waiting for {ahead} other check{'s' if ahead != 1 else ''} to finish first…")

    def wrap(self, work: Callable[..., Any]) -> Callable[..., Any]:
        def queued(*args: Any, **kwargs: Any) -> Any:
            name = threading.current_thread().name
            job_id = name[len(SCAN_THREAD_PREFIX):] if name.startswith(SCAN_THREAD_PREFIX) else name
            with self.condition:
                self.waiting.append(job_id)
                self._tell_positions()
                while self.running >= self.parallel() or self.waiting[0] != job_id:
                    self.condition.wait(timeout=5)
                self.waiting.pop(0)
                self.running += 1
                self._tell_positions()
            with self.lock:
                job = self.jobs.get(job_id) or {}
            self._say(job_id, self.starting(job))
            try:
                return work(*args, **kwargs)
            finally:
                with self.condition:
                    self.running -= 1
                    self._tell_positions()
                    self.condition.notify_all()

        queued.__wrapped__ = work  # type: ignore[attr-defined]
        return queued


# --- Installing it --------------------------------------------------------------------------------------------


def _json_error(message: str, status: int, **extra: Any) -> tuple[Response, int]:
    return jsonify({"error": message, **extra}), status


def public_progress(reader: Callable[[str], dict[str, Any] | None]) -> Callable[[str], dict[str, Any] | None]:
    """The scraper's progress lines, marked `needs_team` whenever they ask for a person."""

    def read(line: str) -> dict[str, Any] | None:
        update = reader(line)
        if update and "needs_you" in update:
            update = {**update, "needs_team": update["needs_you"]}
        return update

    read.__wrapped__ = reader  # type: ignore[attr-defined]
    return read


def use_public_wording(webapp: Any) -> None:
    """For serve.py: progress messages for a visitor who is not at the scanning computer."""
    webapp.LAZADA_LOGIN_MESSAGE = PUBLIC_LOGIN_MESSAGE
    webapp.LAZADA_CHECK_MESSAGE = PUBLIC_CHECK_MESSAGE
    webapp.LAZADA_REVIEWS_HELD_MESSAGE = PUBLIC_REVIEWS_HELD_MESSAGE
    reader = webapp.SCAN_PROGRESS_READERS.get("lazada")
    if reader is not None and not hasattr(reader, "__wrapped__"):
        webapp.SCAN_PROGRESS_READERS["lazada"] = public_progress(reader)


def _housekeeping(webapp: Any, accounts_db: str) -> None:
    """Forget what is no longer needed: stale sign-in failures, finished jobs, old daily counts."""
    now = time.monotonic()
    with webapp._lock:
        for email in [e for e, moments in webapp._login_failures.items()
                      if not any(now - m < webapp.LOGIN_FAILURE_WINDOW for m in moments)]:
            webapp._login_failures.pop(email, None)
        cutoff = datetime.now(timezone.utc) - timedelta(days=1)
        for job_id in [i for i, job in webapp._jobs.items() if job.get("state") != "running"
                       and str(job.get("created_at") or "") < cutoff.isoformat()]:
            webapp._jobs.pop(job_id, None)
        if isinstance(webapp._catalogs, SessionCatalogs):
            webapp._catalogs.prune()
    week_ago = (datetime.now(timezone.utc) - timedelta(days=7)).date().isoformat()
    try:
        with closing(sqlite3.connect(accounts_db)) as connection, connection:
            connection.execute("DELETE FROM guest_scans WHERE day < ?", (week_ago,))
    except sqlite3.Error:
        pass


def install(webapp: Any, accounts: Any, app: Flask | None = None) -> ScanQueue:
    """Put every protection in place on the original app. Call once, before the first request."""
    app = app or webapp.app

    # 4. Sessions start empty and are forgotten in time.
    webapp._load_initial_catalog = lambda: []
    if not isinstance(webapp._catalogs, SessionCatalogs):
        webapp._catalogs = SessionCatalogs(webapp._catalogs)

    # 3. One Chrome at a time.
    queue = ScanQueue(webapp._jobs, webapp._lock)
    if not hasattr(webapp._run_scraper, "__wrapped__"):
        webapp._run_scraper = queue.wrap(webapp._run_scraper)

    housekeeping = {"next": 0.0}

    @app.before_request
    def close_and_count() -> Any:
        path = request.path
        # 1. Closed routes.
        if (path in CLOSED_PATHS or path.startswith(CLOSED_PREFIXES)) and os.environ.get("DEFAKETIVE_OLD_ROUTES") != "1":
            return _json_error("Not found.", 404)

        if time.monotonic() >= housekeeping["next"]:
            housekeeping["next"] = time.monotonic() + 300
            _housekeeping(webapp, current_app.config["ACCOUNTS_DB"])

        # 2. Daily limits, for a request that would start a check.
        if request.method != "POST" or path not in COUNTED_PATHS:
            return None
        if path == "/api/search":
            payload = request.get_json(silent=True)
            if not isinstance(payload, dict) or not payload.get("live"):
                return None
        with webapp._lock:
            active = sum(1 for job in webapp._jobs.values() if job.get("state") == "running")
        if active >= limits.active_scans:
            return _json_error(BUSY_MESSAGE, 503, busy=True)

        database = current_app.config["ACCOUNTS_DB"]
        day = accounts.manila_day()
        taken: list[str] = []

        def take(key: str, limit: int) -> bool:
            if accounts.reserve_guest_scan(database, key, day, limit):
                taken.append(key)
                return True
            for done in taken:
                accounts.release_guest_scan(database, done, day)
            taken.clear()
            return False

        user = webapp._current_user()
        if not take(SITE_KEY, limits.site):
            return _json_error(SITE_LIMIT_MESSAGE, 429, site_limit=True)
        if user is not None:
            if not take(f"account:{user['id']}", limits.account):
                return _json_error(ACCOUNT_LIMIT_MESSAGE.format(limit=limits.account), 429, account_limit=True)
        elif not take(network_key(current_app.config["SECRET_KEY"], client_address()), limits.network):
            return _json_error(NETWORK_LIMIT_MESSAGE, 429, network_limit=True)
        g.scan_counts = (database, day, taken)
        return None

    @app.after_request
    def finish(response: Response) -> Response:
        # 2. A scan that did not start gives its counts back.
        counted = g.pop("scan_counts", None)
        if counted and response.status_code != 202:
            database, day, taken = counted
            for key in taken:
                accounts.release_guest_scan(database, key, day)
        # 5. No reviewer names leave the server.
        if request.path in REPORT_PATHS and response.status_code == 200 and response.is_json:
            body = response.get_json(silent=True)
            if isinstance(body, dict) and isinstance(body.get("product"), dict):
                body["product"] = without_names(body["product"])
                response.set_data(app.json.dumps(body))
        return response

    return queue
