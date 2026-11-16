import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "builder"))

from build_country_market_packs import make_row
from export_off_snapshot import export_row


class SnapshotTests(unittest.TestCase):
    def setUp(self):
        self.product = [
            "0123456700001", ["en:spain", "en:france"],
            [{"lang": "main", "text": "Product"}, {"lang": "es", "text": "Pan"}],
            "en", "Brand", "30", "1 slice (30 g)", 15, 0.9,
            [{"name": name, "100g": value} for name, value in
             (("energy-kcal", 210), ("proteins", 8), ("carbohydrates", 40), ("fat", 2))],
        ]

    def test_preserves_country_tags_names_nutrition_and_gram_serving(self):
        row = export_row(self.product, "es")
        _, record = make_row(row, "ES")
        self.assertEqual(record["de"], "Pan")
        self.assertEqual(record["base_unit"], "g")
        self.assertEqual(record["serving"], 30)
        self.assertEqual(record["n"], dict(kcal=210, protein=8, carbs=40, fat=2, sugar=None, fiber=None))
        self.assertIsNone(make_row(row, "IT"))

    def test_incomplete_nutrients_and_incompatible_servings(self):
        self.product[6] = "30 ml"
        row = export_row(self.product, "es")
        self.assertIsNone(make_row(row, "ES")[1]["serving"])
        self.product[-1].pop()
        self.assertIsNone(export_row(self.product, "es"))
