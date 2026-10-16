# Final project review — 2026-10-16

## Scope

Reviewed the `new-ui-code` project for integration into `main`: all Python source
and entry points, agent roles/tools and policy gates, dated screening and
follow-up, case/approval persistence, delete/restore, UI and trace displays,
data preparation/validation, AWS helpers, evaluation, configuration and CI.
The final application is `app.py` with the `rd/` package. The three existing
agent roles are retained; the daily monitor runs grouped SQL before an explicit
Investigator/Response run.

The two commits unique to the old `main` changed only the obsolete README.
Their history is preserved when integrating the reviewed application.

## Corrections included

| Area | Correction |
| --- | --- |
| CLI case preservation | Running a demo preserves cases by default. An explicit `--reset-cases` saves and verifies a workspace backup before clearing populated state. |
| Historical cutoffs | CLI examples and follow-ups use the workflow guard. Later return attachments and assessments advance the workspace cutoff, preventing earlier replays from seeing later case knowledge. |
| Windows JSON writes | Retry briefly when a sync client/indexer locks the destination. A persistent lock raises an error and retains the previous complete store. |
| AWS checks | Default identity/Athena checks make no model call. Model checks require an explicit flag; failures show a shareable status rather than credentials. |
| S3 exporter | Verify the destination bucket owner before uploading and require that owner on every upload. |
| Query memory | Bound the SQL result cache to 256 recently used queries, with a lock around cache updates. |
| Audit timestamps | New case-store activity timestamps explicitly use UTC. Historical evidence dates remain separate. |
| Legacy replay | Handle no signals without crashing, exclude incomplete month-end reports, and leave incomplete follow-up outcomes unknown. Retained historical result files are preserved with their limitations. |
| Fixtures | Fail the generator when a seeded screen check fails; explicitly select the generated four-table schema. |
| Delivery | Remove unused UI helpers and update README, team workflow, architecture, AWS instructions and offline CI for the final project. |

## Verification performed

- **100 automated tests passed** on Windows with Python 3.11, without live model
  calls or SNS publishing. Tests cover authority/refusal gates, approval reuse and
  rejections, date cutoffs, verification outcomes, DynamoDB pagination/namespace
  isolation, deletion backup/restore, calendar plans, UI entry points and the
  corrections above.
- **Seven independent scripted scenarios passed**: official `isolated` (0 cases),
  `quality` (1 case, 3 approvals), `fit` (1 case, 1 approval); synthetic
  `syn_isolated` (0 cases), `syn_quality` (1 case, 3 approvals), `syn_fit` (1 case,
  1 approval), `syn_damage` (1 case, no approval required). These validate routing
  and saved state; they are not independent root-cause accuracy estimates.
- **Complete official snapshot validation passed**: nine tables, all file hashes,
  schemas, source-row retention, tokenized identifiers, transaction-grain money
  reconciliation and temporal/eligibility checks. Includes 649,745 returns and
  8,701,520 transactions.
- Python source parsed successfully. The committed Athena DDL matches the
  current nine-table manifest exactly.
- Tracked-file checks found no `.env`, AWS credentials directory, private keys,
  raw inputs, runtime state or high-confidence AWS/GitHub secret patterns.
  This is a scoped source check, not a forensic scan of every historical commit.
- Read-only live storage checks succeeded in account `354918407702`, region
  `us-east-1`: private S3, all Glue tables, Athena `aldo_returns_v2`
  (649,745 returns), DynamoDB `return-detective-state`. No cases were changed.
  Workshop credentials expire; this is a dated connection result.
- CI runs Python 3.12 offline checks, snapshot validation and all seven scenarios.
  See GitHub Actions for the result on the exact final commit.

## Prototype boundaries retained

- Retail approvals, refunds, stock holds, supplier claims and outreach are
  simulated records. A typed reviewer name is not authenticated authorization.
- Optional SNS publishing is real when configured, but acceptance is not proof
  of inbox delivery. No notification or paid model request was made during this
  release check. Existing measured model examples are documented separately.
- At the initial review, calendar plans were manual. The subsequent reminder
  repair adds explicit one-time Scheduler emails; see [current setup](../aws/REVIEW_REMINDERS.md).
  Agent follow-ups are still manual.
- The store supports one application process per workspace; it does not provide
  transactional concurrent updates across servers.
- Statistical anomalies, confidence labels and persistence proxies do not prove
  physical root causes, population return rates, causal savings or winning odds.
  The value planner displays assumptions, costs and uncertainty.

See [demo sequence](FINAL_DEMO.md), [UI guide](UI_WORKSPACE.md),
[data contracts](DATA_CONTRACTS.md) and [evaluation notes](../evaluation/README.md).
