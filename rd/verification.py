"""Date-driven verification for the demo, using observed data and existing agents.

The UI/CLI invokes due checks; this module does not run a background scheduler.
Signal changes are observations, never proof that an intervention caused savings.
"""
import datetime as dt
import json

from . import store, tools
from .data import one


def schedule(case_id, as_of, days=21):
    days = int(days)
    if not 1 <= days <= 365:
        raise ValueError("Verification delay must be between 1 and 365 days.")
    case = store.get_case(case_id)
    if not case:
        raise ValueError("Unknown case.")
    current = case.get("verification") or {}
    if current.get("status") == "SCHEDULED":
        return current
    due = dt.date.fromisoformat(as_of) + dt.timedelta(days=days)
    value = {"status": "SCHEDULED", "scheduled_as_of": as_of,
             "due_on": due.isoformat(), "check_after_days": days}
    store.update_case(case_id, verification=value)
    store.log_action(case_id, 0, "Schedule verification", value)
    return value


def check_case(case_id, as_of, emit=lambda event: None, *, scripted=False, retry_review=False):
    """Check a due case, close a subsided signal or reopen and investigate again.

    Pending approvals, incomplete coverage and sparse observations cannot resolve
    a case. Repeated checks at the same date do not repeat model/action calls.
    """
    as_of = dt.date.fromisoformat(str(as_of)).isoformat()
    case = store.get_case(case_id)
    if not case:
        raise ValueError("Unknown case.")
    if case.get("status") == "CLOSED":
        return {"case_id": case_id, "outcome": "ALREADY_CLOSED"}
    checks = case.get("verification_checks") or []
    retry_review = bool(retry_review and checks and checks[-1]['as_of'] == as_of and
                        case.get('review_error_as_of') == as_of)
    if checks and as_of <= checks[-1]["as_of"]:
        if as_of == checks[-1]["as_of"]:
            if not (retry_review and case.get('review_error_as_of') == as_of):
                return checks[-1]
        else:
            raise ValueError("Verification cannot run before the previous check.")
    scheduled = case.get("verification") or {}
    due = scheduled.get("due_on")
    if not due:
        return {"case_id": case_id, "outcome": "NOT_SCHEDULED"}
    if as_of < due and not retry_review:
        return {"case_id": case_id, "outcome": "NOT_DUE", "due_on": due}
    db = store.snapshot()
    if any(a["case_id"] == case_id and a["status"] == "PENDING" for a in db["approvals"]):
        return {"case_id": case_id, "outcome": "WAITING_APPROVAL",
                "message": "Resolve pending approval requests before checking the action outcome."}
    # No new rows alone cannot establish that returns fell. Require a supplied
    # snapshot covering the requested date and at least five style observations.
    coverage = one("select max(return_date) as through_date from returns")
    through = str((coverage or {}).get("through_date") or "")[:10]
    if not through or as_of > through:
        return {"case_id": case_id, "outcome": "DATA_UNAVAILABLE", "data_through": through,
                "message": "The supplied snapshot does not cover this verification date."}
    tools.AS_OF.set(as_of)
    evidence = json.loads(tools.verify_case(case_id))
    current = evidence["now"]
    if current["style_returns"] < 5:
        return {"case_id": case_id, "outcome": "INSUFFICIENT_EVIDENCE", **evidence,
                "message": "At least five recent style returns are required; zero returns do not prove success."}
    mitigations = [a for a in db["actions"] if a["case_id"] == case_id and a["tier"] >= 2]
    outcome = "SIGNAL_SUBSIDED" if current["level"] == "NORMAL" else "REOPENED"
    if outcome == "SIGNAL_SUBSIDED" and not mitigations:
        return {"case_id": case_id, "outcome": "NO_RECORDED_INTERVENTION", **evidence,
                "message": "The signal subsided, but no mitigation was recorded. Do not claim an action worked."}
    result = {"case_id": case_id, "as_of": as_of, "outcome": outcome, **evidence,
              "previous_root_cause": case.get("root_cause"),
              "previous_confidence": case.get("confidence"),
              "previous_hypotheses": case.get("hypotheses", []),
              "causal_effect_established": False}
    if not checks or checks[-1]['as_of'] != as_of:
        checks.append(result)
    store.update_case(case_id, status="CLOSED" if outcome == "SIGNAL_SUBSIDED" else "REOPENED",
                      verification_checks=checks,
                      verification={**scheduled, "status": outcome, "checked_as_of": as_of})
    store.log_action(case_id, 0, "Verification result", result)
    emit({"agent": "System", "type": "verification", "data": result})
    if outcome == "SIGNAL_SUBSIDED":
        emit({"agent": "System", "type": "stage",
              "text": "Observed signal subsided; case closed. Causal savings have not been established."})
        return result
    emit({"agent": "System", "type": "stage",
          "text": "Signal persists: case reopened; reconsider the previous hypothesis and action."})
    try:
        if scripted:
            from .offline import investigate_scripted
            investigate_scripted(case["style"], case["category"], emit, case_id=case_id)
        else:
            from .agents.pipeline import investigate_and_respond
            context = {"verification": result, "prior_case": case,
                       "prior_actions": [a for a in db["actions"] if a["case_id"] == case_id],
                       "prior_approvals": [a for a in db["approvals"] if a["case_id"] == case_id]}
            investigate_and_respond(case["style"], case["category"], as_of, emit,
                                    "The signal persists in supplied historical observations. Recorded actions are "
                                    "simulations and do not alter those observations. Reassess alternatives without "
                                    "attributing change to an intervention.",
                                    case_id=case_id, context=context)
        latest = store.get_case(case_id)
        store.update_case(case_id, verification={**(latest.get("verification") or {}),
                                                 "review_completed_as_of": as_of}, review_error_as_of='')
    except Exception:
        # Keep the durable reopened state for a deliberate retry; do not mark a
        # failed model invocation as a completed investigation.
        store.update_case(case_id, status="REOPENED", review_error_as_of=as_of)
        raise
    return result
