import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit

from src.temu_scraper import TemuScraper, build_parser


class TestTemuScraper(unittest.TestCase):
    def setUp(self):
        self.scraper = TemuScraper(
            keyword="laptop stand",
            max_products=5,
            review_limit=20,
            pages=2,
            pause_for_verification=False,
        )

    def test_initialization(self):
        self.assertEqual(self.scraper.keyword, "laptop stand")
        self.assertEqual(self.scraper.max_products, 5)
        self.assertEqual(self.scraper.review_limit, 20)
        self.assertEqual(self.scraper.pages, 2)
        self.assertEqual(self.scraper.out_file, "temu_ph_laptop_stand.json")

    def test_requires_keyword_or_product_url(self):
        with self.assertRaises(ValueError):
            TemuScraper()

    def test_rejects_list_containing_only_invalid_urls(self):
        with self.assertRaises(ValueError):
            TemuScraper(product_urls=["https://example.com/product/123"])

    def test_builds_ph_search_url(self):
        parts = urlsplit(self.scraper._build_search_url(2))
        query = parse_qs(parts.query)
        self.assertEqual(parts.netloc, "www.temu.com")
        self.assertEqual(parts.path, "/ph-en/search_result.html")
        self.assertEqual(query["search_key"], ["laptop stand"])
        self.assertEqual(query["page"], ["2"])

    def test_normalizes_goods_query_url(self):
        url = "https://www.temu.com/goods.html?_bg_fs=1&goods_id=601099521225879#reviews"
        self.assertEqual(
            self.scraper._normalize_product_url(url),
            "https://www.temu.com/goods.html?goods_id=601099521225879",
        )

    def test_normalizes_slug_product_url(self):
        url = "https://m.temu.com/ph-en/portable-laptop-stand-g-601099588578152.html?share=1"
        self.assertEqual(
            self.scraper._normalize_product_url(url),
            "https://www.temu.com/goods.html?goods_id=601099588578152",
        )

    def test_rejects_other_hosts_and_search_pages(self):
        self.assertEqual(
            self.scraper._normalize_product_url(
                "https://example.com/goods.html?goods_id=601099521225879"
            ),
            "",
        )
        self.assertEqual(
            self.scraper._normalize_product_url(
                "https://www.temu.com/ph-en/search_result.html?search_key=laptop"
            ),
            "",
        )

    def test_parses_compact_counts(self):
        self.assertEqual(self.scraper._parse_compact_number("1,234 reviews"), 1234)
        self.assertEqual(self.scraper._parse_compact_number("2.5K+ sold"), 2500)
        self.assertEqual(self.scraper._parse_compact_number("1,2k bought"), 1200)
        self.assertEqual(self.scraper._parse_compact_number("none"), 0)

    def test_parses_rating(self):
        self.assertEqual(self.scraper._parse_rating("4.8 out of five stars"), 4.8)
        self.assertEqual(self.scraper._parse_rating("Rated 1 star"), 1.0)
        self.assertEqual(self.scraper._parse_rating("unrated"), 0.0)

    def test_direct_url_mode_uses_compatible_schema(self):
        url = "https://www.temu.com/goods.html?goods_id=601099521225879"
        scraper = TemuScraper(product_urls=[url], pause_for_verification=False)
        product = scraper._product_from_url(url)
        self.assertEqual(product["goods_id"], "601099521225879")
        self.assertEqual(product["platform"], "temu")
        self.assertEqual(product["market"], "PH")
        self.assertEqual(product["currency"], "PHP")

    def test_applies_json_ld_product(self):
        product = self.scraper._product_from_url(
            "https://www.temu.com/goods.html?goods_id=601099521225879"
        )
        self.scraper._apply_json_ld(
            product,
            {
                "@type": "Product",
                "name": "Portable laptop stand",
                "brand": {"name": "Example"},
                "image": ["https://img.kwcdn.com/product/example.jpg"],
                "offers": {"price": "199.00", "priceCurrency": "PHP"},
                "aggregateRating": {"ratingValue": "4.7", "reviewCount": "1.2K"},
            },
        )
        self.assertEqual(product["name"], "Portable laptop stand")
        self.assertEqual(product["price"], "₱199.00")
        self.assertEqual(product["rating"], 4.7)
        self.assertEqual(product["total_rating"], 1200)

    def test_normalizes_review_snapshot(self):
        class FakeDriver:
            @staticmethod
            def execute_script(_script, _root):
                return [
                    {
                        "comment_id": "review-1",
                        "author": "A****a",
                        "rating_label": "2 out of 5 stars",
                        "time": "14 Aug 2026",
                        "content": "  Sira agad\nnot sturdy  ",
                        "variation": "Color: Silver",
                        "helpful": "Helpful (1.2K)",
                    }
                ]

        self.scraper.driver = FakeDriver()
        reviews = self.scraper._reviews_from_current_view(object())
        self.assertEqual(reviews[0]["comment_id"], "review-1")
        self.assertEqual(reviews[0]["rating"], 2)
        self.assertEqual(reviews[0]["content"], "Sira agad not sturdy")
        self.assertEqual(reviews[0]["like_count"], 1200)

    def test_skips_empty_written_review_by_default(self):
        class FakeDriver:
            @staticmethod
            def execute_script(_script, _root):
                return [{"rating_label": "5 stars", "content": ""}]

        self.scraper.driver = FakeDriver()
        self.assertEqual(self.scraper._reviews_from_current_view(object()), [])

    def test_product_filters(self):
        self.scraper.min_rating = 4.0
        self.scraper.min_reviews = 100
        self.assertTrue(self.scraper._qualifies({"rating": 4.0, "total_rating": 100}))
        self.assertFalse(self.scraper._qualifies({"rating": 3.9, "total_rating": 1000}))
        self.assertFalse(self.scraper._qualifies({"rating": 5.0, "total_rating": 99}))

    def test_orders_reviews_from_lowest_to_highest_rating(self):
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

    def test_detects_login_redirect(self):
        class Body:
            text = "Sign in to continue"

        class FakeDriver:
            current_url = "https://www.temu.com/login.html?from=search"
            title = "Sign in / Register"

            @staticmethod
            def find_element(_by, _value):
                return Body()

        self.scraper.driver = FakeDriver()
        self.assertTrue(self.scraper._check_verification())

    def test_parser_supports_all_reviews_and_filters(self):
        args = build_parser().parse_args(
            ["electronic gadgets", "--all-reviews", "--min-rating", "4", "--min-reviews", "100"]
        )
        self.assertTrue(args.all_reviews)
        self.assertEqual(args.min_rating, 4.0)
        self.assertEqual(args.min_reviews, 100)

    def test_resumes_past_duplicate_review_batches(self):
        self.scraper.review_limit = 2
        old_review = {"comment_id": "old", "author": "a", "time": "1", "content": "old", "rating": 5}
        new_review = {"comment_id": "new", "author": "b", "time": "2", "content": "new", "rating": 4}
        pages = [[old_review], [new_review]]
        state = {"page": 0}
        root = object()
        self.scraper._reviews_from_current_view = lambda _root: pages[state["page"]]
        self.scraper._review_signature = lambda _root: str(state["page"])

        def advance(_root, _signature):
            if state["page"] + 1 >= len(pages):
                return False
            state["page"] += 1
            return True

        self.scraper._advance_reviews = advance
        with TemporaryDirectory() as directory:
            self.scraper.out_file = str(Path(directory) / "reviews.json")
            product = {"link": "https://www.temu.com/goods.html?goods_id=1", "comments": [old_review]}
            reviews = self.scraper._collect_reviews(root, product=product)
        self.assertEqual([review["comment_id"] for review in reviews], ["old", "new"])
        self.assertEqual(product["review_checkpoint"]["stop_reason"], "target_reached")

    def test_records_no_reviews_as_a_terminal_product_result(self):
        product = {
            "link": "https://www.temu.com/goods.html?goods_id=1",
            "comments": [],
        }
        with TemporaryDirectory() as directory:
            self.scraper.out_file = str(Path(directory) / "empty.json")
            self.scraper._record_no_reviews(product)
        self.assertEqual(product["review_status"], "no_reviews")
        self.assertEqual(product["comments"], [])
        self.assertEqual(product["review_checkpoint"]["stop_reason"], "no_reviews")


if __name__ == "__main__":
    unittest.main()
