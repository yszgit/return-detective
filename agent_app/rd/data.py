"""Data access layer.

Two interchangeable backends, chosen with the RD_BACKEND environment variable:
  * athena  (default on AWS) - queries the Glue/Athena tables in database `aldo_returns`
  * duckdb  (local fallback) - queries the Parquet files in ./data

All SQL in the tools is written to run unchanged on both engines (Trino and DuckDB):
date bounds are computed in Python and passed as DATE literals, and every value is
inlined through `lit()`, which escapes quotes.
"""
import datetime as dt
import os
import threading
import time

BACKEND = os.environ.get("RD_BACKEND", "athena").lower()
ATHENA_DB = os.environ.get("RD_ATHENA_DB", "aldo_returns")
ATHENA_OUTPUT = os.environ.get("RD_ATHENA_OUTPUT", "s3://aldo-return-detective-9969/athena-results/")
ATHENA_WORKGROUP = os.environ.get("RD_ATHENA_WORKGROUP", "primary")
REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "us-east-1"))
DATA_DIR = os.environ.get("RD_DATA_DIR", os.path.join(os.path.dirname(__file__), "..", "data"))

TABLES = ("returns", "sku_sales", "exchanges", "baseline")
_local = threading.local()
_cache = {}


def lit(v):
    """Render a Python value as a safe SQL literal."""
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, (int, float)):
        return repr(v)
    if isinstance(v, (dt.date, dt.datetime)):
        return f"DATE '{v.isoformat()[:10]}'"
    return "'" + str(v).replace("'", "''") + "'"


def dlit(d):
    """Date literal from 'YYYY-MM-DD' or a date."""
    if isinstance(d, str):
        d = dt.date.fromisoformat(d[:10])
    return f"DATE '{d.isoformat()}'"


def days_before(d, n):
    if isinstance(d, str):
        d = dt.date.fromisoformat(d[:10])
    return d - dt.timedelta(days=int(n))


def _clean(v):
    if hasattr(v, "isoformat"):
        return v.isoformat()
    if isinstance(v, float):
        return round(v, 4)
    if hasattr(v, "item"):  # numpy scalars
        return _clean(v.item())
    return v


# ------------------------------------------------------------------ DuckDB
def _duck():
    c = getattr(_local, "duck", None)
    if c is None:
        import duckdb
        c = duckdb.connect()
        for t in TABLES:
            p = os.path.join(DATA_DIR, f"{t}.parquet").replace("'", "''")
            c.execute(f"create view {t} as select * from read_parquet('{p}')")
        _local.duck = c
    return c


def _rows_duck(sql):
    cur = _duck().execute(sql)
    cols = [d[0] for d in cur.description]
    return [{k: _clean(v) for k, v in zip(cols, r)} for r in cur.fetchall()]


# ------------------------------------------------------------------ Athena
def _athena():
    c = getattr(_local, "athena", None)
    if c is None:
        import boto3
        c = boto3.client("athena", region_name=REGION)
        _local.athena = c
    return c


def _convert(value, typ):
    if value is None:
        return None
    if typ in ("integer", "bigint", "smallint", "tinyint"):
        return int(value)
    if typ in ("double", "float", "real", "decimal"):
        return round(float(value), 4)
    if typ == "boolean":
        return value.lower() == "true"
    return value


def _rows_athena(sql):
    cli = _athena()
    qid = cli.start_query_execution(
        QueryString=sql,
        QueryExecutionContext={"Database": ATHENA_DB},
        ResultConfiguration={"OutputLocation": ATHENA_OUTPUT},
        WorkGroup=ATHENA_WORKGROUP,
    )["QueryExecutionId"]
    delay = 0.2
    while True:
        st = cli.get_query_execution(QueryExecutionId=qid)["QueryExecution"]["Status"]
        if st["State"] in ("SUCCEEDED", "FAILED", "CANCELLED"):
            break
        time.sleep(delay)
        delay = min(delay * 1.5, 1.0)
    if st["State"] != "SUCCEEDED":
        raise RuntimeError(f"Athena query {st['State']}: {st.get('StateChangeReason')}\n{sql}")
    out, cols, types, token, first = [], None, None, None, True
    while True:
        kw = {"QueryExecutionId": qid, "MaxResults": 1000}
        if token:
            kw["NextToken"] = token
        page = cli.get_query_results(**kw)
        if cols is None:
            meta = page["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]
            cols = [m["Name"] for m in meta]
            types = [m["Type"] for m in meta]
        data = page["ResultSet"]["Rows"]
        if first:
            data = data[1:]  # header row
            first = False
        for r in data:
            vals = [c.get("VarCharValue") for c in r["Data"]]
            out.append({k: _convert(v, t) for k, v, t in zip(cols, vals, types)})
        token = page.get("NextToken")
        if not token:
            return out


# ------------------------------------------------------------------ public
def rows(sql):
    if sql in _cache:
        return _cache[sql]
    r = _rows_athena(sql) if BACKEND == "athena" else _rows_duck(sql)
    _cache[sql] = r
    return r


def one(sql):
    r = rows(sql)
    return r[0] if r else None


def baseline_share(category):
    r = one(f"select share from baseline where category = {lit(category)}")
    return r["share"] if r else 0.0
