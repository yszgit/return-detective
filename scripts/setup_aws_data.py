"""Upload an explicitly selected four-table snapshot and register its Parquet schemas in Glue.

This script never creates the bucket or DynamoDB tables; deploy aws/return-detective.yaml
first. Dry run is the default. Only synthetic data is accepted without --allow-private.
"""
import argparse
import re
from pathlib import Path

TABLES = ("returns", "sku_sales", "exchanges", "baseline")
ROOT = Path(__file__).resolve().parent.parent


def glue_type(duck_type):
    typ = duck_type.upper()
    base = {"VARCHAR": "string", "TEXT": "string", "BIGINT": "bigint",
            "INTEGER": "int", "SMALLINT": "smallint", "DOUBLE": "double",
            "FLOAT": "float", "BOOLEAN": "boolean", "DATE": "date",
            "TIMESTAMP": "timestamp"}
    if typ in base:
        return base[typ]
    if re.fullmatch(r"DECIMAL\(\d+,\d+\)", typ):
        return typ.lower()
    raise ValueError(f"Unsupported Parquet column type: {duck_type}")


def schema(path):
    import duckdb
    with duckdb.connect() as con:
        result = con.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(path)])
        return [{"Name": row[0], "Type": glue_type(row[1])} for row in result.fetchall()]


def table_input(name, columns, location):
    return {
        "Name": name,
        "TableType": "EXTERNAL_TABLE",
        "Parameters": {"classification": "parquet", "EXTERNAL": "TRUE"},
        "StorageDescriptor": {
            "Columns": columns,
            "Location": location,
            "InputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetInputFormat",
            "OutputFormat": "org.apache.hadoop.hive.ql.io.parquet.MapredParquetOutputFormat",
            "SerdeInfo": {"SerializationLibrary":
                          "org.apache.hadoop.hive.ql.io.parquet.serde.ParquetHiveSerDe"},
        },
    }


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--bucket", required=True, help="existing private bucket from the stack output")
    p.add_argument("--database", default="aldo_returns")
    p.add_argument("--dataset", default="demo", help="S3 prefix under datasets/; choose a fresh name")
    p.add_argument("--data-dir", type=Path, default=ROOT / "data" / "synthetic")
    p.add_argument("--allow-private", action="store_true",
                   help="explicitly authorize uploading the selected non-synthetic data directory")
    p.add_argument("--apply", action="store_true", help="write S3 objects and Glue tables")
    a = p.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", a.bucket):
        p.error("bucket must be a valid S3 bucket name, not an s3:// URL")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", a.database):
        p.error("database must contain lowercase letters, digits and underscores")
    if not re.fullmatch(r"[a-z0-9][a-z0-9_-]*", a.dataset):
        p.error("dataset must contain lowercase letters, digits, underscores or hyphens")
    files = {name: a.data_dir / f"{name}.parquet" for name in TABLES}
    missing = [name for name, path in files.items() if not path.is_file()]
    if missing:
        p.error(f"missing Parquet tables: {', '.join(missing)}")
    synthetic = (a.data_dir / "_SYNTHETIC.txt").is_file()
    if not synthetic and not a.allow_private:
        p.error("non-synthetic data requires --allow-private after confirming the AWS account and data permissions")

    plans = {}
    for name, path in files.items():
        location = f"s3://{a.bucket}/datasets/{a.dataset}/{name}/"
        plans[name] = (path, f"datasets/{a.dataset}/{name}/part-00000.parquet",
                       table_input(name, schema(path), location))
        print(f"{name}: {path.name}, {path.stat().st_size} bytes, "
              f"{len(plans[name][2]['StorageDescriptor']['Columns'])} columns -> {location}")
    if not a.apply:
        print("Dry run only. Use --apply after the CloudFormation stack exists.")
        return

    import boto3
    session = boto3.Session()
    sts, s3, glue = (session.client(name) for name in ("sts", "s3", "glue"))
    account = sts.get_caller_identity()["Account"]
    s3.head_bucket(Bucket=a.bucket, ExpectedBucketOwner=account)
    glue.get_database(CatalogId=account, Name=a.database)
    print(f"Uploading to account {account}, region {session.region_name}; synthetic={synthetic}")
    for name, (path, key, table) in plans.items():
        try:
            existing = glue.get_table(CatalogId=account, DatabaseName=a.database, Name=name)["Table"]
        except glue.exceptions.EntityNotFoundException:
            existing = None
        if existing:
            old = existing["StorageDescriptor"]
            new = table["StorageDescriptor"]
            if old.get("Location") != new["Location"] or old.get("Columns") != new["Columns"]:
                raise RuntimeError(f"Glue table {name} already exists with different location/schema")
        with path.open("rb") as body:
            s3.put_object(Bucket=a.bucket, Key=key, Body=body,
                          ServerSideEncryption="AES256", ExpectedBucketOwner=account)
        if not existing:
            glue.create_table(CatalogId=account, DatabaseName=a.database, TableInput=table)
        print(f"Ready: {a.database}.{name}")


if __name__ == "__main__":
    main()
