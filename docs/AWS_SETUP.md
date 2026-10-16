# AWS setup for the current agent app

The local scripted demo needs no AWS. To run live agents, install root `requirements.txt`, set the three temporary Workshop credentials in your own terminal, and choose the actual enabled region/model or inference-profile ID.

Credentials belong in your terminal/profile, not Git, `.env.example`, screenshots or documentation. Copy `.env.example` to `.env` for configuration if helpful; `rd/config.py` loads it without replacing terminal values.

## Bedrock with local synthetic data

```sh
export AWS_REGION=us-east-1
export RD_MODEL_ID='<enabled-model-or-inference-profile-id>'
export RD_BACKEND=duckdb
export RD_DATA_DIR=data/synthetic
python scripts/generate_synthetic_data.py
python run_demo.py syn_quality
```

Use the region actually assigned by the workshop. Optional `RD_FAST_MODEL_ID` changes Triage/Response to another enabled model; the Investigator keeps `RD_MODEL_ID`. Guardrails require `RD_GUARDRAIL_ID` and `RD_GUARDRAIL_VERSION`. `RD_TEMPERATURE` is only appropriate if your selected model supports it.

## Create S3, Glue, Athena and DynamoDB demo resources

The account needs valid Workshop credentials and permission for the resources used below. Reuse existing authorized team resources when available; deploying this template is optional. This repository contains a storage template, not an automatic deployment or a guarantee of account access.

1. In the AWS Console, select the Workshop region and open **CloudFormation → Create stack → Upload a template file**. Upload [`aws/return-detective.yaml`](../aws/return-detective.yaml). Use a short stack name such as `return-detective-demo`, a globally unique private bucket name and the default `aldo_returns` Glue database. Wait for `CREATE_COMPLETE`; copy the six stack outputs.
2. Generate the synthetic fixtures with `python scripts/generate_synthetic_data.py`. Review the proposed upload with `python scripts/setup_aws_data.py --bucket <bucket-from-output>`. After checking the target account and bucket, run the same command with `--apply`. It uploads only the four synthetic Parquet tables and registers them in Glue. A non-synthetic directory requires both `--data-dir` and `--allow-private`; do that only with the data owner's authorization and the approved team account.
3. Copy `.env.example` to `.env` if no local configuration exists. Fill the values below from the stack outputs. Prefer temporary credentials in the terminal or AWS profile; a local `.env` containing credentials must remain ignored and excluded from sharing/synchronization. Use a unique namespace so deletion controls affect only your demo records.

```text
AWS_REGION=<workshop-region>
RD_BACKEND=athena
RD_DATASET_KIND=synthetic
RD_S3_BUCKET=<DataBucket-output>
RD_ATHENA_DB=<GlueDatabase-output>
RD_ATHENA_OUTPUT=s3://<DataBucket-output>/athena-results/
RD_ATHENA_WORKGROUP=<AthenaWorkGroup-output>
RD_STORE_BACKEND=dynamodb
RD_STORE_NAMESPACE=<unique-demo-name>
RD_CASES_TABLE=<CasesTable-output>
RD_ACTIONS_TABLE=<ActionsTable-output>
RD_APPROVALS_TABLE=<ApprovalsTable-output>
```

4. Run `python scripts/check_storage.py`. It verifies the account-owned bucket, four Glue tables, Athena count query and three active DynamoDB tables. Athena writes its query result to the private S3 output prefix and may incur a small charge. Then run `python run_demo.py syn_quality --scripted` to exercise the connected data and case store without Bedrock.

The demo store uses namespace-partitioned records. Each mutation reads and rewrites the small demo namespace; it has no cross-table transaction or authenticated reviewer. Use separate namespaces for concurrently running application processes. Both UI and CLI preserve cases by default. The UI's **Delete / restore cases** controls and CLI `--reset-cases` explicitly back up before clearing a populated workspace. `--keep-cases` remains accepted for compatibility.

## Athena over authorized private data

For the current official v2 release, build with `scripts/prepare_official_data.py` and validate/upload all nine tables using `scripts/export_aws_dataset.py`; follow [the v2 handoff guide](OFFICIAL_DATA_V2.md). It generates the exact schemas and month partitions. The uploader does not provision infrastructure or upload raw customer sources.

The four-table `scripts/setup_aws_data.py` workflow above is for synthetic/v1 fixtures only. Keep it separate from the nine-table official v2 database and use only the authorized team account for private data.

```sh
export RD_BACKEND=athena
export RD_DATASET_VERSION=2
export RD_ATHENA_DB=aldo_returns_v2
export RD_ATHENA_OUTPUT='s3://<your-private-bucket>/athena-results/'
export RD_ATHENA_WORKGROUP='<stack-workgroup-output>'
python scripts/check_aws.py
python run_demo.py quality
python -m streamlit run app.py
```

In PowerShell use `$env:RD_BACKEND="athena"` (and the same pattern for other fields). Choose an authorized output bucket. The checker prints actual counts without assuming one dataset size. By default it checks identity and Athena without invoking a model. Use `python scripts/check_aws.py --model-only` to explicitly check Bedrock, or `--allow-model-call` to include it with storage checks. `--region us-east-1` can override the configured Workshop region. Model checks incur model usage; status output never prints credentials.

For a real local snapshot, set `RD_BACKEND=duckdb`, `RD_DATA_DIR=data/private`. Named ALDO scenarios refer to the IDs from the original prepared snapshot; use explicit `--return-id ... --as-of YYYY-MM-DD` if your snapshot differs.

## Access and integration status

The AWS role needs the selected model invocation permissions, the intended Athena workgroup/Glue database, and read/write access to the relevant private S3 prefixes. Resolve account/role limitations through the workshop administrator. Do not add credentials to source or broaden sharing to work around a permission error.

Case state uses local JSON by default, or configured DynamoDB tables when `RD_STORE_BACKEND=dynamodb`. One PK/SK table is also supported through `RD_STATE_TABLE`. Live UI investigations can publish an optional SNS case alert; see [SNS setup](../aws/SNS.md). SNS acceptance is not proof of email delivery. Authenticated approvals, connected retail execution and durable scheduled follow-up remain outside this prototype.
