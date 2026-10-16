# Context for Kiro (paste this into Kiro chat or keep it in the repo as steering)

Project: Return Detective, a multi-agent system for ALDO Group returns, built for a hackathon judged by ALDO and AWS.
Stack: Python 3.11/3.12 (CI uses 3.12), Strands Agents SDK, Amazon Bedrock, optional Athena over private S3,
DuckDB local synthetic/prepared data, Streamlit UI. The supported app is at the repository root.

Agent code lives in rd/agents/: triage.py, investigator.py and response.py own the roles;
shared.py owns model/trace helpers; pipeline.py coordinates them. Existing imports from
rd.agents remain compatible. Keep the agents in one application process for this prototype.

Rules for any code you write:
1. Do not change the signatures or return JSON shape of functions in `rd/tools.py`; other team members depend on them.
2. All SQL must run on both Athena (Trino) and DuckDB: no `::` casts, no DuckDB-only functions; compute dates in
   Python and use `dlit()`; inline values with `lit()`.
3. Evidence tools should only see data up to `tools.AS_OF.get()` (replay date). V2 uses prior-day
   baselines and dated lookups; withheld snapshot facts, coverage limits and the process-global date
   are documented in docs/DATA_CONTRACTS.md.
4. Authority limits and approval gates live in code inside the action tools, never only in prompts.
5. Never return `customer_uid` or other customer identifiers to a model.
6. data/private, data/raw, data/synthetic and runtime remain ignored. At the user's request,
   the explicitly selected, pseudonymized data/cleaned snapshot is included in this private branch.
   Do not add customer identifiers, original order numbers or other raw/private datasets.
   See docs/DATA_POLICY.md and data/cleaned/README.md.

Final project:
- `main` is the reviewed project. Root `app.py` is the single supported UI; `rd/ui.py` owns its three pages.
- UI and CLI preserve cases. Explicit deletion/reset creates a local backup. Dated work shares historical guards.
- Optional SNS case alerts run after new live UI investigations. Future human review plans can explicitly schedule an EventBridge Scheduler email to the topic's confirmed subscribers; they never run Agents automatically. See aws/REVIEW_REMINDERS.md.
- Historical rule results and synthetic acceptance checks do not establish real-world root-cause accuracy or causal savings.
- Production work remains: transactional/concurrent storage, authenticated approvals, real retail integrations and automatic Agent follow-up orchestration. AgentCore deployment is optional and not part of the current app.
