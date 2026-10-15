"""Verify the complete v2 release, without displaying customer/business records."""
import argparse
import json
from pathlib import Path
import sys

import duckdb

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.prepare_official_data import checksum, quote, TABLES


def require(condition,message):
    if not condition:
        raise ValueError(message)


def validate(data_dir, verbose=True):
    data_dir=Path(data_dir).resolve()
    manifest=json.loads((data_dir/'manifest.json').read_text())
    quality=json.loads((data_dir/'quality_report.json').read_text())
    require(manifest['schema_version']==2,'Expected the v2 dataset contract')
    require(set(manifest['tables'])==set(TABLES),'Incomplete table set')
    con=duckdb.connect()
    con.execute("set memory_limit='2GB'")
    con.execute('set threads=4')
    declared=set()
    forbidden={'customer_uid','cnsmr_prof_sid','consumer_profile_guid','postal_code'}
    for name,meta in manifest['tables'].items():
        paths=[]
        for file in meta['files']:
            p=(data_dir/file['path']).resolve()
            require(p.is_relative_to(data_dir),'Manifest path escapes dataset')
            require(p.is_file(),f'{name}: missing file')
            require(p.stat().st_size==file['bytes'],f'{name}: byte count mismatch')
            require(p.stat().st_size<90*1024*1024,f'{name}: split files below 90 MiB')
            require(checksum(p)==file['sha256'],f'{name}: checksum mismatch')
            declared.add(p)
            paths.append(str(p))
        require(paths,f'{name}: no files')
        path_sql='['+','.join(quote(p) for p in paths)+']'
        con.execute(f'create view {name} as select * from read_parquet({path_sql},hive_partitioning=true)')
        schema=[{'name':r[0],'type':r[1]} for r in con.execute(f'describe {name}').fetchall()]
        require(schema==meta['columns'],f'{name}: schema mismatch')
        require(not forbidden.intersection(c['name'] for c in schema),f'{name}: direct identifier in output')
        n=con.execute(f'select count(*) from {name}').fetchone()[0]
        require(n==meta['rows'],f'{name}: row count mismatch')
        if any(c['name']=='source_record_id' for c in schema):
            unique=con.execute(f'select count(distinct source_record_id) from {name}').fetchone()[0]
            require(unique==n,f'{name}: duplicate/missing source record identity')
        if verbose:
            print(f'{name}: {n:,} rows; all file hashes, schema, source IDs and row counts PASS',flush=True)
    require(declared==set(data_dir.rglob('*.parquet')),'Undeclared Parquet file in release')
    for source,target in [('oms','returns'),('flags','item_flags'),('fees','return_fees'),
                          ('orders','order_lines'),('exchanges','exchanges'),('transactions','transactions')]:
        require(manifest['sources'][source]['rows']==manifest['tables'][target]['rows'],f'{source}: rows lost/multiplied')
        require(quality['source_coverage'][source]['source_rows']==manifest['sources'][source]['rows'],f'{source}: source quality metadata mismatch')

    def count(sql):
        return con.execute(sql).fetchone()[0]

    require(count('select count(*)-count(distinct return_id) from returns')==0,'Duplicate return IDs')
    require(count('select count(*)-count(distinct return_order_number) from return_fees')==0,'Duplicate fees per transaction')
    require(count('select count(*)-count(distinct (order_number,sku)) from item_flags')==0,'Duplicate flags per item')
    require(count('select count(*)-count(distinct (order_number,sku)) from order_lines')==0,'Duplicate order lines')
    require(count('select count(*) from return_fees where fee_amount is null or fee_minor_units<>cast(round(fee_amount*100,0) as bigint)')==0,'Fee precision/null failure')
    fee_total=str(con.execute('select sum(fee_amount) from return_fees').fetchone()[0])
    require(fee_total==quality['fees']['source_nominal_total'],'Transaction fee source total mismatch')
    for field,reconciliation in quality['transactions']['money_reconciliation'].items():
        require(field in {'net_sales_retail_amount','net_sales_cost_amount','gross_margin_amount'},'Unexpected monetary field')
        actual=str(con.execute(f'select sum({field}) from transactions').fetchone()[0])
        require(actual==reconciliation['source_nominal_total']==reconciliation['output_nominal_total'],
                f'{field}: transaction monetary total mismatch')
    require(count('''select count(*) from returns where eligible_for_detection is distinct from
        (style is not null and qty>0 and return_date is not null and return_created_at_utc is not null and category<>'Unknown')''')==0,'Detection eligibility mismatch')
    require(count('select count(*) from returns where invalid_date')==0,'Invalid return date')
    require(count('''select count(*) from returns r left join item_flags f using(order_number,sku)
        where r.final_sale is distinct from f.final_sale''')==0,'Unknown flags were imputed or incorrectly joined')
    for table,column,prefix in [('returns','order_number','ORDER'),('returns','return_order_number','RETURN'),
                                ('item_flags','order_number','ORDER'),('order_lines','order_number','ORDER'),
                                ('exchanges','order_number','ORDER'),('exchanges','transaction_number','TXN'),
                                ('return_fees','return_order_number','RETURN'),
                                ('transactions','transaction_number','TXN'),('transactions','original_transaction_number','TXN')]:
        require(count(f"select count(*) from {table} where {column} is not null and not regexp_full_match({column},'RD-{prefix}-[0-9a-f]{{32}}')")==0,f'{table}.{column}: non-tokenized identifier')
    require(count("select count(*) from transactions where article_image_url like '%?%' or article_image_url like '%#%'")==0,'Image URL query parameters remain')
    actual='select return_date,category,count(*)::bigint n from returns where eligible_for_detection group by 1,2'
    require(count(f'select count(*) from (({actual}) except all select * from company_daily)')==0,'Daily history differs from eligible returns')
    require(count(f'select count(*) from (select * from company_daily except all ({actual}))')==0,'Unexpected company history')
    require(count('select sum(n) from baseline')==manifest['tables']['returns']['rows'],'Descriptive baseline count mismatch')
    require(count('select count(*) from return_fees where currency_verified or policy_verified')==0,'Source cannot establish fee currency/policy verification')
    require(not quality['automatic_financial_execution_supported'],'Source must not authorize automatic money movement')
    for name,flag in [('transactions','invalid_transaction'),('order_lines','invalid_order_line'),('exchanges','invalid_exchange')]:
        # Invalid source facts remain traceable; no affected record may be silently accepted as valid.
        require(count(f'select count(*) from {name} where {flag} is null')==0,f'{name}: unknown quality decision')
    con.close()
    if verbose:
        print('PASS: complete six-source coverage, transaction-grain money, privacy, eligibility, temporal history and explicit unknowns.',flush=True)
    return manifest,quality


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parents[1]/'data/cleaned')
    validate(p.parse_args().data_dir)
