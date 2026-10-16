# Existing PK/SK DynamoDB table: Athena end-to-end demo

This mode uses the existing `return-detective-state` table in us-east-1 with String partition key `PK` and String sort key `SK`. No historical Parquet import or additional DynamoDB table is needed. The separate three-table CloudFormation mode remains supported when RD_STATE_TABLE is unset.

From the activated local environment, with working temporary AWS credentials:

```sh
export AWS_REGION=us-east-1
export AWS_DEFAULT_REGION=us-east-1
export RD_BACKEND=athena
export RD_DATASET_VERSION=2
export RD_S3_BUCKET=return-detective-20261015
export RD_ATHENA_DB=aldo_returns_v2
export RD_ATHENA_WORKGROUP=primary
export RD_ATHENA_OUTPUT=s3://return-detective-20261015/athena-results/
export RD_STORE_BACKEND=dynamodb
export RD_STATE_TABLE=return-detective-state
export RD_STORE_NAMESPACE=changsun-e2e-20261015
export RD_RUNTIME_DIR=runtime/athena-dynamodb

python scripts/check_storage.py
python run_demo.py quality --scripted --keep-cases
```

Storage check describes the table and checks S3, all nine Glue tables and an Athena count. It does not modify case data. Running the scenario writes cases, approvals and simulated actions. Expected: INVESTIGATE, a case, pending approval proposals. Repeating the same command should attach the return to the existing open case. Use --keep-cases so the CLI does not reset the namespace first.

In DynamoDB Explore items, Query `PK = RUN#changsun-e2e-20261015`. Sort keys begin with CASE#, ACTION# or APPROVAL#. Payloads retain the existing case_id/action_id/approval_id fields. PK partitions isolate runs. Use a new namespace for an independent replay; use the same namespace after restarting to keep the case history. Never mix reverse historical dates in the same namespace.

```sh
python -c "from rd import store; d=store.snapshot(); print('cases:', len(d['cases']), 'actions:', len(d['actions']), 'approvals:', len(d['approvals']))"
python -m streamlit run app.py
```

Select Scripted (no LLM) for the first UI check. DynamoDB runs preserve existing cases; saved trace replay displays events without restoring an old snapshot into DynamoDB. The explicit Reset case store button still deletes records in the selected namespace only. Other namespaces remain intact. For live agents configure an authorized RD_MODEL_ID and AWS Bedrock permissions, then select Live (Bedrock).

Required table permissions: DescribeTable, Query, BatchWriteItem. Existing three-table mode also uses these operations. S3/Glue/Athena/Bedrock permissions remain separate. AccessDenied requires the corresponding role permission; do not switch silently to local JSON.

Limits: this adapter retains a single-process read/modify/write demo API. Batch writes across types are not atomic; simultaneous writers in one namespace can lose updates. Run one application process per namespace and run historical dates serially. No production retail execution or authenticated approval identity is supplied by persistence. Cases/history must remain under DynamoDB's per-item size limit. This release is tested with isolated fake storage; actual AWS write/read acceptance is completed by the commands above in the user's credentialed terminal.
