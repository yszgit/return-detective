"""Command-line demo of Return Detective on real ALDO return data.

  python run_demo.py isolated     # Day 1: one 'Defective' return -> judged isolated
  python run_demo.py quality      # Glindafied: emerging quality defect -> case, actions, approvals
  python run_demo.py fit          # Wellsloafer_wm: runs big -> fit-guidance fix, not a quality case
  python run_demo.py --return-id 243470 --as-of 2024-11-23

Environment: RD_BACKEND=athena|duckdb (default athena), RD_MODEL_ID (Bedrock model or inference profile id),
AWS credentials for us-east-1.
"""
import argparse
import json
import textwrap

from rd import store
from rd.agents import run_pipeline

SCENARIOS = {
    "isolated": (212632, "2024-10-22"),   # first Glindafied 'Defective' return: not yet a pattern
    "quality": (243470, "2024-11-23"),    # Glindafied: 5 weeks of defects across 12+ locations
    "fit": (165717, "2024-09-01"),        # Sperry Wellsloafer_wm: 80% of returns say 'too big'
}

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
    elif t == "briefing":
        pass


def main():
    p = argparse.ArgumentParser()
    p.add_argument("scenario", nargs="?", choices=list(SCENARIOS))
    p.add_argument("--return-id", type=int)
    p.add_argument("--as-of")
    p.add_argument("--keep-cases", action="store_true", help="do not reset the case store first")
    a = p.parse_args()
    rid, as_of = (a.return_id, a.as_of) if a.return_id else SCENARIOS[a.scenario or "quality"]
    if not a.keep_cases:
        store.reset()
    run_pipeline(rid, as_of, emit)
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
