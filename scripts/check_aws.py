"""Check local data (--data-only), or AWS identity, data and a small Bedrock call."""
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-only", action="store_true")
    args = parser.parse_args()
    try:
        from rd import data
        if not args.data_only:
            import boto3
            from rd.config import model_settings
            region, model_id = model_settings()
            session = boto3.Session(region_name=region)
            session.client("sts").get_caller_identity()
            print("AWS identity verified.")
        print("Data backend:", data.BACKEND)
        print("Observed return records:", data.one("select count(*) as n from returns")["n"])
        if not args.data_only:
            response = session.client("bedrock-runtime").converse(modelId=model_id,
                messages=[{"role": "user", "content": [{"text": "Reply with exactly: Bedrock OK"}]}],
                inferenceConfig={"maxTokens": 32})
            print("Bedrock response:", " ".join(block.get("text", "") for block in response["output"]["message"]["content"]))
        return 0
    except Exception as error:
        code = getattr(error, "response", {}).get("Error", {}).get("Code", type(error).__name__)
        print(f"Check failed ({code}). See docs/AWS_SETUP.md; do not share credentials.")
        return 1

if __name__ == "__main__":
    raise SystemExit(main())
