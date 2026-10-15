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

## Athena over authorized private data

For the current official v2 release, validate and upload all nine tables using `scripts/export_aws_dataset.py`; follow [the v2 handoff guide](OFFICIAL_DATA_V2.md). It generates the exact schemas and month partitions. `scripts/prepare_data.py` describes legacy v1 only. The uploader does not provision infrastructure or upload raw customer sources.

```sh
export RD_BACKEND=athena
export RD_DATASET_VERSION=2
export RD_ATHENA_DB=aldo_returns_v2
export RD_ATHENA_OUTPUT='s3://<your-private-bucket>/athena-results/'
export RD_ATHENA_WORKGROUP=primary
python scripts/check_aws.py
python run_demo.py quality
python -m streamlit run app.py
```

In PowerShell use `$env:RD_BACKEND="athena"` (and the same pattern for other fields). Choose your own authorized output bucket; the former account-specific default has been removed. The checker makes read queries and a small Bedrock request, so run it only with authorized data/model access. Expected counts printed by the checker refer to the original private ALDO snapshot, not synthetic data.

For a real local snapshot, set `RD_BACKEND=duckdb`, `RD_DATA_DIR=data/private`. Named ALDO scenarios refer to the IDs from the original prepared snapshot; use explicit `--return-id ... --as-of YYYY-MM-DD` if your snapshot differs.

## Access and integration status

The AWS role needs the selected model invocation permissions, the intended Athena workgroup/Glue database, and read/write access to the relevant private S3 prefixes. Resolve account/role limitations through the workshop administrator. Do not add credentials to source or broaden sharing to work around a permission error.

Case state remains local JSON even with Athena/Bedrock. DynamoDB, SNS, authenticated approval checks, idempotent retail execution and durable follow-up scheduling are not implemented here; see `aws/README.md`.
