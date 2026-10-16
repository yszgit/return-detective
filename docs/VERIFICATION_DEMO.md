# Verify, reopen and compare the agents

## What changed

The original three roles remain: Triage, Investigator and Response. A scheduled
follow-up now persists its historical due date. The UI or CLI runs the due check;
there is no background cloud scheduler. Persistent signals reopen the same case
and send its previous hypothesis, actions, human decisions and new statistics to
the Investigator. Response reuses the case and proposes the next step.

All business actions remain simulations in the configured JSON/DynamoDB demo
store. Observed signal changes do not prove that a mitigation caused savings.

## Show the loop in Streamlit

From the repository root, using the configured conda environment:

```powershell
python -m streamlit run app.py
```

1. Run a quality or fit case with data covering its future follow-up period.
   The prepared ALDO quality scenario opens on 2024-11-23 and schedules a check
   for 2024-12-14. Synthetic fixtures stop on 2026-01-31; the UI correctly refuses
   to treat a missing February snapshot as proof of resolution.
2. Resolve every pending simulated approval using Approve or Decline.
3. Expand **Verify outcome and continue investigation**. Choose an observation
   date and a follow-up mode. **Scripted (no LLM)** is the fixed-tool baseline;
   **Live (Bedrock)** uses the terminal's configured Workshop credentials/model.
4. Press **Check outcome**. NORMAL with at least five recent style observations
   and a recorded mitigation closes the case. WATCH/SIGNAL reopens it and runs
   another investigation. Five observations is a prototype operational minimum,
   not a statistically validated confidence threshold.
5. Show the before/after observations, previous hypothesis, new investigation,
   resulting proposals and next due date. An unchanged hypothesis is acceptable
   when the evidence supports it; the agent must explain its reasoning.

Old cases without a stored due date have a **Schedule follow-up** button. Model
failures leave the case REOPENED. **Retry follow-up** explicitly retries the same
date after pending approvals are resolved. Repeated successful checks do not
repeat model calls, cases or identical action proposals. Identical rejected
proposals remain rejected.

CLI equivalent, preserving the existing case store:

```powershell
python run_demo.py --verify-case CASE-ID --as-of 2024-12-14 --scripted
# Live follow-up: omit --scripted. Add --retry-review only after a failed review.
```

Unknown coverage, too few observations, unresolved approvals and no recorded
mitigation cannot become a successful intervention claim. The prototype is
single-process; authenticated review, durable scheduling and transactional
multi-user state remain production work.

## Compare rules with real agents

Both modes use the same six seeded synthetic acceptance cases and isolated JSON
stores. The rules baseline is the existing fixed tool/playbook sequence. It is
not a monthly report with an artificially higher detection threshold.

```powershell
# No model or AWS calls. Outputs are ignored under runtime/.
python evaluation/compare_agents.py --mode rules

# Real Bedrock requests, using your own Workshop terminal credentials.
python evaluation/compare_agents.py --mode agent --allow-model-calls

# Begin with one live case to check access, latency and token usage.
python evaluation/compare_agents.py --mode agent --allow-model-calls --case quality
```

Review **Agent evaluation** in Streamlit or
`runtime/evaluation/agent_comparison/{rules,agent}/summary.json`. Each case report
contains decisions, actual stored actions/approvals, tool events, elapsed time,
and SDK token/model-cycle telemetry when available. Unknown usage stays null;
USD cost is not estimated without verified model billing information. Different
dataset hashes are not paired results. A single-case run cannot be compared as a
six-case aggregate.

The checks cover routing, ownership, case creation, approval separation and
duplicate handling. A failed check makes the command exit nonzero. They do not
measure held-out real-world root-cause accuracy or causal business impact.
Explanation quality requires a reviewer to inspect cited evidence and alternatives.
The real-agent comparison is pending until the live command has actually run;
scripted results must never be presented as measured LLM performance.
