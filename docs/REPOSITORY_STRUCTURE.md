# Final repository structure

The supported project is on **main** and runs from the repository root. There is one Streamlit application, with three pages described in [UI_WORKSPACE.md](UI_WORKSPACE.md).

```text
app.py                         Streamlit entry point, styling and supporting views
run_demo.py                    CLI: incoming-return replay and dated verification
rd/
  agents/
    triage.py                  Incoming-return decision and screening tools
    investigator.py            Competing hypotheses and evidence tools
    response.py                Playbook, actions and human approval requests
    pipeline.py                Initial/reopened-case stage coordination
    shared.py                  Bedrock setup, trace hooks, usage and JSON parsing
  config.py                    .env settings and repository-relative paths
  data.py                      DuckDB/Athena access and bounded query results
  detect.py                    Shared statistical signal rules
  tools.py                     Evidence tools and enforced action authority
  store.py                     JSON or DynamoDB demo case/approval/action store
  workflow.py                  Grouped screening, dispatch and replay-date guards
  verification.py              Historical due checks, reopening and closing
  offline.py                   Fixed-tool baseline without a language model
  scenarios.py                 Shared official/synthetic scenarios
  ui.py                        Monitor, case and approvals/follow-up pages
  approval_view.py              Explain pending, absent or completed proposals
  trace_view.py                 Actual tool results, counts and evidence windows
  ui_evaluation.py              Paired acceptance and historical replay views
  value.py                     Explicit planning-value assumptions
  review_plans.py               Future manual review appointments
  workspace_state.py            Scoped backup, deletion and restoration
  notifications.py             Optional immediate SNS case alerts
  policy/response_playbook.md   Operating policy and authority tiers
scripts/                       Build/validate data, export AWS layouts, check access
aws/                           Optional storage template, Athena schemas and SNS guide
evaluation/                    Rule replay, paired acceptance and aggregate results
tests/                         Offline regression and Streamlit workflow checks
data/cleaned/                  Authorized pseudonymized official v2 snapshot
docs/                          Setup, contracts, team workflow, demo and review notes
.github/workflows/ci.yml        Source, data, tests and seven offline scenario gates
runtime/                       Ignored cases, traces, backups and generated results
```

Synthetic/v1 compatibility uses four tables. The official v2 snapshot has nine.
See [data contracts](DATA_CONTRACTS.md) and the [v2 preparation/AWS guide](OFFICIAL_DATA_V2.md).

The three Agents are separate roles in one application process. The daily monitor
uses statistical triage before selecting Investigator → Response; prepared
single-return scenarios keep the complete Triage → Investigator → Response flow.

Old starter implementations are outside the active tree and recoverable through
Git history. Earlier branch names describe that history, not additional supported apps.
