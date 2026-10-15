"""Case files, action log and the human-approval queue (a JSON file, good enough for a demo).
In production this would be DynamoDB."""
import json, os, threading, uuid, datetime

RUNTIME_DIR = os.environ.get("RD_RUNTIME_DIR", os.path.join(os.path.dirname(__file__), "..", "runtime"))
_PATH = os.path.join(RUNTIME_DIR, "cases.json")
_lock = threading.Lock()


def _load():
    if not os.path.exists(_PATH):
        return {"cases": {}, "actions": [], "approvals": []}
    with open(_PATH) as f:
        return json.load(f)


def _save(db):
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    tmp = _PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(db, f, indent=2, default=str)
    os.replace(tmp, _PATH)


def reset():
    with _lock:
        _save({"cases": {}, "actions": [], "approvals": []})


def restore(db):
    with _lock:
        _save(db)


def snapshot():
    with _lock:
        return _load()


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


def get_case(case_id):
    return snapshot()["cases"].get(case_id)


def find_open_case(style, category):
    db = snapshot()
    for c in db["cases"].values():
        if c["style"] == style and c["category"] == category and c["status"] != "CLOSED":
            return c
    return None


def open_case(style, category, opened_as_of, summary, evidence):
    with _lock:
        db = _load()
        for c in db["cases"].values():
            if c["style"] == style and c["category"] == category and c["status"] != "CLOSED":
                return c
        cid = "CASE-" + uuid.uuid4().hex[:6].upper()
        c = {"case_id": cid, "style": style, "category": category, "status": "OPEN", "opened_as_of": opened_as_of,
             "summary": summary, "evidence": evidence, "hypotheses": [], "root_cause": None, "confidence": None,
             "owner_team": None, "linked_return_ids": [], "history": [{"at": _now(), "event": "Case opened"}]}
        db["cases"][cid] = c
        _save(db)
        return c


def update_case(case_id, **fields):
    with _lock:
        db = _load()
        c = db["cases"].get(case_id)
        if not c:
            return None
        for k, v in fields.items():
            if v is not None:
                c[k] = v
        c["history"].append({"at": _now(), "event": "Updated: " + ", ".join(k for k, v in fields.items() if v is not None)})
        _save(db)
        return c


def link_returns(case_id, return_ids):
    with _lock:
        db = _load()
        c = db["cases"].get(case_id)
        if not c:
            return None
        s = set(c["linked_return_ids"]) | set(int(r) for r in return_ids)
        c["linked_return_ids"] = sorted(s)
        _save(db)
        return c


def log_action(case_id, tier, action, detail, executed_by="agent"):
    with _lock:
        db = _load()
        a = {"action_id": "ACT-" + uuid.uuid4().hex[:6].upper(), "case_id": case_id, "tier": tier, "action": action,
             "detail": detail, "executed_by": executed_by, "at": _now()}
        db["actions"].append(a)
        if case_id in db["cases"]:
            db["cases"][case_id]["history"].append({"at": a["at"], "event": f"Action T{tier}: {action}"})
        _save(db)
        return a


def request_approval(case_id, tier, action, detail, approver):
    with _lock:
        db = _load()
        r = {"approval_id": "APR-" + uuid.uuid4().hex[:6].upper(), "case_id": case_id, "tier": tier, "action": action,
             "detail": detail, "approver": approver, "status": "PENDING", "requested_at": _now(), "decided_at": None}
        db["approvals"].append(r)
        if case_id in db["cases"]:
            db["cases"][case_id]["status"] = "AWAITING_APPROVAL"
            db["cases"][case_id]["history"].append({"at": r["requested_at"], "event": f"Approval requested from {approver}: {action}"})
        _save(db)
        return r


def decide_approval(approval_id, approve, decided_by="human reviewer"):
    with _lock:
        db = _load()
        for r in db["approvals"]:
            if r["approval_id"] == approval_id and r["status"] == "PENDING":
                r["status"] = "APPROVED" if approve else "REJECTED"
                r["decided_at"] = _now()
                c = db["cases"].get(r["case_id"])
                if c:
                    c["history"].append({"at": r["decided_at"], "event": f"{r['status']} by {decided_by}: {r['action']}"})
                    if not any(x["status"] == "PENDING" for x in db["approvals"] if x["case_id"] == r["case_id"]):
                        c["status"] = "ACTIONED"
                if approve:
                    db["actions"].append({"action_id": "ACT-" + uuid.uuid4().hex[:6].upper(), "case_id": r["case_id"],
                                          "tier": r["tier"], "action": r["action"], "detail": r["detail"],
                                          "executed_by": f"agent after approval by {decided_by}", "at": r["decided_at"]})
                _save(db)
                return r
        return None
