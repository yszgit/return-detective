# Historical v1 snapshot provenance

This document records the superseded four-table release. The active release is v2; use [current data contracts](DATA_CONTRACTS.md) and [the v2 guide](OFFICIAL_DATA_V2.md) for current commands and limitations.

These four prepared tables were supplied in `return_detective_starter.zip` and added at the user's request for this private team's `agent` branch. They are real business data, not synthetic fixtures.

| File | Rows | Contents |
| --- | ---: | --- |
| `returns.parquet` | 649,745 | Prepared returns, normalized categories, fees and sale flags |
| `sku_sales.parquet` | 64,388 | SKU-level sales denominators |
| `exchanges.parquet` | 61,934 | Prepared exchange records |
| `baseline.parquet` | 12 | Return category counts and shares |

Return dates cover **2024-02-04 through 2026-01-31**. `manifest.json` records source/output checksums, schemas, row counts and privacy transformations. The archive's 1,201-row `cases_backtest.csv` is identical to the already retained `evaluation/results/cases_backtest_from_zip.csv`; it is not duplicated here.

## Privacy transformations

- Removed `customer_uid` from `returns` (545,097 source rows had a value).
- Replaced non-empty `order_number` values with keyed HMAC-SHA256 tokens, consistently across returns and exchanges.
- Replaced non-empty `return_order_number` values with tokens using a separate HMAC domain.
- Kept the random key and original files outside this repository. They are not included in the commit.
- Preserved nulls, row counts, generated `return_id`, dates, styles/SKUs, numeric values, categories and all other analysis fields. Both unmodified aggregate tables retain their original bytes.

Tokens preserve joins and grouping but are not original order numbers. The files remain private commercial data: product names, dates and business metrics are still real. Pseudonymization does not make them anonymous or authorize broader distribution. The original attachment is preserved locally; this directory contains the prepared, pseudonymized copy.

## Current startup instructions

This page records historical provenance. `data/cleaned/` now contains v2, with nine
tables and prior-day baselines. Use the [current README](../README.md) and
[v2 guide](OFFICIAL_DATA_V2.md) for startup and independent scenario replays.
The old four-table snapshot remains recoverable from Git history; it should not
replace the current data directory. Its static-baseline and undated-sales limits
remain documented in [legacy contracts](DATA_CONTRACTS_V1.md) and
[evaluation notes](../evaluation/README.md).
