"""dashboard_utils._recommendation_type: devices are known by name, accessories are not the device."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
ORIGINAL = Path(os.environ.get("DEFAKETIVE_ORIGINAL") or HERE.parent / "Capstone-Version-Control-Version-1.1")
sys.path[:0] = [str(HERE), str(ORIGINAL), str(HERE / "backend")]

from dashboard_utils import _recommendation_type  # noqa: E402

DEVICES = {
    "Apple iPad 10th Gen 64GB WiFi": "tablet",
    "Samsung Galaxy Tab A9+ 8+128": "tablet",
    "Redmi Pad SE 8GB": "tablet",
    "10.1 inch Android Tablet 8+256 Kids": "tablet",
    "Apple iPhone 16 Pro Max with Case and Charger": "phone",
    "Infinix Hot 40i 8GB Fast Charging 5000mAh": "phone",
    "Samsung Galaxy S24 Ultra": "phone",
    "MacBook Air M2 13": "laptop",
    "Apple Watch Series 9 45mm": "smartwatch",
    "AirPods Pro 2": "earbuds",
    "Nintendo Switch OLED": "console",
    "Samsung 55 inch Smart TV 4K": "tv",
    "GoPro Hero 12": "camera",
}
NOT_THE_DEVICE = [
    "USB C to Lightning Cable for iPhone 15",
    "iPad Pro Keyboard Case Magnetic",
    "Apple Pencil 2 for iPad",
    "Stylus Pen for Tablet iPad Android",
    "Apple Watch Strap Silicone",
    "AirPods Case Cover",
    "GoPro Mount Tripod",
    "LCD Writing Tablet 8.5 inch",
]


class RecommendationTypes(unittest.TestCase):
    def test_devices_are_known_by_name(self) -> None:
        for name, kind in DEVICES.items():
            with self.subTest(name=name):
                self.assertEqual(_recommendation_type({"name": name}), kind)

    def test_accessories_are_not_the_device(self) -> None:
        devices = {"phone", "tablet", "laptop", "smartwatch", "earbuds", "console", "tv", "camera"}
        for name in NOT_THE_DEVICE:
            with self.subTest(name=name):
                self.assertNotIn(_recommendation_type({"name": name}), devices)


if __name__ == "__main__":
    unittest.main()
