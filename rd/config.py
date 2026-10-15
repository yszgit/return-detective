"""Shared configuration for the UI, CLI and package."""
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env", override=False)

def backend():
    value = os.getenv("RD_BACKEND", "duckdb").lower()
    if value not in {"duckdb", "athena"}:
        raise ValueError("RD_BACKEND must be duckdb or athena")
    return value

def model_settings():
    region = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
    model = os.getenv("RD_MODEL_ID") or os.getenv("BEDROCK_MODEL_ID")
    if not region or not model:
        raise ValueError("Set AWS_REGION and RD_MODEL_ID locally; see docs/AWS_SETUP.md")
    return region, model
