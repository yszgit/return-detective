# Context for Kiro (paste this into Kiro chat or keep it in the repo as steering)

Project: Return Detective, a multi-agent system for ALDO Group returns, built for a hackathon judged by ALDO and AWS.
Stack: Python 3.12, Strands Agents SDK, Amazon Bedrock, optional Athena over private S3,
DuckDB local synthetic data, Streamlit UI. The supported app is at the repository root;
legacy/starter preserves the earlier implementation.

Rules for any code you write:
1. Do not change the signatures or return JSON shape of functions in `rd/tools.py`; other team members depend on them.
2. All SQL must run on both Athena (Trino) and DuckDB: no `::` casts, no DuckDB-only functions; compute dates in
   Python and use `dlit()`; inline values with `lit()`.
3. Evidence tools should only see data up to `tools.AS_OF.get()` (replay date). Known exceptions
   (static baseline/sales tables, single-return lookup, global date) are documented in docs/DATA_CONTRACTS.md.
4. Authority limits and approval gates live in code inside the action tools, never only in prompts.
5. Never return `customer_uid` or other customer identifiers to a model.
6. data/private, data/raw, data/synthetic and runtime remain ignored. At the user's request,
   the explicitly selected, pseudonymized data/cleaned snapshot is included in this private branch.
   Do not add customer identifiers, original order numbers or other raw/private datasets.
   See docs/DATA_POLICY.md and data/cleaned/README.md.

Open tasks:
- UI (`app.py`, Streamlit) now has shared synthetic/ALDO scenarios, live and scripted modes, saved live
  traces, case files and demo approvals. Historical impact data is in evaluation/results/cases_backtest.csv;
  it is not shown for synthetic runs. Improve verified business metrics separately from this layout cleanup.
- Replace `rd/store.py` JSON storage with DynamoDB tables `rd_cases`, `rd_actions`, `rd_approvals`, same function API.
- On approval requests, publish to an SNS topic so approvers get an email.
- Optional: Bedrock Guardrail (deny PII output), set RD_GUARDRAIL_ID; deploy agents to Bedrock AgentCore Runtime.
