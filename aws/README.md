# AWS integration status

For an existing single DynamoDB table with String keys PK/SK, set RD_STATE_TABLE
and follow [the single-table Athena walkthrough](../docs/DYNAMODB_SINGLE_TABLE.md).
The three-table mode remains available when RD_STATE_TABLE is unset.

Implemented adapters: Amazon Bedrock/Strands (`rd/agents/`), Athena over private S3/Glue tables (`rd/data.py`) and an optional three-table DynamoDB demo store (`rd/store.py`). Deployable storage template: `return-detective.yaml`. Synthetic upload/Glue registration: `scripts/setup_aws_data.py`. Configuration and connection checks: `docs/AWS_SETUP.md`, `scripts/check_storage.py`.

The complete official v2 dataset includes all six business sources. `scripts/export_aws_dataset.py` validates it, generates the nine-table Athena DDL and prints an S3 upload plan; `--execute` uploads only the cleaned release. `athena_v2.sql` is a schema template. Use `RD_DATASET_VERSION=2` and the [v2 guide](../docs/OFFICIAL_DATA_V2.md).

Still needed for production: transactional case updates, authenticated human reviewers, SNS approval notifications, idempotent retail action execution, and durable verification scheduling. The DynamoDB adapter persists demo records but is not safe for concurrent reviewers. No infrastructure has been provisioned in the current Workshop account. A JSON or DynamoDB action log is a simulation rather than proof of a refund, hold or notification.

Current data schemas are defined by the v2 manifest and Athena export script. Action authority and case state are defined by `rd/tools.py`, `rd/store.py` and the response playbook.
