"""fault_rules f13: reviews that report a fault in words the older rules missed, and ones that must stay unflagged."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend" / "sentiment-analysis"))

from defaketive_sentiment.fault_rules import f11_match  # noqa: E402

FAULTS = [
    "only one piece is working",
    "Yung isa lang gumagana, nakakadisappoint lang",
    "the cord was working but the adapter wasn't",
    "Sound Quality:good Performance:can't connect on a call",
    "Can't connect ayaw mag appear nung bluethooth name",
    "Accuracy:not accurate pabago bgo nalabas na timbang",
    "Alam nyu nman na May Damaged yung item nyu",
    "good handling but not working",
]
NOT_FAULTS = [
    "The colors are not accurate to the pictures but I like them",  # not-as-described, not a defect
    "The box has a crack but the item is fine",  # packaging
    "akala ko may sira yung isa pero okay naman pala",  # a mistake that was cleared up
    "no damage at all, works great",
    "Very accurate and easy to connect",
]


NEGATED_DAMAGE = [
    "Yung Hindi agad mag crack pag nhulog",
    "doesn't easily crack",
    "di basta basta mag crack",
    "hindi madaling mabasag",
    "never scratches or dents",
    "won't break even when dropped",
    "hindi agad masira, matibay",
    "walang gasgas",
    "zero damage",
    "scratch resistant",
    "crack-proof, anti-scratch",
    "protects against cracks",
    "para di mag crack",
]
NEGATED_DRAIN = [
    "battery doesn't drain quickly",
    "hindi ito mabilis malowbat",
    "hindi mabilis mag drain",
]
TRUE_DRAIN = [
    "battery drains fast",
    "mabilis malowbat",
    "does not last and drains quickly",
]
REAL_DAMAGE = [
    "may crack na ang screen",
    "arrived cracked",
    "dumating na basag",
    "nasira agad pagdating",
]


class NegatedDamage(unittest.TestCase):
    def test_negated_damage_is_not_flagged(self) -> None:
        from defaketive_sentiment.extra_labels import quality_spans
        from defaketive_sentiment.risk_heads import HybridRiskCategoryClassifier as H

        for text in NEGATED_DAMAGE:
            with self.subTest(text=text):
                self.assertLess(H.damage_probability(text), 0.1)
                self.assertEqual(quality_spans(text.lower()), [])

    def test_real_damage_is_still_flagged(self) -> None:
        from defaketive_sentiment.risk_heads import HybridRiskCategoryClassifier as H

        for text in REAL_DAMAGE[:3]:
            with self.subTest(text=text):
                self.assertGreater(H.damage_probability(text), 0.5)


class DrainNegation(unittest.TestCase):
    def test_negated_drain_is_not_flagged(self) -> None:
        for text in NEGATED_DRAIN:
            with self.subTest(text=text):
                self.assertIsNone(f11_match(text))

    def test_real_drain_is_flagged(self) -> None:
        for text in TRUE_DRAIN:
            with self.subTest(text=text):
                self.assertIsNotNone(f11_match(text))


class FaultRules(unittest.TestCase):
    def test_faults_are_flagged(self) -> None:
        for text in FAULTS:
            with self.subTest(text=text):
                self.assertIsNotNone(f11_match(text))

    def test_other_sentences_are_not(self) -> None:
        for text in NOT_FAULTS:
            with self.subTest(text=text):
                self.assertIsNone(f11_match(text))


if __name__ == "__main__":
    unittest.main()
