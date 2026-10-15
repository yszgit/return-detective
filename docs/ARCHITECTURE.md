# Architecture and status

~~~text
app.py / run_demo.py
          |
    rd.agents.run_pipeline
  Triage → Investigator → Response
          |
    rd.tools → rd.data → DuckDB / Athena
          |
    rd.store → local JSON
  approvals / simulation records / follow-up plans
~~~

`preview_return` uses the same evidence modules without model calls or case mutation. Live hand-offs use typed outputs. Incoming returns link to the case, and a follow-up plan is recorded.

The UI receives tool/assistant events through a queue and renders them on the Streamlit thread. Prototype runs serialize across replay dates.

Implemented: shared package, UI and CLI; local data; Athena pagination/timeout adapter; as-of lookups/baselines; schema-validated orchestration; local approvals, simulation records and manual evidence comparison.

Remaining: verify live Bedrock/Athena; shared persistent store; authenticated approvers; real retail executors and receipts; notifications; cloud scheduling; recomputed backtests and sales cohorts.

No measured savings, confirmed root causes or deployed cloud execution are claimed.
