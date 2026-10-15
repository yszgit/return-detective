# AWS integration status

Implemented adapters: Amazon Bedrock/Strands (`rd/agents/`) and Athena over private S3/Glue tables (`rd/data.py`). Configuration and connection checks: `docs/AWS_SETUP.md`, `scripts/check_aws.py`.

Still needed for production: DynamoDB case/action/approval persistence behind the `rd/store.py` API, authenticated human reviewers, SNS approval notifications, idempotent retail action execution, and durable verification scheduling. No infrastructure is provisioned by this branch. A JSON action log is a simulation rather than proof of a refund, hold or notification.

The earlier starter's proposed inventory/Lambda contract is preserved in `legacy/starter/aws/README.md`. Reconcile it with the current style/category case model before integration.
