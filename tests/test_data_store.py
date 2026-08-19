import tempfile
import unittest
from pathlib import Path

from data_store import database_counts, save_evaluation_run, save_products, save_survey_response


class TestDataStore(unittest.TestCase):
    def test_central_store_upserts_and_saves_research_results(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "test.db"
            product = {
                "link": "https://example.test/product",
                "name": "Test product",
                "comments": [{"author": "A", "time": "now", "content": "okay", "sentiment_analysis": {"label": "neutral", "risk": {"detected": False}}}],
                "sentiment_summary": {"risk_score": 20, "sentiment_ratios": {"positive": .8}},
            }
            save_products([product], path=database)
            save_products([product], path=database)
            save_survey_response("Monthly", [3] * 10, [4] * 4, 50, 50, path=database)
            save_evaluation_run("verified.csv", {"sample_count": 2, "accuracy": .5, "precision": .5, "recall": .5, "f1": .5, "labels": ["negative", "positive"], "matrix": [[1, 0], [1, 0]]}, path=database)
            self.assertEqual(database_counts(database), {"products": 1, "reviews": 1, "survey_responses": 1, "evaluation_runs": 1})


if __name__ == "__main__":
    unittest.main()
