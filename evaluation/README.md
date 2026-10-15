# Evaluation workstream

Owner branch: `feature/evaluation`.

`scenarios.json` contains held-out expectations for fixture checks; do not expose it to the investigator. Add new scenarios beyond the starter and compare fixed alerts against the agent on the same chronological replay. Freeze thresholds before evaluating held-out scenarios.

Measure false alarms, missed cases, time to evidence-supported escalation, approval bypass attempts, duplicate action handling, and execution verification. Model calls, cost, and latency require live measurement.

For business estimates, document each assumption: affected units, excess return risk, per-return incremental loss, holding/inspection cost, and replacement/lost-margin cost. Do not report illustrative annual savings as actual results.
