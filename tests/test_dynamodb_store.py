"""Exercise the optional DynamoDB persistence contract without AWS calls."""
import importlib
import os
import sys
import types
import unittest
from unittest.mock import patch


class FakeBatch:
    def __init__(self, table):
        self.table = table

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def put_item(self, Item):
        key = (Item["namespace"], Item[self.table.id_field])
        self.table.items[key] = Item

    def delete_item(self, Key):
        key = (Key["namespace"], Key[self.table.id_field])
        self.table.items.pop(key, None)


class FakeTable:
    def __init__(self, id_field):
        self.id_field = id_field
        self.items = {}

    def query(self, **kwargs):
        namespace = kwargs["KeyConditionExpression"]
        return {"Items": [v for (ns, _), v in self.items.items() if ns == namespace]}

    def batch_writer(self):
        return FakeBatch(self)


class FakeResource:
    def __init__(self):
        self.tables = {"rd_cases": FakeTable("case_id"),
                       "rd_actions": FakeTable("action_id"),
                       "rd_approvals": FakeTable("approval_id")}

    def Table(self, name):
        return self.tables[name]


class DynamoStoreTest(unittest.TestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, {"RD_STORE_BACKEND": "dynamodb",
                                        "RD_STORE_NAMESPACE": "test-run"})
        self.env.start()
        conditions = types.ModuleType("boto3.dynamodb.conditions")

        class Key:
            def __init__(self, name):
                self.name = name

            def eq(self, value):
                return value

        conditions.Key = Key
        self.modules = patch.dict(sys.modules, {"boto3": types.ModuleType("boto3"),
                                                "boto3.dynamodb": types.ModuleType("boto3.dynamodb"),
                                                "boto3.dynamodb.conditions": conditions})
        self.modules.start()
        self.store = importlib.reload(importlib.import_module("rd.store"))
        self.resource = FakeResource()
        self.store._DDB = self.resource

    def tearDown(self):
        self.modules.stop()
        self.env.stop()

    def test_cases_actions_approvals_round_trip_and_namespace_reset(self):
        c = self.store.open_case("shoe", "Quality", "2026-01-31", "summary", "evidence")
        self.store.update_case(c["case_id"], confidence="High")
        self.store.link_returns(c["case_id"], [42])
        self.store.log_action(c["case_id"], 1, "Notify owner", {"amount": 2.5})
        a = self.store.request_approval(c["case_id"], 2, "Waive fee", {}, "Lead")
        self.store.decide_approval(a["approval_id"], True, "Reviewer")
        result = self.store.snapshot()
        self.assertEqual(result["cases"][c["case_id"]]["linked_return_ids"], [42])
        self.assertEqual(result["cases"][c["case_id"]]["status"], "ACTIONED")
        self.assertEqual(result["approvals"][0]["status"], "APPROVED")
        self.assertEqual(len(result["actions"]), 2)
        self.assertEqual(result["actions"][0]["detail"]["amount"], 2.5)
        self.resource.Table("rd_cases").items[("someone-else", "CASE-OTHER")] = {
            "namespace": "someone-else", "case_id": "CASE-OTHER"}
        self.store.reset()
        self.assertEqual(self.store.snapshot(), {"cases": {}, "actions": [], "approvals": []})
        self.assertIn(("someone-else", "CASE-OTHER"), self.resource.Table("rd_cases").items)


if __name__ == "__main__":
    unittest.main()
