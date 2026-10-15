# Active v2 data contracts

The active real-data release is `data/cleaned/manifest.json`, schema version **2**. The precise names/types of every stored column and the row counts are machine-readable in that manifest. [Official v2 guide](OFFICIAL_DATA_V2.md) describes preparation and AWS deployment. [V1 contracts](DATA_CONTRACTS_V1.md) apply only to synthetic/legacy compatibility.

| Table | Key / grain | Main fields and constraints |
|---|---|---|
| returns | Preserved integer `return_id`; unique `source_record_id` | Tokens, SKU/style, source business date, `return_created_at_utc`, snapshot status, decimal refund, integer qty, raw/normalized reason, quality flags, `eligible_for_detection`, order linkage |
| return_fees | Unique token `return_order_number` | Decimal(18,2) `fee_amount`, integer `fee_minor_units`, category multiplicity, linkage, unknown currency, policy/currency/time verification flags |
| item_flags | Unique token order+SKU | Nullable boolean final_sale; source flag validation; undated snapshot |
| order_lines | Unique token order+SKU | Order date, style, size/category, requested/shipped integer quantities, validation flag; shipped quantity is an undated snapshot |
| exchanges | Unique source record | Exchange date, transaction/order tokens, exchanged SKU, qty/sales, CONFIRMED/ASSUMED and validation flag |
| transactions | Unique source record, **not transaction number alone** | Business date, site/banner/country, product attributes, current/original transaction tokens, original site, channels/reasons, sales/return indicators, integer signed units, decimal(38,12) retail/cost/margin, quality flags |
| sku_sales | SKU | Supplied order-line counts and shipped units, final-sale unknown counts, dates and explicit partial-population scope |
| company_daily | Date+category | Count of eligible return requests; historical baseline uses dates strictly less than replay date |
| baseline | Category | Full-snapshot descriptive count/share; not a historical feature |

## Eligibility and unknowns

`eligible_for_detection` requires a nonmissing style, positive quantity, valid source date/timestamp and known reason category. It determines request-count screening and company baselines, not whether a customer can return a product. Zero quantities and incomplete rows remain in `returns` with provenance and flags. A completed positive-quantity refund is a different metric, explicitly flagged.

Unknown final-sale flags remain NULL. `currency_code` is NULL throughout this source release; country labels do not prove currency. Monetary sums across countries are not FX-normalized. Source statuses, fees, flags and shipped quantities must not be treated as facts observed at historical creation time.

`transaction_fee_amount` on a return is a non-additive reference to a transaction-level fee. Audit/financial queries must use `return_fees` and distinct related return transactions. Mixed-reason transactions need policy evidence; a quality item alone does not prove the whole fee is refundable.

## Identity and source completeness

No customer/profile fields are stored. Token domains are consistent across original orders, flags, returns, exchanges and fees. Transaction tokens preserve current/original-number matching but require site/date context; they are not globally unique business events. The full source file SHA-256 plus physical CSV row position is the source record locator. Rebuilds reject an incorrect key or incompatible legacy ID mapping.

All six original business-file row counts reconcile to their original-grain output tables. Extra rows are not removed just because a key repeats. SKU identifiers are strings; sizes and locations retain string semantics. Product Master is mentioned in Notes.docx but absent from the supplied archive; exact style-name transaction evidence is explicitly weaker than a verified SKU join.

## Query and state boundaries

DuckDB discovers all nine tables, including monthly transaction shards. Athena uses matching table schemas, registered month partitions and explicit `RD_DATASET_VERSION=2`. Decimal values are retained in storage; presentation tools round numeric transport to four decimals. Financial authority does not use rounded display amounts.

`get_return`, exchange evidence and transaction evidence filter by replay cutoff. Undated status/refund/final-sale/fee outcomes are withheld from historical Agent inputs, while their source values remain in the analytical files for descriptive reconciliation. `fee_audit` reports that historical charges are unavailable rather than inventing a zero. `baseline_share` requires a historical cutoff for v2. Business-date sources do not provide intraday ordering. The current `AS_OF` is still process-global: chronological tool runs must be serial or isolated in separate processes.

Case/action/approval persistence remains the separate `rd/store.py` demo contract. DynamoDB integration, authenticated approvers, real retail execution and durable follow-up scheduling are not provided by cleaning these historical tables.
