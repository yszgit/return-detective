import csv
from collections import Counter
from datetime import date, timedelta

from .config import DATA_DIR, SNAPSHOT_DATE


def records(table):
    if table not in {"orders", "returns", "reviews", "inventory"}:
        raise ValueError("Unknown data table")
    with (DATA_DIR / f"{table}.csv").open(encoding="utf-8", newline="") as source:
        return list(csv.DictReader(source))


def evidence(table, sku, as_of=SNAPSHOT_DATE):
    if table not in {"returns", "reviews"}:
        raise ValueError("Use returns or reviews")
    cutoff = date.fromisoformat(as_of)
    field = "return_date" if table == "returns" else "review_date"
    return [r for r in records(table)
            if r["sku"] == sku and date.fromisoformat(r[field]) <= cutoff][:100]


def cohort_rates(sku, as_of=SNAPSHOT_DATE):
    cutoff = date.fromisoformat(as_of)
    orders = [r for r in records("orders") if r["sku"] == sku]
    eligible = {r["order_line_id"]: r for r in orders
                if date.fromisoformat(r["delivered_date"]) + timedelta(days=30) <= cutoff}
    returned = Counter()
    for row in records("returns"):
        order = eligible.get(row["order_line_id"])
        if order is None:
            continue
        if row["sku"] != order["sku"]:
            raise ValueError("Return SKU does not match its order line")
        delivery = date.fromisoformat(order["delivered_date"])
        event = date.fromisoformat(row["return_date"])
        if delivery <= event <= min(cutoff, delivery + timedelta(days=30)):
            returned[row["order_line_id"]] += int(row["quantity"])
    totals = {}
    for line_id, order in eligible.items():
        key = (order["dc"], order["cohort_id"])
        group = totals.setdefault(key, {"dc": key[0], "cohort_id": key[1],
                                       "sold_units": 0, "returned_units": 0,
                                       "observation_days": 30})
        quantity = int(order["quantity"])
        if returned[line_id] > quantity:
            raise ValueError("Returned quantity exceeds sold quantity")
        group["sold_units"] += quantity
        group["returned_units"] += returned[line_id]
    result = []
    for key in sorted(totals):
        group = totals[key]
        group["rate"] = group["returned_units"] / group["sold_units"]
        result.append(group)
    return result


def screen(sku, as_of=SNAPSHOT_DATE):
    groups = cohort_rates(sku, as_of)
    comparable = [r for r in groups if r["sold_units"] >= 30]
    if len(comparable) < 2:
        status = "insufficient_evidence"
    else:
        high = max(comparable, key=lambda r: r["rate"])
        low = min(comparable, key=lambda r: r["rate"])
        status = ("possible_pattern" if high["returned_units"] >= 3
                  and high["rate"] >= 0.10 and high["rate"] > 2 * low["rate"]
                  else "monitor")
    return {"sku": sku, "as_of": as_of, "status": status, "cohorts": groups}
