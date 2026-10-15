# Evaluation

`backtest.py` uses the thresholds imported from `rd/detect.py`. It compares daily trailing-28-day signals with a month-end report using a minimum of 30 category returns. The retained `results/cases_backtest.csv` is the historical output inherited from `feature/agent`, not a result newly produced during this reorganization.

`results/cases_backtest_from_zip.csv` separately preserves the 1,201-row aggregate result supplied in `return_detective_code.zip`. It has no `sustained_next_28d` column and does not replace the default 1,391-row branch snapshot. See [snapshot provenance](results/README.md) for the exact source, columns and checksum. Neither snapshot is cleaned return-level data.

## Run on local data

```sh
RD_BACKEND=duckdb python evaluation/backtest.py
```

The default output is ignored `runtime/evaluation/cases_backtest.csv`, so a synthetic run cannot overwrite the checked-in historical result. Select another destination with `--out <path>`. Set `RD_DATA_DIR=data/private` for authorized local ALDO data. Output under `runtime/` remains ignored. Use `RD_BACKTEST_PATH` to select a reviewed result for the real-data UI.

The synthetic generator and `tests/test_synthetic_pipeline.py` verify seeded behavior without a language model. They are not a held-out estimate of false positive rates or business value.

## Limits of historical results

- A prepared pseudonymized snapshot is now included in `data/cleaned/`; original raw inputs are not committed. Set `RD_DATA_DIR=data/cleaned` to analyze it. Adding the snapshot does not itself validate inherited business claims.
- Baseline category shares are computed from the full input history; SKU sales have no event dates. The present evaluation is retrospective and can leak future information. Use prior-period/as-of baselines and dated denominators before claiming unbiased early detection.
- `sustained_next_28d` is a persistence proxy, not verified true/false root-cause labels. Near the end of the dataset the follow-up window can be incomplete.
- The monthly baseline may flag before the daily screen on some cases. Compare aligned windows and denominators and report negative lead times too.
- Savings calculations are illustrative gross avoided-return cost assumptions; intervention cost, stock holding, lost margin and uncertainty are not fully modeled.

The original machine-specific analysis is preserved at `legacy/backtest_original.py` for provenance; do not use it as the supported evaluation entry point.
