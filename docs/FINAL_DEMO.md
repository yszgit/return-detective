# Final demonstration: evidence before claims

## Suggested sequence

Use a dedicated workspace/namespace and progress forward through historical dates.
For an earlier replay, select a separate workspace or back up and clear the current
demo workspace through the sidebar controls. Future manual review plans and
historical follow-up replays are separate. The explicit email option creates a
one-time AWS reminder to confirmed SNS subscribers; a plain calendar plan is
manual. Neither option automatically runs an Agent. Configured SNS also sends
immediate case alerts after a successful live investigation.

1. Open **Returns monitor**. Explain that all supplied returns for a historical
   day are screened with grouped SQL and zero model calls. Review the counts and
   compact investigation queue. A signal is an unusual return-reason pattern,
   not a confirmed defect or a population return rate.
2. Select a signal and explicitly investigate it with **Live agents (Bedrock)**.
   Show the statistics, cited evidence, competing explanations and current
   likely explanation in **Case workspace**. Identify what additional inspection
   or operational evidence would distinguish the remaining explanations.
3. Show the proposed owner/action, the owner briefing and **Actions and
   decisions**. Open **Approvals & follow-up** to demonstrate the human decision
   gate. Retail actions remain simulated records. A demo reviewer name is not
   authenticated operational approval.
4. Show a dated follow-up on the same case. A persistent pattern reopens the
   case and passes prior hypotheses and decisions back to the agents. Sparse
   observations, missing coverage and pending approvals cannot become success.
   Historical data is unchanged by simulated actions; no causal effect is claimed.
5. In the case value planner, edit the **assumptions**. Explain intervention
   cost, the assumed model/query budget and downside sensitivity, then download
   the assumptions. This is a planning scenario, not observed savings.
6. Open **Supporting analysis & architecture → Agent evaluation**. Present the
   paired acceptance results, time and token usage, then inspect one pair of
   investigations. Both modes pass the normalized six-case checks. Explain what
   still needs independent review before claiming incremental agent value.

## Evidence available

- Paired measured synthetic results: `evaluation/results/agent_comparison.json`.
  The fit owner's documented playbook alias is accepted; the original failed
  exact-string check, normalization note and raw report hash are retained.
- Official 2025 statistical replay: 889 signals, 889 complete follow-ups,
  55.46% persistence proxy, and 40.5-day median lead across 94 monthly-report
  comparable cases. Thresholds/cadences differ; these are not root-cause accuracy
  or incremental LLM value. Source: `evaluation/results/curated_v2_backtest.summary.json`.
- Private cloud rehearsal artifacts remain under ignored `runtime/pitch-live/`.
  Their cases use a separate DynamoDB namespace from the team's main workspace.
  Automated rehearsal decisions must remain labelled as test decisions.
  The recorded rehearsal had three pending proposals for human review. Its actual
  initial Bedrock assessment was Medium; the later historical follow-up raised
  it to High. The same-cutoff fixed-policy run proposed three actions immediately.
  The comparison is visible on the rehearsal case and preserves uncertainty
  about which assessment is correct; this one case is not an accuracy estimate.

## Reproduce the paired acceptance run

From the configured project environment:

```powershell
python evaluation/compare_agents.py --mode rules --out runtime/evaluation/my-run
python evaluation/compare_agents.py --mode agent --allow-model-calls --out runtime/evaluation/my-run
python evaluation/export_comparison.py --root runtime/evaluation/my-run
```

The second command makes actual Bedrock calls. The dataset and case stores are
synthetic and isolated from interactive cases. Do not tune on these seeded cases
and relabel the result as held-out performance.

## Review before claiming an agent advantage

For the same evidence cutoff, independently assess each pair on factual support,
competing explanations, useful next evidence, proportionate action and clarity.
Blind the mode labels where practical. Keep failures and disagreements. More
words, more tools or a passing routing check do not establish better decisions.

## Offline fallback for a saved real run

Private snapshots and traces stay under ignored `runtime/`. Prepare a separate
copy; an existing case directory is never overwritten:

```powershell
python scripts/prepare_recorded_replay.py --snapshot runtime/pitch-live/rehearsal-case-snapshot.json --out runtime/my-recorded-replay
```

In a separate terminal, start the recorded view with these settings:

```powershell
$env:RD_BACKEND='duckdb'
$env:RD_DATASET_VERSION='2'
$env:RD_DATA_DIR='data/cleaned'
$env:RD_STORE_BACKEND='json'
$env:RD_STATE_TABLE=''
$env:RD_RUNTIME_DIR='runtime/my-recorded-replay'
$env:RD_STORE_NAMESPACE='my-recorded-replay'
$env:RD_RECORDED_REPLAY='1'
python -m streamlit run app.py --server.port 8514
```

This view identifies the saved Bedrock run and disables new investigations,
approval decisions and follow-ups. The planning calculator remains interactive.
It makes no fresh model calls. For a live view, use the normal terminal settings
and refreshed Workshop credentials. An unavailable connection cannot expose
saved candidates as new work ready to investigate.
