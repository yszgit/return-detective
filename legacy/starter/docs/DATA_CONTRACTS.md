# Shared data and tool contracts

All committed records are synthetic. Order quantities are one in the initial fixtures. Times are ISO dates in a single documented simulation calendar; the sample snapshot is 2026-10-15.

| CSV | Key | Fields used by starter |
| --- | --- | --- |
| orders.csv | order_line_id | order_id, sku, size, dc, cohort_id, delivered_date, quantity |
| returns.csv | return_id | order_line_id, sku, return_date, quantity, reason, comment |
| reviews.csv | review_id | sku, review_date, rating, text |
| inventory.csv | stock_id | sku, dc, cohort_id, available, held |

Returns link to **order lines**, not just order IDs. Inventory includes a synthetic cohort mapping so an operation can target its actual stock group. This extra mapping does not establish a manufacturing defect.

`cohort_rates(sku, as_of)` returns a list with `dc`, `cohort_id`, `sold_units`, `returned_units`, `rate`, and `observation_days`. It uses delivered orders with a complete 30-day follow-up and returns observed within that follow-up and by `as_of`. Numerator and denominator refer to the same order lines.

`screen(sku, as_of)` returns `possible_pattern`, `monitor`, or `insufficient_evidence`, plus the exact cohort summaries. The starter thresholds (30 units, 3 returns, 10%, 2x peer rate) are illustrative and require evaluation.

Review and return queries must exclude events after the as-of time. Every claim should cite record IDs or cohort fields. No table contains customer PII. Ground-truth labels belong under `evaluation/` and must not be passed to the investigator.

Change this contract with agreement from the data, agent, AWS, and interface owners before changing shared field names.
