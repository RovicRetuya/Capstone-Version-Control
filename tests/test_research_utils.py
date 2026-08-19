import unittest

from research_utils import score_sus, score_umux


class TestResearchUtils(unittest.TestCase):
    def test_sus_extremes_and_midpoint(self):
        self.assertEqual(score_sus([5, 1] * 5), 100.0)
        self.assertEqual(score_sus([1, 5] * 5), 0.0)
        self.assertEqual(score_sus([3] * 10), 50.0)

    def test_umux_extremes_and_midpoint(self):
        self.assertEqual(score_umux([7, 1, 7, 1]), 100.0)
        self.assertEqual(score_umux([1, 7, 1, 7]), 0.0)
        self.assertEqual(score_umux([4, 4, 4, 4]), 50.0)

    def test_invalid_response_counts(self):
        with self.assertRaises(ValueError):
            score_sus([3] * 9)
        with self.assertRaises(ValueError):
            score_umux([4] * 3)


if __name__ == "__main__":
    unittest.main()
