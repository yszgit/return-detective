"""Run Triage, then Investigator and Response when investigation is needed."""
import json

from .. import tools, store
from .triage import create_triage_agent
from .investigator import create_investigator_agent
from .response import create_response_agent
from .shared import extract_json


def run_pipeline(return_id, as_of, emit=print):
    """Run Triage, then (if needed) Investigator and Response, for one incoming return."""
    tools.AS_OF.set(str(as_of)[:10])
    emit({"agent": "System", "type": "stage", "text": f"New return #{return_id} received on {as_of}"})

    triage = create_triage_agent(emit)
    t_out = str(triage(f"New return_id {return_id} was just created. Today's date is {as_of}. Triage it."))
    t = extract_json(t_out)
    if t.get("decision") == "ATTACH_TO_CASE":
        shown = dict(t)
        case = store.find_open_case(t.get("style"), t.get("category"))
        if case:
            store.link_returns(case["case_id"], [return_id])
            store.log_action(case["case_id"], 0, "Attach return to case",
                             {"return_id": int(return_id), "note": f"New return #{return_id} attached to open case on {as_of}"})
            shown.update(case_id=case["case_id"], attached_return_id=int(return_id),
                         rationale=f"{t.get('rationale', '')} Return #{return_id} attached to open case {case['case_id']}.".strip())
        emit({"agent": "Triage Agent", "type": "decision", "data": shown})
        return {"triage": t}
    emit({"agent": "Triage Agent", "type": "decision", "data": t})
    if t.get("decision") != "INVESTIGATE":
        return {"triage": t}

    emit({"agent": "System", "type": "stage", "text": "Signal confirmed: opening an investigation"})
    inv = create_investigator_agent(emit)
    i_out = str(inv(f"Today is {as_of}. Investigate style '{t['style']}', category '{t['category']}'. "
                    f"Triage note: {t.get('rationale', '')}"))
    finding = extract_json(i_out)
    emit({"agent": "Investigator Agent", "type": "decision", "data": finding})

    emit({"agent": "System", "type": "stage", "text": "Acting on the findings within the playbook"})
    resp = create_response_agent(emit)
    r_out = str(resp(f"Today is {as_of}. Style '{t['style']}', category '{t['category']}'.\n"
                     f"Investigation result JSON:\n{json.dumps(finding)}\n\nInvestigator narrative:\n{i_out}"))
    emit({"agent": "Response Agent", "type": "briefing", "text": r_out})
    return {"triage": t, "finding": finding, "briefing": r_out}
