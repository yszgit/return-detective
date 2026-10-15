"""Data access layer: DuckDB over the Parquet files produced by scripts/prepare_data.py.

Every query takes an `as_of` date so the agents only ever see returns that existed
at that moment. This keeps the replay demo honest: no peeking into the future.
"""
import os, threading
import duckdb

DATA_DIR = os.environ.get("RD_DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))
_local = threading.local()


def con():
    c = getattr(_local, "con", None)
    if c is None:
        c = duckdb.connect()
        p = lambda f: os.path.join(DATA_DIR, f).replace("'", "''")
        c.execute(f"create view returns as select * from read_parquet('{p('returns.parquet')}')")
        c.execute(f"create view sku_sales as select * from read_parquet('{p('sku_sales.parquet')}')")
        c.execute(f"create view exchanges as select * from read_parquet('{p('exchanges.parquet')}')")
        c.execute(f"create view baseline as select * from read_parquet('{p('baseline.parquet')}')")
        _local.con = c
    return c


def rows(sql, params=None):
    cur = con().execute(sql, params or [])
    cols = [d[0] for d in cur.description]
    out = []
    for r in cur.fetchall():
        d = {}
        for k, v in zip(cols, r):
            if hasattr(v, "isoformat"):
                v = v.isoformat()
            elif isinstance(v, float):
                v = round(v, 4)
            d[k] = v
        out.append(d)
    return out


def one(sql, params=None):
    r = rows(sql, params)
    return r[0] if r else None


def baseline_share(category):
    r = one("select share from baseline where category = ?", [category])
    return r["share"] if r else 0.0
