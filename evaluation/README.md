# Evaluation status

cases_backtest.csv preserves the supplied export: 1,201 candidate records; 134 have a monthly-report comparison date. For those paired records the exported medians are 15 related returns at flag, 85.5 at report and 59 days lead.

These describe an archived calculation using a full-period company baseline and an assumed monthly-report comparator. Current tools fix that future leakage. Recompute the backtest before reusing its headline metrics.

archive/backtest_original.py preserves the original script, including its historical absolute path. It is not a runnable current pipeline; the required original source database was not supplied.

Current regression coverage is in tests/. Remaining evaluation includes dated sales cohorts, fee-grain validation, confirmed labels, comparator calibration, execution receipts and causal impact. after_flag is later observed volume, not measured avoided returns or savings.
