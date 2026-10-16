"""Case files, action log and approval queue for the single-process demo.

RD_STORE_BACKEND=dynamodb persists records in separate tables, or in a PK/SK
table when RD_STATE_TABLE is set. Each namespace is an isolated demo run.
The read/modify/write API is still a demo API, not a concurrent transaction system.
"""
import json, os, threading, uuid, datetime
import time
from decimal import Decimal
from .config import RUNTIME_DIR

_PATH = os.path.join(RUNTIME_DIR, "cases.json")
_lock = threading.Lock()
STORE_BACKEND = os.environ.get("RD_STORE_BACKEND", "json").lower()
if STORE_BACKEND not in ("json", "dynamodb"):
    raise ValueError("RD_STORE_BACKEND must be 'json' or 'dynamodb'")
_NAMESPACE = os.environ.get("RD_STORE_NAMESPACE", "").strip()
if STORE_BACKEND == "dynamodb" and not _NAMESPACE:
    raise ValueError("Set RD_STORE_NAMESPACE to a unique demo namespace before using DynamoDB")
_TABLES = {name: os.environ.get(f"RD_{name.upper()}_TABLE", f"rd_{name}")
           for name in ("cases", "actions", "approvals")}
_KEYS = {"cases": "case_id", "actions": "action_id", "approvals": "approval_id"}
STATE_TABLE = os.environ.get("RD_STATE_TABLE", "").strip()
_PREFIXES = {"cases": "CASE#", "actions": "ACTION#", "approvals": "APPROVAL#"}
_DDB = None


def _ddb():
    global _DDB
    if _DDB is None:
        import boto3
        _DDB = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION") or
                              os.environ.get("AWS_DEFAULT_REGION") or "us-east-1")
    return _DDB


def _plain(value):
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_plain(v) for v in value]
    return value


def _records(name):
    from boto3.dynamodb.conditions import Key
    table = _ddb().Table(STATE_TABLE or _TABLES[name])
    condition = (Key("PK").eq("RUN#" + _NAMESPACE) & Key("SK").begins_with(_PREFIXES[name])
                 if STATE_TABLE else Key("namespace").eq(_NAMESPACE))
    kwargs = {"KeyConditionExpression": condition,
              "ConsistentRead": True}
    items = []
    while True:
        page = table.query(**kwargs)
        items.extend(_plain({k: v for k, v in item.items() if k not in ("namespace", "PK", "SK")})
                     for item in page.get("Items", []))
        if "LastEvaluatedKey" not in page:
            return items
        kwargs["ExclusiveStartKey"] = page["LastEvaluatedKey"]


def _load():
    if STORE_BACKEND == "dynamodb":
        cases = _records("cases")
        return {"cases": {c["case_id"]: c for c in cases},
                "actions": _records("actions"), "approvals": _records("approvals")}
    if not os.path.exists(_PATH):
        return {"cases": {}, "actions": [], "approvals": []}
    with open(_PATH) as f:
        return json.load(f)


def _save(db):
    if STORE_BACKEND == "dynamodb":
        for name in _TABLES:
            table = _ddb().Table(STATE_TABLE or _TABLES[name])
            key = _KEYS[name]
            records = list(db["cases"].values()) if name == "cases" else db[name]
            current = {item[key] for item in _records(name)}
            wanted = {item[key] for item in records}
            with table.batch_writer() as batch:
                for item in records:
                    payload = json.loads(json.dumps(item, default=str, allow_nan=False),
                                         parse_float=Decimal)
                    identity = ({"PK": "RUN#" + _NAMESPACE, "SK": _PREFIXES[name] + item[key]}
                                if STATE_TABLE else {"namespace": _NAMESPACE})
                    batch.put_item(Item={**payload, **identity})
                for record_id in current - wanted:
                    identity = ({"PK": "RUN#" + _NAMESPACE, "SK": _PREFIXES[name] + record_id}
                                if STATE_TABLE else {"namespace": _NAMESPACE, key: record_id})
                    batch.delete_item(Key=identity)
        return
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    tmp = _PATH + ".tmp"
    with open(tmp, "w") as f:
        json.dump(db, f, indent=2, default=str)
    # Windows indexers/sync clients can briefly lock the destination after a write.
    # Keep the previous complete store if the lock persists; never truncate it.
    for attempt in range(6):
        try:
            os.replace(tmp, _PATH)
            break
        except PermissionError:
            if attempt == 5:
                raise
            time.sleep(0.05 * 2 ** attempt)


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
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


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
        for existing in db['actions']:
            if (existing['case_id'] == case_id and existing['tier'] == tier and
                    existing['action'] == action and existing['detail'] == detail):
                return existing
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
        for existing in db['approvals']:
            if (existing['case_id'] == case_id and existing['action'] == action and
                    existing['detail'] == detail and existing['approver'] == approver):
                # A rejected proposal stays rejected. A changed proposal needs
                # new evidence/detail and a new explicit human decision.
                return existing
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
                        mine = [x["status"] for x in db["approvals"] if x["case_id"] == r["case_id"]]
                        c["status"] = "ACTIONED" if "APPROVED" in mine else "DECLINED"
                if approve:
                    if c and r['action'] == 'Waive restocking fees':
                        c['fees_waived_cad'] = round(float(c.get('fees_waived_cad') or 0) +
                                                    float(r['detail']['amount_cad']), 2)
                        c['waived_return_ids'] = sorted(set(c.get('waived_return_ids') or []) |
                                                       set(r['detail'].get('return_ids') or []))
                    db["actions"].append({"action_id": "ACT-" + uuid.uuid4().hex[:6].upper(), "case_id": r["case_id"],
                                          "tier": r["tier"], "action": r["action"], "detail": r["detail"],
                                          "executed_by": f"agent after approval by {decided_by}", "at": r["decided_at"]})
                _save(db)
                return r
        return None
