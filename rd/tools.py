"""Tools the three agents can call.

Read tools query the ALDO return data (Athena or DuckDB) as of the replay date, so an
agent never sees the future. Action tools write to the case store. Financial authority
and approval gates are enforced here in code, not left to the language model.
"""
import json
import os

from strands import tool

from . import store
from .data import rows, one, lit, dlit, days_before, baseline_share, CURATED
from .detect import screen, screen_all, window_sql

class _AsOf:
    """Replay date shared by all tools. A plain global (not a contextvar) because Strands may run
    tools on worker threads that do not inherit context."""
    value = "2026-01-31"

    def set(self, v):
        self.value = str(v)[:10]

    def get(self):
        return self.value


AS_OF = _AsOf()
FEE_AUTHORITY_CAD = 500.0
PLAYBOOK = os.path.join(os.path.dirname(__file__), "policy", "response_playbook.md")
ALDO_FAULT = ("Quality", "Fulfilment error", "Damaged in transit", "Delivery failure")
RETURN_COLS = ("return_id, banner, order_number, sku, style, return_order_number, channel, return_date, status, "
               "refund, qty, raw_reason, store, category, restocking_fee, final_sale, aldo_fault")
if CURATED:
    RETURN_COLS = RETURN_COLS.replace('restocking_fee', 'transaction_fee_amount') + (
        ', return_created_at_utc, missing_style, invalid_quantity, unknown_category, flag_missing, '
        'fee_missing, eligible_for_detection, currency_code')


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
    if r and CURATED:
        r=dict(r)
        # These values are kept in the analytical snapshot, but their observation times
        # were not supplied. They cannot become features of a historical agent run.
        for field in ('status','refund','final_sale','transaction_fee_amount','flag_missing','fee_missing'):
            r[field]=None
        r['snapshot_attributes_point_in_time_available']=False
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
    c = store.find_open_case(style, category)
    return _j(c or {"open_case": None})


@tool
def read_case(case_id: str) -> str:
    """Read a case and recorded actions/approvals before proposing follow-up actions.
    Rejected proposals must stay rejected; an action log represents a simulation.
    """
    db = store.snapshot()
    return _j({'case': db['cases'].get(case_id),
               'actions': [a for a in db['actions'] if a['case_id'] == case_id],
               'approvals': [a for a in db['approvals'] if a['case_id'] == case_id]})


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
    money = 'null as refund, null as transaction_fee_amount' if CURATED else 'refund,restocking_fee'
    r = rows(f"""select return_id, return_date, banner, channel, store, sku, raw_reason, {money}
                 from returns where style = {lit(style)} and category = {lit(category)} and return_date <= {dlit(_asof())}
                 order by return_date desc, return_id desc limit {int(limit)}""")
    return _j(r)


@tool
def sku_return_rate(style: str) -> str:
    """Return rate by SKU using order lines sold as the denominator. Sales data only covers orders from
    Aug 2025 onward, so earlier periods have no rate."""
    if CURATED:
        r = rows(f"""select sku,count(*) as return_lines,
            sum(case when order_line_present then 1 else 0 end) as linked_return_lines
            from returns where style={lit(style)} and return_date<={dlit(_asof())}
            group by sku order by return_lines desc,sku limit 10""")
        for x in r:
            x['return_rate'] = None
            x['rate_status'] = 'unavailable_partial_order_coverage_and_undated_shipment_snapshot'
        return _j({'style':style,'skus':r,'population_return_rate_available':False,
                   'note':'Order sample coverage and temporal eligibility are insufficient for a population return rate; unknown is not zero.'})
    r = rows(f"""select r.sku, count(*) as returns, max(s.lines_sold) as lines_sold
                 from returns r left join sku_sales s on r.sku = s.sku
                 where r.style = {lit(style)} and r.return_date <= {dlit(_asof())} and r.return_date >= DATE '2025-08-01'
                 group by r.sku order by returns desc limit 10""")
    for x in r:
        x["return_rate"] = round(x["returns"] / x["lines_sold"], 3) if x["lines_sold"] else None
    return _j({"style": style, "note": "denominator available for Aug-2025+ orders only", "skus": r})


@tool
def fee_audit(style: str, category: str) -> str:
    """Check whether customers returning this style for this category were charged a restocking fee. Charging a
    fee is unfair when the cause is ALDO's responsibility (quality, fulfilment, transit damage)."""
    if CURATED:
        related = f"""select distinct return_order_number from returns where style={lit(style)}
            and category={lit(category)} and qty>0 and return_date<={dlit(_asof())}"""
        n=one(f'select count(*) as n from ({related}) r')['n']
        return _j({'related_return_transactions':n,'charged':None,'fees':None,
                   'historical_fee_evidence_available':False,'currency_verified':False,
                   'aldo_fault_category':category in ALDO_FAULT,
                   'note':'Fee amounts/charge outcomes are undated snapshot facts and are withheld from historical agent decisions. Descriptive transaction-grain reconciliation is in quality_report.json; mixed-reason transactions do not prove refund eligibility.'})
    r = one(f"""select count(*) as n, {_flag('restocking_fee > 0')} as charged, coalesce(sum(restocking_fee), 0) as fees
                from returns where style = {lit(style)} and category = {lit(category)} and return_date <= {dlit(_asof())}""")
    r["aldo_fault_category"] = category in ALDO_FAULT
    return _j(r)


@tool
def exchange_evidence(style: str) -> str:
    """Order-level exchange evidence up to the replay date; CONFIRMED and ASSUMED are different.
    An order can contain multiple products, so this is not an item-level sizing conclusion."""
    if not CURATED:
        return _j({'available':False,'reason':'Requires the v2 official dataset.'})
    r = rows(f"""select e.confidence,count(*) as exchange_lines,min(e.exchange_date) as first_date,
        max(e.exchange_date) as last_date from exchanges e join (
          select distinct order_number from returns where style={lit(style)} and return_date<={dlit(_asof())}
        ) r using(order_number) where e.exchange_date<={dlit(_asof())} and not e.invalid_exchange
        group by e.confidence order by e.confidence""")
    return _j({'available':True,'style':style,'as_of':_asof(),'evidence':r,
               'link_grain':'original_order_only; item match and sizing direction unproven'})


@tool
def transaction_context(style: str, days: int = 90) -> str:
    """Dated transaction context by country/banner. Exact style-name matches are not SKU joins.
    Monetary fields retain source scale; currency/FX and causal savings are not established."""
    if not CURATED:
        return _j({'available':False,'reason':'Requires the v2 official dataset.'})
    r = rows(f"""select banner,country_code,return_indicator,count(*) as transaction_lines,
        sum(net_sales_units) as net_units,sum(gross_margin_amount) as source_nominal_margin
        from transactions where lower(style_name)=lower({lit(style)}) and not invalid_transaction
        and business_date>{dlit(days_before(_asof(),max(1,int(days))))} and business_date<={dlit(_asof())}
        and business_month>={lit(str(days_before(_asof(),max(1,int(days))))[:7])}
        and business_month<={lit(_asof()[:7])}
        group by banner,country_code,return_indicator order by banner,country_code,return_indicator""")
    return _j({'available':True,'style':style,'as_of':_asof(),'groups':r,
               'currency_verified':False,'link_grain':'exact_style_name_only; no SKU/product-master join',
               'note':'An empty result means no matching evidence in the supplied coverage, not zero population sales.'})


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
    """Tier 1: send the case summary to the owner team (Quality & Sourcing, Merchandising, E-commerce Ops, Logistics, Store Ops)."""
    a = store.log_action(case_id, 1, f"Notify {team}", message)
    return _j({"done": True, "action_id": a["action_id"]})


@tool
def waive_restocking_fees(case_id: str) -> str:
    """Tier 2: refund restocking fees charged on returns linked to this case and make future returns of this style
    and category fee-free. Only allowed for ALDO-fault categories with confidence Medium or High. Executes
    automatically up to CA$500 per case; above that it creates an approval request for the Customer Care lead."""
    c = store.get_case(case_id)
    if not c:
        return _j({"error": "unknown case"})
    if c["category"] not in ALDO_FAULT:
        return _j({"refused": "Fee waivers apply only when the root cause is ALDO's responsibility."})
    if c.get("confidence") not in ("Medium", "High"):
        return _j({"refused": "Confidence must be Medium or High before waiving fees. Record findings first."})
    if CURATED:
        return _j({'refused':'Official data does not supply verified currency, fee-policy effective dates or charge observation times. Financial execution requires those facts.',
                   'executed':False,'data_status':'missing_financial_authorization_evidence'})
    f = rows(f"""select return_id, restocking_fee from returns where style = {lit(c['style'])} and category = {lit(c['category'])}
                 and restocking_fee > 0 and return_date <= {dlit(_asof())}""")
    already_ids = set(int(i) for i in c.get("waived_return_ids") or [])
    already_waived = float(c.get("fees_waived_cad") or 0)
    f = [x for x in f if int(x["return_id"]) not in already_ids]
    if not f:
        return _j({"executed": False, "already_waived": True,
                   "message": f"All fee-charged returns for this case are already waived (CA${already_waived:.2f} so far). Nothing new to waive."})
    total = round(sum(x["restocking_fee"] for x in f), 2)
    detail = {"returns_refunded": len(f), "amount_cad": total, "return_ids": [x["return_id"] for x in f],
              "future_returns": "fee-free for this style and category while the case is open"}
    store.link_returns(case_id, [x["return_id"] for x in f])
    if already_waived + total <= FEE_AUTHORITY_CAD:
        a = store.log_action(case_id, 2, "Waive restocking fees", detail)
        store.update_case(case_id, fees_waived_cad=round(already_waived + total, 2),
                          waived_return_ids=sorted(already_ids | set(int(x["return_id"]) for x in f)))
        return _j({"executed": True, "within_authority": True, **detail, "action_id": a["action_id"]})
    r = store.request_approval(case_id, 2, "Waive restocking fees", detail, "Customer Care lead")
    return _j({"executed": False, "approval_requested": r["approval_id"], "approval_status": r['status'],
               "reason": f"CA${already_waived + total:.2f} (CA${already_waived:.2f} already waived + CA${total:.2f}) exceeds the agent's CA${FEE_AUTHORITY_CAD:.0f} authority", **detail})


@tool
def request_fit_guidance_update(case_id: str, proposed_text: str) -> str:
    """Tier 3: propose a product-page fit note (e.g. 'Runs small: we recommend half a size up'). Requires Merchandising approval."""
    c = store.get_case(case_id)
    if not c or not (c["category"].startswith("Fit") or c["category"] == "Expectation gap"):
        return _j({"refused": "Fit-guidance updates apply only to fit or expectation-gap cases."})
    if c.get("confidence") not in ("Medium", "High"):
        return _j({"refused": "Record findings with confidence Medium or High first."})
    r = store.request_approval(case_id, 3, "Update product-page fit guidance", {"proposed_text": proposed_text}, "Merchandising")
    return _j({"approval_requested": r["approval_id"], "approval_status": r['status'], "approver": "Merchandising"})


@tool
def request_stock_hold(case_id: str, scope: str) -> str:
    """Tier 4: request a hold on remaining stock of the style (DC and stores) pending quality inspection.
    Requires Quality and Merchandising approval and a Quality case with confidence High."""
    c = store.get_case(case_id)
    if not c or c.get("category") != "Quality" or c.get("confidence") != "High":
        return _j({"refused": "Stock holds require a Quality case with confidence High."})
    r = store.request_approval(case_id, 4, "Hold stock pending inspection", {"scope": scope}, "Quality & Merchandising")
    return _j({"approval_requested": r["approval_id"], "approval_status": r['status'], "approver": "Quality & Merchandising"})


@tool
def draft_supplier_claim(case_id: str, claim_text: str) -> str:
    """Tier 5: draft a supplier quality claim with the evidence. The agent only drafts; sending requires
    Quality & Sourcing approval and a Quality case with confidence High."""
    c = store.get_case(case_id)
    if not c or c.get("category") != "Quality" or c.get("confidence") != "High":
        return _j({"refused": "Supplier claims require a Quality case with confidence High."})
    r = store.request_approval(case_id, 5, "Send supplier quality claim", {"draft": claim_text}, "Quality & Sourcing")
    return _j({"approval_requested": r["approval_id"], "approval_status": r['status'], "approver": "Quality & Sourcing"})


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
    return _j({"approval_requested": r["approval_id"], "approval_status": r['status'], "approver": "Customer Care & Privacy"})


@tool
def schedule_verification(case_id: str, check_after_days: int = 21) -> str:
    """Schedule a follow-up check: after N days, re-run the screen; if the signal has not fallen back, reopen the case."""
    from .verification import schedule
    value = schedule(case_id, _asof(), check_after_days)
    return _j({"scheduled": True, "trigger": "UI or CLI date-driven check", **value})


@tool
def verify_case(case_id: str) -> str:
    """Re-run the statistical screen for the case's style and category as of today and compare it with the
    moment the case was opened."""
    c = store.get_case(case_id)
    if not c:
        return _j({"error": "unknown case"})
    return _j({"opened": screen(c["style"], c["category"], c["opened_as_of"]),
               "now": screen(c["style"], c["category"], _asof())})


TRIAGE_TOOLS = [get_return, screen_style, find_open_case]
INVESTIGATOR_TOOLS = [style_reason_mix, weekly_timeline, spread_analysis, sample_returns, sku_return_rate,
                      fee_audit, exchange_evidence, transaction_context, read_playbook]
RESPONSE_TOOLS = [read_playbook, read_case, open_case, record_findings, notify_owner_team, waive_restocking_fees,
                  request_fit_guidance_update, request_stock_hold, draft_supplier_claim, request_proactive_outreach,
                  schedule_verification]
