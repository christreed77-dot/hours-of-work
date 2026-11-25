import math, os, sys, unittest
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import fake_fred, build_data as B

class T(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fake_fred.install(); cls.d = B.build()
        cls.items = {i["id"]: i for i in cls.d["items"]}

    def test_five_income_levels_in_order(self):
        w = self.d["wages"]["weekly"]; keys = ["p10", "p25", "p50", "p75", "p90"]
        self.assertEqual([i["id"] for i in self.d["incomes"]], keys)
        for i in range(len(self.d["wages"]["quarters"])):
            vals = [w[k][i] for k in keys]
            self.assertEqual(vals, sorted(vals))

    def test_all_expected_items_present(self):
        for k in ["eggs", "gas", "house", "rent", "car", "childcare", "college"]:
            self.assertIn(k, self.items)

    def test_every_item_has_limitations_and_source(self):
        for it in self.d["items"]:
            self.assertTrue(it["limitations"], it["id"]); self.assertTrue(it["source"]); self.assertTrue(it["url"])

    def test_missing_quarter_dropped_and_carried(self):
        self.assertNotIn("2025-10-01", self.d["wages"]["quarters"])
        eggs = self.items["eggs"]
        self.assertTrue(eggs["wage_carried"][eggs["dates"].index("2025-11-01")])
        self.assertFalse(eggs["wage_carried"][eggs["dates"].index("2025-08-01")])

    def test_hours_math(self):
        eggs = self.items["eggs"]; q = self.d["wages"]
        j = q["quarters"].index("2024-01-01"); k = eggs["dates"].index("2024-02-01")
        self.assertAlmostEqual(eggs["hours"]["p50"][k], eggs["prices"][k] / (q["weekly"]["p50"][j] / 40), places=4)
        self.assertGreater(eggs["hours"]["p10"][k], eggs["hours"]["p90"][k])

    def test_chain_anchors_hit_published_numbers(self):
        cc = self.items["childcare"]
        yr22 = [p for d, p in zip(cc["dates"], cc["prices"]) if d.startswith("2022-")]
        self.assertAlmostEqual(sum(yr22) / len(yr22), B.CHILD_ANCHOR["value"], delta=2)   # annual mean equals the anchor
        col = self.items["college"]
        self.assertAlmostEqual(col["prices"][col["dates"].index("2025-09-01")], 11950, delta=1)
        self.assertTrue(all(d[5:7] == "09" for d in col["dates"]))

    def test_manual_vehicle_points_loaded(self):
        car = self.items["car"]; self.assertEqual(car["method"], "manual")
        self.assertEqual(car["prices"][car["dates"].index("2026-08-01")], 50089)

    def test_failed_source_is_skipped_not_fatal(self):
        orig = B.fetch_rent
        B.fetch_rent = lambda: (_ for _ in ()).throw(RuntimeError("boom"))
        try:
            d = B.build()
        finally:
            B.fetch_rent = orig
        self.assertNotIn("rent", [i["id"] for i in d["items"]]); self.assertIn("eggs", [i["id"] for i in d["items"]])

if __name__ == "__main__":
    unittest.main()
