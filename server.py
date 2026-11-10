"""Starts the DeFaketive Flask app plus the few extra routes the SvelteKit screens need.

The Flask app (backend/webapp.py, a copy of the original capstone app made by scripts/sync_backend.py) is imported,
not edited. On the live server that copy is the only one there is; on the developer's PC the original app beside
this folder is used instead when it is there (see _original_app). Its accounts, scan limits, live
scans, review checker and verdict wording all stay exactly as they are, and it keeps using the same two databases:
`defaketive.db` (analyzed products and reviews) and `instance/accounts.db` (accounts, history, wishlist).

What the original does not offer is a way to list or open every product in `defaketive.db`. The lists and reports it
serves come from the visitor's own session catalog, so a product that is only in the database (for example one that
another person scanned) cannot be opened. The routes below add that, reading the same database:

    GET /api/saved/products          every analyzed product, as list cards (no review text)
    GET /api/saved/detail?link=...   one product with all its reviews, plus similar products picked from the
                                     whole database (same shape as /api/products/detail)
    GET /api/saved/popular           products saved by two or more accounts, with how many saved them

It also puts in place what protects the app once the public can reach it (protections.py), the route the
browser extension sends collected reviews to (extension_api.py, POST /api/extension/check), and the admin page's
routes for the DTI staff who run the site (admin_api.py, /api/admin/*: accounts, daily limits, reports, password
requests), plus the "Report a problem" and "Forgot password" forms and the Lazada short-link resolver.

Who sees what: these routes serve the SHARED pool (the products table), which is what recommendations are picked
from. A person's own history and wishlist stay in their account (user_activity, user_wishlist) and are only ever
served to them, by the original app's /api/me/* routes.

This file alone is the app on a developer's PC (start.cmd and dev.cmd run it on port 5000, with the screens on
port 5173). The live site runs serve.py instead, which imports this file and adds the public web server.
"""

from __future__ import annotations

import os
import sys
import threading
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

HERE = Path(__file__).resolve().parent


def _original_app() -> Path:
    """Where the original app is: DEFAKETIVE_ORIGINAL, else its own folder beside this project (the developer's PC,
    with the real database), else backend/, the copy this repo carries so it runs on another PC."""
    named = os.environ.get("DEFAKETIVE_ORIGINAL")
    if named:
        return Path(named)
    beside = HERE.parent / "Capstone-Version-Control-Version-1.1"
    return beside if (beside / "webapp.py").is_file() else HERE / "backend"


ORIGINAL = _original_app()
if not (ORIGINAL / "webapp.py").exists():
    sys.exit(f"The original DeFaketive app was not found at {ORIGINAL}. Set DEFAKETIVE_ORIGINAL to its folder.")

# The original resolves its own folders from where its files are, but work from its folder to be safe.
sys.path.insert(0, str(ORIGINAL))
os.chdir(ORIGINAL)

import accounts  # noqa: E402  (the original accounts module)
import webapp  # noqa: E402  (the original app; importing it creates `webapp.app`)
from dashboard_utils import analysis_is_current, merge_product_catalogs, rank_recommendations, with_badge_view  # noqa: E402
from data_store import DEFAULT_DB  # noqa: E402
from flask import Blueprint, jsonify, redirect, request  # noqa: E402

import admin_api  # noqa: E402  (beside this file)
import extension_api  # noqa: E402  (beside this file)
import link_resolver  # noqa: E402  (beside this file)
import password_requests  # noqa: E402  (beside this file)
import problem_reports  # noqa: E402  (beside this file)
import protections  # noqa: E402  (beside this file)
from saved_pool import SavedPool  # noqa: E402  (beside this file)

# These helpers are private to the original module. Fail with a clear message if they ever change.
for name in ("app", "_products", "_cards", "_card", "_accounts_db", "_merged_catalog", "_prepare_saved"):
    if not hasattr(webapp, name):
        sys.exit(f"webapp.{name} is missing: server.py needs updating to match the original app.")

saved = Blueprint("saved", __name__, url_prefix="/api/saved")

# Every saved product, kept between requests and read again only when the database changes (see saved_pool.py).
# Its products are shared by all requests: nothing here alters one.
pool = SavedPool(DEFAULT_DB)


def _merged_catalog() -> list[dict[str, Any]]:
    """The original app's own merge of the session catalog and the saved products, reading them from the pool.

    Its /api/picks, /api/products/detail and /api/wishlist/popular call this, and the screens call those. The
    original reads the whole database each time, which is what made every page wait once it held 168 products.
    """
    return merge_product_catalogs(webapp._products(), pool.snapshot()[0])


webapp._merged_catalog = _merged_catalog


# With no scan file in its folder (a fresh copy on another PC), the original app starts every new browser session
# with its own deep copy of every saved product: seconds, and about 150 MB, per session. Here the saved products are
# served from the pool for every list and report, so a session starts with only what it scans itself.
webapp._prepare_saved = lambda: []


def _identity(link: Any) -> tuple[str, ...]:
    """A listing address reduced to what names the product, so two copies of one link compare equal.

    Host and path are enough for Shopee and Lazada (the rest is tracking). Temu gives every product the same
    path (/goods.html), so its goods_id is part of the identity: without it, all Temu listings look like one.
    """
    parts = urlsplit(str(link or "").strip())
    host = parts.netloc.casefold().removeprefix("www.")
    path = parts.path.rstrip("/").casefold()
    if host.endswith("temu.com"):
        goods = (parse_qs(parts.query).get("goods_id") or [""])[0]
        if goods:
            return (host, path, goods)
    return (host, path)


def _catalog() -> list[dict[str, Any]]:
    """This visitor's session catalog first, then everything in the database. One entry per listing."""
    merged: list[dict[str, Any]] = []
    seen: set[tuple[str, ...]] = set()
    saved_products, saved_at = pool.snapshot()
    # When each product's report was last saved, by listing. The saved product itself carries no date, so without
    # this every report says "Report date: Unavailable". The database row records when it was last written, which
    # is when its report was last made.
    dates = {_identity(link): updated_at for link, updated_at in saved_at.items()}
    for product in [*webapp._products(), *saved_products]:
        if not isinstance(product, dict) or not product.get("link"):
            continue
        key = _identity(product["link"])
        if key in seen:
            continue
        seen.add(key)
        # A copy, so the original app's own session catalog is never altered.
        if dates.get(key) and not (product.get("analysis_date") or product.get("analyzed_at") or product.get("updated_at")):
            product = {**product, "updated_at": dates[key]}
        merged.append(product)
    return merged


def _checked_with_current(product: dict[str, Any]) -> bool:
    """Whether this saved report was made by the checker the app is running now.

    A saved report is shown as it was stored. When the checker is changed afterwards the report does not
    change with it, so the screens say so until it is re-checked (scripts/recheck_products.py) or the
    product is scanned again. The original app's own test decides what "current" means.
    """
    return analysis_is_current([product])


@saved.get("/products")
def saved_products():
    products = _catalog()
    cards = webapp._cards(products)
    for card, product in zip(cards, products):
        card["checked_with_current"] = _checked_with_current(product)
    return jsonify({"products": cards, "count": len(products)})


@saved.get("/detail")
def saved_detail():
    link = str(request.args.get("link") or "")
    catalog = _catalog()
    wanted = _identity(link)
    product = next((p for p in catalog if str(p.get("link") or "") == link), None) or next(
        (p for p in catalog if wanted[0] and _identity(p.get("link")) == wanted), None
    )
    if not product:
        return jsonify({"error": "Product not found in the saved database."}), 404
    recommendations = rank_recommendations(product, catalog, limit=3)
    shown = {**with_badge_view(product), "checked_with_current": _checked_with_current(product)}
    return jsonify({"product": shown, "recommendations": webapp._cards(recommendations)})


@saved.get("/popular")
def saved_popular():
    by_identity = {_identity(product.get("link")): product for product in reversed(_catalog())}
    popular = []
    for link, saves in accounts.popular_wishlist(webapp._accounts_db()):
        product = by_identity.get(_identity(link))
        if product:
            popular.append({"product": webapp._card(product), "saves": saves})
    return jsonify({"products": popular})


webapp.app.register_blueprint(saved)
webapp.app.register_blueprint(link_resolver.blueprint)

# What keeps the app safe once people outside the team can reach it: closed old routes, daily limits, one Chrome
# at a time, no copy of a scan per visitor, no reviewer names in what is sent (protections.py says why).
scan_queue = protections.install(webapp, accounts)

# Reviews the DeFaketive browser extension collected in a shopper's own browser: checked, then analysed like a
# scan's (extension_api.py).
analysis_queue = extension_api.install(webapp)


def _saved_report(link: str) -> dict[str, str] | None:
    """When this listing's saved report was last written (its row's updated_at), for extension_api's recent-report rule."""
    wanted = _identity(link)
    for saved_link, updated_at in pool.snapshot()[1].items():
        if _identity(saved_link) == wanted and updated_at:
            return {"link": saved_link, "checked_at": updated_at}
    return None


extension_api.saved_report = _saved_report


@webapp.app.before_request
def one_address():
    """Developer PC only (the live site is never opened at 127.0.0.1:5000): a page opened at
    http://127.0.0.1:5000 goes to http://localhost:5000: the same computer, but the browser keeps
    separate sign-ins for the two names, so people were seeing two apps. Only pages are moved, never /api calls."""
    if request.method == "GET" and request.host == "127.0.0.1:5000" and not request.path.startswith("/api/"):
        if "text/html" in request.headers.get("Accept", ""):
            return redirect(request.url.replace("127.0.0.1", "localhost", 1), 307)
    return None


# The admin page's routes (accounts, daily limits, Products page options, reports, password requests), open only to
# admin accounts (admin_api.py: Admin@defake.com and the admins it makes).
# After protections.install, so the limits an admin saved replace the environment's.
admin_api.install(webapp, products_db=DEFAULT_DB)
# The "Report a problem" form (problem_reports.py).
problem_reports.install(webapp)
# The "Forgot password" form (password_requests.py).
password_requests.install(webapp)

if __name__ == "__main__":
    # Flask's debug mode shows a developer's error page in the browser. That is for changing the code (dev.cmd
    # sets DEFAKETIVE_DEBUG=1), not for using or demonstrating the app, so it is off unless asked for.
    debug = os.environ.get("DEFAKETIVE_DEBUG") == "1"
    # Read the saved products while the server starts, so the first page does not wait for them.
    threading.Thread(target=pool.snapshot, daemon=True).start()
    webapp.app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "5000")), debug=debug, use_reloader=False)
