-- Execute one statement at a time. Snapshot v2; no future-data baseline.

CREATE DATABASE IF NOT EXISTS aldo_returns_v2;

CREATE EXTERNAL TABLE IF NOT EXISTS aldo_returns_v2.returns (
  `return_id` bigint,
  `source_record_id` string,
  `source_row` bigint,
  `banner` string,
  `order_number` string,
  `sku` string,
  `style` string,
  `return_order_number` string,
  `channel` string,
  `return_date` date,
  `return_created_at_utc` timestamp,
  `status` string,
  `refund` decimal(18,2),
  `qty` int,
  `raw_reason` string,
  `store` string,
  `category` string,
  `transaction_fee_amount` decimal(18,2),
  `final_sale` boolean,
  `aldo_fault` boolean,
  `country_code` string,
  `currency_code` string,
  `missing_style` boolean,
  `invalid_quantity` boolean,
  `missing_reason` boolean,
  `unknown_category` boolean,
  `invalid_date` boolean,
  `flag_missing` boolean,
  `fee_missing` boolean,
  `order_line_present` boolean,
  `order_date` date,
  `order_after_return` boolean,
  `eligible_for_detection` boolean,
  `completed_positive_quantity` boolean,
  `snapshot_attributes_point_in_time_available` boolean
)
STORED AS PARQUET
LOCATION 's3://your-private-bucket/curated/aldo_v2/returns/';

CREATE EXTERNAL TABLE IF NOT EXISTS aldo_returns_v2.return_fees (
  `source_record_id` string,
  `source_row` bigint,
  `return_order_number` string,
  `fee_amount` decimal(18,2),
  `invalid_amount` boolean,
  `fee_minor_units` bigint,
  `first_return_date` date,
  `return_lines` bigint,
  `distinct_categories` bigint,
  `country_code` string,
  `currency_code` string,
  `currency_verified` boolean,
  `policy_verified` boolean,
  `point_in_time_available` boolean,
  `linked_to_returns` boolean
)
STORED AS PARQUET
LOCATION 's3://your-private-bucket/curated/aldo_v2/return_fees/';

CREATE EXTERNAL TABLE IF NOT EXISTS aldo_returns_v2.item_flags (
  `source_record_id` string,
  `source_row` bigint,
  `order_number` string,
  `sku` string,
  `final_sale` boolean,
  `point_in_time_available` boolean,
  `invalid_flag` boolean
)
STORED AS PARQUET
LOCATION 's3://your-private-bucket/curated/aldo_v2/item_flags/';

CREATE EXTERNAL TABLE IF NOT EXISTS aldo_returns_v2.order_lines (
  `source_record_id` string,
  `source_row` bigint,
  `banner` string,
  `order_number` string,
  `order_date` date,
  `sku` string,
  `style` string,
  `size` string,
  `product_category` string,
  `requested_qty` int,
  `shipped_qty` int,
  `shipped_point_in_time_available` boolean,
  `invalid_order_line` boolean
)
STORED AS PARQUET
LOCATION 's3://your-private-bucket/curated/aldo_v2/order_lines/';

CREATE EXTERNAL TABLE IF NOT EXISTS aldo_returns_v2.exchanges (
  `source_record_id` string,
  `source_row` bigint,
  `confidence` string,
  `exchange_date` date,
  `transaction_number` string,
  `order_number` string,
  `exchange_sku` string,
  `qty` int,
  `store` string,
  `sales` decimal(24,6),
  `currency_code` string,
  `invalid_exchange` boolean
)
STORED AS PARQUET
LOCATION 's3://your-private-bucket/curated/aldo_v2/exchanges/';

CREATE EXTERNAL TABLE IF NOT EXISTS aldo_returns_v2.transactions (
  `source_record_id` string,
  `source_row` bigint,
  `banner` string,
  `site_id` string,
  `region_name` string,
  `state_code` string,
  `city_name` string,
  `store_type_description` string,
  `cluster_group_name` string,
  `business_date` date,
  `brand_description` string,
  `merchandise_category_name` string,
  `style_name` string,
  `color_name` string,
  `main_material_description` string,
  `fashion_fabric_description` string,
  `size_value` string,
  `article_image_url` string,
  `country_of_origin` string,
  `transaction_number` string,
  `original_transaction_number` string,
  `original_site_id` string,
  `channel` string,
  `return_reason` string,
  `in_store_return_indicator` boolean,
  `return_indicator` int,
  `price_group` string,
  `net_sales_retail_amount` decimal(38,12),
  `net_sales_units` int,
  `net_sales_cost_amount` decimal(38,12),
  `gross_margin_amount` decimal(38,12),
  `country_code` string,
  `currency_code` string,
  `invalid_transaction` boolean,
  `unusual_quantity_sign` boolean
)
PARTITIONED BY (`business_month` string)
STORED AS PARQUET
LOCATION 's3://your-private-bucket/curated/aldo_v2/transactions/';

MSCK REPAIR TABLE aldo_returns_v2.transactions;

CREATE EXTERNAL TABLE IF NOT EXISTS aldo_returns_v2.sku_sales (
  `sku` string,
  `lines_sold` bigint,
  `shipped_units` bigint,
  `final_sale_lines` bigint,
  `unknown_flag_lines` bigint,
  `first_order_date` date,
  `last_order_date` date,
  `denominator_scope` string,
  `point_in_time_available` boolean
)
STORED AS PARQUET
LOCATION 's3://your-private-bucket/curated/aldo_v2/sku_sales/';

CREATE EXTERNAL TABLE IF NOT EXISTS aldo_returns_v2.company_daily (
  `return_date` date,
  `category` string,
  `n` bigint
)
STORED AS PARQUET
LOCATION 's3://your-private-bucket/curated/aldo_v2/company_daily/';

CREATE EXTERNAL TABLE IF NOT EXISTS aldo_returns_v2.baseline (
  `category` string,
  `n` bigint,
  `share` double,
  `purpose` string
)
STORED AS PARQUET
LOCATION 's3://your-private-bucket/curated/aldo_v2/baseline/';
