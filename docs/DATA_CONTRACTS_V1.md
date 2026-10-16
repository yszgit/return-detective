# Synthetic and v1 compatibility contracts

These four tables support the reproducible synthetic demo and older prepared
snapshots through `rd/data.py`. Generate synthetic files with
`scripts/generate_synthetic_data.py`. The active real-data release is v2; use
[current contracts](DATA_CONTRACTS.md) and `scripts/prepare_official_data.py` for it.

| Table | Columns |
| --- | --- |
| `returns` | `return_id`, `banner`, `order_number`, `sku`, `style`, `return_order_number`, `channel`, `return_date`, `status`, `refund`, `qty`, `raw_reason`, `store`, `category`, `restocking_fee`, `final_sale`, `aldo_fault` |
| `sku_sales` | `sku`, `lines_sold`, `final_sale_lines` |
| `exchanges` | `confidence`, `exchange_date`, `order_number`, `exchange_sku`, `qty`, `store`, `sales` |
| `baseline` | `category`, `n`, `share` |

Synthetic return IDs are generated reproducibly from the fixed seed. Synthetic
amounts are fixture assumptions in CAD, not verified facts about real source
currencies. The synthetic files contain no customer identifiers. Nullable values
are retained in background records.

The 28-day screen compares category share among returns, not a population defect
rate. Synthetic/v1 baselines and SKU sales totals are static compatibility data;
they do not establish unbiased chronological business results. Current v2 uses
strictly prior-day baselines and withholds unsupported financial/rate claims.

Evidence return lookups are date-bounded. The replay date/cache and store API
remain single-process prototype state. Case/action/approval shapes are defined
by `rd/store.py`; actions are simulated and reviewers are not authenticated.
