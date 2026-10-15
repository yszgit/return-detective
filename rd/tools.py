"""Tools the three agents can call.

Read tools query the ALDO return data (Athena or DuckDB) as of the replay date, so an
agent never sees the future. Action tools write to the case store. Financial authority
and approval gates are enforced here in code, not left to the language model.
"""
import json
import os
import datetime as dt
import threading
from contextlib import contextmanager

from strands import tool

from . import store
from .data import rows, one, lit, dlit, days_before, baseline_share
from .detect import screen, screen_all, window_sql

class _AsOf:
    """Replay date shared by all tools. A plain global (not a contextvar) because Strands may run
    tools on worker threads that do not inherit context."""
    value = "2026-01-31"

    def set(self, v):
        self.value = dt.date.fromisoformat(str(v)[:10]).isoformat()

    def get(self):
        return self.value


AS_OF = _AsOf()
_replay_lock = threading.RLock()


@contextmanager
def replay_context(as_of):
    """Serialize prototype runs so SDK worker threads share one stable replay date."""
    with _replay_lock:
        previous = AS_OF.get()
        AS_OF.set(as_of)
        try:
            yield
        finally:
            AS_OF.set(previous)


FEE_AUTHORITY_CAD = 500.0
PLAYBOOK = os.path.join(os.path.dirname(__file__), "policy", "response_playbook.md")
ALDO_FAULT = ("Quality", "Fulfilment error", "Damaged in transit", "Delivery failure")
RETURN_COLS = ("return_id, banner, order_number, sku, style, return_order_number, channel, return_date, status, "
               "refund, qty, raw_reason, store, category, restocking_fee, final_sale, aldo_fault")


def _asof():
    return AS_OF.get()


def _j(x):
    return json.dumps(x, default=str)


def _flag(cond):
    return f"sum(case when {cond} then 1 else 0 end)"


# ----------------------------------------------------------------- Triage tools
@tool
def get_return(return_id: int) -> str:
    """Get one return record: style, SKU, banner, channel, store, date, reason, normalized category, refund and restocking fee.
    Customer identifiers are deliberately not returned."""
    r = one(f"select {RETURN_COLS} from returns where return_id = {int(return_id)} and return_date <= {dlit(_asof())}")
    return _j(r or {"error": "return not found"})


@tool
def screen_style(style: str) -> str:
    """Run the statistical screen for every watched return category of a style over the last 28 days
    (as of the current replay date). For each category: count, share, company baseline share, lift, z-score
    and a level (NORMAL, WATCH or SIGNAL)."""
    return _j(screen_all(style, _asof()))


@tool
def find_open_case(style: str, category: str) -> str:
    """Check whether an investigation case is already open for this style and return category."""
    c = store.find_open_case(style, category, _asof())
    return _j(c or {"open_case": None})


# ----------------------------------------------------------- Investigator tools
@tool
def style_reason_mix(style: str, days: int = 90) -> str:
    """Compare the style's mix of return categories over the last N days with the company-wide baseline mix."""
    r = rows(f"""select category, count(*) as n from returns where style = {lit(style)} and {window_sql(_asof(), days)}
                 group by category order by n desc""")
    tot = sum(x["n"] for x in r) or 1
    for x in r:
        x["share"] = round(x["n"] / tot, 3)
        x["company_share"] = round(baseline_share(x["category"], _asof()), 3)
    return _j({"style": style, "days": days, "total_returns": tot, "mix": r})


@tool
def weekly_timeline(style: str, category: str, weeks: int = 16) -> str:
    """Weekly counts of this style's returns in the category vs all its returns, to see when the pattern
    started and whether it is growing or fading."""
    r = rows(f"""select date_trunc('week', return_date) as week_start, count(*) as all_returns,
                        {_flag('category = ' + lit(category))} as category_returns
                 from returns where style = {lit(style)} and {window_sql(_asof(), int(weeks) * 7)}
                 group by date_trunc('week', return_date) order by week_start""")
    for x in r:
        x["week_start"] = str(x["week_start"])[:10]
    return _j({"style": style, "category": category, "weeks": r})


@tool
def spread_analysis(style: str, category: str, days: int = 60) -> str:
    """Where do the category returns come from? Breakdown by banner, channel, store and SKU, with concentration
    measures. Widespread across many stores and channels points to the product itself; concentration in one store
    points to local handling; concentration in mail or online channels points to fulfilment or transit; one SKU
    points to a specific size or colour."""
    w = f"style = {lit(style)} and category = {lit(category)} and {window_sql(_asof(), days)}"
    tot = one(f"select count(*) as n from returns where {w}")["n"] or 0

    def by(col):
        return rows(f"""select coalesce(cast({col} as varchar), '(online)') as k, count(*) as n from returns where {w}
                        group by coalesce(cast({col} as varchar), '(online)') order by n desc limit 8""")

    stores, skus = by("store"), by("sku")
    nstores = one(f"select count(distinct store) as n from returns where {w} and store is not null")["n"]
    return _j({"style": style, "category": category, "days": days, "total": tot,
               "by_banner": by("banner"), "by_channel": by("channel"),
               "top_stores": stores, "distinct_stores": nstores,
               "top_store_share": round(stores[0]["n"] / tot, 2) if tot and stores else 0,
               "top_skus": skus, "top_sku_share": round(skus[0]["n"] / tot, 2) if tot and skus else 0})


@tool
def sample_returns(style: str, category: str, limit: int = 12) -> str:
    """List the most recent returns of the style in this category (IDs, date, channel, store, SKU, raw reason,
    refund, fee) to cite as evidence."""
    r = rows(f"""select return_id, return_date, banner, channel, store, sku, raw_reason, refund, restocking_fee
                 from returns where style = {lit(style)} and category = {lit(category)} and return_date <= {dlit(_asof())}
                 order by return_date desc, return_id desc limit {int(limit)}""")
    return _j(r)


@tool
def sku_return_rate(style: str) -> str:
    """Return observed SKU counts. A cohort return rate is unavailable because the sales aggregate has no order dates."""
    result = rows(f"""select sku, count(*) as returns from returns
        where style = {lit(style)} and return_date <= {dlit(_asof())}
        group by sku order by returns desc limit 10""")
    for row in result:
        row.update(lines_sold=None, return_rate=None)
    return _j({"style": style, "note": "Rate unavailable: sku_sales has no dated order cohort; counts are return records.",
               "skus": result})



@tool
def fee_audit(style: str, category: str) -> str:
    """Audit candidate fees per return order, not per duplicated item row. This does not establish customer-level counts."""
    result = one(f"""select count(*) as n,
        sum(case when fee > 0 then 1 else 0 end) as charged,
        coalesce(sum(fee), 0) as fees from (
            select return_order_number, max(restocking_fee) as fee from returns
            where style = {lit(style)} and category = {lit(category)}
            and return_date <= {dlit(_asof())} group by return_order_number
        ) orders_with_fees""")
    result["aldo_fault_category"] = category in ALDO_FAULT
    result["grain"] = "return order; amount is a candidate for review, not confirmed attributable savings"
    return _j(result)



@tool
def read_playbook() -> str:
    """Read the Return Detective response playbook: confidence levels, root-cause classes, owner teams,
    action tiers and authority limits."""
    with open(PLAYBOOK, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- Response tools
@tool
def open_case(style: str, category: str, summary: str, evidence: str) -> str:
    """Open (or fetch the existing) investigation case for a style and category. Evidence should cite numbers and return IDs."""
    c = store.open_case(style, category, _asof(), summary, evidence)
    return _j({"case_id": c["case_id"], "status": c["status"]})


@tool
def record_findings(case_id: str, root_cause: str, confidence: str, owner_team: str, hypotheses: list) -> str:
    """Save the investigation result on the case. confidence must be Low, Medium or High. hypotheses is a list of
    objects {"hypothesis": str, "verdict": "supported" | "ruled out" | "inconclusive", "evidence": str}."""
    if confidence not in ("Low", "Medium", "High"):
        return _j({"error": "confidence must be Low, Medium or High"})
    c = store.update_case(case_id, root_cause=root_cause, confidence=confidence, owner_team=owner_team, hypotheses=hypotheses)
    return _j({"ok": bool(c)})


@tool
def notify_owner_team(case_id: str, team: str, message: str) -> str:
    """Tier 1 prototype: record a notification simulation. No email or external message is sent."""
    action = store.log_action(case_id, 1, f"Notify {team}", message)
    return _j({"done": False, "simulated": True, "recorded": True, "action_id": action["action_id"]})



@tool
def waive_restocking_fees(case_id: str) -> str:
    """Tier 2 simulation: candidate fees up to CAD 500 per case; higher amounts require approval.
    Only ALDO-fault categories with Medium/High confidence qualify. No money is refunded by this prototype."""
    case = store.get_case(case_id)
    if not case:
        return _j({"error": "unknown case"})
    if case["category"] not in ALDO_FAULT or case.get("confidence") not in ("Medium", "High"):
        return _j({"refused": "An ALDO-fault category and Medium/High confidence are required."})
    records = rows(f"""select return_id, return_order_number, restocking_fee from returns
        where style = {lit(case['style'])} and category = {lit(case['category'])}
        and restocking_fee > 0 and return_date <= {dlit(_asof())}""")
    orders = {}
    for record in records:
        key = str(record["return_order_number"])
        orders[key] = max(orders.get(key, 0), record["restocking_fee"])
    total = round(sum(orders.values()), 2)
    detail = {"returns_refunded": 0, "returns_in_scope": len(records), "return_orders_in_scope": len(orders),
              "amount_cad": total, "return_ids": [record["return_id"] for record in records][:50],
              "future_returns": "proposed fee-free policy; no retail system has been updated",
              "amount_note": "deduplicated return-order fees; mixed-item attribution requires review"}
    store.link_returns(case_id, [record["return_id"] for record in records])
    if total <= FEE_AUTHORITY_CAD:
        action = store.log_action(case_id, 2, "Waive restocking fees", detail,
                                  idempotency_key=case_id + ":fee-waiver")
        return _j({"executed": False, "simulated": True, "within_authority": True, **detail,
                   "action_id": action["action_id"]})
    approval = store.request_approval(case_id, 2, "Waive restocking fees", detail, "Customer Care lead")
    return _j({"executed": False, "simulated": True, "approval_requested": approval["approval_id"],
               "reason": f"CAD {total} exceeds CAD {FEE_AUTHORITY_CAD:.0f} prototype authority", **detail})



@tool
def request_fit_guidance_update(case_id: str, proposed_text: str) -> str:
    """Tier 3: propose a product-page fit note (e.g. 'Runs small: we recommend half a size up'). Requires Merchandising approval."""
    c = store.get_case(case_id)
    if not c or not (c["category"].startswith("Fit") or c["category"] == "Expectation gap"):
        return _j({"refused": "Fit-guidance updates apply only to fit or expectation-gap cases."})
    if c.get("confidence") not in ("Medium", "High"):
        return _j({"refused": "Record findings with confidence Medium or High first."})
    r = store.request_approval(case_id, 3, "Update product-page fit guidance", {"proposed_text": proposed_text}, "Merchandising")
    return _j({"approval_requested": r["approval_id"], "approver": "Merchandising"})


@tool
def request_stock_hold(case_id: str, scope: str) -> str:
    """Tier 4: request a hold on remaining stock of the style (DC and stores) pending quality inspection.
    Requires Quality and Merchandising approval and a Quality case with confidence High."""
    c = store.get_case(case_id)
    if not c or c.get("category") != "Quality" or c.get("confidence") != "High":
        return _j({"refused": "Stock holds require a Quality case with confidence High."})
    r = store.request_approval(case_id, 4, "Hold stock pending inspection", {"scope": scope}, "Quality & Merchandising")
    return _j({"approval_requested": r["approval_id"], "approver": "Quality & Merchandising"})


@tool
def draft_supplier_claim(case_id: str, claim_text: str) -> str:
    """Tier 5: draft a supplier quality claim with the evidence. The agent only drafts; sending requires
    Quality & Sourcing approval and a Quality case with confidence High."""
    c = store.get_case(case_id)
    if not c or c.get("category") != "Quality" or c.get("confidence") != "High":
        return _j({"refused": "Supplier claims require a Quality case with confidence High."})
    r = store.request_approval(case_id, 5, "Send supplier quality claim", {"draft": claim_text}, "Quality & Sourcing")
    return _j({"approval_requested": r["approval_id"], "approver": "Quality & Sourcing"})


@tool
def request_proactive_outreach(case_id: str, offer: str) -> str:
    """Tier 5: propose contacting recent buyers of the style (opted-in channels only) with a replacement or
    free-return offer before they hit the defect. Requires Customer Care and Privacy approval and a Quality case
    with confidence High."""
    c = store.get_case(case_id)
    if not c or c.get("category") != "Quality" or c.get("confidence") != "High":
        return _j({"refused": "Proactive outreach requires a Quality case with confidence High."})
    r = store.request_approval(case_id, 5, "Proactive customer outreach",
                               {"offer": offer, "channel": "opted-in email only"}, "Customer Care & Privacy")
    return _j({"approval_requested": r["approval_id"], "approver": "Customer Care & Privacy"})


@tool
def schedule_verification(case_id: str, check_after_days: int = 21) -> str:
    """Record a dated follow-up plan. This local prototype does not create a cloud scheduler."""
    days = int(check_after_days)
    if not 1 <= days <= 365:
        return _j({"refused": "check_after_days must be between 1 and 365"})
    due = (dt.date.fromisoformat(_asof()) + dt.timedelta(days=days)).isoformat()
    if not store.update_case(case_id, verification_due_date=due):
        return _j({"error": "unknown case"})
    action = store.log_action(case_id, 0, "Plan verification", {"check_after_days": days, "due_date": due})
    return _j({"scheduled": False, "planned": True, "due_date": due, "action_id": action["action_id"]})



@tool
def verify_case(case_id: str) -> str:
    """Compare observed screens at opening and a later replay date. This does not prove an intervention caused a change."""
    case = store.get_case(case_id)
    if not case:
        return _j({"error": "unknown case"})
    if _asof() < case["opened_as_of"]:
        return _j({"refused": "Verification date cannot precede case opening"})
    opened = screen(case["style"], case["category"], case["opened_as_of"])
    now = screen(case["style"], case["category"], _asof())
    status = "REOPENED" if now["level"] in ("SIGNAL", "WATCH") else "MONITORING"
    store.update_case(case_id, status=status, last_verified_as_of=_asof())
    return _j({"opened": opened, "now": now, "case_status": status, "observational_only": True})



TRIAGE_TOOLS = [get_return, screen_style, find_open_case]
INVESTIGATOR_TOOLS = [style_reason_mix, weekly_timeline, spread_analysis, sample_returns, sku_return_rate,
                      fee_audit, read_playbook]
RESPONSE_TOOLS = [read_playbook, open_case, record_findings, notify_owner_team, waive_restocking_fees,
                  request_fit_guidance_update, request_stock_hold, draft_supplier_claim, request_proactive_outreach,
                  schedule_verification]
VERIFY_TOOLS = [verify_case, weekly_timeline]
