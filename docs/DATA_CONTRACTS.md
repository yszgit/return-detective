# Data and tool contracts

`rd/` is the shared package; the original synthetic order-cohort example is isolated under `examples/legacy_demo/`.

| Table | Meaning | Replay use |
| --- | --- | --- |
| returns | supplied return item records, keyed by return_id | observed return_date <= as_of |
| sku_sales | static SKU sales aggregate, no dated cohort | no sales-cohort rate computed |
| exchanges | supplied exchange records | available for future bounded tools |
| baseline | original full-period artifact | not used as historical baseline |

Screening measures category share **among returns**, not a sales-cohort return rate. Company comparisons use returns observed by the replay date.

`get_return` and `sample_returns` use explicit evidence columns and exclude customer_uid.

## Interfaces

- `rows(sql)` / `one(sql)` share SQL across engines; internal values use `lit` and `dlit`.
- `baseline_share(category, as_of)` requires an explicit date.
- `screen(style, category, as_of)` and `screen_all(style, as_of)` return statistical evidence.
- Public Agent tools live in `rd/tools.py`. Use `tools.replay_context(as_of)` around direct tool calls.
- `run_pipeline(return_id, as_of, emit)` runs Bedrock; `preview_return(return_id, as_of)` only previews evidence.
- `decide_approval(approval_id, approve, decided_by)` records a local simulation decision.

Fees are deduplicated per return order. Mixed-item fee attribution remains uncertain; values are candidate amounts for review. `fee_audit` n/charged count return orders, not unique people. `sku_return_rate` returns null for rates and denominators.

Action records have `status=SIMULATED` and `executed=false`. Future cloud executors must provide authenticated approval, idempotent attempts and verified receipts.

Historical CSV metrics used a full-period baseline and assumed monthly comparator. Recompute before reporting current performance. `after_flag` is later observed volume, not avoided returns or savings.

Coordinate shared-interface changes across data, Agent, AWS and UI owners.
