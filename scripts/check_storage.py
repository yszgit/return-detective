"""Verify configured S3, Glue, Athena and DynamoDB resources.

Athena's SELECT query writes results to the configured private S3 output prefix
and may incur a small query charge. No case data is changed.
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from rd.config import BACKEND
from rd import data, store


def main():
    if BACKEND != "athena" or store.STORE_BACKEND != "dynamodb":
        raise SystemExit("Set RD_BACKEND=athena and RD_STORE_BACKEND=dynamodb first")
    bucket = os.environ.get("RD_S3_BUCKET")
    if not bucket or not data.ATHENA_OUTPUT.startswith(f"s3://{bucket}/"):
        raise SystemExit("Set RD_S3_BUCKET and its matching RD_ATHENA_OUTPUT")
    import boto3
    session = boto3.Session(region_name=data.REGION)
    account = session.client("sts").get_caller_identity()["Account"]
    session.client("s3").head_bucket(Bucket=bucket, ExpectedBucketOwner=account)
    glue = session.client("glue")
    for name in data.TABLES:
        glue.get_table(CatalogId=account, DatabaseName=data.ATHENA_DB, Name=name)
    dynamodb = session.client("dynamodb")
    for name in store._TABLES.values():
        table = dynamodb.describe_table(TableName=name)["Table"]
        if table["TableStatus"] != "ACTIVE":
            raise RuntimeError(f"DynamoDB table {name} is {table['TableStatus']}")
    count = data.one("select count(*) as n from returns")["n"]
    print(f"Connected: account {account}, region {data.REGION}, "
          f"S3/Glue/Athena {data.ATHENA_DB} ({count} returns), "
          f"three DynamoDB tables; namespace {store._NAMESPACE}")


if __name__ == "__main__":
    main()
