import unittest
from urllib.parse import parse_qs, urlsplit

from src.retriv import ShopeeScraper


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

if __name__ == '__main__':
    unittest.main()
