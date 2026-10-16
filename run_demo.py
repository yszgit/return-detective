"""Command-line demo of Return Detective on synthetic or authorized ALDO data.

  python run_demo.py isolated     # Day 1: one 'Defective' return -> judged isolated
  python run_demo.py quality      # Glindafied: emerging quality defect -> case, actions, approvals
  python run_demo.py fit          # Wellsloafer_wm: runs big -> fit-guidance fix, not a quality case
  python run_demo.py --return-id 243470 --as-of 2024-11-23

  python run_demo.py syn_quality --scripted  # fully local, no AWS or model

Environment: RD_BACKEND=athena|duckdb (default duckdb), RD_MODEL_ID (Bedrock model or inference profile id),
AWS credentials for us-east-1.
"""
import argparse
import datetime as dt
import json
import os
import textwrap

from rd import store
from rd.config import data_available, is_synthetic
from rd.scenarios import SCENARIOS

COLORS = {"Triage Agent": "\033[36m", "Investigator Agent": "\033[35m", "Response Agent": "\033[33m", "System": "\033[32m"}
RESET = "\033[0m"


def emit(e):
    c = COLORS.get(e["agent"], "")
    tag = f"{c}[{e['agent']}]{RESET}"
    t = e["type"]
    if t == "stage":
        print(f"\n{c}=== {e['text']} ==={RESET}")
    elif t == "thought":
        print(f"{tag} 💭 " + textwrap.fill(e["text"], 110, subsequent_indent="      "))
    elif t == "tool_call":
        print(f"{tag} 🔧 {e['tool']}({json.dumps(e['input'])[:160]})")
    elif t == "tool_result":
        print(f"{tag}    ↳ {e['output'][:220]}")
    elif t == "decision":
        print(f"{tag} ✅ {json.dumps(e['data'])[:600]}")
    elif t in ('verification', 'usage'):
        print(f"{tag} {t}: {json.dumps(e['data'])}")
    elif t == "briefing":
        pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument("scenario", nargs="?", choices=list(SCENARIOS))
    p.add_argument("--return-id", type=int)
    p.add_argument("--as-of")
    p.add_argument('--verify-case', help='check a previously scheduled case without resetting the store')
    p.add_argument('--retry-review', action='store_true', help='retry a failed follow-up at the same date')
    p.add_argument("--scripted", action="store_true", help="fixed tool sequence, no AWS/LLM with DuckDB data")
    p.add_argument("--keep-cases", action="store_true", help="do not reset the case store first")
    a = p.parse_args()
    if a.verify_case:
        if not a.as_of or a.return_id or a.scenario:
            p.error('--verify-case requires --as-of and cannot be combined with a return/scenario')
        if not a.scripted and not os.environ.get('RD_MODEL_ID'):
            p.error('set RD_MODEL_ID for follow-up agents, or choose --scripted')
        try:
            dt.date.fromisoformat(a.as_of)
        except ValueError:
            p.error('--as-of must be an ISO date (YYYY-MM-DD)')
        from rd.verification import check_case
        result = check_case(a.verify_case, a.as_of, emit, scripted=a.scripted, retry_review=a.retry_review)
        print(json.dumps(result, indent=2, default=str))
        return
    if bool(a.return_id) != bool(a.as_of):
        p.error("--return-id and --as-of must be supplied together")
    if a.scenario and a.return_id:
        p.error("choose a named scenario or --return-id/--as-of")
    if not data_available():
        p.error("local data is missing; run python scripts/generate_synthetic_data.py first")
    if a.return_id:
        rid, as_of = a.return_id, a.as_of
    else:
        scenario = SCENARIOS[a.scenario or ("syn_quality" if is_synthetic() else "quality")]
        if scenario["synthetic"] != is_synthetic():
            p.error("scenario and dataset do not match; set RD_BACKEND/RD_DATA_DIR for the chosen scenario")
        rid, as_of = scenario["return_id"], scenario["as_of"]
    try:
        dt.date.fromisoformat(as_of)
    except ValueError:
        p.error("--as-of must be an ISO date (YYYY-MM-DD)")
    if a.scripted:
        from rd.offline import run_scripted as run
    else:
        if not os.environ.get("RD_MODEL_ID"):
            p.error("set RD_MODEL_ID for Bedrock, or use --scripted for the local demo")
        from rd.agents import run_pipeline as run
    if not a.keep_cases:
        store.reset()
    run(rid, as_of, emit)
    db = store.snapshot()
    print("\n=== Case store ===")
    for c in db["cases"].values():
        print(f"{c['case_id']} | {c['style']} | {c['category']} | {c['status']} | confidence {c['confidence']} | {c['root_cause']}")
    for x in db["actions"]:
        print(f"  ACTION   T{x['tier']} {x['action']}")
    for x in db["approvals"]:
        print(f"  APPROVAL T{x['tier']} {x['action']} -> {x['approver']} [{x['status']}]")


if __name__ == "__main__":
    main()
