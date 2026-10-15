# Historical result provenance

Two separate snapshots are retained. The ZIP snapshot does not replace the default result used by the application.

| File | Source | Rows | Persistence proxy |
| --- | --- | --- | --- |
| `cases_backtest.csv` | `feature/agent` at `f8008f0` | 1,391 | Includes `sustained_next_28d` |
| `cases_backtest_from_zip.csv` | User-provided `return_detective_code.zip` | 1,201 | Not included |

## Branch snapshot

`cases_backtest.csv` is copied byte-for-byte from `feature/agent` (`f8008f0`), previously `agent_app/evaluation/cases_backtest.csv`. It has 1,391 style/category aggregate rows with flag/report dates, counts and a persistence proxy. It contains no customer, order or return IDs, but style-level counts are still private commercial information.

This file is retained so the existing internal impact view remains available when the correct real dataset is configured. It is not recomputed or validated against private inputs by this cleanup. Keep it internal unless the data owner authorizes wider distribution. New backtest runs go to ignored `runtime/evaluation/` by default.

## User-provided ZIP snapshot

`cases_backtest_from_zip.csv` was added at the user's request from the archive entry `return_detective/evaluation/cases_backtest.csv`. Its original bytes are preserved:

- Size: 58,764 bytes.
- SHA-256: `d19f06059550c312b54fac557ad48b77c1bafa031aeafc458ad77a41ff6620e6`.
- Columns: `style`, `category`, `flag_date`, `returns_at_flag`, `after_flag`, `total`, `report_date`, `returns_at_report`.
- Category rows: Quality 201; Fit: too small 268; Fit: too big 325; Expectation gap 237; Fulfilment error 93; Damaged in transit 77.

This is an aggregate backtest result, not cleaned return-level data. It contains no customer, order or return identifiers. The ZIP does not include the four prepared Parquet tables or private inputs needed to reproduce the results. Basic CSV structure and count consistency have been checked; the business claims have not been independently validated. It remains an internal commercial artifact in this private repository.

See [method limitations](../README.md) and [data policy](../../docs/DATA_POLICY.md).
