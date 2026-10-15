"""Local prototype case store. Action records simulate retail operations."""
import datetime
import hashlib
import json
import os
import threading
import uuid
from .config import ROOT

RUNTIME_DIR = os.getenv("RD_RUNTIME_DIR", str(ROOT / "runtime"))
_lock = threading.RLock()

def _now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")

def _path():
    return os.path.join(RUNTIME_DIR, "cases.json")

def _load():
    if not os.path.isfile(_path()):
        return {"cases": {}, "actions": [], "approvals": []}
    with open(_path(), encoding="utf-8") as source:
        return json.load(source)

def _save(db):
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    temporary = _path() + ".tmp"
    with open(temporary, "w", encoding="utf-8") as target:
        json.dump(db, target, indent=2, default=str, ensure_ascii=False)
    os.replace(temporary, _path())

def reset():
    with _lock:
        _save({"cases": {}, "actions": [], "approvals": []})

def snapshot():
    with _lock:
        return _load()

def get_case(case_id):
    return snapshot()["cases"].get(case_id)

def find_open_case(style, category, as_of=None):
    return next((case for case in snapshot()["cases"].values()
        if case["style"] == style and case["category"] == category and case["status"] != "CLOSED"
        and (as_of is None or case["opened_as_of"] <= str(as_of)[:10])), None)

def open_case(style, category, opened_as_of, summary, evidence):
    with _lock:
        existing = find_open_case(style, category, opened_as_of)
        if existing:
            return existing
        db = _load()
        case_id = "CASE-" + uuid.uuid4().hex[:8].upper()
        case = {"case_id": case_id, "style": style, "category": category, "status": "OPEN",
            "opened_as_of": str(opened_as_of)[:10], "summary": summary, "evidence": evidence,
            "hypotheses": [], "root_cause": None, "confidence": None, "owner_team": None,
            "linked_return_ids": [], "history": [{"at": _now(), "event": "Case opened"}]}
        db["cases"][case_id] = case
        _save(db)
        return case

def update_case(case_id, **fields):
    with _lock:
        db = _load()
        case = db["cases"].get(case_id)
        if case is None:
            return None
        case.update({key: value for key, value in fields.items() if value is not None})
        case["history"].append({"at": _now(), "event": "Updated: " + ", ".join(fields)})
        _save(db)
        return case

def link_returns(case_id, return_ids):
    with _lock:
        case = get_case(case_id)
        if not case:
            return None
        ids = sorted(set(case["linked_return_ids"]) | {int(value) for value in return_ids})
        return update_case(case_id, linked_return_ids=ids)

def _key(case_id, action, detail):
    raw = json.dumps([case_id, action, detail], sort_keys=True, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()

def log_action(case_id, tier, action, detail, executed_by="agent", idempotency_key=None):
    with _lock:
        db = _load()
        if case_id not in db["cases"]:
            raise ValueError("Unknown case")
        key = idempotency_key or _key(case_id, action, detail)
        existing = next((item for item in db["actions"] if item.get("idempotency_key") == key), None)
        if existing:
            return existing
        record = {"action_id": "ACT-" + uuid.uuid4().hex[:8].upper(), "case_id": case_id, "tier": tier,
            "action": action, "detail": detail, "executed_by": executed_by, "at": _now(),
            "status": "SIMULATED", "executed": False, "idempotency_key": key}
        db["actions"].append(record)
        db["cases"][case_id]["history"].append({"at": record["at"], "event": "Simulation recorded: " + action})
        _save(db)
        return record

def request_approval(case_id, tier, action, detail, approver):
    with _lock:
        db = _load()
        if case_id not in db["cases"]:
            raise ValueError("Unknown case")
        key = _key(case_id, action, detail)
        existing = next((item for item in db["approvals"] if item.get("idempotency_key") == key), None)
        if existing:
            return existing
        record = {"approval_id": "APR-" + uuid.uuid4().hex[:8].upper(), "case_id": case_id, "tier": tier,
            "action": action, "detail": detail, "approver": approver, "status": "PENDING",
            "requested_at": _now(), "decided_at": None, "idempotency_key": key}
        db["approvals"].append(record)
        case = db["cases"][case_id]
        case["status"] = "AWAITING_APPROVAL"
        case["history"].append({"at": record["requested_at"], "event": "Approval requested: " + action})
        _save(db)
        return record

def decide_approval(approval_id, approve, decided_by="human reviewer"):
    if type(approve) is not bool or not decided_by.strip():
        raise ValueError("A boolean decision and reviewer name are required")
    with _lock:
        db = _load()
        record = next((item for item in db["approvals"] if item["approval_id"] == approval_id), None)
        if record is None or record["status"] != "PENDING":
            return record
        record.update(status="APPROVED" if approve else "REJECTED", decided_at=_now(), decided_by=decided_by)
        case = db["cases"][record["case_id"]]
        related = [item for item in db["approvals"] if item["case_id"] == record["case_id"]]
        case["status"] = ("AWAITING_APPROVAL" if any(item["status"] == "PENDING" for item in related)
            else "APPROVED" if any(item["status"] == "APPROVED" for item in related) else "REJECTED")
        case["history"].append({"at": record["decided_at"], "event": f"{record['status']} by {decided_by}: {record['action']}"})
        _save(db)
        if approve:
            log_action(record["case_id"], record["tier"], record["action"], record["detail"],
                executed_by="simulation after approval by " + decided_by, idempotency_key="approval:" + approval_id)
        return record
