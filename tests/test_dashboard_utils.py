import json
import unittest

from dashboard_utils import (
    cached_product_matches,
    csv_bytes,
    detect_marketplace,
    load_products,
    has_usable_products,
    merge_product_catalogs,
    normalized_risk_score,
    price_value,
    platform_name,
    product_reliability,
    product_risk_level,
    product_risk_percent,
    rank_alternatives,
    rank_recommendations,
    recommendation_search_query,
    reliability_score,
    review_rows,
    risk_keyword_counts,
    risk_level,
    risk_score_percent,
    search_slug,
)


class TestDashboardUtils(unittest.TestCase):
    def test_cached_product_matching_uses_names_and_normalized_links(self):
        products = [
            {"name": "Raspberry Pi Pico 2 Board", "link": "https://shopee.ph/sample-i.1.2?tracking=1", "sentiment_summary": {"risk_score": 20}},
            {"name": "Wireless Earbuds", "link": "https://www.lazada.com.ph/products/earbuds-i1-s2.html", "sentiment_summary": {"risk_score": 10}},
        ]
        self.assertEqual(cached_product_matches(products, "raspberry pico")[0]["name"], "Raspberry Pi Pico 2 Board")
        self.assertEqual(
            cached_product_matches(products, "https://shopee.ph/sample-i.1.2?from=share")[0]["name"],
            "Raspberry Pi Pico 2 Board",
        )
        self.assertEqual(cached_product_matches(products, "not in database"), [])

    def test_recommendations_are_similar_low_risk_and_well_reviewed(self):
        target = {
            "link": "target",
            "name": "Anker 25000mAh Laptop Power Bank",
            "brand": "Anker",
            "category": "Power Banks",
            "sentiment_summary": {"risk_score": 1, "risk_score_scale": "percent"},
        }
        good_match = {
            "link": "good",
            "name": "UGREEN 20000mAh USB-C Power Bank",
            "brand": "UGREEN",
            "category": "Power Banks",
            "rating": 4.8,
            "sentiment_summary": {
                "risk_score": 4,
                "risk_score_scale": "percent",
                "review_count": 30,
                "sentiment_ratios": {"positive": 0.9},
            },
        }
        risky_match = {
            "link": "risky",
            "name": "Anker Power Bank",
            "brand": "Anker",
            "category": "Power Banks",
            "rating": 4.9,
            "sentiment_summary": {
                "risk_score": 70,
                "risk_score_scale": "percent",
                "review_count": 30,
                "sentiment_ratios": {"positive": 0.9},
            },
        }
        unrelated = {
            "link": "unrelated",
            "name": "Low-Power USB-C Raspberry Pi Development Board",
            "rating": 5,
            "sentiment_summary": {
                "risk_score": 0,
                "risk_score_scale": "percent",
                "review_count": 30,
                "sentiment_ratios": {"positive": 1},
            },
        }

        recommendations = rank_recommendations(
            target, [target, risky_match, unrelated, good_match], limit=3
        )

        self.assertEqual([item["link"] for item in recommendations], ["good"])
        self.assertEqual(recommendation_search_query(target), "Anker power bank")

    def test_merge_product_catalogs_normalizes_tracking_links(self):
        current = {"name": "Current", "link": "https://www.lazada.com.ph/products/item-i1.html?tracking=1"}
        stale = {"name": "Stale", "link": "https://lazada.com.ph/products/item-i1.html?tracking=2"}
        other = {"name": "Other", "link": "https://shopee.ph/other-i.1.2"}
        self.assertEqual(merge_product_catalogs([current], [stale, other]), [current, other])

    def test_usable_product_detection_rejects_blank_failed_scrapes(self):
        self.assertFalse(has_usable_products([{"link": "https://shopee.ph/item-i.1.2", "comments": []}]))
        self.assertTrue(has_usable_products([{"name": "Real product", "comments": []}]))
        self.assertTrue(has_usable_products([{"review_status": "no_reviews", "comments": []}]))

    def test_search_slug(self):
        self.assertEqual(search_slug("Laptop Stand & Bag"), "laptop_stand_bag")
        self.assertEqual(search_slug("!!!"), "search")

    def test_marketplace_detection_and_display(self):
        self.assertEqual(detect_marketplace("https://shopee.ph/item-i.1.2"), "shopee")
        self.assertEqual(detect_marketplace("https://www.lazada.com.ph/products/item.html"), "lazada")
        self.assertEqual(detect_marketplace("https://www.temu.com/ph-en/goods.html"), "temu")
        self.assertEqual(detect_marketplace("wireless earbuds", "lazada"), "lazada")
        self.assertEqual(platform_name({"platform": "temu"}), "Temu PH")
        with self.assertRaises(ValueError):
            detect_marketplace("https://example.com/item")

    def test_price_value_uses_range_midpoint(self):
        self.assertEqual(price_value("₱1,000 - ₱1,500"), 1250.0)
        self.assertEqual(price_value("â‚±299"), 299.0)
        self.assertIsNone(price_value(""))

    def test_load_and_flatten_reviews(self):
        payload = [{"name": "Item", "comments": [{"rating": 5, "content": "Good"}]}]
        products = load_products(json.dumps(payload).encode())
        rows = review_rows(products)
        self.assertEqual(rows[0]["Product"], "Item")
        self.assertEqual(rows[0]["Sentiment"], "unanalyzed")
        self.assertIn(b"Review", csv_bytes(rows))

    def test_risk_display_helpers(self):
        self.assertEqual(normalized_risk_score(61), 0.61)
        self.assertEqual(normalized_risk_score(0.4), 0.4)
        self.assertEqual(normalized_risk_score(1.0, "percent"), 0.01)
        self.assertEqual(normalized_risk_score(1.0, "ratio"), 1.0)
        self.assertEqual(risk_score_percent(1.0, "percent"), 1.0)
        self.assertEqual(risk_level(30), "Low")
        self.assertEqual(risk_level(31), "Moderate")
        self.assertEqual(risk_level(61), "High")
        self.assertEqual(risk_level(1.0, "percent"), "Low")
        self.assertEqual(risk_level(1.0, "ratio"), "High")
        self.assertEqual(reliability_score(61), 39.0)
        self.assertEqual(reliability_score(20, 0.75), 55.0)
        self.assertEqual(reliability_score(1.0, 0.6667, "percent"), 65.7)

    def test_product_risk_helpers_respect_explicit_percent_scale(self):
        product = {
            "sentiment_summary": {
                "risk_score": 1.0,
                "risk_score_scale": "percent",
                "sentiment_ratios": {"positive": 0.6667},
            }
        }
        self.assertEqual(product_risk_percent(product), 1.0)
        self.assertEqual(product_risk_level(product), "Low")
        self.assertEqual(product_reliability(product), 65.7)

    def test_product_reliability_and_alternative_ranking(self):
        current = {"link": "current", "category": "Audio", "sentiment_summary": {"risk_score": 70, "sentiment_ratios": {"positive": .2}}}
        same_category = {"link": "same", "category": "Audio", "sentiment_summary": {"risk_score": 10, "sentiment_ratios": {"positive": .7}, "review_count": 5}}
        other_category = {"link": "other", "category": "Power", "sentiment_summary": {"risk_score": 0, "sentiment_ratios": {"positive": 1}, "review_count": 20}}
        self.assertEqual(product_reliability(same_category), 60.0)
        self.assertEqual(rank_alternatives(current, [current, other_category, same_category], 2)[0]["link"], "same")

    def test_keyword_counts_ignore_negated_evidence(self):
        product = {"comments": [{"sentiment_analysis": {"risk": {"evidence": [
            {"term": "Sira", "negated": False},
            {"term": "peke", "negated": True},
            {"term": "sira", "negated": False},
        ]}}}]}
        self.assertEqual(risk_keyword_counts(product), {"sira": 2})


if __name__ == "__main__":
    unittest.main()
