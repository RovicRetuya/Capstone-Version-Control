import unittest
import pickle
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit

from selenium.common.exceptions import TimeoutException
from src.retriv import ShopeeScraper, build_parser


class TestShopeeScraper(unittest.TestCase):

    def setUp(self):
        self.scraper = ShopeeScraper(
            search_term='test',
            max_products=5,
            index_only=False,
            review_limit=10,
            all_star_types=False,
            star_limit_per_type=5,
            chrome_user_data_dir=None
        )

    def test_initialization(self):
        self.assertEqual(self.scraper.search_term, 'test')
        self.assertEqual(self.scraper.max_products, 5)
        self.assertFalse(self.scraper.index_only)
        self.assertEqual(self.scraper.review_limit, 10)
        self.assertEqual(self.scraper.site, 'shopee.ph')
        self.assertEqual(self.scraper.base_url, 'https://shopee.ph')
        self.assertEqual(self.scraper.cookies_file, 'cookies_shopee_ph.dat')
        self.assertIn('--no-first-run', self.scraper.options.arguments)
        self.assertIn('--disable-search-engine-choice-screen', self.scraper.options.arguments)

    def test_uses_explicit_persistent_browser_profile(self):
        with TemporaryDirectory() as directory:
            scraper = ShopeeScraper('test', 1, True, 0, chrome_user_data_dir=directory)
            profile_argument = next(
                argument for argument in scraper.options.arguments
                if argument.startswith('--user-data-dir=')
            )
            self.assertTrue(Path(profile_argument.split('=', 1)[1]).samefile(directory))

    def test_cookie_save_is_atomic_and_preserves_previous_session_on_browser_failure(self):
        class BrokenDriver:
            @staticmethod
            def get_cookies():
                raise RuntimeError('browser closed')

        with TemporaryDirectory() as directory:
            cookie_path = Path(directory) / 'cookies.dat'
            original = [{'name': 'session', 'value': 'existing'}]
            cookie_path.write_bytes(pickle.dumps(original))
            self.scraper.cookies_file = str(cookie_path)
            self.scraper.driver = BrokenDriver()
            self.scraper._save_cookies()
            self.assertEqual(pickle.loads(cookie_path.read_bytes()), original)

            class EmptyDriver:
                @staticmethod
                def get_cookies():
                    return []

            self.scraper.driver = EmptyDriver()
            self.scraper._save_cookies()
            self.assertEqual(pickle.loads(cookie_path.read_bytes()), original)

    def test_prepares_session_before_checking_login(self):
        events = []
        self.scraper._safe_get = lambda url, check_verification=True: events.append(
            ("open", url, check_verification)
        )
        self.scraper._load_cookies = lambda: events.append(("cookies",)) or False
        self.scraper._check_captcha = lambda: events.append(("verify",)) or False

        self.scraper._prepare_session()

        self.assertEqual(
            events,
            [("open", "https://shopee.ph", False), ("cookies",), ("verify",)],
        )

    def test_captcha_check_accepts_byte_url(self):
        class FakeDriver:
            current_url = b"https://shopee.ph/search?keyword=test"

        self.scraper.driver = FakeDriver()
        self.assertFalse(self.scraper._check_captcha())

    def test_terminal_verification_failure_stops_without_retrying(self):
        class Body:
            text = "Please Try Again Later. Verification can't be completed."

        class FakeDriver:
            current_url = "https://shopee.ph/verify/captcha?anti_bot_tracking_id=test"

            @staticmethod
            def find_element(_by, _value):
                return Body()

        self.scraper.driver = FakeDriver()
        with self.assertRaisesRegex(TimeoutException, "SHOPEE_VERIFICATION_BLOCKED"):
            self.scraper._check_captcha()

    def test_detects_installed_chrome_major(self):
        major = self.scraper._detect_chrome_major()
        if major is not None:
            self.assertGreaterEqual(major, 1)
            cached_driver = self.scraper._cached_driver_for_major(major)
            if cached_driver is not None:
                self.assertTrue(cached_driver.endswith('undetected_chromedriver.exe'))

    def test_parse_star_text(self):
        self.assertEqual(self.scraper._parse_star_text('1,2k'), 1200)
        self.assertEqual(self.scraper._parse_star_text('1.2K'), 1200)
        self.assertEqual(self.scraper._parse_star_text('15k'), 15000)
        self.assertEqual(self.scraper._parse_star_text('100'), 100)
        self.assertEqual(self.scraper._parse_star_text('1,234'), 1234)
        self.assertEqual(self.scraper._parse_star_text('2.5M'), 2500000)
        self.assertEqual(self.scraper._parse_star_text('invalid'), 0)

    def test_parse_ph_rating_filters(self):
        self.assertEqual(self.scraper._parse_rating_filter('5 Star (1.2K)'), ('5_star', 1200))
        self.assertEqual(self.scraper._parse_rating_filter('4 Stars (99)'), ('4_star', 99))
        self.assertEqual(self.scraper._parse_rating_filter('All (1,234)'), ('all', 1234))
        self.assertEqual(self.scraper._parse_rating_filter('With Comments (25)'), ('commented', 25))
        self.assertEqual(self.scraper._parse_rating_filter('With Media (10)'), ('media', 10))

    def test_orders_star_filters_and_reviews_lowest_first(self):
        product = {
            "detailed_rating": {
                "all": 50,
                "5_star": 20,
                "2_star": 8,
                "1_star": 4,
                "4_star": 10,
                "3_star": 8,
            }
        }
        limits = self.scraper._star_limits_low_to_high(product)
        self.assertEqual(
            [key for key, _count in limits],
            ["1_star", "2_star", "3_star", "4_star", "5_star"],
        )
        reviews = [
            {"comment_id": "high", "rating": 5},
            {"comment_id": "low", "rating": 1},
            {"comment_id": "middle", "rating": 3},
        ]
        ordered = self.scraper._order_reviews_low_to_high(reviews)
        self.assertEqual(
            [review["comment_id"] for review in ordered],
            ["low", "middle", "high"],
        )

    def test_parses_ph_card_text_fallbacks(self):
        self.assertEqual(self.scraper._price_from_text('Deal\n₱ 1,299 - ₱ 1,599\nSold'), '₱1,299-₱1,599')
        self.assertEqual(self.scraper._rating_from_text('15 sold\nManila'), '')
        self.assertEqual(self.scraper._rating_from_text('15 sold\n4.9\nManila'), '4.9')

    def test_builds_shopee_ph_search_url(self):
        scraper = ShopeeScraper('laptop stand & bag', 1, True, 0, site='ph')
        parts = urlsplit(scraper._build_search_url())
        query = parse_qs(parts.query)
        self.assertEqual(parts.netloc, 'shopee.ph')
        self.assertEqual(parts.path, '/search')
        self.assertEqual(query['keyword'], ['laptop stand & bag'])
        self.assertEqual(query['page'], ['0'])
        self.assertEqual(query['sortBy'], ['sales'])

    def test_normalizes_ph_product_links(self):
        relative = '/Sample-Product-i.12345.98765?sp_atk=tracking'
        self.assertEqual(
            self.scraper._normalize_product_url(relative),
            'https://shopee.ph/Sample-Product-i.12345.98765',
        )
        self.assertEqual(self.scraper._normalize_product_url('https://shopee.vn/a-i.1.2'), '')

    def test_direct_product_url_mode(self):
        url = "https://shopee.ph/sample-i.1325174344.27161131426?tracking=1"
        scraper = ShopeeScraper(
            "",
            1,
            False,
            10,
            product_urls=[url],
            output="direct_test.json",
        )
        product = scraper._product_from_url(url)
        self.assertEqual(
            product["link"],
            "https://shopee.ph/sample-i.1325174344.27161131426",
        )
        self.assertEqual(product["market"], "PH")
        self.assertEqual(scraper.out_file, "direct_test.json")

    def test_parser_supports_direct_product_url(self):
        args = build_parser().parse_args(
            ["--product-url", "https://shopee.ph/sample-i.1.2", "--output", "result.json", "--no-prompt"]
        )
        self.assertEqual(args.product_url, ["https://shopee.ph/sample-i.1.2"])
        self.assertEqual(args.output, "result.json")
        self.assertTrue(args.no_prompt)

    def test_normalizes_atomic_review_snapshot(self):
        class FakeDriver:
            @staticmethod
            def execute_script(_script):
                return [{
                    'comment_id': '123',
                    'author': 'buyer_one',
                    'rating': 5,
                    'time': '2026-06-19 09:14 | Variation: Silver',
                    'content': 'Stability: sturdy\nVery good item',
                    'seller_respond': '',
                    'like_count_text': '1.2K',
                }]

        self.scraper.driver = FakeDriver()
        reviews = self.scraper._reviews_from_current_page()
        self.assertEqual(reviews[0]['comment_id'], '123')
        self.assertEqual(reviews[0]['author'], 'buyer_one')
        self.assertEqual(reviews[0]['rating'], 5)
        self.assertEqual(reviews[0]['like_count'], 1200)

    def test_rejects_non_ph_site(self):
        with self.assertRaises(ValueError):
            ShopeeScraper('test', 1, True, 0, site='shopee.vn')

    def test_safe_get(self):
        # This test would require a live environment to run properly
        # Here we can only check if the method exists
        self.assertTrue(hasattr(self.scraper, '_safe_get'))

    def test_retrieve_products(self):
        # This test would require a live environment to run properly
        # Here we can only check if the method exists
        self.assertTrue(hasattr(self.scraper, '_retrieve_products'))

    def test_resumes_past_duplicate_review_pages(self):
        old_review = {"comment_id": "old", "author": "a", "time": "1", "content": "old", "rating": 5}
        new_review = {"comment_id": "new", "author": "b", "time": "2", "content": "new", "rating": 4}
        pages = [[old_review], [new_review]]
        state = {"page": 0}
        self.scraper._review_container = lambda timeout=5: object()
        self.scraper._reviews_from_current_page = lambda: pages[state["page"]]
        self.scraper._current_review_signature = lambda: str(state["page"])

        def advance(_signature):
            if state["page"] + 1 >= len(pages):
                return False
            state["page"] += 1
            return True

        self.scraper._next_review_page = advance
        with TemporaryDirectory() as directory:
            self.scraper.out_file = str(Path(directory) / "reviews.json")
            product = {"link": "https://shopee.ph/item-i.1.2", "comments": [old_review]}
            reviews = self.scraper._collect_reviews(2, product=product)
        self.assertEqual([review["comment_id"] for review in reviews], ["old", "new"])
        self.assertEqual(product["review_checkpoint"]["stop_reason"], "target_reached")

    def test_records_no_reviews_as_a_terminal_product_result(self):
        product = {"link": "https://shopee.ph/empty-i.1.2", "comments": []}
        with TemporaryDirectory() as directory:
            self.scraper.out_file = str(Path(directory) / "empty.json")
            self.scraper._record_no_reviews(product)
        self.assertEqual(product["review_status"], "no_reviews")
        self.assertEqual(product["comments"], [])
        self.assertEqual(product["review_checkpoint"]["stop_reason"], "no_reviews")

if __name__ == '__main__':
    unittest.main()
