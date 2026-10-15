import json
import unittest

from return_detective.config import ROOT
from return_detective.data import cohort_rates, evidence, records, screen
from return_detective.mock_retail import DemoRetail


class DataTests(unittest.TestCase):
    def test_linked_return_quantities(self):
        orders = {r["order_line_id"]: r for r in records("orders")}
        for row in records("returns"):
            order = orders[row["order_line_id"]]
            self.assertEqual(row["sku"], order["sku"])
            self.assertLessEqual(int(row["quantity"]), int(order["quantity"]))

    def test_expected_screens(self):
        scenarios = json.loads((ROOT / "evaluation" / "scenarios.json").read_text())
        for case in scenarios["scenarios"]:
            with self.subTest(sku=case["sku"]):
                self.assertEqual(screen(case["sku"])["status"], case["expected_screen"])

    def test_rates_use_sales_denominators(self):
        rates = cohort_rates("SHOE-001")
        self.assertEqual([(r["sold_units"], r["returned_units"]) for r in rates], [(100, 18), (100, 4)])

    def test_no_future_or_immature_observations(self):
        self.assertEqual(cohort_rates("SHOE-001", "2026-08-26"), [])
        self.assertEqual(evidence("reviews", "SHOE-001", "2026-09-01"), [])
        self.assertEqual(evidence("returns", "SHOE-001", "2026-08-26"), [])


class ApprovalTests(unittest.TestCase):
    def setUp(self):
        self.retail = DemoRetail()
        self.stock = "SHOE-001:DC-A:AUG-2026"
        self.action = self.retail.propose_hold("CASE-001", self.stock, 10)["action_id"]

    def test_unapproved_action_cannot_mutate_stock(self):
        before = self.retail.read_inventory(self.stock)
        with self.assertRaises(PermissionError):
            self.retail.execute_hold(self.action)
        self.assertEqual(before, self.retail.read_inventory(self.stock))

    def test_approved_action_is_idempotent(self):
        self.retail.approve(self.action, "TEST-QA")
        self.retail.execute_hold(self.action)
        self.retail.execute_hold(self.action)
        self.assertEqual(self.retail.read_inventory(self.stock)["available"], 110)
        self.assertEqual(self.retail.read_inventory(self.stock)["held"], 10)
        self.assertEqual(sum(r["event"] == "EXECUTED" for r in self.retail.audit), 1)

    def test_rechecks_stock_after_approval(self):
        self.retail.approve(self.action, "TEST-QA")
        self.retail.inventory[self.stock]["available"] = 0
        with self.assertRaises(ValueError):
            self.retail.execute_hold(self.action)
        self.assertEqual(self.retail.actions[self.action]["status"], "APPROVED")
        self.assertEqual(self.retail.read_inventory(self.stock)["held"], 0)


if __name__ == "__main__":
    unittest.main()
