from copy import deepcopy
from uuid import uuid4

from .data import records


class DemoRetail:
    """Single-process simulation only. Not an authenticated or durable backend."""

    def __init__(self):
        self.inventory = {r["stock_id"]: {**r, "available": int(r["available"]),
                                         "held": int(r["held"])}
                          for r in records("inventory")}
        self.actions = {}
        self.audit = []

    def propose_hold(self, case_id, stock_id, quantity):
        if not case_id or stock_id not in self.inventory:
            raise ValueError("A case and a known stock group are required")
        if type(quantity) is not int or quantity <= 0:
            raise ValueError("Quantity must be a positive integer")
        if quantity > self.inventory[stock_id]["available"]:
            raise ValueError("Insufficient available stock")
        action_id = uuid4().hex
        self.actions[action_id] = {"action_id": action_id, "case_id": case_id,
                                   "stock_id": stock_id, "quantity": quantity,
                                   "status": "PENDING_APPROVAL"}
        return deepcopy(self.actions[action_id])

    def approve(self, action_id, approver):
        # Caller is the explicit simulated human UI, never an LLM tool.
        action = self.actions[action_id]
        if action["status"] != "PENDING_APPROVAL" or not approver.strip():
            raise ValueError("Pending action and named approver required")
        action.update(status="APPROVED", approver=approver.strip())
        self.audit.append({"event": "APPROVED", "action_id": action_id,
                           "approver": approver.strip()})

    def execute_hold(self, action_id):
        action = self.actions[action_id]
        if action["status"] == "EXECUTED":
            return deepcopy(action)
        if action["status"] != "APPROVED":
            raise PermissionError("Human approval is required")
        stock = self.inventory[action["stock_id"]]
        if stock["available"] < action["quantity"]:
            raise ValueError("Stock changed; action needs review")
        stock["available"] -= action["quantity"]
        stock["held"] += action["quantity"]
        action["status"] = "EXECUTED"
        self.audit.append({"event": "EXECUTED", "action_id": action_id})
        return deepcopy(action)

    def read_inventory(self, stock_id):
        return deepcopy(self.inventory[stock_id])
