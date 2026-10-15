# Context for Kiro (paste this into Kiro chat or keep it in the repo as steering)

Project: Return Detective, a multi-agent system for ALDO Group returns, built for a hackathon judged by ALDO and AWS.
Stack: Python 3.11, Strands Agents SDK, Amazon Bedrock (Claude), Athena over S3 (database `aldo_returns`,
bucket `aldo-return-detective-9969`, region us-east-1), Streamlit UI.

Rules for any code you write:
1. Do not change the signatures or return JSON shape of functions in `rd/tools.py`; other team members depend on them.
2. All SQL must run on both Athena (Trino) and DuckDB: no `::` casts, no DuckDB-only functions; compute dates in
   Python and use `dlit()`; inline values with `lit()`.
3. Tools must only see data up to `tools.AS_OF.get()` (replay date).
4. Authority limits and approval gates live in code inside the action tools, never only in prompts.
5. Never return `customer_uid` or other customer identifiers to a model.
6. Real ALDO data must never be committed: `data/` is git-ignored; data lives in S3.

Open tasks:
- UI (`app.py`, Streamlit): scenario picker → run `rd.agents.run_pipeline(return_id, as_of, emit)` and render the
  emitted events live (thoughts, tool calls with results, decisions); right panel: case file, actions, pending
  approvals with Approve/Reject buttons calling `rd.store.decide_approval`; impact panel from `evaluation/cases_backtest.csv`.
- Replace `rd/store.py` JSON storage with DynamoDB tables `rd_cases`, `rd_actions`, `rd_approvals`, same function API.
- On approval requests, publish to an SNS topic so approvers get an email.
- Optional: Bedrock Guardrail (deny PII output), set RD_GUARDRAIL_ID; deploy agents to Bedrock AgentCore Runtime.
