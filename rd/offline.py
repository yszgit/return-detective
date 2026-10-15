"""Scripted pipeline with no language model: calls the same tools in a fixed order and
writes templated notes. Used to test the UI without Bedrock and as a last-resort fallback.
The UI labels it clearly as 'scripted (no LLM)' - never present it as the agents' reasoning."""
import json

from . import tools


def _call(emit, agent, fn, **kw):
    emit({"agent": agent, "type": "tool_call", "tool": fn.tool_name, "input": kw})
    out = fn(**kw)
    emit({"agent": agent, "type": "tool_result", "tool": fn.tool_name, "status": "success", "output": out})
    return json.loads(out) if out.strip().startswith(("{", "[")) else out


def run_scripted(return_id, as_of, emit=print):
    tools.AS_OF.set(as_of)
    T, I, R = "Triage Agent", "Investigator Agent", "Response Agent"
    emit({"agent": "System", "type": "stage", "text": f"New return #{return_id} received on {as_of} (scripted, no LLM)"})
    ret = _call(emit, T, tools.get_return, return_id=return_id)
    if 'error' in ret or ret.get('eligible_for_detection') is False:
        t={'decision':'DATA_INSUFFICIENT','style':ret.get('style'),'category':ret.get('category'),
           'rationale':'The record is unavailable at this cutoff or fails the documented detection eligibility rules.'}
        emit({'agent':T,'type':'decision','data':t})
        return {'triage':t}
    scr = _call(emit, T, tools.screen_style, style=ret["style"])
    mine = next((s for s in scr if s["category"] == ret["category"]), None)
    sig = next((s for s in scr if s["level"] == "SIGNAL"), None)
    target = mine if mine and mine["level"] == "SIGNAL" else sig
    if not target:
        lvl = mine["level"] if mine else "NORMAL"
        t = {"decision": "WATCH" if lvl == "WATCH" else "ISOLATED", "style": ret["style"], "category": ret["category"],
             "rationale": f"{lvl}: {mine['category_returns'] if mine else 0} {ret['category']} returns in 28 days."}
        emit({"agent": T, "type": "decision", "data": t})
        return {"triage": t}
    existing = _call(emit, T, tools.find_open_case, style=ret["style"], category=target["category"])
    if existing.get('case_id'):
        tools.store.link_returns(existing['case_id'],[return_id])
        t={'decision':'ATTACH_TO_CASE','style':ret['style'],'category':target['category'],
           'case_id':existing['case_id'],'rationale':'Appended this return to the existing open case.'}
        emit({'agent':T,'type':'decision','data':t})
        return {'triage':t}
    t = {"decision": "INVESTIGATE", "style": ret["style"], "category": target["category"],
         "rationale": f"{target['category_returns']}/{target['style_returns']} returns ({target['category_share']:.0%}) vs "
                      f"{target['company_baseline_share']:.0%} baseline, z={target['z_score']}, {target['distinct_locations']} locations."}
    emit({"agent": T, "type": "decision", "data": t})

    emit({"agent": "System", "type": "stage", "text": "Signal confirmed: opening an investigation"})
    st, cat = t["style"], t["category"]
    _call(emit, I, tools.read_playbook)
    _call(emit, I, tools.style_reason_mix, style=st, days=90)
    tl = _call(emit, I, tools.weekly_timeline, style=st, category=cat, weeks=12)
    sp = _call(emit, I, tools.spread_analysis, style=st, category=cat, days=60)
    _call(emit, I, tools.sample_returns, style=st, category=cat, limit=8)
    fa = _call(emit, I, tools.fee_audit, style=st, category=cat)
    weeks = sum(1 for w in tl["weeks"] if w["category_returns"] > 0)
    widespread = sp["distinct_stores"] >= 5 and len(sp["by_channel"]) >= 2
    conf = "High" if widespread and weeks >= 3 else "Medium"
    cls = {"Quality": "Product quality defect", "Fit: too small": "Fit / sizing issue (runs small)",
           "Fit: too big": "Fit / sizing issue (runs big)"}.get(cat, cat)
    finding = {"root_cause_class": cls, "root_cause": f"{cls} on {st}", "confidence": conf,
               "owner_team": "Quality & Sourcing" if cat == "Quality" else "Merchandising",
               "hypotheses": [{"hypothesis": cls, "verdict": "supported", "evidence": f"{sp['total']} returns, {sp['distinct_stores']} stores, {weeks} active weeks"},
                              {"hypothesis": "Local store handling", "verdict": "ruled out" if sp["top_store_share"] < 0.5 else "inconclusive", "evidence": f"top store share {sp['top_store_share']}"}],
               "customers_charged_fees": fa.get("charged", 0)}
    emit({"agent": I, "type": "decision", "data": finding})

    emit({"agent": "System", "type": "stage", "text": "Acting on the findings within the playbook"})
    c = _call(emit, R, tools.open_case, style=st, category=cat, summary=finding["root_cause"], evidence=t["rationale"])
    cid = c["case_id"]
    _call(emit, R, tools.record_findings, case_id=cid, root_cause=finding["root_cause"], confidence=conf,
          owner_team=finding["owner_team"], hypotheses=finding["hypotheses"])
    _call(emit, R, tools.notify_owner_team, case_id=cid, team=finding["owner_team"], message=finding["root_cause"])
    if cat == "Quality":
        _call(emit, R, tools.waive_restocking_fees, case_id=cid)
        _call(emit, R, tools.request_stock_hold, case_id=cid, scope="All remaining stock in DCs and stores")
        _call(emit, R, tools.draft_supplier_claim, case_id=cid, claim_text=f"Quality claim for {st}: {t['rationale']}")
        _call(emit, R, tools.request_proactive_outreach, case_id=cid, offer="Free replacement or free return")
    elif cat.startswith("Fit"):
        txt = "Runs small: we recommend ordering half a size up." if "small" in cat else "Runs large: we recommend ordering half a size down."
        _call(emit, R, tools.request_fit_guidance_update, case_id=cid, proposed_text=txt)
    _call(emit, R, tools.schedule_verification, case_id=cid, check_after_days=21)
    emit({"agent": R, "type": "briefing", "text": f"Case {cid} opened for {st} ({cat}); see actions and approvals."})
    return {"triage": t, "finding": finding}
