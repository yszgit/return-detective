# Official data v2 — build, acceptance and AWS handoff

This release was explicitly requested for the private `agent` branch. It covers every row in all six official CSV files. Notes.docx supplies join/grain definitions; Book.xlsx is blank and creates no analytical table. Raw customer data and the HMAC key are not committed.

## Rebuild

Install the root requirements and use the same external key when preserving existing tokens. Source inputs, temporary working database and key must be outside the repository. Choose a new empty output directory; the builder will not overwrite an existing release.

```sh
python scripts/prepare_official_data.py \
  --oms '/private/source/OMS Data_Feb24-Jan26_new.csv' \
  --flags '/private/source/McGill - Returns - Returnable Flag 2024-2025.csv' \
  --fees '/private/source/McGill - Returns - Restocking Fees 2024 - 2025.csv' \
  --exchanges '/private/source/McGill_Instore_return_exchanges.csv' \
  --orders '/private/source/All OMS orders_Feb 2024 to Feb 2026.csv' \
  --transactions '/private/source/Transaction_Detail_ALDO_CA_US_2025.csv' \
  --key-file '/private/keys/aldo-hmac.key' \
  --legacy-dir data/cleaned \
  --work-dir '/private/work/aldo-v2' --out '/private/output/aldo-v2'

python scripts/validate_official_data.py --data-dir '/private/output/aldo-v2'
```

When no legacy release is supplied, IDs are the immutable source row positions. With the published v1/v2 snapshot, IDs must map exactly or the build fails. File-based IDs are stable within the immutable source version, not a claim of a universal source-system event identifier. An updated source file needs an explicit migration.

`scripts/prepare_official_data.py` is the supported real-data builder and owns the return-category normalization rules. Synthetic four-table fixtures use `scripts/generate_synthetic_data.py`.

## Acceptance

Validation checks every Parquet file's checksum/size/schema/count, every original-grain source ID, six-source row reconciliation, distinct business keys where actually unique, fee minor-unit precision and totals, nullable flag joins, detection eligibility, daily history, token formats, absence of customer columns and absence of URL tracking parameters. Repeated order+SKU returns are retained; flags and original orders must be unique at their stated join grain.

Quality flags classify incomplete or anomalous facts without deleting them. Source returns include 2,386 missing styles, 1,587 zero-quantity rows and 78 missing reasons; eligible detection count is 645,695. Unknown final-sale coverage, partial order linkage, mixed-reason transaction fees and unusual signed transaction quantities remain explicit. See `quality_report.json` and [active contracts](DATA_CONTRACTS.md).

This acceptance means the supplied evidence is consistently cleaned and ready for defined backtests. It does not mean the organizer supplied all population sales, currency/policy facts, root-cause truth labels or all historical observation timestamps. The tools return unavailable/refused when those absent facts are required. There are no fabricated accuracy or savings metrics.

## AWS layout and DDL

History goes to private S3, queried by Athena. Cases/approvals/actions later use DynamoDB through its separate adapter; historical source files do not need a DynamoDB bulk import.

```sh
# Validate, generate exact Athena DDL and print the upload plan. No AWS calls.
python scripts/export_aws_dataset.py --bucket YOUR-PRIVATE-BUCKET \
  --prefix curated/aldo_v2 --database aldo_returns_v2

# Upload that validated release only after selecting the intended authorized bucket.
python scripts/export_aws_dataset.py --bucket YOUR-PRIVATE-BUCKET \
  --prefix curated/aldo_v2 --database aldo_returns_v2 --execute
```

Replace the bucket placeholder with a valid lowercase bucket name. Use a new immutable prefix for subsequent snapshots. The uploader separates table schemas and metadata:

```text
curated/aldo_v2/returns/returns.parquet
curated/aldo_v2/return_fees/return_fees.parquet
curated/aldo_v2/item_flags/item_flags.parquet
curated/aldo_v2/order_lines/order_lines.parquet
curated/aldo_v2/exchanges/exchanges.parquet
curated/aldo_v2/transactions/business_month=2025-02/part-0000.parquet
curated/aldo_v2/sku_sales/sku_sales.parquet
curated/aldo_v2/company_daily/company_daily.parquet
curated/aldo_v2/baseline/baseline.parquet
curated/aldo_v2/metadata/{manifest,quality_report}.json
```

Execute `runtime/aws/athena_v2.sql` one statement at a time in Athena. It defines all nine schemas and repairs the monthly transaction partitions. A template is also committed at `aws/athena_v2.sql`; the generator is authoritative for the chosen bucket/prefix. Each table has its own S3 directory; never upload all single-file schemas into one table LOCATION. Configure an Athena workgroup and private S3 results location.

```sh
export RD_BACKEND=athena
export RD_DATASET_VERSION=2
export RD_ATHENA_DB=aldo_returns_v2
export RD_ATHENA_WORKGROUP=rd-backtest
export RD_ATHENA_OUTPUT='s3://YOUR-PRIVATE-BUCKET/athena-results/'
python run_demo.py quality --scripted
```

The scripted run validates cloud data tools without invoking a model. Set an actually authorized `RD_MODEL_ID` and run `scripts/check_aws.py` before live Bedrock testing. Credentials remain in the terminal/profile; no cloud resources are automatically provisioned by this Git change.

## Chronological replay

```sh
RD_BACKEND=duckdb RD_DATA_DIR=data/cleaned python evaluation/backtest.py \
  --start 2025-01-01 --end 2025-12-31 --out runtime/evaluation/v2.csv
```

The same entry point can read aggregate data through Athena. V2 excludes ineligible records from request-count detection, calculates the company mix strictly before the day, triggers only on eligible style arrivals and excludes incomplete follow-up from persistence denominators. The first signal per style/category is taken inside the specified evaluation range; earlier data is baseline history and later data is follow-up only.

The committed `evaluation/results/curated_v2_backtest.csv` has 889 signals for 2025, 889 complete follow-ups, persistence proxy 55.46%, and 94 month-report comparable cases with 40.5-day median lead. These are zero-model rule-replay results, not accuracy or causal savings. The month-end comparator has a higher count threshold and a different cadence, so this is not proof of three-agent incremental value.

For full Agent validation, add reviewed truth labels and a batch driver, run real Bedrock calls, validate state/approval semantics and record latency/cost. Live AWS connectivity, DynamoDB persistence and real business execution remain distinct verification stages.
