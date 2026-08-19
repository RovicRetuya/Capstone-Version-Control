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
from urllib.parse import urlencode, urljoin, urlsplit, urlunsplit

# undetected-chromedriver 3.x still imports ``distutils``, which Python 3.12+
# removed. Setuptools ships the maintained compatibility copy.
try:  # pragma: no cover - depends on the host Python version
    import distutils  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    import setuptools._distutils as _distutils

    sys.modules["distutils"] = _distutils

import undetected_chromedriver as uc
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from tqdm import tqdm


class ShopeeScraper:
    """Selenium scraper configured for Shopee Philippines by default."""

    PRODUCT_CARD_SELECTORS = (
        '[data-sqe="item"]',
        '.shopee-search-item-result__item',
        'section ul > li',
    )
    PRODUCT_LINK_SELECTORS = (
        'a[data-sqe="link"]',
        'a.contents',
        'a[href*="-i."]',
        'a[href*="/product/"]',
    )
    REVIEW_CONTAINER_SELECTORS = (
        '.product-ratings__list',
        '.shopee-product-rating-list',
    )

    def __init__(
        self,
        search_term,
        max_products,
        index_only,
        review_limit,
        all_star_types=False,
        star_limit_per_type=10,
        chrome_user_data_dir=None,
        site="shopee.ph",
        pagination_retries=3,
        pagination_timeout=15.0,
        checkpoint_every=5,
        max_review_pages=5000,
        product_urls=None,
        output=None,
        interactive=True,
        verification_timeout=600,
    ):
        self.driver = None
        self.search_term = search_term
        self.max_products = max(0, max_products)
        self.index_only = index_only
        self.review_limit = max(0, review_limit)
        self.all_star_types = all_star_types
        self.star_limit_per_type = max(0, star_limit_per_type)
        self.chrome_user_data_dir = chrome_user_data_dir
        self.site = self._normalize_site(site)
        self.pagination_retries = max(1, pagination_retries)
        self.pagination_timeout = max(1.0, pagination_timeout)
        self.checkpoint_every = max(1, checkpoint_every)
        self.max_review_pages = max(1, max_review_pages)
        self.interactive = bool(interactive)
        self.verification_timeout = max(30, int(verification_timeout))
        self._last_pagination_stop_reason = ""
        self.base_url = f"https://{self.site}"
        self.product_urls = [
            normalized
            for normalized in (
                self._normalize_product_url(url) for url in (product_urls or [])
            )
            if normalized
        ]
        self.cookies_file = f"cookies_{self.site.replace('.', '_')}.dat"
        self._cookies_loaded = False

        self._setup_logging()
        self.options = uc.ChromeOptions()
        self._configure_options()
        self.output_data = {}
        slug_source = "products" if self.product_urls else self.search_term
        slug = re.sub(r"[^a-z0-9_]+", "_", slug_source.lower()).strip("_")
        self.out_file = output or f"shopee_ph_{slug or 'search'}.json"
        self._load_existing_data()

    @staticmethod
    def _normalize_site(site):
        site = (site or "shopee.ph").strip().lower()
        site = re.sub(r"^https?://", "", site).strip("/")
        if site == "ph":
            site = "shopee.ph"
        if site != "shopee.ph":
            raise ValueError("This version supports the Shopee Philippines site: shopee.ph")
        return site

    def _setup_logging(self):
        os.makedirs("logs", exist_ok=True)
        # Avoid creating unused FileHandler objects when this class is instantiated
        # repeatedly by a host application or the test suite.
        if logging.getLogger().handlers:
            return
        log_filename = datetime.datetime.now().strftime("shopee_ph_%d_%m_%H_%M_%S.log")
        log_filepath = os.path.join("logs", log_filename)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(message)s",
            handlers=[logging.FileHandler(log_filepath), logging.StreamHandler(sys.stdout)],
        )

    def _configure_options(self):
        # Let Chrome create an isolated profile unless the user explicitly supplies one.
        # This avoids profile-lock errors and accidental use of an unrelated local account.
        if self.chrome_user_data_dir:
            profile_path = os.path.abspath(os.path.expanduser(self.chrome_user_data_dir))
            self.options.add_argument(f"--user-data-dir={profile_path}")
        if sys.platform.startswith("linux"):
            self.options.add_argument("--disable-gpu")
        self.options.add_argument("--no-sandbox")
        self.options.add_argument("--disable-dev-shm-usage")
        self.options.add_argument("--disable-blink-features=AutomationControlled")
        self.options.add_argument("--start-maximized")
        self.options.add_argument("--lang=en-PH")

    @staticmethod
    def _detect_chrome_major():
        """Return the installed Chrome major version on Windows when detectable."""
        if not sys.platform.startswith("win"):
            return None
        application_dirs = [
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application"),
        ]
        versions = []
        for application_dir in application_dirs:
            if not os.path.isdir(application_dir):
                continue
            try:
                for entry in os.listdir(application_dir):
                    if re.fullmatch(r"\d+(?:\.\d+){1,3}", entry):
                        versions.append(tuple(int(part) for part in entry.split(".")))
            except OSError:
                continue
        return max(versions)[0] if versions else None

    @staticmethod
    def _cached_driver_for_major(chrome_major):
        if not chrome_major or not sys.platform.startswith("win"):
            return None
        cache_path = os.path.join(
            os.environ.get("APPDATA", ""),
            "undetected_chromedriver",
            "undetected_chromedriver.exe",
        )
        if not os.path.isfile(cache_path):
            return None
        try:
            creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            result = subprocess.run(
                [cache_path, "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                creationflags=creation_flags,
                check=False,
            )
            match = re.search(r"ChromeDriver\s+(\d+)", result.stdout)
            if match and int(match.group(1)) == chrome_major:
                return cache_path
        except (OSError, subprocess.SubprocessError):
            pass
        return None

    def _save_search_debug_artifacts(self):
        """Save the rendered failure page so selector/blocking issues are diagnosable."""
        try:
            os.makedirs("debug", exist_ok=True)
            html_path = os.path.join("debug", "shopee_ph_search.html")
            screenshot_path = os.path.join("debug", "shopee_ph_search.png")
            with open(html_path, "w", encoding="utf-8") as file:
                file.write(self.driver.page_source)
            self.driver.save_screenshot(screenshot_path)
            logging.warning(
                "Search diagnostics saved (URL=%s, title=%s).",
                self.driver.current_url,
                self.driver.title,
            )
        except Exception as exc:
            logging.warning("Could not save search diagnostics: %s", exc)

    def _save_review_debug_artifacts(self, kind="reviews"):
        try:
            os.makedirs("debug", exist_ok=True)
            safe_kind = re.sub(r"[^a-z0-9_]+", "_", kind.casefold()).strip("_")
            html_path = os.path.join("debug", f"shopee_ph_{safe_kind or 'reviews'}.html")
            screenshot_path = os.path.join("debug", f"shopee_ph_{safe_kind or 'reviews'}.png")
            with open(html_path, "w", encoding="utf-8") as file:
                file.write(self.driver.page_source)
            self.driver.save_screenshot(screenshot_path)
            logging.warning("Review diagnostics saved for %s.", self.driver.current_url)
        except Exception as exc:
            logging.warning("Could not save review diagnostics: %s", exc)

    def _handle_exception(self, exc_type, exc_value, exc_traceback):
        logging.error("Uncaught exception", exc_info=(exc_type, exc_value, exc_traceback))

    def _build_search_url(self, page=0):
        query = urlencode(
            {
                "keyword": self.search_term.strip(),
                "page": max(0, page),
                "sortBy": "sales",
            }
        )
        return f"{self.base_url}/search?{query}"

    def _normalize_product_url(self, href):
        if not href:
            return ""
        absolute = urljoin(f"{self.base_url}/", href)
        parts = urlsplit(absolute)
        if parts.netloc.lower() != self.site:
            return ""
        if not re.search(r"(?:-i\.\d+\.\d+|/product/\d+/\d+)", parts.path):
            return ""
        return urlunsplit(("https", self.site, parts.path, "", ""))

    def _save_cookies(self):
        if not self.driver:
            return
        try:
            with open(self.cookies_file, "wb") as file:
                pickle.dump(self.driver.get_cookies(), file)
        except Exception as exc:
            logging.warning("Could not save Shopee PH cookies: %s", exc)

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
                    # Expired or incompatible cookies should not stop the scrape.
                    continue
            self._cookies_loaded = True
        except Exception as exc:
            logging.warning("Could not load saved Shopee PH cookies: %s", exc)

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
            self.output_data = {}

    def _periodic_save(self):
        try:
            temporary_path = f"{self.out_file}.tmp"
            with open(temporary_path, "w", encoding="utf-8") as file:
                json.dump(list(self.output_data.values()), file, ensure_ascii=False, indent=2)
            os.replace(temporary_path, self.out_file)
            logging.info("Saved %s product(s) to %s.", len(self.output_data), self.out_file)
        except OSError as exc:
            logging.warning("Periodic save failed: %s", exc)

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
    def _star_number(star_key):
        match = re.match(r"^([1-5])_star$", star_key or "")
        return int(match.group(1)) if match else 6

    def _review_matches_source_filter(self, review, source_filter):
        recorded_filter = review.get("source_rating_filter")
        if recorded_filter:
            return recorded_filter == source_filter
        return int(review.get("rating", 0) or 0) == self._star_number(source_filter)

    def _star_limits_low_to_high(self, product):
        return sorted(
            (
                (key, count)
                for key, count in product.get("detailed_rating", {}).items()
                if key.endswith("_star") and count > 0
            ),
            key=lambda item: self._star_number(item[0]),
        )

    def _order_reviews_low_to_high(self, reviews):
        return sorted(
            self._deduplicate_reviews(reviews),
            key=lambda review: self._star_number(
                review.get("source_rating_filter")
                or (f"{int(review.get('rating', 0))}_star" if review.get("rating") else "")
            ),
        )

    def _checkpoint_reviews(self, product, reviews, page_number, stop_reason="", context="all"):
        product["comments"] = self._deduplicate_reviews(reviews)
        previous = product.get("review_checkpoint", {})
        product["review_checkpoint"] = {
            "context": context,
            "completed_pages": max(int(previous.get("completed_pages", 0)), page_number),
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
        logging.info("No written Shopee reviews found for %s", product.get("link"))
        self._checkpoint_reviews(
            product,
            [],
            page_number=0,
            stop_reason="no_reviews",
            context="all",
        )

    def _scrape_missing_comments(self):
        logging.info("Resuming missing or incomplete comments from existing data...")
        for link, product in list(self.output_data.items()):
            expected = self.star_limit_per_type * 5 if self.all_star_types else self.review_limit
            checkpoint = product.get("review_checkpoint", {})
            stop_reason = checkpoint.get("stop_reason")
            reached_end = checkpoint.get("context") == "all" and stop_reason in {
                "target_reached",
                "next_button_disabled",
                "no_reviews",
            }
            if expected > 0 and len(product.get("comments", [])) < expected and not reached_end:
                try:
                    logging.info(
                        "Retrying incomplete Shopee result for %s (%s/%s reviews)",
                        link,
                        len(product.get("comments", [])),
                        expected,
                    )
                    self._scrape_details(product)
                    self.output_data[link] = product
                    self._periodic_save()
                except Exception as exc:
                    logging.warning("Error scraping comments for %s: %s", link, exc)

    @staticmethod
    def _first_text(root, selectors):
        for selector in selectors:
            try:
                for element in root.find_elements(By.CSS_SELECTOR, selector):
                    text = element.text.strip()
                    if text:
                        return text
            except (NoSuchElementException, AttributeError):
                continue
        return ""

    @staticmethod
    def _first_attribute(root, selectors, attribute):
        for selector in selectors:
            try:
                value = root.find_element(By.CSS_SELECTOR, selector).get_attribute(attribute)
                if value:
                    return value
            except (NoSuchElementException, AttributeError):
                continue
        return ""

    @staticmethod
    def _first_xpath_text(root, xpaths):
        for xpath in xpaths:
            try:
                text = root.find_element(By.XPATH, xpath).text.strip()
                if text:
                    return text
            except (NoSuchElementException, AttributeError):
                continue
        return ""

    def _product_link_from_card(self, card):
        try:
            if card.tag_name.lower() == "a":
                link = self._normalize_product_url(card.get_attribute("href"))
                if link:
                    return link, card
        except Exception:
            pass
        for selector in self.PRODUCT_LINK_SELECTORS:
            try:
                for anchor in card.find_elements(By.CSS_SELECTOR, selector):
                    link = self._normalize_product_url(anchor.get_attribute("href"))
                    if link:
                        return link, anchor
            except Exception:
                continue
        return "", None

    def _find_product_cards(self):
        cards = []
        seen = set()
        for selector in self.PRODUCT_CARD_SELECTORS:
            for card in self.driver.find_elements(By.CSS_SELECTOR, selector):
                link, _ = self._product_link_from_card(card)
                if link and link not in seen:
                    cards.append(card)
                    seen.add(link)
            if cards:
                break

        # Fallback for layouts where the product link is stable but its wrapper changed.
        if not cards:
            anchors = self.driver.find_elements(
                By.CSS_SELECTOR, 'a[href*="-i."], a[href*="/product/"]'
            )
            for anchor in anchors:
                link = self._normalize_product_url(anchor.get_attribute("href"))
                if not link or link in seen:
                    continue
                try:
                    card = anchor.find_element(By.XPATH, "ancestor::li[1]")
                except NoSuchElementException:
                    card = anchor
                cards.append(card)
                seen.add(link)
        return cards

    def _scroll_search_results(self):
        previous_count = -1
        unchanged_rounds = 0
        for _ in range(12):
            cards = self._find_product_cards()
            if len(cards) >= self.max_products:
                return cards
            if len(cards) == previous_count:
                unchanged_rounds += 1
            else:
                unchanged_rounds = 0
            if unchanged_rounds >= 2:
                return cards
            previous_count = len(cards)
            self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(1)
        return self._find_product_cards()

    @staticmethod
    def _price_from_text(text):
        match = re.search(
            r"₱\s*[\d,.]+(?:\s*-\s*₱?\s*[\d,.]+)?", text.replace("\n", " ")
        )
        return re.sub(r"\s+", "", match.group(0)) if match else ""

    @staticmethod
    def _rating_from_text(text):
        for line in reversed(text.splitlines()):
            match = re.fullmatch(r"\s*([0-5](?:\.\d)?)\s*", line)
            if match:
                return match.group(1)
        return ""

    def _product_from_card(self, card):
        link, anchor = self._product_link_from_card(card)
        if not link:
            return None
        root = anchor or card
        name = self._first_text(
            card,
            (
                '[data-sqe="name"]',
                '[class*="line-clamp-2"]',
                '[class*="break-words"]',
            ),
        )
        if not name:
            name = root.get_attribute("title") or self._first_attribute(card, ("img",), "alt")

        card_text = card.text.strip()
        price = self._first_text(
            card,
            (
                '[class*="items-baseline"]',
                '[class*="text-shopee-primary"]',
                '[class*="price"]',
            ),
        )
        if "₱" in price:
            price = re.sub(r"\s+", "", price)
        else:
            price = self._price_from_text(card_text)

        rating = self._first_text(
            card,
            (
                '[class*="text-shopee-black87"][class*="text-xs"]',
                '[aria-label*="rating" i]',
                '[class*="rating"]',
            ),
        )
        rating_match = re.search(r"(?<!\d)[0-5](?:\.\d)?(?!\d)", rating)
        rating = rating_match.group(0) if rating_match else self._rating_from_text(card_text)

        location = self._first_text(
            card,
            (
                '[class*="text-shopee-black54"][class*="truncate"]',
                '[class*="location"]',
            ),
        )
        image = self._first_attribute(card, ("img",), "src")
        if not image or image.startswith("data:image"):
            image = self._first_attribute(card, ("img",), "data-src")

        shipping = ""
        for line in card_text.splitlines():
            if "shipping" in line.lower():
                shipping = line.strip()
                break

        return {
            "link": link,
            "name": name,
            "price": price,
            "rating": rating,
            "img": image,
            "shipping": shipping,
            "location": location,
            "platform": "shopee",
            "market": "PH",
            "currency": "PHP",
        }

    def _product_from_url(self, url):
        return {
            "link": self._normalize_product_url(url),
            "name": "",
            "price": "",
            "rating": "",
            "img": "",
            "shipping": "",
            "location": "",
            "platform": "shopee",
            "market": "PH",
            "currency": "PHP",
        }

    def _retrieve_products(self):
        logging.info("Retrieving Shopee PH product data...")
        try:
            WebDriverWait(self.driver, 20).until(lambda _: bool(self._find_product_cards()))
        except TimeoutException:
            logging.warning("Could not locate Shopee PH product cards.")
            self._save_search_debug_artifacts()
            return []

        products = []
        seen = set()
        for card in self._scroll_search_results():
            if len(products) >= self.max_products:
                break
            try:
                product = self._product_from_card(card)
                if product and product["link"] not in seen:
                    products.append(product)
                    seen.add(product["link"])
            except Exception as exc:
                logging.warning("Skipping a product card: %s", exc)
        return products

    def _check_captcha(self):
        path = urlsplit(self.driver.current_url).path.lower()
        blocked_paths = ("/buyer/login", "/captcha", "/verify", "/security-check")
        if any(token in path for token in blocked_paths):
            logging.info("Shopee login or verification detected. Complete it in Chrome.")
            if self.interactive:
                input("Press Enter after the Shopee page is ready...")
            else:
                deadline = time.time() + self.verification_timeout
                while time.time() < deadline:
                    time.sleep(2)
                    current_path = urlsplit(self.driver.current_url).path.lower()
                    if not any(token in current_path for token in blocked_paths):
                        logging.info("Shopee verification completed; resuming the scrape.")
                        break
                else:
                    raise TimeoutException(
                        "Shopee verification was not completed within "
                        f"{self.verification_timeout} seconds."
                    )
            time.sleep(3)
            return True
        return False

    def _safe_get(self, url):
        self.driver.get(url)
        try:
            WebDriverWait(self.driver, 20).until(
                lambda driver: driver.execute_script("return document.readyState") == "complete"
            )
        except TimeoutException:
            logging.warning("Timed out waiting for %s to finish loading.", url)
        self._check_captcha()

    def _scrape_page(self):
        logging.info("Loading Shopee Philippines search page...")
        # Cookies can only be added after visiting their domain once.
        self._safe_get(self.base_url)
        self._load_cookies()
        self._safe_get(self._build_search_url())
        return self._retrieve_products()

    @staticmethod
    def _parse_compact_number(text):
        """Parse PH/English counts such as 1,234, 1.2K, 2M, or 1,2k."""
        if text is None:
            return 0
        value = re.sub(r"[^0-9.,kmbKMB]", "", str(text)).strip()
        if not value:
            return 0
        suffix = value[-1].lower() if value[-1].isalpha() else ""
        if suffix:
            value = value[:-1]
            multiplier = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(suffix, 1)
            if "," in value and "." not in value:
                value = value.replace(",", ".")
        else:
            multiplier = 1
            value = value.replace(",", "")
        try:
            return int(float(value) * multiplier)
        except ValueError:
            return 0

    # Backward-compatible name retained for callers of the original project.
    def _parse_star_text(self, text):
        return self._parse_compact_number(text)

    def _parse_rating_filter(self, text):
        normalized = re.sub(r"\s+", " ", text or "").strip()
        count_match = re.search(r"\(([^)]*)\)", normalized)
        count = self._parse_compact_number(count_match.group(1)) if count_match else 0
        star_match = re.match(r"^([1-5])(?:\s*(?:star(?:s)?|sao))?\b", normalized, re.I)
        if star_match:
            return f"{star_match.group(1)}_star", count

        lowered = normalized.lower()
        if lowered.startswith("all") or lowered.startswith("tất cả"):
            return "all", count
        if "comment" in lowered or "bình luận" in lowered:
            return "commented", count
        if "media" in lowered or "photo" in lowered or "video" in lowered or "hình ảnh" in lowered:
            return "media", count
        return "", count

    def _rating_filters(self):
        return self.driver.find_elements(By.CSS_SELECTOR, ".product-rating-overview__filter")

    def _scroll_to_reviews(self):
        """Progressively scroll so Shopee's lazy review microfrontend is mounted."""
        previous_y = -1
        unchanged_rounds = 0
        for _ in range(36):
            if self._rating_filters():
                return True
            headings = self.driver.find_elements(
                By.XPATH,
                '//*[self::h1 or self::h2 or self::h3][contains(translate(normalize-space(.), '
                '"ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz"), "product ratings")]',
            )
            if headings:
                return True
            current_y = self.driver.execute_script("return window.pageYOffset")
            if current_y == previous_y:
                unchanged_rounds += 1
            else:
                unchanged_rounds = 0
            if unchanged_rounds >= 3:
                break
            previous_y = current_y
            self.driver.execute_script(
                "window.scrollBy(0, Math.max(700, Math.floor(window.innerHeight * 0.8)));"
            )
            time.sleep(0.6)
        return bool(self._rating_filters())

    def _scrape_rating_overview(self, product):
        product["detailed_rating"] = {}
        try:
            overview = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".product-rating-overview"))
            )
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", overview)
            for rating_filter in self._rating_filters():
                key, count = self._parse_rating_filter(rating_filter.text)
                if key:
                    product["detailed_rating"][key] = count
        except TimeoutException:
            logging.warning("Rating overview was not found for %s", product.get("link"))

        star_counts = [
            count
            for key, count in product["detailed_rating"].items()
            if key.endswith("_star")
        ]
        product["total_rating"] = sum(star_counts)

    def _click_star_filter(self, star_key):
        for rating_filter in self._rating_filters():
            key, _ = self._parse_rating_filter(rating_filter.text)
            if key == star_key:
                self.driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", rating_filter
                )
                try:
                    rating_filter.click()
                except Exception:
                    self.driver.execute_script("arguments[0].click();", rating_filter)
                time.sleep(1)
                return True
        return False

    def _scrape_details(self, product):
        try:
            self._safe_get(product["link"])
            product["name"] = self._first_text(
                self.driver,
                ('h1', '[data-testid="product-title"]', '[class*="product-title"]'),
            ) or product.get("name", "")
            product["price"] = self._first_text(
                self.driver,
                ('[data-testid="product-price"]', '[class*="product-price"]'),
            ) or product.get("price", "")
            product["img"] = product.get("img") or self._first_attribute(
                self.driver,
                ('[data-testid="product-image"] img', '.product-briefing img', 'main img'),
                "src",
            )
            product["category"] = self._first_text(
                self.driver,
                (
                    '.page-product__breadcrumb',
                    'nav[aria-label="breadcrumb" i]',
                    '[class*="breadcrumb"]',
                ),
            )
            if not product["category"]:
                product["category"] = self._first_xpath_text(
                    self.driver,
                    (
                        '//*[@id="sll2-normal-pdp-main"]//section[1]/div',
                        '//*[normalize-space()="Home"]/ancestor::*[contains(@class,"breadcrumb")][1]',
                    ),
                )
            product["description"] = self._first_text(
                self.driver,
                (
                    '[data-testid="product-description"]',
                    '.product-detail .product-detail__content',
                ),
            )
            if not product["description"]:
                product["description"] = self._first_xpath_text(
                    self.driver,
                    (
                        '//h2[normalize-space()="Product Description"]/following-sibling::div[1]',
                        '//*[@id="sll2-normal-pdp-main"]//section[2]/div/div',
                    ),
                )

            self._scroll_to_reviews()
            self._scrape_rating_overview(product)

            if product["total_rating"] == 0 and not self._reviews_from_current_page():
                self._record_no_reviews(product)
                return
            product["review_status"] = "collecting"

            if self.all_star_types:
                reviews = []
                for key, count in self._star_limits_low_to_high(product):
                    if self._click_star_filter(key):
                        reviews.extend(
                            self._collect_reviews(
                                min(count, self.star_limit_per_type),
                                product=product,
                                source_filter=key,
                            )
                        )
                product["comments"] = self._order_reviews_low_to_high(reviews)
                if product["comments"]:
                    product["review_status"] = "complete"
                else:
                    self._record_no_reviews(product)
            else:
                available = product["total_rating"]
                target = min(available, self.review_limit) if available else self.review_limit
                # The research score needs the marketplace's natural review
                # order. Prioritizing low-star filters would bias the negative
                # ratio and keyword-failure rate upward.
                product["comments"] = self._collect_reviews(target, product=product)
                if product["comments"]:
                    product["review_status"] = "complete"
                else:
                    self._record_no_reviews(product)
        except Exception as exc:
            logging.warning("Detail scrape failed for %s: %s", product.get("link"), exc)
            product.setdefault("comments", [])

    def _review_container(self, timeout=5):
        for selector in self.REVIEW_CONTAINER_SELECTORS:
            try:
                return WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
            except TimeoutException:
                continue
        return None

    def _review_items(self, container):
        items = container.find_elements(
            By.CSS_SELECTOR, ".shopee-product-comment-list > [data-cmtid]"
        )
        if not items:
            items = container.find_elements(By.CSS_SELECTOR, "[data-cmtid]")
        if not items:
            items = container.find_elements(By.CSS_SELECTOR, ".shopee-product-rating")
        if not items:
            items = container.find_elements(By.CSS_SELECTOR, ".shopee-product-rating__main")
        return items

    def _review_from_element(self, item):
        author = self._first_text(
            item,
            (
                '.shopee-product-rating__author-name',
                'a[href*="/shop/buyer/"]',
            ),
        )
        rating = len(item.find_elements(By.CSS_SELECTOR, '[class*="rating-solid--active"]'))
        if not rating:
            rating = len(item.find_elements(By.CSS_SELECTOR, "svg.icon-rating-solid"))
        review_time = self._first_text(item, ('.shopee-product-rating__time',))
        if not review_time:
            time_candidates = []
            for element in item.find_elements(By.XPATH, ".//*"):
                text = element.text.strip()
                if re.match(r"^\d{4}-\d{2}-\d{2}(?:\s+\d{2}:\d{2})?", text):
                    time_candidates.append(text)
            if time_candidates:
                review_time = min(time_candidates, key=len)
        content = self._first_text(
            item,
            (
                '.shopee-product-rating__content',
                '[style*="white-space: pre-wrap"]',
            ),
        )
        if not content:
            content = self._first_xpath_text(
                item,
                (
                    './div[2]/div[2]',
                    './/*[contains(@class,"comment") and not(contains(@class,"list"))]',
                ),
            )
        seller_response = self._first_text(
            item,
            (
                '.shopee-product-rating__response',
                '[class*="seller-response"]',
                '.TQTPT9 .qiTixQ',
            ),
        )
        like_text = self._first_text(item, ('.shopee-product-rating__like-count',))
        return {
            "author": author,
            "rating": rating,
            "time": review_time,
            "content": content,
            "seller_respond": seller_response,
            "like_count": self._parse_compact_number(like_text),
        }

    def _reviews_from_current_page(self):
        """Read each rendered review atomically to avoid React stale-element races."""
        records = self.driver.execute_script(
            r"""
            return Array.from(
                document.querySelectorAll('.product-ratings__list [data-cmtid]')
            ).map((item) => {
                const nodeText = (node) => (
                    (node && (node.innerText || node.textContent)) || ''
                ).trim();
                const buyerLinks = Array.from(
                    item.querySelectorAll('a[href*="/shop/buyer/"]')
                );
                const authorLink = buyerLinks.find((node) => nodeText(node));
                const texts = Array.from(item.querySelectorAll('*'))
                    .map((node) => nodeText(node))
                    .filter((text) => /^\d{4}-\d{2}-\d{2}/.test(text))
                    .sort((left, right) => left.length - right.length);
                const mainColumn = item.children.length > 1 ? item.children[1] : null;
                const contentNode = mainColumn && mainColumn.children.length > 1
                    ? mainColumn.children[1]
                    : null;
                const responseCandidates = Array.from(item.querySelectorAll('*'))
                    .filter((node) => /seller.{0,3}response/i.test(nodeText(node)))
                    .sort((left, right) => nodeText(left).length - nodeText(right).length);
                const likeNode = item.querySelector('.shopee-product-rating__like-count');
                return {
                    comment_id: item.getAttribute('data-cmtid') || '',
                    author: nodeText(authorLink),
                    rating: item.querySelectorAll('svg.icon-rating-solid').length,
                    time: texts.length ? texts[0] : '',
                    content: nodeText(contentNode),
                    seller_respond: responseCandidates.length
                        ? nodeText(responseCandidates[0])
                        : '',
                    like_count_text: nodeText(likeNode)
                };
            });
            """
        )
        reviews = []
        for record in records or []:
            reviews.append(
                {
                    "author": record.get("author", ""),
                    "rating": int(record.get("rating", 0) or 0),
                    "time": record.get("time", ""),
                    "content": record.get("content", ""),
                    "seller_respond": record.get("seller_respond", ""),
                    "like_count": self._parse_compact_number(
                        record.get("like_count_text", "")
                    ),
                    "comment_id": record.get("comment_id", ""),
                }
            )
        return reviews

    def _next_review_page(self, previous_signature):
        selectors = (
            'button.shopee-icon-button--right',
            'button[class*="icon-button--right"]',
        )
        self._last_pagination_stop_reason = ""
        for attempt in range(1, self.pagination_retries + 1):
            if self._current_review_signature() != previous_signature:
                return True
            next_button = None
            for selector in selectors:
                candidates = self.driver.find_elements(By.CSS_SELECTOR, selector)
                if candidates:
                    next_button = candidates[-1]
                    break
            if next_button is None:
                candidates = self.driver.find_elements(
                    By.XPATH, '//button[.//*[contains(@class,"icon-arrow-right")]]'
                )
                next_button = candidates[-1] if candidates else None
            if next_button is None:
                self._last_pagination_stop_reason = "next_button_not_found"
            else:
                classes = (next_button.get_attribute("class") or "").casefold()
                aria_disabled = (next_button.get_attribute("aria-disabled") or "").casefold()
                if (
                    next_button.get_attribute("disabled") is not None
                    or "disabled" in classes
                    or aria_disabled == "true"
                ):
                    self._last_pagination_stop_reason = "next_button_disabled"
                else:
                    try:
                        next_button.click()
                    except Exception:
                        self.driver.execute_script("arguments[0].click();", next_button)
                    try:
                        WebDriverWait(self.driver, self.pagination_timeout).until(
                            lambda _: self._current_review_signature() != previous_signature
                        )
                        return True
                    except TimeoutException:
                        self._last_pagination_stop_reason = (
                            f"page_signature_timeout_attempt_{attempt}"
                        )
            if attempt < self.pagination_retries:
                logging.warning(
                    "Shopee review pagination attempt %s/%s failed: %s",
                    attempt,
                    self.pagination_retries,
                    self._last_pagination_stop_reason,
                )
                time.sleep(min(1.5 * attempt, 5))
        if self._last_pagination_stop_reason != "next_button_disabled":
            self._save_review_debug_artifacts("review_pagination_failure")
        return False

    def _current_review_signature(self):
        return self.driver.execute_script(
            """
            return Array.from(
                document.querySelectorAll('.product-ratings__list [data-cmtid]')
            ).slice(0, 2).map((item) => item.getAttribute('data-cmtid')).join('|');
            """
        )

    def _collect_reviews(self, max_reviews, product=None, source_filter=None):
        if max_reviews <= 0:
            return []
        container = self._review_container()
        if container is None:
            self._save_review_debug_artifacts()
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
        stop_reason = "target_reached" if len(collected) >= max_reviews else ""
        page_number = 0
        with tqdm(
            total=max_reviews,
            initial=min(len(collected), max_reviews),
            desc="Collecting reviews",
        ) as progress:
            while len(collected) < max_reviews and page_number < self.max_review_pages:
                page_number += 1
                container = self._review_container(timeout=2)
                if container is None:
                    stop_reason = "review_container_missing"
                    self._save_review_debug_artifacts("review_pagination_failure")
                    break
                page_reviews = self._reviews_from_current_page()
                if not page_reviews:
                    stop_reason = "empty_review_page"
                    self._save_review_debug_artifacts("reviews")
                    break
                for review in page_reviews:
                    if len(collected) >= max_reviews:
                        break
                    if source_filter is not None:
                        review["source_rating_filter"] = source_filter
                    identity = review.get("comment_id") or (
                        review["author"], review["time"], review["content"], review["rating"]
                    )
                    if identity in seen:
                        continue
                    seen.add(identity)
                    collected.append(review)
                    progress.update(1)
                if product and page_number % self.checkpoint_every == 0:
                    if source_filter is None:
                        checkpoint_reviews = collected
                    else:
                        checkpoint_reviews = [
                            review
                            for review in existing_reviews
                            if not self._review_matches_source_filter(review, source_filter)
                        ] + collected
                    self._checkpoint_reviews(
                        product, checkpoint_reviews, page_number, context=str(source_filter or "all")
                    )
                if len(collected) >= max_reviews:
                    stop_reason = "target_reached"
                    break
                signature = self._current_review_signature()
                if not signature:
                    stop_reason = "missing_page_signature"
                    self._save_review_debug_artifacts("review_pagination_failure")
                    break
                if not self._next_review_page(signature):
                    stop_reason = self._last_pagination_stop_reason or "page_transition_failed"
                    break
            else:
                if page_number >= self.max_review_pages and len(collected) < max_reviews:
                    stop_reason = "max_review_pages_reached"
        if stop_reason and stop_reason != "target_reached":
            logging.info(
                "Shopee review pagination stopped after page %s with %s review(s): %s",
                page_number,
                len(collected),
                stop_reason,
            )
        if product:
            if source_filter is None:
                checkpoint_reviews = collected
            else:
                checkpoint_reviews = [
                    review
                    for review in existing_reviews
                    if not self._review_matches_source_filter(review, source_filter)
                ] + collected
            self._checkpoint_reviews(
                product,
                checkpoint_reviews,
                page_number,
                stop_reason=stop_reason,
                context=str(source_filter or "all"),
            )
        return collected

    def execute(self):
        sys.excepthook = self._handle_exception
        chrome_major = self._detect_chrome_major()
        chrome_kwargs = {
            "options": self.options,
            "enable_cdp_events": False,
            "headless": False,
        }
        if chrome_major:
            # undetected-chromedriver otherwise downloads the newest stable driver,
            # which can be one major version ahead of the locally installed Chrome.
            chrome_kwargs["version_main"] = chrome_major
            logging.info("Starting Chrome with matching major version %s.", chrome_major)
            cached_driver = self._cached_driver_for_major(chrome_major)
            if cached_driver:
                chrome_kwargs["driver_executable_path"] = cached_driver
                logging.info("Reusing the cached matching ChromeDriver.")
        self.driver = uc.Chrome(**chrome_kwargs)
        self.driver.maximize_window()

        try:
            if self.output_data:
                # Establish the PH domain and restore saved authentication before
                # revisiting product pages from a previous run.
                self._safe_get(self.base_url)
                self._load_cookies()
                self._scrape_missing_comments()

            if self.product_urls:
                if not self.output_data:
                    self._safe_get(self.base_url)
                    self._load_cookies()
                products = [self._product_from_url(url) for url in self.product_urls]
            else:
                products = self._scrape_page()
            for product in tqdm(products, desc="Processing products"):
                link = product["link"]
                if link in self.output_data:
                    continue
                if not self.index_only:
                    self._scrape_details(product)
                self.output_data[link] = product
                self._periodic_save()
        except Exception as exc:
            logging.error("Error scraping Shopee PH: %s", exc, exc_info=True)
        finally:
            logging.info("Saving cookies and quitting Chrome...")
            self._save_cookies()
            if self.driver:
                self.driver.quit()

        self._periodic_save()
        logging.info("Data saved to %s", self.out_file)


def build_parser():
    parser = argparse.ArgumentParser(description="Scrape products and reviews from Shopee Philippines")
    parser.add_argument("-k", "--keyword", default="Raspberry Pi", help="Search term")
    parser.add_argument("-n", "--num", type=int, default=10, help="Number of products")
    parser.add_argument("-r", "--review-limit", type=int, default=30, help="Max reviews per product")
    parser.add_argument("--index-only", action="store_true", help="Only retrieve search-result data")
    parser.add_argument("--all-star-types", action="store_true", help="Retrieve reviews from each star filter")
    parser.add_argument("--star-limit-per-type", type=int, default=10, help="Reviews to retrieve per star filter")
    parser.add_argument("--chrome-user-data-dir", default=None, help="Optional Chrome user-data directory")
    parser.add_argument("--site", default="shopee.ph", choices=("shopee.ph", "ph"), help="Shopee site (PH only)")
    parser.add_argument("--product-url", action="append", default=[], help="Direct Shopee PH product URL; repeatable")
    parser.add_argument("-o", "--output", help="Output JSON file")
    parser.add_argument("--pagination-retries", type=int, default=3, help="Retries for a failed review-page transition")
    parser.add_argument("--pagination-timeout", type=float, default=15, help="Seconds to wait for each review-page transition")
    parser.add_argument("--checkpoint-every", type=int, default=5, help="Save review progress every N pages")
    parser.add_argument("--max-review-pages", type=int, default=5000, help="Safety cap for review pages per filter")
    parser.add_argument(
        "--no-prompt",
        action="store_true",
        help="Wait for browser verification without requiring terminal input",
    )
    parser.add_argument(
        "--verification-timeout",
        type=int,
        default=600,
        help="Seconds to wait for login/captcha completion in --no-prompt mode",
    )
    return parser


if __name__ == "__main__":
    args = build_parser().parse_args()
    scraper = ShopeeScraper(
        args.keyword,
        args.num,
        args.index_only,
        args.review_limit,
        all_star_types=args.all_star_types,
        star_limit_per_type=args.star_limit_per_type,
        chrome_user_data_dir=args.chrome_user_data_dir,
        site=args.site,
        pagination_retries=args.pagination_retries,
        pagination_timeout=args.pagination_timeout,
        checkpoint_every=args.checkpoint_every,
        max_review_pages=args.max_review_pages,
        product_urls=args.product_url,
        output=args.output,
        interactive=not args.no_prompt,
        verification_timeout=args.verification_timeout,
    )
    scraper.execute()
