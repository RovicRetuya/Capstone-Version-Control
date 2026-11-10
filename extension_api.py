"""Reviews collected by the DeFaketive browser extension, checked and analysed like a scan's.

The extension (extension/) reads a product's reviews in the shopper's own browser and the DeFaketive page it
opens then sends them here, signed in, as JSON. Two marketplaces, two collectors:

- Lazada PH: from the same review list our scanner reads, in the same way, but fewer: up to 60 written reviews from
  each star level (the website's own paste-a-link scan reads up to 200), star levels in the order 3, 2, 4, 1, 5, at
  most 300 entries deep per list, 50 per request.
- Shopee PH: every written review the product's review list gives, 59 per request, with no quota and no depth
  limit (SHOPEE_MAX_REVIEWS only bounds what a browser may send).

    POST /api/extension/check   {"product": {...}}   ->  202 {"job": {...}}, then /api/jobs/<id> as for a scan

Nothing a browser sends can be trusted, so before anything is analysed:

- only a signed-in account may send (and the daily limits of protections.py count it like a scan);
- every field is checked for its type and size, the link must be a Lazada PH or a Shopee PH product page;
- the numbers must add up: five star counts, an average that matches them, each star level's reviews no more than
  that level lists (and, for Lazada, no more than 60), every review's stars matching its level, and each level's
  stop reason matching what was collected (Lazada: 60 reviews for "target_reached", none for a level that lists
  none, and so on).

The report is then built exactly as the scanner builds one (lazada-scraper/src/lazada_scraper.py: the feed's
fields, its dates, its record of each star level), so the checker cannot tell the two apart, except for
`collected_via`. The extension never sends reviewers' names; each review gets a stand-in name ("Reviewer 1"...),
as the starter reports do, because the database tells two stored reviews apart by name, date and text.

Analyses take their turn one at a time (protections.ScanQueue), as scans do.

A saved report is not replaced by reviews from a browser while it is recent. Reviews a browser sends cannot be
trusted to be real (the numbers can be made to add up, the text cannot be checked), and a saved report is
what everybody sees and what "Similar products" is picked from. So when the listing was checked less than
RECHECK_DAYS ago (30; DEFAKETIVE_EXTENSION_RECHECK_DAYS, 0 turns the rule off), the server answers with the saved report
and does nothing else: no analysis, nothing saved, and the check is not counted against the daily limits. After
that, a new check may replace the report. A listing nobody has checked yet is taken on trust.
"""

from __future__ import annotations

import datetime
import math
import os
import re
import secrets
import threading
from collections.abc import Callable
from typing import Any

from flask import Blueprint, jsonify

import protections

blueprint = Blueprint("extension", __name__, url_prefix="/api/extension")

QUOTA = 60  # Lazada reviews per star level the extension reads (LAZADA_EXTENSION_REVIEWS_PER_STAR in src/lib/product.ts); a paste-a-link scan reads 200
FEED_DEPTH = 300
SHOPEE_MAX_REVIEWS = 30_000  # the Shopee collector reads every written review; this only bounds what a browser may send
COLLECTION_ORDER = (3, 2, 4, 1, 5)
STOP_REASONS = {"target_reached", "feed_ended", "feed_limit", "none_listed"}
LINK = re.compile(r"^https://www\.lazada\.com\.ph/products/[^?#\s]{1,400}?-i(\d{5,})(?:-s\d+)?\.html$")
# A Shopee PH product page: /<name>-i.<shop>.<item>, or /product/<shop>/<item>.
SHOPEE_LINK = re.compile(r"^https://shopee\.ph/(?:[^?#\s/]{1,400}-i\.\d+\.\d+|product/\d+/\d+)$")
IMAGE_HOSTS = ("lazcdn.com", "alicdn.com", "slatic.net", "lazada.com.ph")
SHOPEE_IMAGE_HOSTS = ("susercontent.com", "shopee.ph", "shopee.com")
ISO_DAY = re.compile(r"^\d{4}-\d{2}-\d{2}$")
SOURCE = "defaketive-extension"

RECHECK_DAYS = 30
# Set by server.py: link -> {"link", "checked_at"} for the saved report of that listing, or None if there is none.
# A name of this module, so tests can replace it.
saved_report: Callable[[str], dict[str, str] | None] = lambda link: None

SIGN_IN_MESSAGE = "Sign in to check products with the DeFaketive extension."
INVALID_MESSAGE = (
    "The reviews the extension sent didn't add up, so nothing was checked. "
    "Reload the product page and press Check again."
)


def recheck_days() -> int:
    try:
        return max(0, int(os.environ.get("DEFAKETIVE_EXTENSION_RECHECK_DAYS", RECHECK_DAYS)))
    except ValueError:
        return RECHECK_DAYS


def recent_report(link: str, now: datetime.datetime | None = None) -> dict[str, Any] | None:
    """The saved report of this listing if it was made less than recheck_days() ago, else None."""
    days = recheck_days()
    saved = saved_report(link) if days else None
    if not saved:
        return None
    try:
        checked = datetime.datetime.fromisoformat(str(saved["checked_at"]))
    except (KeyError, ValueError):
        return None
    if checked.tzinfo is None:
        checked = checked.replace(tzinfo=datetime.timezone.utc)
    age = (now or datetime.datetime.now(datetime.timezone.utc)) - checked
    if age >= datetime.timedelta(days=days):
        return None
    return {"link": saved["link"], "checked_at": checked.isoformat(), "days_ago": max(0, age.days), "keeps_for": days}


class Invalid(ValueError):
    """What was wrong with the data, for the log and the tests; the visitor sees INVALID_MESSAGE."""


def _clean(value: Any, limit: int, field: str, required: bool = False) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise Invalid(f"{field} is not text")
    text = re.sub(r"\s+", " ", value.replace(" ", " ")).strip()
    if len(text) > limit:
        raise Invalid(f"{field} is longer than {limit}")
    if required and not text:
        raise Invalid(f"{field} is empty")
    return text


def _whole(value: Any, field: str, low: int, high: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or int(value) != value:
        raise Invalid(f"{field} is not a whole number")
    if not low <= int(value) <= high:
        raise Invalid(f"{field} is out of range")
    return int(value)


def _feed_date(text: str) -> str:
    """The feed's '31 May 2026' written the way the scanner writes it ('2 weeks ago' stays as it is)."""
    try:
        return datetime.datetime.strptime(text, "%d %b %Y").date().isoformat()
    except ValueError:
        return text


def _image(value: Any, hosts: tuple[str, ...] = IMAGE_HOSTS) -> str:
    link = _clean(value, 600, "img")
    if not link:
        return ""
    match = re.match(r"^https://([^/?#]+)/", link)
    if not match or not match.group(1).casefold().endswith(hosts):
        raise Invalid("img is not an image of the marketplace")
    return link


def _review_day(text: str, marketplace: str) -> str:
    """Lazada's feed writes '31 May 2026'; the Shopee collector sends the day as 2026-05-31 (or nothing)."""
    if marketplace == "lazada":
        return _feed_date(text)
    if text and not ISO_DAY.match(text):
        raise Invalid("a review's time is not a day")
    return text


def product_from_extension(sent: Any) -> dict[str, Any]:
    """The product record a scan would have made from the same reviews, or Invalid."""
    if not isinstance(sent, dict):
        raise Invalid("product is not an object")
    link = _clean(sent.get("link"), 600, "link", required=True)
    if LINK.match(link):
        marketplace = "lazada"
    elif SHOPEE_LINK.match(link):
        marketplace = "shopee"
    else:
        raise Invalid("link is not a Lazada PH or Shopee PH product page")

    ratings = sent.get("ratings")
    if not isinstance(ratings, dict) or not isinstance(ratings.get("scores"), list) or len(ratings["scores"]) != 5:
        raise Invalid("ratings.scores must list five star counts")
    scores = [_whole(value, "ratings.scores", 0, 50_000_000) for value in ratings["scores"]]
    # The extension sends 5 stars first, from either marketplace.
    listed = {star: scores[5 - star] for star in range(1, 6)}
    total = sum(scores)
    if total <= 0:
        raise Invalid("the listing has no ratings")
    average = ratings.get("average")
    if isinstance(average, bool) or not isinstance(average, (int, float)) or not 0 <= average <= 5:
        raise Invalid("ratings.average is not a rating")
    mean = sum(star * count for star, count in listed.items()) / total
    if abs(mean - float(average)) > 0.15:
        raise Invalid("ratings.average does not match the star counts")

    levels = sent.get("levels")
    if not isinstance(levels, dict) or set(levels) != {str(star) for star in range(1, 6)}:
        raise Invalid("levels must describe the five star levels")
    reviews = sent.get("reviews")
    cap = SHOPEE_MAX_REVIEWS if marketplace == "shopee" else QUOTA * 5
    if not isinstance(reviews, list) or len(reviews) > cap:
        raise Invalid(f"reviews is not a list of at most {cap}")

    comments: list[dict[str, Any]] = []
    seen: set[str] = set()
    per_star = {star: 0 for star in range(1, 6)}
    for review in reviews:
        if not isinstance(review, dict):
            raise Invalid("a review is not an object")
        comment_id = _clean(review.get("comment_id"), 40, "comment_id", required=True)
        if not comment_id.isdigit() or comment_id in seen:
            raise Invalid("comment_id is missing, not a number, or repeated")
        seen.add(comment_id)
        rating = _whole(review.get("rating"), "rating", 1, 5)
        if _whole(review.get("source_rating_filter"), "source_rating_filter", 1, 5) != rating:
            raise Invalid("a review's stars do not match its star level")
        per_star[rating] += 1
        comments.append({
            "comment_id": comment_id,
            "rating": rating,
            "time": _review_day(_clean(review.get("time"), 40, "time"), marketplace),
            "content": _clean(review.get("content"), 5000, "content", required=True),
            "variation": _clean(review.get("variation"), 300, "variation"),
            "seller_respond": "",
            "like_count": _whole(review.get("like_count") or 0, "like_count", 0, 50_000_000),
            "source_rating_filter": rating,
        })

    star_collection: dict[str, dict[str, Any]] = {}
    for star in COLLECTION_ORDER:
        level = levels[str(star)]
        if not isinstance(level, dict):
            raise Invalid("a star level is not an object")
        stop = level.get("stop_reason")
        if stop not in STOP_REASONS:
            raise Invalid(f"{star}-star stop reason is not one a finished collection gives")
        collected = per_star[star]
        if collected > (listed[star] if marketplace == "shopee" else min(QUOTA, listed[star])):
            raise Invalid(f"more {star}-star reviews than the level lists or the quota allows")
        if (listed[star] == 0) != (stop == "none_listed"):
            raise Invalid(f"{star}-star level: 'none_listed' must mean the level lists none")
        if stop == "target_reached" and marketplace != "shopee" and collected != QUOTA:
            raise Invalid(f"{star}-star level reached its target without {QUOTA} reviews")
        # The list is cut at 300 entries; a level listing fewer cannot reach that cut. Lazada's 2-star list also
        # holds the 1-star reviews, so there the two together count.
        in_list = listed[1] + listed[2] if star == 2 and marketplace == "lazada" else listed[star]
        if stop == "feed_limit" and in_list <= FEED_DEPTH:
            raise Invalid(f"{star}-star level stopped at the list's depth but its list is shorter than {FEED_DEPTH}")
        if stop == "none_listed":
            star_collection[str(star)] = {"listed": 0, "collected": 0, "stop_reason": stop, "complete": True}
            continue
        star_collection[str(star)] = {
            "listed": listed[star],
            "collected": collected,
            "stop_reason": stop,
            # As the scanner records it: a level cut at the list's depth can be weighted if it holds any review.
            "complete": stop in {"target_reached", "feed_ended"} or (stop == "feed_limit" and collected > 0),
        }

    # The scanner keeps each level's reviews in the order collected, levels from 1 star up. Stand-in names are
    # numbered in that stored order, as in the starter reports.
    comments.sort(key=lambda review: review["source_rating_filter"])
    comments = [{"author": f"Reviewer {number}", **review} for number, review in enumerate(comments, start=1)]
    rating = round(float(average), 1)
    return {
        "link": link,
        "name": _clean(sent.get("name"), 300, "name", required=True),
        "price": _clean(sent.get("price"), 40, "price"),
        "rating": rating,
        "sold_count": 0,
        "img": _image(sent.get("img"), IMAGE_HOSTS if marketplace == "lazada" else SHOPEE_IMAGE_HOSTS),
        "location": "",
        "platform": marketplace,
        "market": "PH",
        "currency": "PHP",
        "brand": _clean(sent.get("brand"), 120, "brand"),
        "seller": _clean(sent.get("seller"), 120, "seller"),
        "description": "",
        "total_rating": total,
        "review_star_distribution": {str(star): listed[star] for star in range(1, 6)},
        "review_star_distribution_source": f"{marketplace}_review_feed",
        "reported_review_count": total,
        "written_reviews_collected": len(comments),
        "qualification": {
            "status": "qualified", "rating": rating, "reported_review_count": total,
            "min_rating": 0.0, "min_reviews": 0, "reasons": [],
        },
        "review_status": "complete",
        "review_source": f"{marketplace}_review_feed",
        "comments": comments,
        "applied_rating_filters": list(COLLECTION_ORDER),
        "star_collection": star_collection,
        "sampling_method": "stratified_by_star",
        "star_quota": max(listed.values()) if marketplace == "shopee" else QUOTA,
        "review_order": "review_feed_default_within_star",
        "collected_via": SOURCE,
    }


def install(webapp: Any, app: Any = None) -> protections.ScanQueue:
    """Add the route to the Flask app (backend/webapp.py). Analyses wait their turn in their own queue."""
    app = app or webapp.app
    analyses = protections.ScanQueue(
        webapp._jobs, webapp._lock, parallel=lambda: 1,
        starting=lambda job: "Analyzing English, Filipino, and Taglish review sentiment…",
    )
    analyse = analyses.wrap(lambda products: webapp.analyze_products(products))

    def start(catalog_key: str, product: dict[str, Any]) -> dict[str, Any]:
        job_id = secrets.token_urlsafe(12)
        job = {
            "id": job_id,
            "state": "running",
            "stage": 2,
            "stage_label": "Analyze reviews",
            "progress": 68,
            "message": "Analyzing English, Filipino, and Taglish review sentiment…",
            "needs_you": False,
            "platform": product["platform"],
            "query": product["link"],
            "product_limit": 1,
            "review_limit": len(product["comments"]),
            "created_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        with webapp._lock:
            webapp._jobs[job_id] = job

        def run() -> None:
            try:
                analyzed = analyse([product])
                with webapp._lock:
                    job.update(stage=3, stage_label="Prepare report", progress=92,
                               message="Preparing the risk report and saving analyzed results…")
                webapp.save_products(analyzed, source=SOURCE)
                with webapp._lock:
                    webapp._catalogs[catalog_key] = analyzed
                    job.update(state="complete", stage=3, stage_label="Complete", progress=100,
                               message=f"Analysis complete — {len(analyzed)} product(s) found.",
                               product_count=len(analyzed))
            except webapp.ModelUnavailableError as error:
                with webapp._lock:
                    job.update(state="error", stage_label="Stopped", message=f"{webapp.MODEL_UNAVAILABLE_MESSAGE} {error}")
            except Exception:
                with webapp._lock:
                    job.update(state="error", stage_label="Stopped",
                               message="The reviews could not be analyzed. Please try again later.")

        threading.Thread(target=run, daemon=True, name=f"{protections.SCAN_THREAD_PREFIX}{job_id}").start()
        return job

    @blueprint.post("/check")
    def check() -> Any:
        payload = webapp._json_body()
        if payload is None:
            return jsonify({"error": "Send this request as JSON."}), 415
        if webapp._current_user() is None:
            return jsonify({"error": SIGN_IN_MESSAGE, "sign_in": True}), 401
        try:
            product = product_from_extension(payload.get("product"))
        except Invalid as problem:
            app.logger.warning("Extension data refused: %s", problem)
            return jsonify({"error": INVALID_MESSAGE, "invalid": True}), 400
        existing = recent_report(product["link"])
        if existing:
            # Not a new check: nothing is analysed or saved, so protections.py gives the daily counts back.
            return jsonify({"existing": existing}), 200
        webapp.require_model()
        job = start(webapp._catalog_key(), product)
        return jsonify({"job": job}), 202

    app.register_blueprint(blueprint)
    return analyses
