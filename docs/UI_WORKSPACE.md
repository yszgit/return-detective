# Operations workspace

The `new-ui-code` branch uses the same root `app.py`, existing agents, data
adapters, case store and authority checks. The original interface remains in the
`agent` branch history. Start with `python -m streamlit run app.py`.

## Three pages

1. **Returns monitor**: choose a historical date and process all supplied returns
   on that date. The screen uses grouped SQL and makes zero model calls. Its
   normal/watch/signal/data-insufficient counts reconcile to the day's total.
   Flagged counts refer to individual return records; investigation tasks group
   them by style and category. A flagged record can have a different reason from
   the style's investigation category. Existing cases receive their
   related return IDs; only new signals are offered for explicit investigation.
2. **Case workspace**: show the detection evidence, competing explanations,
   current likely explanation, owner and proposed next steps. Batch/supplier
   causes and population return rates remain unproven when the source lacks them.
   Actual tool names, purposes, results and evidence scopes are visible by default
   under **Agent investigation steps**. Complete tool inputs/outputs and raw case
   JSON remain inside technical drawers. Numeric evidence is labeled by window,
   style/category and channel coverage; samples and return transactions are not
   presented as the same grain as return records.
   Model confidence is explicitly uncalibrated; the physical cause remains
   unconfirmed without independent evidence. Owner briefings, recorded actions
   and approval decisions are available without opening raw JSON. **Review pending
   proposals** opens the approval queue filtered to this case.
3. **Approvals & follow-up**: record a demo reviewer decision, show the case
   journey, and save a future manual review appointment with date, time, time zone
   and optional contact email. Email reminders and automatic Agent runs are **not
   enabled**. A saved appointment is not a queued email or background job.
   **Historical follow-up replay** is a separate collapsed section. Existing coverage, minimum-observation,
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

Disabled investigation buttons display a reason and remedy: recorded read-only
mode, unavailable data/store, missing `RD_MODEL_ID`, or an earlier replay date
than this workspace's case activity. A configured model is not presented as
proof of Bedrock permissions or current service availability.

The prepared scenarios, historical analysis, architecture and rule/agent
comparison remain available in secondary drawers. Saved-example playback never
restores an old case snapshot over the active store.

## Measured comparison and planning value

`evaluation/results/agent_comparison.json` contains the compact paired result
from actual Bedrock calls on the six seeded synthetic acceptance cases. It keeps
original checks and source-report hashes. A documented playbook alias,
`Merchandising (product content)`, is normalized to `Merchandising`; the original
fit-case exact-string failure is retained. Both approaches pass the normalized
acceptance checks; this is functional parity, not measured superiority in
explanation quality or real-world accuracy. Runtime traces remain ignored.

`evaluation/export_comparison.py --root <run-directory>` rejects mismatched data
or case sets before exporting. The comparison uses the prepared three-agent
pipeline; it does not benchmark the monitor's model-free triage cost.

The case-level value planner takes explicit future-return, avoidance, unit-cost,
labor and intervention assumptions. It shows negative outcomes and sensitivity,
includes a model/query budget, and exports the assumptions. It does not use
undated source fees, infer population return rates, or claim realized savings.
Historical replay no longer annualizes results by a hardcoded two-year divisor
or presents old fixed Glindafied dates as current v2 evidence.

## Persistence and replay dates

Cases/actions/approvals continue to use the configured JSON or DynamoDB store.
The interface never resets the case store on a run. Day reports and technical
traces are local ignored runtime artifacts, separated by data source and case
namespace. They are not uploaded to S3 or Git.

`RD_RECORDED_REPLAY=1` labels an isolated saved rehearsal and disables new
investigations, case decisions and follow-ups in the UI. The private snapshot
preparation command is documented in [FINAL_DEMO.md](FINAL_DEMO.md). If an AWS
connection expires, saved report counts are explicitly marked as saved and the
unverified investigation queue is unavailable until the connection is restored.

Dates must progress forwards within a workspace containing cases. An earlier
replay needs a separate workspace; a future case must not leak into a historical
decision. Dated operations share a nonblocking process lock because the existing
agent tools share a replay date. Multiple application processes must still use
separate DynamoDB namespaces. This is not a production transaction system.

Calendar appointments live in the case's `review_plan` field, separate from
historical `verification.due_on`. They retain local time, IANA time zone and UTC,
reject past or ambiguous/nonexistent clock-change times, and do not advance the
historical evidence cutoff. The optional email is a saved contact only.

The reviewer name is a demo audit label, not authenticated identity. Notifications,
refunds, stock holds, supplier claims and outreach remain proposed or simulated
records, with existing code-level authority gates. No scheduler or live retail
integration is introduced by this UI change.

## Clear a demo workspace

The left sidebar has **Delete saved cases**. It shows the current namespace and
counts of cases, approvals and actions. Select **Clear all records listed above**,
then **Back up and delete**. The app saves and verifies a local backup before
clearing only the configured case store namespace. It also clears that workspace's
saved daily reports so deleted case links cannot linger. Source datasets, other
namespaces and recorded tool traces are preserved.

Backups stay under ignored `runtime/<workspace>/backups/<source-key>/` (or the
configured runtime directory). **Download latest backup** exports the latest
backup. **Restore latest backup** restores the case store and day reports only
while the workspace is empty; it refuses another namespace or configuration.
Deletion and restoration are disabled in recorded read-only mode. These controls
are intended for the single-process demo, not concurrent production administration.

## Checks

`tests/test_workflow.py` covers grouped-policy equivalence, bounded query count,
zero-model screening, deduplication, existing-case links, partial-run recovery,
empty days and concurrent/date guards. Official-schema tests cover invalid rows
and prior-day baselines. Streamlit AppTest exercises daily processing → selected
investigation → case detail → named approval decision, including missing data.
