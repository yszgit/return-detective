# Structure and migration

Source: `feature/agent` commit `f8008f00a88a6cbc4038d02641ee50ce2d398aa3`. Destination: the separate `agent` branch. The source branch and other team branches are unchanged.

Previously the root contained an early standard-library starter while `agent_app/` contained a second, more complete implementation, a second dependency file, a second UI and a second set of tests. Root CI tested only the early starter. The root README therefore did not describe the full agent application.

## Path map

| Previous path | Current path |
| --- | --- |
| `agent_app/app.py`, `agent_app/run_demo.py` | `app.py`, `run_demo.py` |
| `agent_app/rd/` | `rd/` |
| `agent_app/scripts/` | `scripts/` |
| `agent_app/tests/` | `tests/` |
| `agent_app/.streamlit/` | `.streamlit/` |
| `agent_app/KIRO.md` | `KIRO.md` (paths/configuration updated) |
| `agent_app/requirements.txt` | `requirements.txt` (all current direct dependencies) |
| `agent_app/evaluation/backtest.py` | `evaluation/backtest.py` |
| `agent_app/evaluation/cases_backtest.csv` | `evaluation/results/cases_backtest.csv` (unchanged contents) |
| `agent_app/evaluation/backtest_original.py` | `legacy/backtest_original.py` (historical, machine-specific) |
| `agent_app/README.md`, `.gitignore` | `legacy/agent_app_README.md`, `legacy/agent_app.gitignore` |
| Original root `app.py`, `return_detective/`, `scripts/`, `tests/` | Same relative paths under `legacy/starter/` |
| Original root `data/`, `evaluation/`, `prompts/`, `aws/` | Same relative paths under `legacy/starter/` |
| Original root README, requirements, env template, architecture/setup/contracts | Preserved under `legacy/starter/` |

## Behavior needed for the consolidated entry point

- Run everything from the root; do not `cd agent_app`.
- Shared `rd/config.py` resolves data/runtime paths independently of the working directory and loads root `.env` without overriding terminal settings.
- DuckDB with `data/synthetic/` is the default. Athena now requires explicit `RD_BACKEND=athena` and `RD_ATHENA_OUTPUT`; no account-specific bucket is hardcoded.
- Raw-data preparation defaults to `data/private/`; synthetic generation defaults to `data/synthetic/`.
- CLI and UI share `rd/scenarios.py`. CLI `--scripted` makes the local demo usable without a model. Mismatched named scenarios/datasets are rejected.
- The UI opens without local data and provides setup guidance. Synthetic runs do not display historical ALDO impact figures.
- New backtest runs write into ignored `runtime/evaluation/`; the historical committed result is not overwritten by default.
- CI installs current dependencies, tests the active pipeline and runs scripted scenarios, as well as checking the archived starter.

Detection thresholds, agent tool signatures, the playbook, and action authority rules are preserved. See `docs/ARCHITECTURE.md` for known prototype limitations.

## Agent module split

The former `rd/agents.py` is now the `rd/agents/` package:

| Module | Responsibility |
| --- | --- |
| `triage.py` | Triage prompt, read-only screening tools and fast-model selection |
| `investigator.py` | Investigator prompt, evidence tools and primary-model selection |
| `response.py` | Response prompt, playbook/action tools and fast-model selection |
| `shared.py` | Shared model construction, trace hooks and complete JSON object parsing |
| `pipeline.py` | Sequential stage calls, handoffs, early exits and emitted decisions |
| `__init__.py` | Existing public import compatibility |

Existing CLI, UI and AWS checker imports continue to work. All three prompts, role tool lists and model-selection rules are preserved. Result parsing now keeps complete nested investigation JSON rather than accidentally extracting an inner hypothesis object. The agents still run in one application process; separate deployment is not part of this change.
