import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "sample"
SNAPSHOT_DATE = "2026-10-15"


def aws_settings():
    try:
        from dotenv import load_dotenv
        load_dotenv(ROOT / ".env", override=False)
    except ImportError:
        pass
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    model = os.getenv("BEDROCK_MODEL_ID")
    if not region or not model:
        raise ValueError("Set the competition region and BEDROCK_MODEL_ID first.")
    return region, model
