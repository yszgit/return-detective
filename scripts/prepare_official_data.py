"""Build the complete, pseudonymized ALDO v2 snapshot from the six official CSVs.

No rows are silently discarded. Unknowns stay unknown; financial snapshots and
partial sales coverage are labelled rather than presented as historical facts.
The HMAC key and working DuckDB file MUST stay outside the repository.
"""
import argparse
import hashlib
import hmac
import json
from pathlib import Path
import sys

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.prepare_data import CATEGORY_SQL

SOURCE_FILES = {
    'oms': 'OMS Data_Feb24-Jan26_new.csv',
    'flags': 'McGill - Returns - Returnable Flag 2024-2025.csv',
    'fees': 'McGill - Returns - Restocking Fees 2024 - 2025.csv',
    'exchanges': 'McGill_Instore_return_exchanges.csv',
    'orders': 'All OMS orders_Feb 2024 to Feb 2026.csv',
    'transactions': 'Transaction_Detail_ALDO_CA_US_2025.csv',
}
TABLES = ('returns', 'return_fees', 'item_flags', 'order_lines', 'exchanges',
          'transactions', 'sku_sales', 'company_daily', 'baseline')


def quote(value):
    return "'" + str(value).replace("'", "''") + "'"


def checksum(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as f:
        while block := f.read(8 * 1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str) + '\n')


def build(a):
    out = Path(a.out).resolve()
    work = Path(a.work_dir).resolve()
    key_path = Path(a.key_file).resolve()
    if out.exists() and any(out.iterdir()):
        raise ValueError('Output must be empty; publish a new snapshot, never overwrite one in place.')
    if key_path.is_relative_to(ROOT):
        raise ValueError('The pseudonymization key must be outside the repository.')
    if work.is_relative_to(ROOT):
        raise ValueError('The private working database must be outside the repository.')
    key = key_path.read_bytes()
    if len(key) < 32:
        raise ValueError('Use a private HMAC key of at least 32 bytes.')
    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(work / 'build.duckdb'))
    con.execute("set memory_limit='2GB'")
    con.execute('set threads=4')
    con.execute("set preserve_insertion_order=true")
    con.execute(f"set temp_directory={quote(work / 'spill')}")

    def token(domain, value):
        if value is None or not str(value).strip():
            return None
        # Same domain and format as the already committed v1 snapshot.
        digest = hmac.new(key, f'{domain}:{value}'.encode(), hashlib.sha256).hexdigest()[:32]
        return f'RD-{domain.upper()}-{digest}'

    def token_function(domain):
        def apply(value):
            return token(domain, value)
        return apply

    for domain in ('order', 'return', 'txn'):
        con.create_function('token_' + domain, token_function(domain),
                            ['VARCHAR'], 'VARCHAR', null_handling='special')

    sources = {}
    for name in SOURCE_FILES:
        path = Path(getattr(a, name)).resolve()
        sha = checksum(path)
        sources[name] = {'file': SOURCE_FILES[name], 'sha256': sha, 'bytes': path.stat().st_size}
        # Serial CSV reading gives immutable source row positions, including repeated business keys.
        con.execute(f"""create or replace table raw_{name} as select row_number() over ()::bigint source_row,
            * from read_csv({quote(path)},header=true,all_varchar=true,parallel=false)""")
        sources[name]['rows'] = con.execute(f'select count(*) from raw_{name}').fetchone()[0]
        print(f'Loaded {name}: {sources[name]["rows"]:,} source rows', flush=True)

    def source_id(name):
        # The full immutable file digest plus row position is a stable locator.
        # A shared prefix compresses well; random per-row digests add hundreds of MB.
        return f"{quote(name + ':' + sources[name]['sha256'] + ':')} || source_row::varchar"

    # Preserve original-grain flags; never infer false from an unmatched flag.
    con.execute(f"""create or replace table item_flags as select {source_id('flags')} source_record_id,
        source_row, token_order(order_number) order_number, nullif(trim(sku),'') sku,
        case lower(trim("Is item final sale?")) when 'yes' then true when 'no' then false end final_sale,
        false point_in_time_available,
        lower(trim("Is item final sale?")) not in ('yes','no') or "Is item final sale?" is null invalid_flag
        from raw_flags""")
    conflicts = con.execute('''select count(*) from (select order_number,sku,count(*) n
        from item_flags group by 1,2 having count(*)>1)''').fetchone()[0]
    if conflicts:
        raise ValueError('Repeated item flag keys require reconciliation before publishing.')

    con.execute(f"""create or replace table fee_source as select {source_id('fees')} source_record_id,
        source_row,token_return(return_order_number) return_order_number,
        try_cast("restocking revenue" as decimal(18,2)) fee_amount,
        (try_cast("restocking revenue" as decimal(24,6)) is null
         or try_cast("restocking revenue" as decimal(24,6)) < 0
         or try_cast("restocking revenue" as decimal(24,6)) <> try_cast("restocking revenue" as decimal(18,2))) invalid_amount
        from raw_fees""")
    if con.execute('select count(*)-count(distinct return_order_number) from fee_source').fetchone()[0]:
        raise ValueError('Fees must contain one row per return transaction; no MAX-based deduplication.')

    # Use exactly the legacy interpretation only to recover the already published return IDs.
    con.execute(f"""create or replace table initial_returns as
        with b as (select *,lower(regexp_replace(coalesce(reason,''),'^return\\.page\\.reasons\\.','')) r0 from raw_oms)
        select {source_id('oms')} source_record_id,source_row,
        store_banner banner,token_order(order_number) order_number,sku,orderitem_product_name style,
        token_return(return_order_number) return_order_number,return_channel channel,
        try_cast(return_creation_date as date) return_date,
        "last return status" status,try_cast("Refund amount" as double) refund,
        try_cast("item return qty" as integer) qty,reason raw_reason,"Instore return location" store,
        {CATEGORY_SQL} category,
        date_trunc('millisecond',timezone('UTC',try_strptime(return_creation_date_tmstmp,
            ['%Y-%m-%d %H:%M:%S.%f %Z','%Y-%m-%d %H:%M:%S %Z']))) return_created_at_utc
        from b""")
    con.execute('''create or replace table legacy_shaped as select r.*,f.fee_amount::double restocking_fee,
        fl.final_sale,r.category in ('Quality','Fulfilment error','Damaged in transit','Delivery failure') aldo_fault
        from initial_returns r left join fee_source f using(return_order_number)
        left join item_flags fl using(order_number,sku)''')
    legacy = Path(a.legacy_dir) / 'returns.parquet' if a.legacy_dir else None
    if legacy and legacy.is_file():
        con.execute(f'create or replace view legacy as select * from read_parquet({quote(legacy)})')
        legacy_columns={r[0] for r in con.execute('describe legacy').fetchall()}
        fields = ['banner','order_number','sku','style','return_order_number','channel','return_date',
                  'status','refund','qty','raw_reason','store','category','restocking_fee','final_sale','aldo_fault']
        condition = ('r.source_record_id=l.source_record_id' if 'source_record_id' in legacy_columns else
                     ' and '.join(f'r.{c} is not distinct from l.{c}' for c in fields))
        con.execute(f'''create or replace table return_ids as
            select r.source_record_id,l.return_id from legacy_shaped r left join legacy l on {condition}''')
        missing, n, distinct = con.execute('''select count(*) filter(where return_id is null),count(*),
            count(distinct return_id) from return_ids''').fetchone()
        if missing or n != sources['oms']['rows'] or distinct != n:
            raise ValueError('Legacy IDs could not be preserved exactly; check key/source/legacy snapshot.')
        if con.execute(f'''select count(*) from legacy_shaped r join legacy l on {condition}
            where r.order_number is distinct from l.order_number
            or r.return_order_number is distinct from l.return_order_number''').fetchone()[0]:
            raise ValueError('The HMAC key does not match the preserved business identifiers.')
    else:
        con.execute('''create or replace table return_ids as
            select source_record_id,source_row return_id from initial_returns''')

    con.execute(f"""create or replace table order_lines as select {source_id('orders')} source_record_id,
        source_row,nullif(trim(Banner),'') banner,token_order(order_number) order_number,
        try_cast(order_date_est as timestamp)::date order_date,nullif(trim(sku),'') sku,
        nullif(trim(Style),'') style,nullif(trim(Size),'') size,
        nullif(trim("category name"),'') product_category,
        try_cast(Requested_QTY as integer) requested_qty,try_cast(Shipped as integer) shipped_qty,
        false shipped_point_in_time_available,
        (order_date_est is null or try_cast(order_date_est as timestamp) is null
          or nullif(trim(sku),'') is null or order_number is null
          or try_cast(Requested_QTY as integer) is null or try_cast(Requested_QTY as integer)<=0
          or try_cast(Shipped as integer) is null or try_cast(Shipped as integer)<0
          or try_cast(Shipped as integer)>try_cast(Requested_QTY as integer)) invalid_order_line
        from raw_orders""")
    if con.execute('select count(*)-count(distinct (order_number,sku)) from order_lines').fetchone()[0]:
        raise ValueError('Repeated order+SKU keys require explicit reconciliation before joining returns.')

    con.execute('''create or replace table returns as
        select ids.return_id,r.source_record_id,r.source_row,
        nullif(trim(r.banner),'') banner,r.order_number,r.sku,nullif(trim(r.style),'') style,
        r.return_order_number,r.channel,r.return_date,r.return_created_at_utc,r.status,
        r.refund::decimal(18,2) refund,r.qty,r.raw_reason,r.store,r.category,
        f.fee_amount transaction_fee_amount,fl.final_sale,r.aldo_fault,
        nullif(regexp_extract(r.banner,'_(CA|US)$',1),'') country_code,
        null::varchar currency_code,
        nullif(trim(r.style),'') is null missing_style,
        r.qty is null or r.qty<=0 invalid_quantity,
        r.raw_reason is null or trim(r.raw_reason)='' missing_reason,
        r.category='Unknown' unknown_category,
        r.return_date is null or r.return_created_at_utc is null invalid_date,
        fl.source_record_id is null flag_missing,
        f.source_record_id is null fee_missing,
        o.source_record_id is not null order_line_present,
        o.order_date,
        o.order_date>r.return_date order_after_return,
        (nullif(trim(r.style),'') is not null and r.qty>0 and r.return_date is not null
            and r.return_created_at_utc is not null and r.category<>'Unknown') eligible_for_detection,
        (r.qty>0 and r.status='RETURN_COMPLETED') completed_positive_quantity,
        false snapshot_attributes_point_in_time_available
        from legacy_shaped r join return_ids ids using(source_record_id)
        left join fee_source f using(return_order_number)
        left join item_flags fl using(order_number,sku)
        left join order_lines o using(order_number,sku)''')
    con.execute('''create or replace table return_fees as
        select f.*,cast(round(fee_amount*100,0) as bigint) fee_minor_units,
        g.first_return_date,g.return_lines,g.distinct_categories,
        g.country_code,null::varchar currency_code,false currency_verified,
        false policy_verified,false point_in_time_available,
        (g.return_order_number is not null) linked_to_returns
        from fee_source f left join (
            select return_order_number,min(return_date) first_return_date,count(*) return_lines,
                count(distinct category) distinct_categories,
                case when count(distinct country_code)=1 then min(country_code) end country_code
            from returns group by return_order_number
        ) g using(return_order_number)''')

    con.execute(f"""create or replace table exchanges as select {source_id('exchanges')} source_record_id,
        source_row,upper(trim(Exchange_Confidence)) confidence,
        try_strptime(transactions_businessdaydate,'%m/%d/%Y')::date exchange_date,
        token_txn(transactions_transnumber) transaction_number,
        token_order("Original Order Number") order_number,nullif(trim("Exchange SKU"),'') exchange_sku,
        try_cast("Exchange QTY" as integer) qty,nullif(trim("Return store"),'') store,
        try_cast(Sales as decimal(24,6)) sales,null::varchar currency_code,
        (try_strptime(transactions_businessdaydate,'%m/%d/%Y') is null
          or try_cast("Exchange QTY" as integer) is null or try_cast("Exchange QTY" as integer)<=0
          or nullif(trim("Exchange SKU"),'') is null
          or Exchange_Confidence is null or upper(trim(Exchange_Confidence)) not in ('CONFIRMED','ASSUMED')) invalid_exchange
        from raw_exchanges""")

    # A separate dated order snapshot replaces the flag-file count as the sales denominator.
    con.execute('''create or replace table sku_sales as
        select o.sku,count(*)::bigint lines_sold,sum(shipped_qty)::bigint shipped_units,
        count(*) filter(where f.final_sale=true)::bigint final_sale_lines,
        count(*) filter(where f.final_sale is null)::bigint unknown_flag_lines,
        min(order_date) first_order_date,max(order_date) last_order_date,
        'supplied_order_snapshot_not_population_sales'::varchar denominator_scope,
        false point_in_time_available
        from order_lines o left join item_flags f using(order_number,sku)
        where not invalid_order_line group by o.sku''')
    con.execute('''create or replace table company_daily as select return_date,category,count(*)::bigint n
        from returns where eligible_for_detection group by return_date,category''')
    con.execute('''create or replace table baseline as select category,count(*)::bigint n,
        count(*)*1.0/sum(count(*)) over () as share,
        'descriptive_full_snapshot_do_not_use_for_historical_decisions'::varchar purpose
        from returns group by category''')

    # Complete analytical transaction fields; customer and postal identifiers are excluded.
    # Numbers are tokens shared between current/original transaction fields, not globally unique IDs.
    con.execute(f"""create or replace table transactions as select {source_id('transactions')} source_record_id,
        source_row,nullif(trim(banner),'') banner,nullif(trim(site_id),'') site_id,
        nullif(trim(region_name),'') region_name,nullif(trim(state_code),'') state_code,
        nullif(trim(city_name),'') city_name,nullif(trim(store_type_description),'') store_type_description,
        nullif(trim(cluster_group_name),'') cluster_group_name,try_cast(business_date as date) business_date,
        nullif(trim(brand_description),'') brand_description,
        nullif(trim(merchandise_category_name),'') merchandise_category_name,
        nullif(trim(style_name),'') style_name,nullif(trim(color_name),'') color_name,
        nullif(trim(main_material_description),'') main_material_description,
        nullif(trim(fashion_fabric_description),'') fashion_fabric_description,
        nullif(trim(size_value),'') size_value,
        nullif(regexp_replace(article_image_url,'[?#].*$',''),'') article_image_url,
        nullif(trim(country_of_origin),'') country_of_origin,
        token_txn(transaction_number) transaction_number,
        token_txn(original_transaction_number) original_transaction_number,
        nullif(trim(original_site_id),'') original_site_id,nullif(trim(channel),'') channel,
        nullif(trim(return_reason),'') return_reason,
        try_cast(in_store_return_indicator as boolean) in_store_return_indicator,
        try_cast(return_indicator as integer) return_indicator,nullif(trim(price_group),'') price_group,
        try_cast(Net_Sales_Retail_Amount as decimal(38,12)) net_sales_retail_amount,
        try_cast(Net_Sales_Units as integer) net_sales_units,
        try_cast(Net_Sales_Cost_Amount as decimal(38,12)) net_sales_cost_amount,
        try_cast(Gross_Margin_Amount as decimal(38,12)) gross_margin_amount,
        nullif(regexp_extract(banner,'_(CA|US)$',1),'') country_code,
        null::varchar currency_code,
        (try_cast(business_date as date) is null or try_cast(return_indicator as integer) is null
          or try_cast(return_indicator as integer) not in (0,1)
          or try_cast(Net_Sales_Units as integer) is null
          or try_cast(Net_Sales_Retail_Amount as decimal(38,12)) is null
          or try_cast(Net_Sales_Cost_Amount as decimal(38,12)) is null
          or try_cast(Gross_Margin_Amount as decimal(38,12)) is null) invalid_transaction,
        (try_cast(return_indicator as integer)=1 and try_cast(Net_Sales_Units as integer)>0)
          or (try_cast(return_indicator as integer)=0 and try_cast(Net_Sales_Units as integer)<0) unusual_quantity_sign,
        coalesce(strftime(try_cast(business_date as date),'%Y-%m'),'unknown') business_month
        from raw_transactions""")
    print('All six sources normalized; exporting complete tables.', flush=True)

    schema = {}
    for name in TABLES:
        schema[name] = [{'name':r[0],'type':r[1]} for r in con.execute(f'describe {name}').fetchall()]
        if name == 'transactions':
            folder = out / name
            # Monthly folders, with bounded row counts per file (< GitHub's 100 MiB hard limit).
            for month, count in con.execute('select business_month,count(*) from transactions group by 1 order by 1').fetchall():
                dest = folder / f'business_month={month}'
                dest.mkdir(parents=True,exist_ok=True)
                for start in range(0,count,100000):
                    target = dest / f'part-{start//100000:04d}.parquet'
                    con.execute(f"""copy (select * exclude(business_month) from transactions
                        where business_month={quote(month)} order by source_row limit 100000 offset {start})
                        to {quote(target)} (format parquet,compression zstd,row_group_size 65536)""")
        else:
            con.execute(f'copy {name} to {quote(out / (name+".parquet"))} (format parquet,compression zstd,row_group_size 65536)')
        print(f'Exported {name}', flush=True)

    def scalar(sql):
        return con.execute(sql).fetchone()[0]

    quality = {
        'source_coverage': {s:{'source_rows':v['rows'],'output_rows':scalar('select count(*) from '+t)}
            for s,t in [('oms','returns'),('flags','item_flags'),('fees','return_fees'),
                        ('exchanges','exchanges'),('orders','order_lines'),('transactions','transactions')]
            for v in [sources[s]]},
        'returns': {name:scalar('select count(*) from returns where '+condition) for name,condition in {
            'missing_style':'missing_style','zero_quantity':'qty=0','invalid_quantity':'invalid_quantity',
            'unknown_reason':'unknown_category','invalid_date':'invalid_date','flag_missing':'flag_missing',
            'fee_missing':'fee_missing','order_line_missing':'not order_line_present',
            'order_after_return':'order_after_return','eligible_for_detection':'eligible_for_detection',
            'completed_positive_quantity':'completed_positive_quantity'}.items()},
        'fees': {'source_nominal_total':str(scalar('select sum(fee_amount) from fee_source')),
                 'transaction_nominal_total':str(scalar('select sum(fee_amount) from return_fees')),
                 'matched_transaction_nominal_total':str(scalar('select sum(fee_amount) from return_fees where linked_to_returns')),
                 'invalid_amounts':scalar('select count(*) from return_fees where invalid_amount'),
                 'mixed_reason_transactions':scalar('select count(*) from return_fees where fee_amount>0 and distinct_categories>1'),
                 'currency_verified_transactions':0},
        'order_lines': {'invalid_lines':scalar('select count(*) from order_lines where invalid_order_line'),
                        'matched_return_lines':scalar('select count(*) from returns where order_line_present')},
        'exchanges': {'invalid_lines':scalar('select count(*) from exchanges where invalid_exchange'),
                      'after_returns_snapshot':scalar('select count(*) from exchanges where exchange_date>(select max(return_date) from returns)')},
        'transactions': {'invalid_lines':scalar('select count(*) from transactions where invalid_transaction'),
                         'unusual_quantity_sign':scalar('select count(*) from transactions where unusual_quantity_sign'),
                         'net_units':scalar('select sum(net_sales_units) from transactions'),
                         'monetary_scale':12},
        'unknowns_are_not_imputed':True,
        'automatic_financial_execution_supported':False,
        'limitations':['No confirmed root-cause labels: cannot report classification accuracy.',
                       'Currency, fee eligibility/effective-date policies and fee observation times not supplied.',
                       'Order sample and transaction brands do not cover all returns; no population sales denominator.',
                       'Final-sale, shipped quantities and final return statuses are undated snapshot attributes.',
                       'Business-date transactions and exchanges have no intraday event ordering.'],
    }
    quality['transactions']['money_reconciliation']={}
    for raw_name,name in [('Net_Sales_Retail_Amount','net_sales_retail_amount'),
                          ('Net_Sales_Cost_Amount','net_sales_cost_amount'),
                          ('Gross_Margin_Amount','gross_margin_amount')]:
        source_sum=scalar(f'select sum(try_cast("{raw_name}" as decimal(38,12))) from raw_transactions')
        output_sum=scalar(f'select sum({name}) from transactions')
        if source_sum!=output_sum:
            raise ValueError('Transaction monetary total changed during conversion.')
        quality['transactions']['money_reconciliation'][name]={'source_nominal_total':str(source_sum),
                                                               'output_nominal_total':str(output_sum)}
    for entry in quality['source_coverage'].values():
        if entry['source_rows'] != entry['output_rows']:
            raise ValueError('Source rows lost or multiplied.')
    if quality['returns']['invalid_date'] or quality['fees']['invalid_amounts']:
        raise ValueError('Invalid return dates or fee amounts require reconciliation.')
    quality['cleaning_acceptance']='PASS'
    write_json(out/'quality_report.json', quality)
    manifest = {'schema_version':2,'dataset':'ALDO complete official-source analytical snapshot',
                'synthetic':False,'sources':sources,'tables':{},
                'privacy':{'customer_identifiers':'removed','postal_code':'excluded',
                           'business_ids':'domain-separated keyed HMAC-SHA256, 128-bit tokens',
                           'key':'external; never included','image_urls':'query strings/fragments removed'},
                'return_date_range':dict(zip(['from','through'],con.execute('select min(return_date),max(return_date) from returns').fetchone())),
                'detection_policy':'eligible_for_detection; company baseline strictly before evaluation calendar day',
                'fees_policy':'return_fees is transaction-grain; returns.transaction_fee_amount is non-additive context only',
                'legacy_return_ids_preserved':bool(legacy and legacy.is_file()),
                'quality_report':'quality_report.json'}
    for name in TABLES:
        paths = sorted((out/name).rglob('*.parquet')) if name=='transactions' else [out/(name+'.parquet')]
        files = [{'path':str(p.relative_to(out)),'bytes':p.stat().st_size,'sha256':checksum(p)} for p in paths]
        if any(p['bytes']>=90*1024*1024 for p in files):
            raise ValueError('A data file is too large for the Git distribution contract; split it.')
        manifest['tables'][name]={'rows':scalar('select count(*) from '+name),'columns':schema[name],
                                 'files':files,'partition_columns':['business_month'] if name=='transactions' else []}
    write_json(out/'manifest.json',manifest)
    con.close()
    print('PASS: complete source coverage, stable legacy IDs, explicit unknowns and reconciliation.',flush=True)
    return manifest,quality


def parser():
    p=argparse.ArgumentParser(description=__doc__)
    for name in SOURCE_FILES:
        p.add_argument('--'+name,required=True)
    p.add_argument('--key-file',required=True)
    p.add_argument('--legacy-dir',help='v1 snapshot used to preserve public return IDs')
    p.add_argument('--out',required=True)
    p.add_argument('--work-dir',required=True,help='Private temporary directory outside Git')
    return p


if __name__=='__main__':
    build(parser().parse_args())
