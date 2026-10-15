# Supplied cleaned data

Four Parquet files were provided in the team's starter and retained byte-for-byte:

- returns.parquet: 649,745 records, 2024-02-04 through 2026-01-31.
- sku_sales.parquet: static SKU sales aggregates.
- exchanges.parquet: exchange records.
- baseline.parquet: original full-period baseline artifact.

Provenance was not independently established during import. Do not label the supplied dataset synthetic or independently certified ALDO production data.

DuckDB reads this directory by default. RD_DATA_DIR can point to an approved alternative with the same files. Athena reads configured Glue tables.

Original synthetic CSVs are in examples/legacy_demo/data/sample/. Historical backtest output is evaluation/cases_backtest.csv.

Replay baselines are computed from observed returns, not baseline.parquet. Dated sales cohorts are absent, so sales-cohort return rates are unavailable. See [contracts](../docs/DATA_CONTRACTS.md).

Keep new private raw inputs in approved storage outside Git. Migrate existing tracked data only through a coordinated change with replacement access instructions.
