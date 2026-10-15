# Historical result provenance

`cases_backtest.csv` is copied byte-for-byte from `feature/agent` (`f8008f0`), previously `agent_app/evaluation/cases_backtest.csv`. It has 1,391 style/category aggregate rows with flag/report dates, counts and a persistence proxy. It contains no customer, order or return IDs, but style-level counts are still private commercial information.

This file is retained so the existing internal impact view remains available when the correct real dataset is configured. It is not recomputed or validated against private inputs by this cleanup. Keep it internal unless the data owner authorizes wider distribution. New backtest runs go to ignored `runtime/evaluation/` by default.

See [method limitations](../README.md) and [data policy](../../docs/DATA_POLICY.md).
