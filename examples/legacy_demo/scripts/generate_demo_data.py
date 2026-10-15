"""Regenerate linked synthetic fixtures. No randomness or real customer records."""
import csv
from datetime import date, timedelta
from pathlib import Path

OUTPUT = Path(__file__).resolve().parents[1] / "data" / "sample"


def write_csv(name, rows):
    with (OUTPUT / f"{name}.csv").open("w", encoding="utf-8", newline="") as target:
        writer = csv.DictWriter(target, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    orders, returns, inventory, reviews = [], [], [], []
    plans = [("SHOE-001", 100, 18, 4), ("SHOE-002", 100, 5, 4), ("SHOE-003", 3, 1, 0)]
    for sku, count, a_returns, b_returns in plans:
        for dc, return_count in [("DC-A", a_returns), ("DC-B", b_returns)]:
            cohort = "AUG-2026"
            for i in range(count):
                line_id = f"{sku}-{dc}-{i + 1:03d}"
                delivery = date(2026, 8, 25) + timedelta(days=i % 8)
                orders.append({"order_line_id": line_id, "order_id": "ORDER-" + line_id,
                               "sku": sku, "size": str(37 + i % 4), "dc": dc,
                               "cohort_id": cohort, "delivered_date": delivery.isoformat(), "quantity": 1})
                if i < return_count:
                    reason = "quality" if sku != "SHOE-002" else "change_of_mind"
                    comment = "Sole separating after two wears" if reason == "quality" else "Changed my mind"
                    returns.append({"return_id": "RET-" + line_id, "order_line_id": line_id,
                                    "sku": sku, "return_date": (delivery + timedelta(days=7)).isoformat(),
                                    "quantity": 1, "reason": reason, "comment": comment})
            inventory.append({"stock_id": f"{sku}:{dc}:{cohort}", "sku": sku, "dc": dc,
                              "cohort_id": cohort, "available": 120, "held": 0})
        reviews.append({"review_id": "REV-" + sku, "sku": sku, "review_date": "2026-09-10",
                        "rating": 2 if sku == "SHOE-001" else 4,
                        "text": "Sole started separating" if sku == "SHOE-001" else "Comfortable shoes"})
    for name, rows in [("orders", orders), ("returns", returns), ("reviews", reviews), ("inventory", inventory)]:
        write_csv(name, rows)
        print(f"{name}: {len(rows)} synthetic records")


if __name__ == "__main__":
    main()
