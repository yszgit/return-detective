"""Build the Return Detective data layer from the ALDO hackathon CSVs.

Usage:
  python scripts/prepare_data.py --oms OMS.csv --flag Returnable_Flag.csv \
      --fees Restocking_Fees.csv --exchanges Instore_return_exchanges.csv

Writes Parquet files into ./data used by the agent tools and the demo app.
"""
import argparse, duckdb, os

CATEGORY_SQL = r"""
case
 when r0 in ('too big','trop grand') then 'Fit: too big'
 when r0 in ('too small','trop petit') then 'Fit: too small'
 when r0 in ('uncomfortable','inconfortable') then 'Fit: uncomfortable'
 when r0 in ('defective','poor quality','manufacturer defect','warranty') then 'Quality'
 when r0 like 'arriv%poor cond%' or r0 like 'arriv% en mauvais%' then 'Damaged in transit'
 when r0 in ('wrong item','wrong item delivered','wrong size delivered','missing item') then 'Fulfilment error'
 when r0 in ('lost in transit','arrived too late','return to sender') then 'Delivery failure'
 when r0 in ('return without merchandise','return without merch') then 'No merchandise'
 when r0 like 'not what i expected%' or r0 like 'ne r%pond pas%' or r0 in ('not as advertised','not satisfied with the colour') then 'Expectation gap'
 when r0 like 'changed%' or r0 like 'j''ai chang%' or r0 in ('found something else','gift return') then 'Preference'
 when r0 like 'return extension%' or r0='in-store return' then 'Admin'
 else 'Unknown' end
"""

def main(a):
    os.makedirs(a.out, exist_ok=True)
    con = duckdb.connect()
    rd = lambda p: f"read_csv('{p}', header=true, all_varchar=true)"
    con.execute(f"create table oms as select * from {rd(a.oms)}")
    con.execute(f"create table flag as select distinct order_number, sku, \"Is item final sale?\"='yes' as final_sale from {rd(a.flag)}")
    con.execute(f"create table fees as select return_order_number, max(try_cast(\"restocking revenue\" as double)) fee from {rd(a.fees)} group by 1")
    con.execute(f"create table exch as select * from {rd(a.exchanges)}")
    con.execute(f"""
    create table returns as
    with b as (select *, lower(regexp_replace(coalesce(reason,''),'^return\\.page\\.reasons\\.','')) r0 from oms)
    select row_number() over (order by return_creation_date_tmstmp, return_order_number, sku) as return_id,
      store_banner as banner, order_number, sku, orderitem_product_name as style, customer_uid,
      return_order_number, return_channel as channel, cast(return_creation_date as date) as return_date,
      "last return status" as status, try_cast("Refund amount" as double) as refund,
      try_cast("item return qty" as int) as qty, reason as raw_reason, "Instore return location" as store,
      {CATEGORY_SQL} as category
    from b""")
    con.execute("""
    create table returns_full as
    select r.*, f.fee as restocking_fee, fl.final_sale,
      r.category in ('Quality','Fulfilment error','Damaged in transit','Delivery failure') as aldo_fault
    from returns r left join fees f using(return_order_number)
    left join flag fl using(order_number, sku)""")
    con.execute(f"COPY returns_full TO '{a.out}/returns.parquet' (FORMAT parquet)")
    # units sold per SKU (order lines; window Aug-2025 onward) -> return-rate denominator
    con.execute(f"COPY (select sku, count(*) as lines_sold, sum(final_sale::int) as final_sale_lines from flag group by 1) TO '{a.out}/sku_sales.parquet' (FORMAT parquet)")
    con.execute(f"""COPY (select Exchange_Confidence as confidence, strptime(transactions_businessdaydate,'%m/%d/%Y')::date as exchange_date,
       "Original Order Number" as order_number, "Exchange SKU" as exchange_sku, try_cast("Exchange QTY" as int) as qty,
       "Return store" as store, try_cast(Sales as double) as sales from exch) TO '{a.out}/exchanges.parquet' (FORMAT parquet)""")
    con.execute(f"""COPY (select category, count(*) n, count(*)*1.0/sum(count(*)) over () as share from returns group by 1)
       TO '{a.out}/baseline.parquet' (FORMAT parquet)""")
    print(con.execute("select count(*), min(return_date), max(return_date) from returns_full").fetchone())

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--oms', required=True); p.add_argument('--flag', required=True)
    p.add_argument('--fees', required=True); p.add_argument('--exchanges', required=True)
    p.add_argument('--out', default=os.path.join(os.path.dirname(__file__), '..', 'data'))
    main(p.parse_args())
