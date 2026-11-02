"""Turns a Lazada app short link (https://s.lazada.com.ph/s.AbCd) into the product page it points to.

The Lazada app copies short links that name no product. The site needs the product page's own address to find a saved
report or to scan, so:

    GET /api/resolve-link?url=<short link>   ->  {"link": "https://www.lazada.com.ph/products/...-i123-s456.html"}

Because the server fetches whatever address it is given, it is strict about what it will fetch: only Lazada's own
short-link hosts to start, only Lazada hosts for each redirect after that, at most five of them, nothing else.
Answers are kept for a day so one shared link is not looked up again and again.
"""

from __future__ import annotations

import re
import time
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urljoin, urlsplit

from flask import Blueprint, jsonify, request

blueprint = Blueprint("link_resolver", __name__, url_prefix="/api")

START_HOSTS = {"s.lazada.com.ph", "lzd.co"}
MAX_REDIRECTS = 5
TIMEOUT = 8
CACHE_SECONDS = 24 * 60 * 60
PRODUCT = re.compile(r'''https?://(?:www\.|m\.)?lazada\.com\.ph(/products/[^\s?#"'<>\\]*?-i\d{5,}(?:-s\d+)?\.html)''', re.I)
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Mobile Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
}
_cache: dict[str, tuple[float, str]] = {}


def _lazada_host(host: str) -> bool:
    host = host.lower()
    return host in START_HOSTS or host == "lazada.com.ph" or host.endswith(".lazada.com.ph")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def _product_link(address: str) -> str:
    """The clean product page address inside `address`, or ''."""
    found = PRODUCT.search(address)
    return f"https://www.lazada.com.ph{found.group(1)}" if found else ""


def resolve(short: str) -> str:
    """Follow a short link's redirects (Lazada hosts only) to a product page; '' when it leads to none."""
    opener = urllib.request.build_opener(_NoRedirect)
    address = short
    for _ in range(MAX_REDIRECTS + 1):
        parts = urlsplit(address)
        if parts.scheme not in {"http", "https"} or not _lazada_host(parts.hostname or ""):
            return ""
        direct = _product_link(address)
        if direct:
            return direct
        try:
            with opener.open(urllib.request.Request(address, headers=HEADERS), timeout=TIMEOUT) as answer:
                # Some short links answer with a small page that sends the browser on from script: read the link out of it.
                return _product_link(answer.read(200_000).decode("utf-8", "replace"))
        except urllib.error.HTTPError as error:
            location = error.headers.get("Location") if 300 <= error.code < 400 else None
            if not location:
                return ""
            address = urljoin(address, location)
        except (urllib.error.URLError, OSError):
            return ""
    return ""


@blueprint.get("/resolve-link")
def resolve_link() -> Any:
    short = (request.args.get("url") or "").strip()[:400]
    parts = urlsplit(short)
    if parts.scheme not in {"http", "https"} or (parts.hostname or "").lower() not in START_HOSTS:
        return jsonify({"error": "That is not a Lazada short link."}), 400
    now = time.monotonic()
    cached = _cache.get(short)
    if cached and now - cached[0] < CACHE_SECONDS:
        return jsonify({"link": cached[1]})
    link = resolve(short)
    if not link:
        return jsonify({"error": "That link does not lead to a Lazada PH product page."}), 404
    if len(_cache) > 500:
        _cache.clear()
    _cache[short] = (now, link)
    return jsonify({"link": link})
