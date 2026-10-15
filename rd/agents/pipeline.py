"""Run Triage, then Investigator and Response when investigation is needed."""
import json

from .. import tools, store
from .triage import create_triage_agent
from .investigator import create_investigator_agent
from .response import create_response_agent
from .shared import extract_json, invoke_agent


def run_pipeline(return_id, as_of, emit=print):
    """Run Triage, then (if needed) Investigator and Response, for one incoming return."""
    tools.AS_OF.set(str(as_of)[:10])
    emit({"agent": "System", "type": "stage", "text": f"New return #{return_id} received on {as_of}"})

    triage = create_triage_agent(emit)
    t_out = invoke_agent(triage, f"New return_id {return_id} was just created. Today's date is {as_of}. Triage it.",
                         "Triage Agent", emit)
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

    result = investigate_and_respond(t['style'], t['category'], as_of, emit, t.get('rationale', ''))
    case = store.find_open_case(t['style'], t['category'])
    if case:
        store.link_returns(case['case_id'], [return_id])
    return {"triage": t, **result}


def investigate_and_respond(style, category, as_of, emit, triage_note, *, case_id=None, context=None):
    """Reuse the same Investigator/Response roles for an initial or reopened case."""
    tools.AS_OF.set(str(as_of)[:10])
    emit({"agent": "System", "type": "stage", "text": "Investigating the signal and competing explanations"})
    inv = create_investigator_agent(emit)
    prompt = f"Today is {as_of}. Investigate style '{style}', category '{category}'. Triage note: {triage_note}"
    if context:
        prompt += ("\nPrevious case and newly observed evidence:\n" + json.dumps(context, default=str) +
                   "\nTest whether the previous explanation/action remains supported. Seek disconfirming evidence; "
                   "revise it when warranted, or explain why uncertainty remains. Do not invent missing facts.")
    i_out = invoke_agent(inv, prompt, "Investigator Agent", emit)
    finding = extract_json(i_out)
    if not finding.get('root_cause') or finding.get('confidence') not in ('Low', 'Medium', 'High'):
        raise ValueError('Investigation returned no valid finding; action stage was stopped.')
    if case_id:
        store.update_case(case_id, root_cause=finding['root_cause'], confidence=finding['confidence'],
                          owner_team=finding.get('owner_team'), hypotheses=finding.get('hypotheses', []))
    emit({"agent": "Investigator Agent", "type": "decision", "data": finding})

    emit({"agent": "System", "type": "stage", "text": "Acting on the findings within the playbook"})
    resp = create_response_agent(emit)
    prompt = (f"Today is {as_of}. Style '{style}', category '{category}'.\n"
              f"Investigation result JSON:\n{json.dumps(finding)}\n\nInvestigator narrative:\n{i_out}")
    if case_id:
        prompt += (f"\nReuse existing case {case_id}; read_case before acting. "
                   "Respect previous human rejections. Do not repeat recorded actions or approved/pending proposals. "
                   "Explain what changed and schedule another verification.\n" + json.dumps(context, default=str))
    r_out = invoke_agent(resp, prompt, "Response Agent", emit)
    emit({"agent": "Response Agent", "type": "briefing", "text": r_out})
    return {"finding": finding, "briefing": r_out}
