"""Regression tests for the USDA International Core converter."""
import json
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "builder"))
import build_core_ci as core

class CoreTests(unittest.TestCase):
    def test_nutrients_from_official_fdc_ids(self):
        food = {"foodNutrients": [
            {"nutrient": {"id": 1008}, "amount": 115},
            {"nutrient": {"id": 1003}, "amount": 4},
            {"nutrient": {"id": 1005}, "amount": 24},
            {"nutrient": {"id": 1004}, "amount": 1},
            {"nutrient": {"id": 1079}, "amount": 3},
        ]}
        n = core.nutrients(food)
        self.assertEqual((n["kcal"], n["protein"], n["carbs"], n["fat"]), (115, 4, 24, 1))
        self.assertTrue(core.check(n))
        self.assertIsNone(n["sugar"])

    def test_no_fabricated_kcal(self):
        food = {"foodNutrients": [{"nutrient": {"id": 1003}, "amount": 9}]}
        self.assertFalse(core.check(core.nutrients(food)))

    def test_legacy_nutrient_numbers(self):
        food = {"foodNutrients": [
            {"nutrient": {"number": "208"}, "amount": 160},
            {"nutrient": {"number": "203"}, "amount": 4},
            {"nutrient": {"number": "205"}, "amount": 21},
            {"nutrient": {"number": "204"}, "amount": 7},
        ]}
        n = core.nutrients(food)
        self.assertTrue(core.check(n))
        self.assertEqual(n["kcal"], 160)

    def test_archive_loads_actual_collection(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "usda.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("FoodData_Central_sr_legacy_food_json_2018-04.json", json.dumps({
                    "SRLegacyFoods": [{"fdcId": 123, "description": "Test food", "foodNutrients": []}]
                }))
                z.writestr("readme.txt", "not food data")
            foods = core.load_foods(archive, "SRLegacyFoods")
            self.assertEqual(foods[0]["fdcId"], 123)

    def test_missing_collection_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "invalid.zip"
            with zipfile.ZipFile(archive, "w") as z:
                z.writestr("test.json", json.dumps({"SomethingElse": []}))
            with self.assertRaises(ValueError):
                core.load_foods(archive, "SRLegacyFoods")

    def test_expected_pack_header(self):
        self.assertEqual(core.MAGIC, b"DTHPK1\n")
        self.assertEqual(len(core.MAGIC), 7)

if __name__ == "__main__":
    unittest.main()
