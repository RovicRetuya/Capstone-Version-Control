import json
import unittest

from dashboard_utils import (
    csv_bytes,
    detect_marketplace,
    load_products,
    normalized_risk_score,
    price_value,
    platform_name,
    product_reliability,
    rank_alternatives,
    reliability_score,
    review_rows,
    risk_keyword_counts,
    risk_level,
    search_slug,
)


class TestDashboardUtils(unittest.TestCase):
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
        self.assertEqual(risk_level(30), "Low")
        self.assertEqual(risk_level(31), "Moderate")
        self.assertEqual(risk_level(61), "High")
        self.assertEqual(reliability_score(61), 39.0)
        self.assertEqual(reliability_score(20, 0.75), 55.0)

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
