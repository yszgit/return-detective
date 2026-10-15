# Complete official ALDO snapshot — v2

This is the user-authorized, pseudonymized analytical release of **all six official business CSVs** in `Aldo Group Test Data.zip`. It supersedes the four-table starter snapshot; [v1 provenance](../../docs/ALDO_V1_PROVENANCE.md) is retained separately.

| Table | Rows | Grain / purpose |
|---|---:|---|
| `returns.parquet` | 649,745 | One original return item event; existing return IDs preserved |
| `return_fees.parquet` | 521,660 | **One fee per return transaction**, including fees outside the return snapshot |
| `item_flags.parquet` | 1,597,921 | Original order+SKU final-sale snapshot; no inferred false values |
| `order_lines.parquet` | 1,000,000 | Dated original order lines, requested and snapshot-shipped quantities |
| `exchanges.parquet` | 61,934 | Original exchange lines, separate CONFIRMED / ASSUMED evidence |
| `transactions/` | 8,701,520 | Complete transaction lines in monthly folders and bounded Parquet shards |
| `sku_sales.parquet` | 31,801 | Supplied-order snapshot totals; **not population sales** |
| `company_daily.parquet` | 7,330 | Eligible daily category counts for strictly prior-day baselines |
| `baseline.parquet` | 12 | Descriptive full-snapshot totals; never the v2 historical decision baseline |

`manifest.json` records source hashes, output hashes, precise schemas, partitions and source row counts. `quality_report.json` records the acceptance result and remaining source limitations. Each original-grain record carries the source file digest and its original row position; source rows are retained, not silently deduplicated or dropped.

## What was cleaned

- Removed customer/profile identifiers and excluded transaction postal codes; order/return/transaction numbers share consistent, domain-separated keyed HMAC tokens. Keys and raw sources stay outside Git. Image URL query strings/fragments are removed.
- Preserved v1 `return_id` values exactly. Rebuilding with this snapshot as `--legacy-dir` retains the same IDs and tokens. Non-unique order+SKU return events remain distinct.
- Parsed named-timezone return timestamps to millisecond UTC timestamps. `return_date` retains the source business calendar date; orders, exchanges and transaction dates are typed.
- Kept monetary values as fixed decimals, fee minor units as integers, quantities as integers and unknown flags as NULL. Transaction money retains twelve decimals and original signs.
- Preserved 2,386 missing styles, 1,587 zero quantities and 78 missing reasons with explicit flags. **645,695** records qualify for request-count detection; nonqualifying records remain available for audit.
- Separated fees at transaction grain. The complete source nominal fee total reconciles to **461,324.40**; the matched return transactions total **449,170.60**. `returns.transaction_fee_amount` is non-additive context and must not be summed by item/category.
- Replaced the flag-file sales count with actual supplied order-line totals, and stopped presenting a population return rate from partial coverage.
- Historical screening uses eligible returns and `company_daily` strictly before the replay day. Every tool's evidence is bounded by its replay cutoff.

## Validated unknowns

Cleaning does not create absent facts. Currency/FX, brand fee rules/effective dates, charge observation timestamps, full sales coverage and confirmed root-cause labels were not supplied. They remain unavailable. Automatic financial execution is refused for this release; source nominal amounts are not labelled CAD or savings.

481,614 return rows have no final-sale match. Original orders link to 150,396 return rows (23.1%). Fees, shipment quantities, final-sale flags and final return statuses are snapshot attributes, not proven historical observations. Exchanges extend to March 2026; 4,423 occur after the January return snapshot and are filtered by date, not deleted. Transactions contain 853 unusual quantity-sign records; their signs are preserved and flagged.

## Validate and run

```sh
python scripts/validate_cleaned_data.py
RD_BACKEND=duckdb RD_DATA_DIR=data/cleaned python run_demo.py quality --scripted
RD_BACKEND=duckdb RD_DATA_DIR=data/cleaned python evaluation/backtest.py \
  --start 2025-01-01 --end 2025-12-31 --out runtime/evaluation/v2.csv
```

Local v2 detection is automatic from the manifest. Athena additionally needs `RD_DATASET_VERSION=2` and all nine tables. [Build, upload and contract instructions](../../docs/OFFICIAL_DATA_V2.md) include the exact commands. All files are below 50 MB; the complete release is approximately 478 MB. This is private commercial data, not anonymous or synthetic data.

For PowerShell, set `$env:RD_BACKEND="duckdb"` and `$env:RD_DATA_DIR="data/cleaned"` before the Python commands. [Executed acceptance checks](../../evaluation/results/curated_v2_acceptance.json) include 35 current tests, 7 preserved starter tests, source numeric reconciliation, three actual-data scenarios and 20 replay/tool cross-checks.
