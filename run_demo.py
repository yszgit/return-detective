"""Run from the repository root. --offline previews evidence without Bedrock."""
import argparse
import json
from rd import store
from rd.agents import preview_return, run_pipeline

SCENARIOS = {
    "isolated": (212632, "2024-10-22"),
    "quality": (243470, "2024-11-23"),
    "fit": (165717, "2024-09-01"),
}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", nargs="?", choices=list(SCENARIOS), default="quality")
    parser.add_argument("--return-id", type=int)
    parser.add_argument("--as-of")
    parser.add_argument("--offline", action="store_true", help="evidence preview only; no model or actions")
    parser.add_argument("--reset-cases", action="store_true", help="explicitly clear the local prototype store")
    args = parser.parse_args()
    if (args.return_id is None) != (args.as_of is None):
        parser.error("--return-id and --as-of must be supplied together")
    return_id, as_of = (args.return_id, args.as_of) if args.return_id is not None else SCENARIOS[args.scenario]
    if args.reset_cases:
        store.reset()
    try:
        result = preview_return(return_id, as_of) if args.offline else run_pipeline(return_id, as_of)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except Exception as error:
        print(f"Demo failed ({type(error).__name__}). Check configuration and docs/AWS_SETUP.md.")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
