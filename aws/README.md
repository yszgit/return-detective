# AWS integration status

Implemented adapters: Amazon Bedrock/Strands (`rd/agents/`) and Athena over private S3/Glue tables (`rd/data.py`). Configuration and connection checks: `docs/AWS_SETUP.md`, `scripts/check_aws.py`.

The complete official v2 dataset includes all six business sources. `scripts/export_aws_dataset.py` validates it, generates the nine-table Athena DDL and prints an S3 upload plan; `--execute` uploads only the cleaned release. `athena_v2.sql` is a schema template. Use `RD_DATASET_VERSION=2` and the [v2 guide](../docs/OFFICIAL_DATA_V2.md).

Still needed for production: DynamoDB case/action/approval persistence behind the `rd/store.py` API, authenticated human reviewers, SNS approval notifications, idempotent retail action execution, and durable verification scheduling. No infrastructure is provisioned by this branch. A JSON action log is a simulation rather than proof of a refund, hold or notification.

The earlier starter's proposed inventory/Lambda contract is preserved in `legacy/starter/aws/README.md`. Reconcile it with the current style/category case model before integration.
