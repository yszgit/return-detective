"""Validate the committed prepared snapshot without printing business records."""
import argparse
import hashlib
import json
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = {
    "returns": {"return_id", "banner", "order_number", "sku", "style", "return_order_number",
                "channel", "return_date", "status", "refund", "qty", "raw_reason", "store",
                "category", "restocking_fee", "final_sale", "aldo_fault"},
    "sku_sales": {"sku", "lines_sold", "final_sale_lines"},
    "exchanges": {"confidence", "exchange_date", "order_number", "exchange_sku", "qty", "store", "sales"},
    "baseline": {"category", "n", "share"},
}


def require(condition, message):
    if not condition:
        raise ValueError(message)


def main(data_dir):
    data_dir = data_dir.resolve()
    manifest = json.loads((data_dir / "manifest.json").read_text())
    require(set(manifest["tables"]) == set(EXPECTED), "Unexpected manifest tables")
    with duckdb.connect() as con:
        for name, expected_columns in EXPECTED.items():
            path = data_dir / f"{name}.parquet"
            meta = manifest["tables"][name]
            require(hashlib.sha256(path.read_bytes()).hexdigest() == meta["sha256"], f"{name}: checksum mismatch")
            safe_path = str(path).replace("'", "''")
            con.execute(f"create view {name} as select * from read_parquet('{safe_path}')")
            columns = [d[0] for d in con.execute(f"select * from {name} limit 0").description]
            require(set(columns) == expected_columns, f"{name}: unexpected columns")
            require(columns == meta["columns"], f"{name}: manifest schema mismatch")
            count = con.execute(f"select count(*) from {name}").fetchone()[0]
            require(count == meta["rows"], f"{name}: row count mismatch")
            print(f"{name}: {count:,} rows; schema and checksum OK")

        n, unique_ids = con.execute("select count(*), count(distinct return_id) from returns").fetchone()
        require(n == unique_ids, "Duplicate or missing return IDs")
        baseline_n, share = con.execute("select sum(n), sum(share) from baseline").fetchone()
        require(n == baseline_n and abs(share - 1) < 1e-8, "Baseline totals do not match returns")
        mismatches = con.execute("""
            select count(*) from (
                select category, count(*) n from returns group by category
            ) actual full outer join baseline b using(category)
            where actual.n is distinct from b.n
        """).fetchone()[0]
        require(mismatches == 0, "Category counts do not match baseline")

        for table, column, pattern in (
            ("returns", "order_number", "RD-ORDER-[0-9a-f]{32}"),
            ("exchanges", "order_number", "RD-ORDER-[0-9a-f]{32}"),
            ("returns", "return_order_number", "RD-RETURN-[0-9a-f]{32}"),
        ):
            invalid = con.execute(f"""select count(*) from {table}
                where {column} is not null and {column} <> ''
                and not regexp_full_match({column}, '{pattern}')""").fetchone()[0]
            require(invalid == 0, f"{table}.{column}: found non-tokenized IDs")
        lo, hi = con.execute("select min(return_date), max(return_date) from returns").fetchone()
        require(str(lo) == manifest["return_date_range"]["from"], "Start date mismatch")
        require(str(hi) == manifest["return_date_range"]["through"], "End date mismatch")
        print("PASS: category counts, unique return IDs, token formats and date range")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=ROOT / "data" / "cleaned")
    main(parser.parse_args().data_dir)
