"""Shared DuckDB / Athena access. Historical evidence takes an explicit as-of date."""
import datetime as dt
import math
import os
import threading
import time
from .config import ROOT, backend

BACKEND = backend()
DATA_DIR = os.getenv("RD_DATA_DIR", str(ROOT / "data"))
ATHENA_DB = os.getenv("RD_ATHENA_DB", "aldo_returns")
ATHENA_OUTPUT = os.getenv("RD_ATHENA_OUTPUT", "")
ATHENA_WORKGROUP = os.getenv("RD_ATHENA_WORKGROUP", "primary")
REGION = os.getenv("AWS_REGION") or os.getenv("AWS_DEFAULT_REGION")
TABLES = ("returns", "sku_sales", "exchanges", "baseline")
_local = threading.local()

def lit(value):
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        return "TRUE" if value else "FALSE"
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("SQL numeric values must be finite")
        return repr(value)
    if isinstance(value, (dt.date, dt.datetime)):
        return dlit(value)
    return "'" + str(value).replace("'", "''") + "'"

def dlit(value):
    day = dt.date.fromisoformat(str(value)[:10])
    return f"DATE '{day.isoformat()}'"

def days_before(value, days):
    return dt.date.fromisoformat(str(value)[:10]) - dt.timedelta(days=int(days))

def _clean(value):
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return round(value, 6) if isinstance(value, float) else value

def _duck():
    if getattr(_local, "duck_dir", None) != DATA_DIR:
        old = getattr(_local, "duck", None)
        if old is not None:
            old.close()
        import duckdb
        connection = duckdb.connect()
        for table in TABLES:
            path = os.path.join(DATA_DIR, table + ".parquet")
            if not os.path.isfile(path):
                connection.close()
                raise FileNotFoundError(f"Missing {table}.parquet. Configure RD_DATA_DIR; see data/README.md.")
            connection.execute(f"create view {table} as select * from read_parquet({lit(path)})")
        _local.duck, _local.duck_dir = connection, DATA_DIR
    return _local.duck

def _athena():
    if not REGION:
        raise ValueError("Set AWS_REGION for Athena")
    if not getattr(_local, "athena", None):
        import boto3
        from botocore.config import Config
        _local.athena = boto3.client("athena", region_name=REGION,
            config=Config(connect_timeout=5, read_timeout=30, retries={"max_attempts": 2}))
    return _local.athena

def _convert(value, typ):
    if value is None:
        return None
    if typ in {"integer", "bigint", "smallint", "tinyint"}:
        return int(value)
    if typ in {"double", "float", "real"} or typ.startswith("decimal"):
        return round(float(value), 6)
    if typ == "boolean":
        return value.lower() == "true"
    return value

def _rows_athena(sql, timeout=120):
    client = _athena()
    arguments = {"QueryString": sql, "QueryExecutionContext": {"Database": ATHENA_DB}, "WorkGroup": ATHENA_WORKGROUP}
    if ATHENA_OUTPUT:
        arguments["ResultConfiguration"] = {"OutputLocation": ATHENA_OUTPUT}
    query_id = client.start_query_execution(**arguments)["QueryExecutionId"]
    deadline = time.monotonic() + timeout
    while True:
        status = client.get_query_execution(QueryExecutionId=query_id)["QueryExecution"]["Status"]
        state = status["State"]
        if state in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            break
        if time.monotonic() >= deadline:
            client.stop_query_execution(QueryExecutionId=query_id)
            raise TimeoutError("Athena query timed out; cancellation was requested")
        time.sleep(0.5)
    if state != "SUCCEEDED":
        raise RuntimeError(f"Athena query {state}; inspect query {query_id} in the AWS console")
    output, columns, types, token, first = [], None, None, None, True
    while True:
        args = {"QueryExecutionId": query_id, "MaxResults": 1000}
        if token:
            args["NextToken"] = token
        page = client.get_query_results(**args)
        if columns is None:
            metadata = page["ResultSet"]["ResultSetMetadata"]["ColumnInfo"]
            columns = [column["Name"] for column in metadata]
            types = [column["Type"] for column in metadata]
        records = page["ResultSet"]["Rows"]
        if first:
            records, first = records[1:], False
        for record in records:
            values = [cell.get("VarCharValue") for cell in record["Data"]]
            values += [None] * (len(columns) - len(values))
            output.append({key: _convert(value, typ) for key, value, typ in zip(columns, values, types)})
        token = page.get("NextToken")
        if not token:
            return output

def rows(sql):
    # No indefinite cache of mutable cloud evidence across investigations.
    if BACKEND == "athena":
        return _rows_athena(sql)
    cursor = _duck().execute(sql)
    columns = [column[0] for column in cursor.description]
    return [{key: _clean(value) for key, value in zip(columns, record)} for record in cursor.fetchall()]

def one(sql):
    result = rows(sql)
    return result[0] if result else None

def baseline_share(category, as_of):
    result = one(f"""select
        sum(case when category = {lit(category)} then 1 else 0 end) * 1.0 / nullif(count(*), 0) as share
        from returns where return_date <= {dlit(as_of)}""")
    return float(result["share"] or 0.0)
