# Local and private data

No raw or generated tables are committed here. Choose a workflow:

| Workflow | Data location | How to prepare |
| --- | --- | --- |
| Default local demo | `data/synthetic/` (ignored) | `python scripts/generate_synthetic_data.py` |
| Authorized real-data local analysis | `data/private/` (ignored) | `python scripts/prepare_data.py --oms <path> --flag <path> --fees <path> --exchanges <path>`; set `RD_DATA_DIR=data/private` |
| Authorized cloud analysis | Private S3 / Glue / Athena | Set `RD_BACKEND=athena`, database and output prefix; see `docs/AWS_SETUP.md` |

Both generators write `returns.parquet`, `sku_sales.parquet`, `exchanges.parquet` and `baseline.parquet`. The synthetic generator adds `_SYNTHETIC.txt` so the UI and CLI can identify the dataset. Do not remove that marker or copy it onto private data.

Synthetic seed: `20260131`; fixed scenario snapshot: `2026-01-31`. Styles use `SYNTH-`, SKUs use `SYN-`, and no customer identifier column is generated. The generator includes quality, fit, transit-damage and negative-control cases, plus messy ordinary records. This tests the prototype; it does not measure actual business performance.

The earlier tiny CSV fixtures are preserved at `legacy/starter/data/sample/`. They use a different schema and are only for that starter.

See [current schemas](../docs/DATA_CONTRACTS.md) and [the data assessment](../docs/DATA_POLICY.md).
