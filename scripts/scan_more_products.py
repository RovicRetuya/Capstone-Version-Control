"""Scan more Lazada listings, only so the app has more products to suggest from.

Why. "Similar products" can only suggest a product the app has a report for, with no warning signs and not one
safety mention. Whole kinds of product had none: of 13 saved earbuds, not one qualified. This collects more
listings; add_scanned_products.py then reads and saves them.

Which listings.
  --known    the listings in the original app's own lists (research/data/lazada_*_discovery.json) that are
             neither saved nor scanned yet;
  --search   the first listings Lazada returns for each search given, such as "wireless earbuds".
Either way a listing is scanned only if it has at least --min-ratings ratings (100): fewer rarely leaves the 30
written reviews a verdict needs. One with fewer is looked at once and passed over.

How. The original app's own scraper, the way the app runs it with the review feed: no Chrome window, all five
star levels, up to 200 written reviews from each, ratings per star level recorded. The scans go to this project's
backups/pool-scans/, never the original app's folder (its scan files are sources for its labelling work) and never
its research/data/reference_scans/feed/ (those are the listings the baseline was measured on, and must stay that
set). A login or a verification is not waited for and never answered: a run that reads nothing from the feed stops
everything.

Run it with the original app's Python, from this folder:

    ..\\Capstone-Version-Control-Version-1.1\\.venv\\Scripts\\python.exe scripts\\scan_more_products.py --known
    ..\\Capstone-Version-Control-Version-1.1\\.venv\\Scripts\\python.exe scripts\\scan_more_products.py --search "wireless earbuds" "power bank"
    ... --scan

Without --scan it only lists what it would do and contacts nobody.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# recheck_products finds the original app, works from its folder and brings in its functions.
from recheck_products import HERE, ORIGINAL, saved_rows
from rescan_products import not_kept

from data_store import DEFAULT_DB  # noqa: E402

OUT = HERE / "backups" / "pool-scans"
LOG = OUT / "scan_log.json"
SCRAPER = ORIGINAL / "lazada-scraper" / "src" / "lazada_scraper.py"
BASELINE_SCANS = ORIGINAL / "research" / "data" / "reference_scans" / "feed"
DISCOVERY = ORIGINAL / "research" / "data"
PER_STAR = 200         # webapp.LAZADA_REVIEWS_PER_STAR
TIME_BUDGET = 40 * 60  # one run: a search and up to a couple of dozen listings
PAUSE_SECONDS = 10


def item_id(link: str) -> str:
    match = re.search(r"-i(\d{5,})", str(link or ""))
    return match.group(1) if match else str(link or "")


def products_in(path: Path) -> list[dict[str, Any]]:
    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
    except (OSError, ValueError):
        return []
    if isinstance(data, dict):
        data = data.get("products", [])
    return [product for product in data if isinstance(product, dict) and product.get("link")] if isinstance(data, list) else []


def already_have() -> set[str]:
    """Items that are saved, or scanned and waiting to be added."""
    items = {item_id(row["link"]) for row in saved_rows(Path(DEFAULT_DB))}
    for folder in (BASELINE_SCANS, OUT):
        for path in folder.glob("*.json"):
            if path.name.endswith("_discovery.json"):
                continue
            # A listing a search passed over is not "had": only one that was read.
            items.update(item_id(product["link"]) for product in products_in(path) if not not_kept(product))
    return items


def known_listings() -> list[dict[str, str]]:
    have = already_have()
    found: dict[str, dict[str, str]] = {}
    for path in sorted(DISCOVERY.glob("lazada_*_discovery.json")):
        for product in products_in(path):
            key = item_id(product["link"])
            if "lazada.com.ph" in product["link"] and key not in have:
                found.setdefault(key, {"link": product["link"], "name": str(product.get("name") or "")})
    return list(found.values())


def run(label: str, target: Path, what: list[str], minimum_ratings: int) -> dict[str, Any]:
    """One scraper run. `what` is the search or the product links, as the scraper takes them."""
    command = [
        sys.executable, str(SCRAPER), "-r", "100", "--all-star-types", "--star-limit-per-type", str(PER_STAR),
        "--min-reviews", str(minimum_ratings), "--window", "headless", "--reviews-from", "feed",
        "--no-verification-pause", "--verification-timeout", "0", "--output", str(target), *what,
    ]
    started = time.time()
    try:
        code: Any = subprocess.run(
            command, cwd=ORIGINAL, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIME_BUDGET
        ).returncode
    except subprocess.TimeoutExpired:
        code = "timeout"
    products = products_in(target) if target.is_file() else []
    kept = [product for product in products if not not_kept(product)]
    passed_over = [product for product in products if product.get("review_status") == "not_qualified"]
    return {
        "label": label, "file": target.name, "exit": code, "seconds": round(time.time() - started),
        "listings_looked_at": len(products), "scanned": len(kept), "passed_over_too_few_ratings": len(passed_over),
        "not_read": len(products) - len(kept) - len(passed_over),
        "scanned_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--known", action="store_true", help="the listings in the original app's lists not saved or scanned yet")
    parser.add_argument("--search", nargs="*", default=[], help="Lazada searches, each in quotes")
    parser.add_argument("--each", type=int, default=14, help="listings to look at for each search (some are passed over)")
    parser.add_argument("--min-ratings", type=int, default=100, help="scan a listing only if it has at least this many ratings")
    parser.add_argument("--scan", action="store_true", help="really scan; without it this only lists")
    arguments = parser.parse_args()
    for stream in (sys.stdout, sys.stderr):
        stream.reconfigure(encoding="utf-8", errors="replace")
    if not arguments.known and not arguments.search:
        parser.error("say what to scan: --known, --search, or both")

    runs: list[tuple[str, Path, list[str]]] = []
    if arguments.known:
        listings = known_listings()
        print(f"{len(listings)} known listings not saved or scanned yet.")
        for listing in listings:
            print(f"    {listing['name'][:90]}")
        if listings:
            runs.append((
                "known listings", OUT / "known.json",
                ["-n", str(len(listings))] + [part for listing in listings for part in ("--product-url", listing["link"])],
            ))
    for search in arguments.search:
        slug = re.sub(r"[^a-z0-9]+", "_", search.casefold()).strip("_")
        print(f'Search "{search}": the first {arguments.each} listings Lazada returns.')
        runs.append((f"search: {search}", OUT / f"search_{slug}.json", [search, "-n", str(arguments.each), "--pages", "3"]))
    print(f"A listing needs at least {arguments.min_ratings} ratings to be scanned. Scans go to {OUT}.")
    if not arguments.scan:
        print("\nNothing was scanned and nobody was contacted. Add --scan to do it.")
        return 0

    OUT.mkdir(parents=True, exist_ok=True)
    log = json.loads(LOG.read_bytes().decode("utf-8")) if LOG.is_file() else {"runs": []}
    for number, (label, target, what) in enumerate(runs, start=1):
        if number > 1:
            time.sleep(PAUSE_SECONDS)
        print(f"[{number}/{len(runs)}] {label} ...", end=" ", flush=True)
        outcome = run(label, target, what, arguments.min_ratings)
        log["runs"].append(outcome)
        LOG.write_bytes((json.dumps(log, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
        print(f"{outcome['scanned']} scanned, {outcome['passed_over_too_few_ratings']} passed over, "
              f"{outcome['not_read']} not read, in {outcome['seconds']} s", flush=True)
        if not outcome["scanned"] and outcome["not_read"]:
            print("Nothing could be read from the review feed in that run. Stopping: Lazada may be asking for a check.")
            return 2
    print(f"Done. Next: scripts\\add_scanned_products.py (it lists what it would add).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
