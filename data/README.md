# Data workstream

Owner branch: `feature/data`. `sample/` contains reproducible synthetic fixtures. Run `python scripts/generate_demo_data.py` to regenerate them.

The team's separately supplied cleaned starter datasets are stored directly in this directory as `returns.parquet`, `sku_sales.parquet`, `exchanges.parquet`, `baseline.parquet`, and `cases_backtest.csv`. They are read by the imported `rd/` package. See `docs/STARTER_IMPORT.md` for provenance, record counts, and integration limitations.

Use `raw/` and `private/` only for local inputs; both are ignored by Git. Document provenance, time conventions, missing fields, observation windows, and transformations. Agree on schema changes through `docs/DATA_CONTRACTS.md`.
