"""Validate v2 and generate Athena DDL / an explicit S3 upload plan.

Without --execute this performs no AWS calls. It never uploads keys or raw CSVs.
"""
import argparse
from pathlib import Path
import re
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from scripts.validate_official_data import validate


def hive_type(typ):
    typ=typ.upper()
    if typ.startswith('DECIMAL('):
        return typ.lower()
    return {'VARCHAR':'string','BIGINT':'bigint','INTEGER':'int','BOOLEAN':'boolean',
            'DATE':'date','TIMESTAMP':'timestamp','DOUBLE':'double'}[typ]


def make_ddl(manifest,bucket,prefix,database):
    if not re.fullmatch('[a-z][a-z0-9_]*',database):
        raise ValueError('Use a lowercase SQL database identifier.')
    if not re.fullmatch(r'[a-z0-9][a-z0-9.\-]*',bucket):
        raise ValueError('Use an S3 bucket name, without s3:// or a path.')
    prefix=prefix.strip('/')
    if not re.fullmatch(r'[A-Za-z0-9/_\-]+',prefix):
        raise ValueError('Use a simple immutable S3 dataset prefix.')
    statements=[f'CREATE DATABASE IF NOT EXISTS {database};']
    for name,table in manifest['tables'].items():
        partition=table['partition_columns']
        fields=',\n'.join(f'  `{c["name"]}` {hive_type(c["type"])}' for c in table['columns'] if c['name'] not in partition)
        part='\nPARTITIONED BY ('+', '.join(f'`{c}` string' for c in partition)+')' if partition else ''
        statements.append(f"CREATE EXTERNAL TABLE IF NOT EXISTS {database}.{name} (\n{fields}\n){part}\n"
                          f"STORED AS PARQUET\nLOCATION 's3://{bucket}/{prefix}/{name}/';")
        if partition:
            statements.append(f'MSCK REPAIR TABLE {database}.{name};')
    return '-- Execute one statement at a time. Snapshot v2; no future-data baseline.\n\n'+'\n\n'.join(statements)+'\n'


def upload_plan(data_dir,manifest,prefix):
    data_dir=Path(data_dir)
    result=[]
    for name,table in manifest['tables'].items():
        for file in table['files']:
            path=Path(file['path'])
            suffix=path.relative_to(name).as_posix() if table['partition_columns'] else path.name
            result.append((data_dir/path,f'{prefix.strip("/")}/{name}/{suffix}'))
    for meta in ['manifest.json','quality_report.json']:
        result.append((data_dir/meta,f'{prefix.strip("/")}/metadata/{meta}'))
    return result


def main(a):
    manifest,_=validate(a.data_dir)
    ddl=make_ddl(manifest,a.bucket,a.prefix,a.database)
    path=Path(a.ddl_out)
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(ddl)
    plan=upload_plan(a.data_dir,manifest,a.prefix)
    print(f'{len(plan)} files; Athena DDL: {path}; execute={a.execute}')
    if a.execute:
        import boto3
        s3=boto3.client('s3')
        for local,key in plan:
            s3.upload_file(str(local),a.bucket,key)
    else:
        for local,key in plan:
            print(f'{local.name} -> s3://{a.bucket}/{key}')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--data-dir',type=Path,default=Path(__file__).resolve().parents[1]/'data/cleaned')
    p.add_argument('--bucket',required=True)
    p.add_argument('--prefix',default='curated/aldo_v2')
    p.add_argument('--database',default='aldo_returns_v2')
    p.add_argument('--ddl-out',default='runtime/aws/athena_v2.sql')
    p.add_argument('--execute',action='store_true')
    main(p.parse_args())
