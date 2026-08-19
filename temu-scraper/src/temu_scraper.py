"""Visible-browser scraper for public Temu Philippines products and reviews.

Temu renders most catalog and review content in JavaScript and frequently
changes generated CSS class names. This scraper therefore prefers canonical
product IDs, JSON-LD, semantic attributes, accessible labels, and text-based
fallbacks. It never substitutes sample data when extraction fails.
"""

from __future__ import annotations

import argparse
import datetime
import json
import logging
import os
import pickle
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit, urlunsplit

# Python 3.12+ compatibility for undetected-chromedriver 3.x.
try:  # pragma: no cover - host-version dependent
    import distutils  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    import setuptools._distutils as _distutils

    sys.modules["distutils"] = _distutils

import undetected_chromedriver as uc
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from tqdm import tqdm


class SafeChrome(uc.Chrome):
    """Suppress undetected-chromedriver's harmless Windows double-quit error."""

    def __del__(self):
        try:
            super().__del__()
        except OSError:
            pass


class TemuScraper:
    """Scrape public Temu product metadata and written customer reviews."""

    BASE_URL = "https://www.temu.com"
    MARKET_HOME = "https://www.temu.com/ph-en/"
    PRODUCT_LINK_SELECTORS = (
        'a[href*="goods.html"][href*="goods_id="]',
        'a[href*="-g-"][href*=".html"]',
        '[data-product-id] a[href]',
        '[data-goods-id] a[href]',
    )
    REVIEW_ROOT_SELECTORS = (
        '[data-testid*="review" i]',
        '[data-uniqid*="review" i]',
        'section[id*="review" i]',
        '[id*="review" i]',
    )

    def __init__(
        self,
        keyword: str = "",
        max_products: int = 10,
        review_limit: int = 30,
        pages: int = 1,
        product_urls: list[str] | None = None,
        all_reviews: bool = False,
        max_review_batches: int = 100,
        min_rating: float = 0.0,
        min_reviews: int = 0,
        include_empty: bool = False,
        chrome_user_data_dir: str | None = None,
        output: str | None = None,
        pause_for_verification: bool = True,
        verification_timeout: int = 0,
        pagination_retries: int = 3,
        pagination_timeout: float = 15.0,
        checkpoint_every: int = 5,
    ):
        raw_urls = product_urls or []
        normalized_urls = [self._normalize_product_url(url) for url in raw_urls]
        normalized_urls = [url for url in normalized_urls if url]
        if raw_urls and not normalized_urls:
            raise ValueError("No valid Temu product URLs were provided")
        if not keyword.strip() and not normalized_urls:
            raise ValueError("Provide a keyword or at least one Temu product URL")
        if not 0 <= min_rating <= 5:
            raise ValueError("min_rating must be between 0 and 5")

        self.driver = None
        self.keyword = keyword.strip()
        self.max_products = max(0, max_products)
        self.review_limit = max(0, review_limit)
        self.pages = max(1, pages)
        self.product_urls = normalized_urls
        self.all_reviews = all_reviews
        self.max_review_batches = max(1, max_review_batches)
        self.min_rating = float(min_rating)
        self.min_reviews = max(0, min_reviews)
        self.include_empty = include_empty
        self.chrome_user_data_dir = chrome_user_data_dir
        self.pause_for_verification = pause_for_verification
        self.verification_timeout = max(0, int(verification_timeout))
        self.pagination_retries = max(1, pagination_retries)
        self.pagination_timeout = max(1.0, pagination_timeout)
        self.checkpoint_every = max(1, checkpoint_every)
        self._last_pagination_stop_reason = ""
        self.cookies_file = "cookies_temu_ph.dat"
        self._cookies_loaded = False

        slug_source = self.keyword or "products"
        slug = re.sub(r"[^a-z0-9_]+", "_", slug_source.casefold()).strip("_")
        self.out_file = output or f"temu_ph_{slug or 'products'}.json"
        self.output_data: dict[str, dict[str, Any]] = {}
        self._setup_logging()
        self.options = uc.ChromeOptions()
        self._configure_options()
        self._load_existing_data()

    def _setup_logging(self):
        os.makedirs("logs", exist_ok=True)
        if logging.getLogger().handlers:
            return
        stamp = datetime.datetime.now().strftime("temu_ph_%d_%m_%H_%M_%S.log")
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[
                logging.FileHandler(Path("logs") / stamp),
                logging.StreamHandler(sys.stdout),
            ],
        )

    def _configure_options(self):
        if self.chrome_user_data_dir:
            profile = os.path.abspath(os.path.expanduser(self.chrome_user_data_dir))
            self.options.add_argument(f"--user-data-dir={profile}")
        if sys.platform.startswith("linux"):
            self.options.add_argument("--disable-gpu")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--start-maximized")
        self.options.add_argument("--lang=en-PH")

    @staticmethod
    def _detect_chrome_major():
        if not sys.platform.startswith("win"):
            return None
        roots = [
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application"),
        ]
        versions = []
        for root in roots:
            if not os.path.isdir(root):
                continue
            for entry in os.listdir(root):
                if re.fullmatch(r"\d+(?:\.\d+){1,3}", entry):
                    versions.append(tuple(int(part) for part in entry.split(".")))
        return max(versions)[0] if versions else None

    @staticmethod
    def _cached_driver_for_major(chrome_major):
        if not chrome_major or not sys.platform.startswith("win"):
            return None
        path = os.path.join(
            os.environ.get("APPDATA", ""),
            "undetected_chromedriver",
            "undetected_chromedriver.exe",
        )
        if not os.path.isfile(path):
            return None
        try:
            result = subprocess.run(
                [path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
            match = re.search(r"ChromeDriver\s+(\d+)", result.stdout)
            return path if match and int(match.group(1)) == chrome_major else None
        except (OSError, subprocess.SubprocessError):
            return None

    @classmethod
    def _normalize_product_url(cls, href):
        if not href:
            return ""
        absolute = urljoin(f"{cls.BASE_URL}/", str(href).strip())
        parts = urlsplit(absolute)
        host = parts.netloc.casefold().split(":")[0]
        if host not in {"temu.com", "www.temu.com", "m.temu.com"}:
            return ""
        query = parse_qs(parts.query)
        goods_id = next(iter(query.get("goods_id", [])), "")
        if not goods_id:
            match = re.search(r"-g-(\d+)\.html(?:$|[/?#])", parts.path, re.I)
            goods_id = match.group(1) if match else ""
        if not re.fullmatch(r"\d{6,}", str(goods_id)):
            return ""
        return urlunsplit(
            ("https", "www.temu.com", "/goods.html", urlencode({"goods_id": goods_id}), "")
        )

    def _build_search_url(self, page=1):
        query = {
            "search_key": self.keyword,
            "search_method": "user",
            "refer_page_el_sn": "200010",
        }
        if page > 1:
            query["page"] = str(page)
        return f"{self.BASE_URL}/ph-en/search_result.html?{urlencode(query)}"

    @staticmethod
    def _parse_compact_number(text):
        if text is None:
            return 0
        match = re.search(r"(\d[\d,.]*)\s*([kmb])?", str(text), re.I)
        if not match:
            return 0
        value, suffix = match.group(1), (match.group(2) or "").casefold()
        multiplier = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(suffix, 1)
        if suffix and "," in value and "." not in value:
            value = value.replace(",", ".")
        else:
            value = value.replace(",", "")
        try:
            return int(float(value) * multiplier)
        except ValueError:
            return 0

    @staticmethod
    def _parse_rating(text):
        match = re.search(
            r"(?<!\d)([0-5](?:\.\d+)?)\s*(?:/\s*5|out\s+of\s+(?:five|5)|stars?)?",
            str(text or ""),
            re.I,
        )
        return float(match.group(1)) if match else 0.0

    @staticmethod
    def _clean_text(text):
        value = str(text or "")
        if any(marker in value for marker in ("Ã¢", "Ã‚")):
            for source_encoding in ("cp1252", "latin-1"):
                try:
                    value = value.encode(source_encoding).decode("utf-8")
                    break
                except (UnicodeEncodeError, UnicodeDecodeError):
                    continue
        return re.sub(r"\s+", " ", value.replace("\u00a0", " ")).strip()

    @classmethod
    def _first_text(cls, root, selectors):
        for selector in selectors:
            try:
                for element in root.find_elements(By.CSS_SELECTOR, selector):
                    text = cls._clean_text(element.text)
                    if text:
                        return text
            except (NoSuchElementException, AttributeError):
                continue
        return ""

    @staticmethod
    def _first_attribute(root, selectors, attribute):
        for selector in selectors:
            try:
                for element in root.find_elements(By.CSS_SELECTOR, selector):
                    value = element.get_attribute(attribute)
                    if value:
                        return value
            except (NoSuchElementException, AttributeError):
                continue
        return ""

    def _save_debug_artifacts(self, kind):
        if not self.driver:
            return
        try:
            os.makedirs("debug", exist_ok=True)
            Path("debug", f"temu_ph_{kind}.html").write_text(
                self.driver.page_source, encoding="utf-8"
            )
            self.driver.save_screenshot(str(Path("debug", f"temu_ph_{kind}.png")))
            logging.warning("Saved %s diagnostics for %s", kind, self.driver.current_url)
        except Exception as exc:
            logging.warning("Could not save diagnostics: %s", exc)

    def _save_cookies(self):
        if not self.driver:
            return
        try:
            with open(self.cookies_file, "wb") as file:
                pickle.dump(self.driver.get_cookies(), file)
        except Exception as exc:
            logging.warning("Could not save Temu cookies: %s", exc)

    def _load_cookies(self):
        if self._cookies_loaded or not os.path.exists(self.cookies_file):
            return
        try:
            with open(self.cookies_file, "rb") as file:
                cookies = pickle.load(file)
            for cookie in cookies:
                cookie.pop("sameSite", None)
                try:
                    self.driver.add_cookie(cookie)
                except Exception:
                    continue
            self._cookies_loaded = True
        except Exception as exc:
            logging.warning("Could not load Temu cookies: %s", exc)

    def _load_existing_data(self):
        if not os.path.exists(self.out_file):
            return
        try:
            with open(self.out_file, "r", encoding="utf-8") as file:
                records = json.load(file)
            self.output_data = {
                item["link"]: item
                for item in records
                if isinstance(item, dict) and item.get("link")
            }
        except (OSError, ValueError, TypeError) as exc:
            logging.warning("Could not load %s: %s", self.out_file, exc)

    def _periodic_save(self):
        output_path = Path(self.out_file)
        temporary_path = output_path.with_name(f"{output_path.name}.tmp")
        with temporary_path.open("w", encoding="utf-8") as file:
            json.dump(list(self.output_data.values()), file, ensure_ascii=False, indent=2)
        os.replace(temporary_path, output_path)
        logging.info("Saved %s product(s) to %s", len(self.output_data), self.out_file)

    @staticmethod
    def _deduplicate_reviews(reviews):
        unique, seen = [], set()
        for review in reviews:
            identity = review.get("comment_id") or (
                review.get("author", ""),
                review.get("time", ""),
                review.get("content", ""),
                review.get("rating", 0),
            )
            if identity in seen:
                continue
            seen.add(identity)
            unique.append(review)
        return unique

    @staticmethod
    def _review_matches_source_filter(review, source_filter):
        recorded_filter = review.get("source_rating_filter")
        if recorded_filter is not None:
            return int(recorded_filter) == int(source_filter)
        return int(float(review.get("rating", 0) or 0)) == int(source_filter)

    def _order_reviews_low_to_high(self, reviews):
        return sorted(
            self._deduplicate_reviews(reviews),
            key=lambda review: int(
                float(review.get("source_rating_filter") or review.get("rating", 0) or 6)
            ),
        )

    def _checkpoint_reviews(self, product, reviews, batch_number, stop_reason="", context=None):
        product["comments"] = self._deduplicate_reviews(reviews)
        previous = product.get("review_checkpoint", {})
        product["review_checkpoint"] = {
            "context": context or ("all" if self.all_reviews else "limited"),
            "completed_batches": max(int(previous.get("completed_batches", 0)), batch_number),
            "collected_reviews": len(product["comments"]),
            "stop_reason": stop_reason,
            "updated_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        if product.get("link"):
            self.output_data[product["link"]] = product
        self._periodic_save()

    def _record_no_reviews(self, product):
        product["comments"] = []
        product["review_status"] = "no_reviews"
        product["review_collection_warning"] = "This product has no written reviews"
        logging.info("No written Temu reviews found for %s", product.get("link"))
        self._checkpoint_reviews(
            product,
            [],
            batch_number=0,
            stop_reason="no_reviews",
            context="all",
        )

    def _verification_detected(self):
        path = urlsplit(self.driver.current_url).path.casefold()
        title = (self.driver.title or "").casefold()
        body = ""
        try:
            body = self.driver.find_element(By.TAG_NAME, "body").text[:2000].casefold()
        except NoSuchElementException:
            pass
        return any(token in path for token in ("captcha", "verify", "login")) or any(
            token in f"{title} {body}"
            for token in (
                "verify you are human",
                "security verification",
                "unusual activity",
                "access denied",
            )
        )

    def _wait_for_verification_clear(self):
        if self.verification_timeout <= 0:
            return False
        logging.info("Waiting up to %s seconds for Temu verification", self.verification_timeout)
        deadline = time.time() + self.verification_timeout
        while time.time() < deadline:
            if not self._verification_detected():
                self._save_cookies()
                return True
            time.sleep(2)
        logging.warning("Temu verification was not completed within the timeout")
        return False

    def _check_verification(self):
        blocked = self._verification_detected()
        if blocked and self.pause_for_verification:
            logging.info("Temu login or verification detected. Complete it manually in Chrome.")
            input("Press Enter after the Temu page is ready...")
            time.sleep(2)
            blocked = self._verification_detected()
            if blocked:
                logging.warning("Temu is still showing login or verification")
        elif blocked and self._wait_for_verification_clear():
            blocked = False
        return blocked

    def _safe_get(self, url):
        self.driver.get(url)
        try:
            WebDriverWait(self.driver, 30).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            logging.warning("Timed out waiting for %s", url)
        time.sleep(1)
        return self._check_verification()

    def _dismiss_popups(self):
        xpath = (
            "//*[self::button or @role='button']["
            "translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz')='close' or "
            "translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz')='not now' or "
            "translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz')='continue shopping']"
        )
        for button in self.driver.find_elements(By.XPATH, xpath)[:3]:
            if not button.is_displayed():
                continue
            try:
                button.click()
            except Exception:
                continue

    def _card_for_anchor(self, anchor):
        try:
            return self.driver.execute_script(
                """
                return arguments[0].closest(
                  '[data-product-id], [data-goods-id], [data-uniqid*="goods"]'
                ) || arguments[0].parentElement?.parentElement?.parentElement || arguments[0];
                """,
                anchor,
            )
        except Exception:
            return anchor

    def _find_product_cards(self):
        cards, seen = [], set()
        for selector in self.PRODUCT_LINK_SELECTORS:
            for anchor in self.driver.find_elements(By.CSS_SELECTOR, selector):
                link = self._normalize_product_url(anchor.get_attribute("href"))
                if not link or link in seen:
                    continue
                seen.add(link)
                cards.append((self._card_for_anchor(anchor), anchor, link))
        return cards

    def _product_from_card(self, card, anchor, link):
        name = (
            anchor.get_attribute("aria-label")
            or anchor.get_attribute("title")
            or self._first_text(card, ('[data-uniqid*="name" i]', "h2", "h3"))
            or self._first_attribute(card, ("img",), "alt")
        )
        card_text = self._clean_text(getattr(card, "text", ""))
        price = self._first_text(
            card,
            (
                '[data-uniqid*="price" i]',
                '[itemprop="price"]',
                '[aria-label*="price" i]',
            ),
        )
        if not price:
            match = re.search(r"(?:₱|PHP\s*)\s*[\d,]+(?:\.\d{1,2})?", card_text, re.I)
            price = match.group(0) if match else ""
        rating_label = self._first_attribute(
            card,
            ('[aria-label*="out of 5" i]', '[aria-label*="star" i]'),
            "aria-label",
        )
        sold_match = re.search(r"([\d,.]+\s*[kmb]?\+?)\s*(?:sold|bought)", card_text, re.I)
        review_match = re.search(r"([\d,.]+\s*[kmb]?\+?)\s*reviews?", card_text, re.I)
        image = self._first_attribute(card, ("img",), "src")
        if not image or image.startswith("data:image"):
            image = self._first_attribute(card, ("img",), "data-src")
        return {
            "link": link,
            "goods_id": parse_qs(urlsplit(link).query).get("goods_id", [""])[0],
            "name": self._clean_text(name),
            "price": self._clean_text(price),
            "rating": self._parse_rating(rating_label),
            "total_rating": self._parse_compact_number(review_match.group(1)) if review_match else 0,
            "sold_count": self._parse_compact_number(sold_match.group(1)) if sold_match else 0,
            "img": image,
            "platform": "temu",
            "market": "PH",
            "currency": "PHP",
        }

    def _retrieve_search_products(self):
        if self._safe_get(self._build_search_url()):
            self._save_debug_artifacts("search")
            return []
        self._dismiss_popups()
        products: dict[str, dict[str, Any]] = {}
        unchanged = 0
        previous = -1
        for _ in range(self.pages * 8):
            for card, anchor, link in self._find_product_cards():
                if link not in products:
                    products[link] = self._product_from_card(card, anchor, link)
                if len(products) >= self.max_products:
                    return list(products.values())
            unchanged = unchanged + 1 if len(products) == previous else 0
            if unchanged >= 3:
                break
            previous = len(products)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight)")
            time.sleep(1.2)
        if not products:
            self._save_debug_artifacts("search")
        return list(products.values())[: self.max_products]

    @staticmethod
    def _product_from_url(url):
        return {
            "link": url,
            "goods_id": parse_qs(urlsplit(url).query).get("goods_id", [""])[0],
            "name": "",
            "price": "",
            "rating": 0.0,
            "total_rating": 0,
            "sold_count": 0,
            "img": "",
            "platform": "temu",
            "market": "PH",
            "currency": "PHP",
        }

    def _json_ld_product(self):
        for element in self.driver.find_elements(By.CSS_SELECTOR, 'script[type="application/ld+json"]'):
            raw = element.get_attribute("textContent") or ""
            try:
                value = json.loads(raw)
            except (TypeError, ValueError):
                continue
            stack = value if isinstance(value, list) else [value]
            while stack:
                item = stack.pop()
                if isinstance(item, list):
                    stack.extend(item)
                    continue
                if not isinstance(item, dict):
                    continue
                item_type = item.get("@type", "")
                types = item_type if isinstance(item_type, list) else [item_type]
                if any(str(value).casefold() == "product" for value in types):
                    return item
                stack.extend(value for value in item.values() if isinstance(value, (dict, list)))
        return {}

    def _apply_json_ld(self, product, data):
        if not data:
            return
        product["name"] = self._clean_text(data.get("name")) or product.get("name", "")
        product["description"] = self._clean_text(data.get("description"))
        image = data.get("image", "")
        if isinstance(image, list):
            image = next(iter(image), "")
        if isinstance(image, dict):
            image = image.get("url", "")
        product["img"] = image or product.get("img", "")
        brand = data.get("brand", "")
        product["brand"] = self._clean_text(brand.get("name") if isinstance(brand, dict) else brand)

        offers = data.get("offers", {})
        if isinstance(offers, list):
            offers = next(iter(offers), {})
        if isinstance(offers, dict):
            raw_price = offers.get("price") or offers.get("lowPrice")
            currency = offers.get("priceCurrency")
            if raw_price not in (None, ""):
                prefix = "₱" if currency == "PHP" else f"{currency or ''} "
                product["price"] = f"{prefix}{raw_price}".strip()
            if currency:
                product["currency"] = currency

        aggregate = data.get("aggregateRating", {})
        if isinstance(aggregate, dict):
            product["rating"] = self._parse_rating(aggregate.get("ratingValue")) or product.get(
                "rating", 0.0
            )
            product["total_rating"] = self._parse_compact_number(
                aggregate.get("reviewCount") or aggregate.get("ratingCount")
            ) or product.get("total_rating", 0)

    def _review_root(self):
        candidates = []
        for selector in self.REVIEW_ROOT_SELECTORS:
            try:
                candidates.extend(self.driver.find_elements(By.CSS_SELECTOR, selector))
            except Exception:
                continue
        visible = [
            item
            for item in candidates
            if item.is_displayed() and len(self._clean_text(item.text)) >= 20
        ]
        return max(visible, key=lambda item: len(item.text), default=None)

    def _open_review_section(self):
        review_text_xpath = (
            "//*[self::button or self::a or @role='button']["
            "contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'see all reviews') or "
            "contains(translate(normalize-space(.), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', "
            "'abcdefghijklmnopqrstuvwxyz'), 'customer reviews')]"
        )
        for _ in range(50):
            root = self._review_root()
            if root:
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'})", root)
                time.sleep(1)
                return root
            buttons = [
                item
                for item in self.driver.find_elements(By.XPATH, review_text_xpath)
                if item.is_displayed()
            ]
            if buttons:
                button = buttons[-1]
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'})", button)
                try:
                    button.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click()", button)
                time.sleep(1.5)
                root = self._review_root()
                if root:
                    return root
            self.driver.execute_script(
                "window.scrollBy(0, Math.max(700, Math.floor(window.innerHeight * 0.85)))"
            )
            time.sleep(0.35)
        return None

    @staticmethod
    def _review_javascript():
        return r"""
        const root = arguments[0] || document;
        const selectors = [
          '[data-review-id]', '[data-comment-id]',
          '[data-testid*="review-item" i]',
          '[data-uniqid*="review-item" i]',
          '[data-uniqid*="review_item" i]'
        ];
        let items = [];
        for (const selector of selectors) {
          const found = Array.from(root.querySelectorAll(selector));
          if (found.length) { items = found; break; }
        }
        if (!items.length) {
          const stars = Array.from(root.querySelectorAll('[aria-label*="star" i], [aria-label*="out of 5" i]'));
          for (const star of stars) {
            let node = star;
            for (let depth = 0; node && depth < 7; depth++, node = node.parentElement) {
              const text = (node.innerText || '').trim();
              if (text.length >= 20 && text.length <= 2500) {
                items.push(node);
                break;
              }
            }
          }
        }
        items = Array.from(new Set(items));
        const firstText = (item, selectors) => {
          for (const selector of selectors) {
            const node = item.querySelector(selector);
            const text = ((node && (node.innerText || node.textContent)) || '').trim();
            if (text) return text;
          }
          return '';
        };
        return items.map((item, index) => {
          const fullText = (item.innerText || '').trim();
          const lines = fullText.split(/\n+/).map(x => x.trim()).filter(Boolean);
          const ratingNode = item.querySelector('[aria-label*="star" i], [aria-label*="out of 5" i]');
          const ratingLabel = ratingNode ? (ratingNode.getAttribute('aria-label') || '') : '';
          let content = firstText(item, [
            '[data-testid*="review-content" i]', '[data-testid*="review-text" i]',
            '[data-uniqid*="review-content" i]', '[data-uniqid*="review_text" i]',
            '[itemprop="reviewBody"]'
          ]);
          if (!content) {
            const candidates = lines.filter(line =>
              line.length >= 5 &&
              !/^\d(?:\.\d)?\s*(?:out of 5|stars?)?$/i.test(line) &&
              !/^(helpful|report|verified purchase|size:|color:|style:)/i.test(line) &&
              !/^\d{1,2}[\/-]\d{1,2}[\/-]\d{2,4}$/.test(line)
            );
            content = candidates.sort((a, b) => b.length - a.length)[0] || '';
          }
          const author = firstText(item, [
            '[data-testid*="author" i]', '[data-testid*="user" i]',
            '[data-uniqid*="author" i]', '[data-uniqid*="user" i]',
            '[itemprop="author"]'
          ]);
          const timeNode = item.querySelector('time');
          let reviewTime = (timeNode && (timeNode.getAttribute('datetime') || timeNode.innerText)) ||
            firstText(item, ['[data-testid*="date" i]', '[data-uniqid*="date" i]']);
          if (!reviewTime) {
            reviewTime = lines.find(line =>
              /\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b/i.test(line) ||
              /\b\d{4}[\/-]\d{1,2}[\/-]\d{1,2}\b/.test(line)
            ) || '';
          }
          const variation = lines.find(line => /^(?:size|color|style|model|type)\s*:/i.test(line)) || '';
          const helpful = firstText(item, [
            '[data-testid*="helpful" i]', '[data-uniqid*="helpful" i]',
            'button[aria-label*="helpful" i]'
          ]);
          return {
            comment_id: item.dataset.reviewId || item.dataset.commentId || item.id || '',
            author,
            rating_label: ratingLabel,
            time: reviewTime,
            content,
            variation,
            helpful,
            snapshot_index: index
          };
        });
        """

    def _reviews_from_current_view(self, root):
        records = self.driver.execute_script(self._review_javascript(), root) or []
        reviews = []
        for item in records:
            content = self._clean_text(item.get("content"))
            if not content and not self.include_empty:
                continue
            rating = self._parse_rating(item.get("rating_label"))
            reviews.append(
                {
                    "comment_id": self._clean_text(item.get("comment_id")),
                    "author": self._clean_text(item.get("author")),
                    "rating": int(rating) if rating.is_integer() else rating,
                    "time": self._clean_text(item.get("time")),
                    "content": content,
                    "variation": self._clean_text(item.get("variation")),
                    "seller_respond": "",
                    "like_count": self._parse_compact_number(item.get("helpful")),
                }
            )
        return reviews

    def _review_signature(self, root):
        reviews = self._reviews_from_current_view(root)
        return "|".join(
            str(item.get("comment_id") or f"{item['author']}:{item['time']}:{item['content']}")
            for item in reviews[-3:]
        )

    def _click_rating_filter(self, root, rating):
        previous_signature = self._review_signature(root)
        candidates = []
        for scope in (root, self.driver):
            try:
                candidates.extend(
                    scope.find_elements(
                        By.CSS_SELECTOR,
                        'button, [role="button"], [role="option"], label',
                    )
                )
            except Exception:
                continue
        pattern = re.compile(rf"(^|\D){rating}\s*(?:star|stars|â˜…)(?:\D|$)", re.I)
        for candidate in candidates:
            try:
                label = self._clean_text(
                    " ".join(
                        filter(
                            None,
                            (
                                candidate.text,
                                candidate.get_attribute("aria-label"),
                                candidate.get_attribute("title"),
                            ),
                        )
                    )
                )
                if len(label) > 100 or not candidate.is_displayed() or not pattern.search(label):
                    continue
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block:'center'})", candidate
                )
                try:
                    candidate.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click()", candidate)
                WebDriverWait(self.driver, min(self.pagination_timeout, 10)).until(
                    lambda _: self._review_signature(self._review_root() or root)
                    != previous_signature
                )
                return True
            except TimeoutException:
                continue
            except Exception:
                continue
        return False

    def _advance_reviews(self, root, previous_signature):
        pattern = re.compile(r"^(?:next|load more|show more|more reviews)(?:\s+reviews?)?$", re.I)
        self._last_pagination_stop_reason = ""
        for attempt in range(1, self.pagination_retries + 1):
            if self._review_signature(root) != previous_signature:
                return True
            candidates = []
            for scope in (root, self.driver):
                try:
                    candidates.extend(
                        scope.find_elements(By.CSS_SELECTOR, 'button, [role="button"], a')
                    )
                except Exception:
                    continue
            button_to_click = None
            disabled_button_seen = False
            for button in candidates:
                label = self._clean_text(
                    " ".join(
                        filter(
                            None,
                            (
                                button.text,
                                button.get_attribute("aria-label"),
                                button.get_attribute("title"),
                            ),
                        )
                    )
                )
                if not button.is_displayed() or not pattern.search(label):
                    continue
                disabled = (button.get_attribute("aria-disabled") or "").casefold() == "true"
                if disabled or button.get_attribute("disabled") is not None:
                    disabled_button_seen = True
                    continue
                button_to_click = button
                break
            try:
                if button_to_click is not None:
                    self.driver.execute_script(
                        "arguments[0].scrollIntoView({block:'center'})", button_to_click
                    )
                    try:
                        button_to_click.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click()", button_to_click)
                    self._last_pagination_stop_reason = (
                        f"page_signature_timeout_attempt_{attempt}"
                    )
                elif disabled_button_seen:
                    self._last_pagination_stop_reason = "next_button_disabled"
                else:
                    self.driver.execute_script(
                        """
                        const root = arguments[0];
                        if (root && root.scrollHeight > root.clientHeight) root.scrollTop = root.scrollHeight;
                        else window.scrollBy(0, Math.floor(window.innerHeight * 0.9));
                        """,
                        root,
                    )
                    self._last_pagination_stop_reason = "no_additional_reviews"
                WebDriverWait(self.driver, self.pagination_timeout).until(
                    lambda _: self._review_signature(root) != previous_signature
                )
                return True
            except TimeoutException:
                pass
            except Exception as exc:
                self._last_pagination_stop_reason = f"page_transition_error_{type(exc).__name__}"
            if attempt < self.pagination_retries:
                logging.warning(
                    "Temu review pagination attempt %s/%s failed: %s",
                    attempt,
                    self.pagination_retries,
                    self._last_pagination_stop_reason,
                )
                time.sleep(min(1.5 * attempt, 5))
        if self._last_pagination_stop_reason != "next_button_disabled":
            self._save_debug_artifacts("review_pagination_failure")
        return False

    def _collect_reviews(self, root, product=None, max_reviews=None, source_filter=None):
        target = (
            None if self.all_reviews else self.review_limit
        ) if max_reviews is None else max(0, max_reviews)
        if target == 0:
            return []
        existing_reviews = list(product.get("comments", [])) if product else []
        if source_filter is None:
            collected = self._deduplicate_reviews(existing_reviews)
        else:
            collected = self._deduplicate_reviews(
                review
                for review in existing_reviews
                if self._review_matches_source_filter(review, source_filter)
            )
            for review in collected:
                review.setdefault("source_rating_filter", source_filter)
        seen = {
            review.get("comment_id")
            or (
                review.get("author", ""),
                review.get("time", ""),
                review.get("content", ""),
                review.get("rating", 0),
            )
            for review in collected
        }
        stop_reason = "target_reached" if target is not None and len(collected) >= target else ""
        batch_number = 0
        if stop_reason:
            if product:
                checkpoint_reviews = (
                    collected
                    if source_filter is None
                    else [
                        review
                        for review in existing_reviews
                        if not self._review_matches_source_filter(review, source_filter)
                    ] + collected
                )
                self._checkpoint_reviews(
                    product,
                    checkpoint_reviews,
                    batch_number,
                    stop_reason=stop_reason,
                    context=str(source_filter) if source_filter is not None else None,
                )
            return collected
        description = "Collecting all exposed Temu reviews" if target is None else "Collecting Temu reviews"
        with tqdm(total=target, initial=len(collected), desc=description) as progress:
            for batch_number in range(1, self.max_review_batches + 1):
                view_reviews = self._reviews_from_current_view(root)
                if not view_reviews:
                    stop_reason = "empty_review_batch"
                    self._save_debug_artifacts("reviews")
                    break
                for review in view_reviews:
                    if source_filter is not None:
                        review["source_rating_filter"] = source_filter
                    identity = review.get("comment_id") or (
                        review["author"],
                        review["time"],
                        review["content"],
                        review["rating"],
                    )
                    if identity in seen:
                        continue
                    seen.add(identity)
                    collected.append(review)
                    progress.update(1)
                    if target is not None and len(collected) >= target:
                        stop_reason = "target_reached"
                        break
                if product and batch_number % self.checkpoint_every == 0:
                    checkpoint_reviews = (
                        collected
                        if source_filter is None
                        else [
                            review
                            for review in existing_reviews
                            if not self._review_matches_source_filter(review, source_filter)
                        ] + collected
                    )
                    self._checkpoint_reviews(
                        product,
                        checkpoint_reviews,
                        batch_number,
                        context=str(source_filter) if source_filter is not None else None,
                    )
                if stop_reason == "target_reached":
                    break
                signature = self._review_signature(root)
                if not signature:
                    stop_reason = "missing_review_signature"
                    self._save_debug_artifacts("review_pagination_failure")
                    break
                if not self._advance_reviews(root, signature):
                    stop_reason = self._last_pagination_stop_reason or "page_transition_failed"
                    break
            else:
                stop_reason = "max_review_batches_reached"
        if stop_reason and stop_reason != "target_reached":
            logging.info(
                "Temu review pagination stopped after batch %s with %s review(s): %s",
                batch_number,
                len(collected),
                stop_reason,
            )
        if product:
            checkpoint_reviews = (
                collected
                if source_filter is None
                else [
                    review
                    for review in existing_reviews
                    if not self._review_matches_source_filter(review, source_filter)
                ] + collected
            )
            self._checkpoint_reviews(
                product,
                checkpoint_reviews,
                batch_number,
                stop_reason=stop_reason,
                context=str(source_filter) if source_filter is not None else None,
            )
        return collected

    def _scrape_details(self, product):
        if self._safe_get(product["link"]):
            self._save_debug_artifacts("blocked_product")
            raise RuntimeError("Temu required login or verification before showing the product")
        if self._normalize_product_url(self.driver.current_url) != product["link"]:
            self._save_debug_artifacts("unexpected_product_redirect")
            raise RuntimeError("Temu redirected away from the requested product page")
        self._dismiss_popups()
        self._apply_json_ld(product, self._json_ld_product())

        product["name"] = self._first_text(
            self.driver,
            ('h1', '[itemprop="name"]', '[data-uniqid*="goods_name" i]'),
        ) or product.get("name", "")
        price = self._first_text(
            self.driver,
            (
                '[itemprop="price"]',
                '[data-uniqid*="price" i]',
                '[aria-label*="price" i]',
            ),
        )
        if price and len(price) < 80:
            product["price"] = price
        rating_label = self._first_attribute(
            self.driver,
            ('[aria-label*="out of 5" i]', '[itemprop="ratingValue"]'),
            "aria-label",
        ) or self._first_attribute(self.driver, ('[itemprop="ratingValue"]',), "content")
        product["rating"] = self._parse_rating(rating_label) or product.get("rating", 0.0)
        product["description"] = product.get("description") or self._first_attribute(
            self.driver, ('meta[name="description"]', 'meta[property="og:description"]'), "content"
        )
        product["img"] = product.get("img") or self._first_attribute(
            self.driver,
            ('meta[property="og:image"]', '[itemprop="image"]', 'img[src*="kwcdn.com"]'),
            "content",
        ) or self._first_attribute(self.driver, ('img[src*="kwcdn.com"]',), "src")

        body_text = self._clean_text(self.driver.find_element(By.TAG_NAME, "body").text)
        if not product.get("total_rating"):
            count_match = re.search(r"([\d,.]+\s*[kmb]?\+?)\s*(?:customer\s+)?reviews?", body_text, re.I)
            if count_match:
                product["total_rating"] = self._parse_compact_number(count_match.group(1))
        if not product.get("sold_count"):
            sold_match = re.search(r"([\d,.]+\s*[kmb]?\+?)\s*(?:sold|bought)", body_text, re.I)
            if sold_match:
                product["sold_count"] = self._parse_compact_number(sold_match.group(1))

        root = self._open_review_section()
        if root is None:
            if product.get("total_rating", 0) == 0:
                self._record_no_reviews(product)
            else:
                logging.warning("Temu review section not found for %s", product["link"])
                self._save_debug_artifacts("reviews")
                product["comments"] = []
                product["review_status"] = "review_widget_missing"
                product["review_collection_warning"] = (
                    "No review section was identified in the rendered page"
                )
            return
        if product.get("total_rating", 0) == 0 and not self._reviews_from_current_view(root):
            self._record_no_reviews(product)
            return
        product["review_status"] = "collecting"
        if not self.all_reviews:
            # Keep the marketplace's rendered order for representative limited
            # samples instead of intentionally front-loading low-star reviews.
            product["comments"] = self._deduplicate_reviews(
                self._collect_reviews(root, product=product, max_reviews=self.review_limit)
            )[: self.review_limit]
            if product["comments"]:
                product["review_status"] = "complete"
            else:
                self._record_no_reviews(product)
            return
        reviews = []
        applied_filters = []
        for star in range(1, 6):
            remaining = None if self.all_reviews else self.review_limit - len(
                self._deduplicate_reviews(reviews)
            )
            if remaining is not None and remaining <= 0:
                break
            active_root = self._review_root() or root
            if not self._click_rating_filter(active_root, star):
                continue
            active_root = self._review_root() or active_root
            star_reviews = self._collect_reviews(
                active_root,
                product=product,
                max_reviews=remaining,
                source_filter=star,
            )
            applied_filters.append(star)
            reviews.extend(star_reviews)
        if applied_filters:
            product["applied_rating_filters"] = applied_filters
            product["comments"] = self._order_reviews_low_to_high(reviews)
            if not self.all_reviews:
                product["comments"] = product["comments"][: self.review_limit]
        else:
            product["review_filter_warning"] = (
                "Temu did not expose identifiable star filters; reviews were "
                "collected in rendered order and sorted by extracted rating"
            )
            product["comments"] = self._order_reviews_low_to_high(
                self._collect_reviews(root, product=product)
            )
        if product["comments"]:
            product["review_status"] = "complete"
        else:
            self._record_no_reviews(product)
        total = product.get("total_rating", 0)
        if self.all_reviews and total and len(product["comments"]) < total:
            product["review_collection_warning"] = (
                f"Temu displayed {total} reviews but exposed only "
                f"{len(product['comments'])} unique written reviews in this browser session"
            )

    def _qualifies(self, product):
        return product.get("rating", 0.0) >= self.min_rating and product.get(
            "total_rating", 0
        ) >= self.min_reviews

    def execute(self):
        major = self._detect_chrome_major()
        kwargs = {"options": self.options, "enable_cdp_events": False, "headless": False}
        if major:
            kwargs["version_main"] = major
            cached = self._cached_driver_for_major(major)
            if cached:
                kwargs["driver_executable_path"] = cached
        logging.info("Starting Chrome for Temu Philippines")
        self.driver = SafeChrome(**kwargs)
        self.driver.maximize_window()
        successful_details = 0
        try:
            self._safe_get(self.MARKET_HOME)
            self._load_cookies()
            if self._cookies_loaded:
                self.driver.refresh()
                time.sleep(1)
            if self.product_urls:
                products = [self._product_from_url(url) for url in self.product_urls]
            else:
                products = self._retrieve_search_products()
            if not products:
                raise RuntimeError("No real Temu products were extracted; inspect debug artifacts")

            for product in tqdm(products, desc="Processing Temu products"):
                link = product["link"]
                existing = self.output_data.get(link)
                if existing:
                    expected = existing.get("total_rating", 0) if self.all_reviews else self.review_limit
                    checkpoint = existing.get("review_checkpoint", {})
                    stop_reason = checkpoint.get("stop_reason")
                    reached_end = checkpoint.get("context") in {"all", "limited"} and stop_reason in {
                        "target_reached",
                        "next_button_disabled",
                        "no_additional_reviews",
                        "no_reviews",
                    }
                    complete = reached_end or (
                        expected > 0 and len(existing.get("comments", [])) >= expected
                    )
                    if complete:
                        successful_details += 1
                        continue
                    logging.info(
                        "Retrying incomplete Temu result for %s (%s/%s reviews)",
                        link,
                        len(existing.get("comments", [])),
                        expected or "unknown",
                    )
                    product = existing
                try:
                    self._scrape_details(product)
                    successful_details += 1
                    if self._qualifies(product):
                        self.output_data[link] = product
                    else:
                        logging.info(
                            "Skipped %s: rating %.1f, %s reviews",
                            link,
                            product.get("rating", 0.0),
                            product.get("total_rating", 0),
                        )
                        self.output_data.pop(link, None)
                except Exception as exc:
                    logging.warning("Detail scrape failed for %s: %s", link, exc, exc_info=True)
                    if product.get("comments"):
                        self.output_data[link] = product
                    else:
                        self.output_data.pop(link, None)
                self._periodic_save()
        finally:
            self._save_cookies()
            if self.driver:
                self.driver.quit()
        self._periodic_save()
        if successful_details == 0:
            raise RuntimeError(
                "No Temu product pages were extracted; complete Temu login/verification "
                "manually and inspect the saved diagnostics"
            )
        return list(self.output_data.values())


def build_parser():
    parser = argparse.ArgumentParser(description="Scrape Temu Philippines products and reviews")
    parser.add_argument("keyword", nargs="?", default="", help="Temu search keyword")
    parser.add_argument("-n", "--num", type=int, default=10, help="Maximum products")
    parser.add_argument("-r", "--review-limit", type=int, default=30, help="Written reviews per product")
    parser.add_argument("--all-reviews", action="store_true", help="Collect until Temu exposes no more reviews")
    parser.add_argument("--max-review-batches", type=int, default=100, help="Safety cap for all-review loading")
    parser.add_argument("--pages", type=int, default=1, help="Search-result scroll batches")
    parser.add_argument("--product-url", action="append", default=[], help="Direct Temu product URL; repeatable")
    parser.add_argument("--min-rating", type=float, default=0.0, help="Minimum product rating")
    parser.add_argument("--min-reviews", type=int, default=0, help="Minimum displayed review count")
    parser.add_argument("--include-empty", action="store_true", help="Include ratings with no written comment")
    parser.add_argument("--chrome-user-data-dir", help="Optional Chrome user-data directory")
    parser.add_argument("-o", "--output", help="Output JSON file")
    parser.add_argument("--no-verification-pause", action="store_true", help="Do not prompt on verification pages")
    parser.add_argument("--verification-timeout", type=int, default=0, help="Seconds to wait for unattended verification")
    parser.add_argument("--pagination-retries", type=int, default=3, help="Retries for a failed review transition")
    parser.add_argument("--pagination-timeout", type=float, default=15, help="Seconds to wait for each review transition")
    parser.add_argument("--checkpoint-every", type=int, default=5, help="Save review progress every N batches")
    return parser


def main():
    args = build_parser().parse_args()
    scraper = TemuScraper(
        keyword=args.keyword,
        max_products=args.num,
        review_limit=args.review_limit,
        pages=args.pages,
        product_urls=args.product_url,
        all_reviews=args.all_reviews,
        max_review_batches=args.max_review_batches,
        min_rating=args.min_rating,
        min_reviews=args.min_reviews,
        include_empty=args.include_empty,
        chrome_user_data_dir=args.chrome_user_data_dir,
        output=args.output,
        pause_for_verification=not args.no_verification_pause,
        verification_timeout=args.verification_timeout,
        pagination_retries=args.pagination_retries,
        pagination_timeout=args.pagination_timeout,
        checkpoint_every=args.checkpoint_every,
    )
    scraper.execute()


if __name__ == "__main__":
    main()
