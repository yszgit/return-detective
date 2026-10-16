# Current repository structure

The supported application runs from the repository root. `new-ui-code` contains the operations workspace described in [UI_WORKSPACE.md](UI_WORKSPACE.md).

```text
app.py                         Streamlit entry point, styling and supporting analysis
run_demo.py                    CLI: incoming return or existing-case verification
rd/
  agents/
    triage.py                  Incoming-return decision and screening tools
    investigator.py            Competing hypotheses and evidence tools
    response.py                Playbook, actions and human approval requests
    pipeline.py                Initial investigation and reopened-case coordination
    shared.py                  Bedrock configuration, trace hooks, token/cycle metrics and JSON parsing
    __init__.py                Public imports used by the UI, CLI, checks and tests
  config.py                    Environment settings and repository-relative paths
  data.py                      DuckDB/Athena data access
  detect.py                    Shared statistical signal rules
  workflow.py                  Grouped daily screening, signal dispatch and replay guards
  ui.py                        Monitor, case workspace and approval/follow-up screens
  ui_evaluation.py             Measured paired acceptance and historical replay views
  value.py                     Case planning-value assumptions and break-even calculation
  tools.py                     Evidence tools and enforced action authority
  store.py                     JSON or optional DynamoDB demo state
  offline.py                   Fixed-tool baseline without a language model
  verification.py              Due dates, outcome checks and case reopening/closing
  scenarios.py                 Shared UI/CLI scenarios
  policy/response_playbook.md   Operating policy and approval tiers
scripts/                       Data generation, official v2 build/validation and AWS setup/checks
aws/                           Storage stack and Athena schema template
evaluation/                    Chronological replay, rule/agent comparison and aggregate results
tests/                         Current application regression tests
data/cleaned/                  Authorized, pseudonymized official v2 release
runtime/                       Ignored cases, traces and newly generated evaluation output
docs/                          Architecture, contracts, setup, team workflow and demo guide
.github/workflows/ci.yml        Current source, data and offline scenario checks
```

Synthetic fixtures and v1 compatibility use four tables; the official v2 release
uses nine. See [data contracts](DATA_CONTRACTS.md) and [v2 preparation/AWS guide](OFFICIAL_DATA_V2.md).

The old starter, machine-specific backtest and historical planning report were
removed from the active tree. They remain recoverable in Git history through
commit `1859ce4`. Current entry points do not depend on those files.

The three agents remain separate roles in one application process. The
[architecture](ARCHITECTURE.md) and [verification guide](VERIFICATION_DEMO.md)
describe implemented behavior and prototype limits.
