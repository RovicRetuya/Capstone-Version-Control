"""Runs DeFaketive for the public: the finished screens and the data from one address, on a proper web server.

Run it with the original app's Python (public.cmd does this, with --https --proxy cloudflare):

    ..\\Capstone-Version-Control-Version-1.1\\.venv\\Scripts\\python.exe serve.py
    ..\\Capstone-Version-Control-Version-1.1\\.venv\\Scripts\\python.exe serve.py --https --proxy cloudflare

How it differs from start.cmd, which stays the way to use the app on this PC:

- Waitress serves, not Flask's development server and Vite's preview. It is ONE process with many threads: the
  progress of running scans lives in this process's memory, so the app must never run as several processes.
- The screens (build/, made by `npm run build`) and /api come from the same address, so nothing passes /api along.
- The scan progress tells visitors that a team member has to clear a Lazada check (protections.use_public_wording).
- --https: sign-in cookies travel only over https. --proxy cloudflare: the visitor's address is read from
  Cloudflare's header (only on requests that come from this computer, which is where cloudflared runs).
- Both databases are backed up a minute after start and then once a day (scripts/backup_databases.py).
- A few safety headers on every answer, and /api answers are never cached.
- The admin side is a page of the app itself (/admin), signed in on the same sign-in as everyone else; only the one
  admin account (admin_api.py) gets past it.

Everything in protections.py (closed old routes, daily limits, one Chrome at a time, no reviewer names) is part of
server.py, so it is on here too.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import os
import sys
import threading
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BUILD = HERE / "build"
# The built app's file names change with their content, so these can be kept for a year.
IMMUTABLE = "_app/immutable/"
BACKUP_EVERY = 24 * 60 * 60


def _arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run DeFaketive for the public.")
    parser.add_argument("--host", default="127.0.0.1", help="address to listen on (default 127.0.0.1: this computer only, "
                        "which is all Cloudflare Tunnel needs)")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT", "8080")), help="port (default 8080)")
    parser.add_argument("--threads", type=int, default=16, help="requests served at the same time (default 16)")
    parser.add_argument("--https", action="store_true", help="the public reaches the app over https (sign-in cookies "
                        "then travel only over https)")
    parser.add_argument("--proxy", choices=("none", "cloudflare"), default=os.environ.get("DEFAKETIVE_PROXY", "none"),
                        help="what stands between the visitor and the app (default none)")
    parser.add_argument("--no-backups", action="store_true", help="do not back up the databases")
    return parser.parse_args(argv)


def create_public_app(https: bool = False) -> Any:
    """The original app with server.py's routes and protections, serving build/ and wording scans for the public."""
    if not (BUILD / "index.html").is_file():
        sys.exit(f"The finished app was not found in {BUILD}. Run `npm run build` first (public.cmd does this).")

    import protections
    import server
    from flask import jsonify, request, send_from_directory

    app = server.webapp.app
    protections.use_public_wording(server.webapp)
    app.config["SESSION_COOKIE_SECURE"] = https
    build = BUILD.resolve()

    def screens(path: str = "") -> Any:
        if path == "api" or path.startswith("api/"):
            return jsonify({"error": "Not found."}), 404
        if path:
            candidate = (build / path).resolve()
            if candidate.is_relative_to(build) and candidate.is_file():
                if path.startswith(IMMUTABLE):
                    response = send_from_directory(build, path, max_age=365 * 24 * 60 * 60)
                    response.cache_control.immutable = True
                else:
                    response = send_from_directory(build, path, max_age=0)
                    response.cache_control.no_cache = True
                return response
        # Every other address is a page of the app: the app's one page draws it (SvelteKit's fallback).
        response = send_from_directory(build, "index.html", max_age=0)
        response.cache_control.no_cache = True
        return response

    # The original's "/" drew its own old page; the public gets the new screens.
    app.view_functions["index"] = screens
    app.add_url_rule("/<path:path>", "screens", screens)

    app.after_request(_safety_headers)
    app.after_request(_hide_scanner_errors)
    return app


def _safety_headers(response: Any) -> Any:
    from flask import request

    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


SCANNER_UNAVAILABLE = ("This site can't read new products by itself. Install the DeFaketive browser extension, open the "
                       "product page on Lazada PH or Shopee PH and press Check. Saved reports open here as usual.")


def _hide_scanner_errors(response: Any) -> Any:
    """A server with no Chrome cannot run the scanner; the visitor gets this message, not its traceback and file paths."""
    from flask import request

    if request.path.startswith("/api/jobs/") and response.mimetype == "application/json":
        job = response.get_json(silent=True)
        if isinstance(job, dict) and job.get("state") == "error" and re.search(r"Traceback|site-packages|\.venv|Stacktrace|selenium|webdriver", str(job.get("message") or "")):
            job["message"] = SCANNER_UNAVAILABLE
            response.set_data(json.dumps(job))
    return response


def _backup_script() -> Any:
    spec = importlib.util.spec_from_file_location("backup_databases", HERE / "scripts" / "backup_databases.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    return module


def _daily_backups() -> None:
    script = _backup_script()
    time.sleep(60)
    while True:
        try:
            sources = script.databases()
            print(f"Databases backed up to {script.backup(sources, HERE / 'backups' / 'daily')}", flush=True)
        except Exception as error:  # a failed backup must not stop the app; it says so and tries again tomorrow
            print(f"The daily backup failed: {error}", flush=True)
        time.sleep(BACKUP_EVERY)


def main(argv: list[str] | None = None) -> None:
    args = _arguments(argv)
    os.environ["DEFAKETIVE_PROXY"] = args.proxy
    app = create_public_app(https=args.https)

    import server
    from waitress import serve

    # Read the saved products while the server starts, so the first page does not wait for them.
    threading.Thread(target=server.pool.snapshot, daemon=True).start()
    if not args.no_backups:
        threading.Thread(target=_daily_backups, daemon=True, name="defaketive-backups").start()
    print(f"DeFaketive is running on http://{args.host}:{args.port} (https: {'yes' if args.https else 'no'}, "
          f"proxy: {args.proxy}). Keep this window open; close it to stop.", flush=True)
    serve(app, host=args.host, port=args.port, threads=args.threads, ident="DeFaketive",
          max_request_body_size=11 * 1024 * 1024)


if __name__ == "__main__":
    main()
