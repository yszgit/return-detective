# Operations workspace

The `new-ui-code` branch uses the same root `app.py`, existing agents, data
adapters, case store and authority checks. The original interface remains in the
`agent` branch history. Start with `python -m streamlit run app.py`.

## Three pages

1. **Returns monitor**: choose a historical date and process all supplied returns
   on that date. The screen uses grouped SQL and makes zero model calls. Its
   normal/watch/signal/data-insufficient counts reconcile to the day's total.
   Signals are grouped by style and category. Existing cases receive their
   related return IDs; only new signals are offered for explicit investigation.
2. **Case workspace**: show the detection evidence, competing explanations,
   current likely explanation, owner and proposed next steps. Batch/supplier
   causes and population return rates remain unproven when the source lacks them.
   Raw case JSON, model output and tool calls are inside technical drawers.
3. **Approvals & follow-up**: record a demo reviewer decision, show the case
   journey, and run a dated follow-up. Existing coverage, minimum-observation,
   pending-approval and recorded-intervention checks still apply. Persistent
   signals reuse the case; observed normal signals can close it under the
   existing rules. Observed change does not establish causal savings.

## Entry points and cost

`rd/workflow.py` is a small operations layer. Daily screening uses three grouped
queries: today's arrivals, trailing counts/locations for active styles, and the
company baseline. It shares `rd.detect.assess_window` with the existing screen;
thresholds and evidence/action tool signatures are unchanged. V2 baselines use
only dates strictly before the replay day. Invalid v2 rows remain visible as
data insufficient, never normal.

The replay is an **end-of-day** view, not an event-by-event timestamp simulation.
It only processes supplied snapshot rows; it is not an OMS event integration.

Selecting a new signal reuses Investigator and Response directly after the
statistical triage. Prepared single-return examples still use the original
Triage → Investigator → Response pipeline. Repeating the same signal attaches
to its open case without another model run. Interrupted investigations that
have already created a case can be explicitly retried against that case.

The prepared scenarios, historical analysis, architecture and rule/agent
comparison remain available in secondary drawers. Saved-example playback never
restores an old case snapshot over the active store.

## Persistence and replay dates

Cases/actions/approvals continue to use the configured JSON or DynamoDB store.
The interface never resets the case store on a run. Day reports and technical
traces are local ignored runtime artifacts, separated by data source and case
namespace. They are not uploaded to S3 or Git.

Dates must progress forwards within a workspace containing cases. An earlier
replay needs a separate workspace; a future case must not leak into a historical
decision. Dated operations share a nonblocking process lock because the existing
agent tools share a replay date. Multiple application processes must still use
separate DynamoDB namespaces. This is not a production transaction system.

The reviewer name is a demo audit label, not authenticated identity. Notifications,
refunds, stock holds, supplier claims and outreach remain proposed or simulated
records, with existing code-level authority gates. No scheduler or live retail
integration is introduced by this UI change.

## Checks

`tests/test_workflow.py` covers grouped-policy equivalence, bounded query count,
zero-model screening, deduplication, existing-case links, partial-run recovery,
empty days and concurrent/date guards. Official-schema tests cover invalid rows
and prior-day baselines. Streamlit AppTest exercises daily processing → selected
investigation → case detail → named approval decision, including missing data.
