import json

from .data import screen
from .mock_retail import DemoRetail


def main():
    print("Synthetic fixture demo: deterministic screening; no AWS or LLM calls.\n")
    for sku in ("SHOE-001", "SHOE-002", "SHOE-003"):
        print(json.dumps(screen(sku), indent=2))
    retail = DemoRetail()
    stock_id = "SHOE-001:DC-A:AUG-2026"
    action = retail.propose_hold("DEMO-CASE-001", stock_id, 10)
    try:
        retail.execute_hold(action["action_id"])
    except PermissionError:
        print("\nUnapproved hold correctly rejected.")
    retail.approve(action["action_id"], "SIMULATED-QA-USER")
    retail.execute_hold(action["action_id"])
    print("Inventory read after simulated approval and execution:")
    print(json.dumps(retail.read_inventory(stock_id), indent=2))


if __name__ == "__main__":
    main()
