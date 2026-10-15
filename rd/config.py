"""Repository-relative settings shared by the CLI, UI and data tools."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env", override=False)


def local_path(name, default):
    value = Path(os.path.expandvars(os.environ.get(name) or str(default))).expanduser()
    return value if value.is_absolute() else ROOT / value


BACKEND = os.environ.get("RD_BACKEND", "duckdb").lower()
if BACKEND not in ("athena", "duckdb"):
    raise ValueError("RD_BACKEND must be 'athena' or 'duckdb'")
DATA_DIR = local_path("RD_DATA_DIR", ROOT / "data" / "synthetic")
RUNTIME_DIR = local_path("RD_RUNTIME_DIR", ROOT / "runtime")
BACKTEST_PATH = local_path("RD_BACKTEST_PATH", ROOT / "evaluation" / "results" / "cases_backtest.csv")


def is_synthetic():
    return BACKEND == "duckdb" and (DATA_DIR / "_SYNTHETIC.txt").exists()


def data_available():
    return BACKEND == "athena" or all(
        (DATA_DIR / f"{table}.parquet").is_file()
        for table in ("returns", "sku_sales", "exchanges", "baseline")
    )
