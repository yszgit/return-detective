"""Meaningful v2 regressions: source retention, grain, cutoffs and unsupported inference."""
import argparse
import csv
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

from scripts.prepare_official_data import build
from scripts.validate_official_data import validate
from scripts.export_aws_dataset import make_ddl, upload_plan


def csv_file(path,columns,records):
    with path.open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=columns)
        w.writeheader()
        for row in records:
            w.writerow(row)


def fixture(folder):
    oms_cols=['store_banner','order_number','sku','orderitem_product_name','cnsmr_prof_sid','customer_uid',
              'return_order_number','return_channel','return_creation_date','return_creation_date_tmstmp',
              'last return status','Refund amount','item return qty','reason','Instore return location']
    records=[]
    for order,sku,ret,date,reason,qty,style in [('O1','SKU1','R1','2025-01-01','Defective',1,'TestStyle'),
                                            ('O1','SKU2','R1','2025-01-01','Wrong item',1,'TestStyle'),
                                            ('O2','SKU3','R2','2025-01-02',None,0,None)]:
        records.append(dict(zip(oms_cols,['ALDO_CA',order,sku,style,'private-profile','private-customer',ret,'Web',date,
                          date+' 20:00:00.123 America/New_York','RETURN_COMPLETED',50 if qty else 0,qty,reason,None])))
    csv_file(folder/'oms.csv',oms_cols,records)
    csv_file(folder/'flags.csv',['order_number','sku','Is item final sale?'],[
        {'order_number':'O1','sku':'SKU1','Is item final sale?':'yes'},
        {'order_number':'O1','sku':'SKU2','Is item final sale?':'no'}])
    csv_file(folder/'fees.csv',['return_order_number','restocking revenue'],[
        {'return_order_number':'R1','restocking revenue':'5.00'},
        {'return_order_number':'R9','restocking revenue':'6.95'}])
    order_cols=['Banner','order_number','order_date_est','sku','Style','Size','category name','Requested_QTY','Shipped']
    csv_file(folder/'orders.csv',order_cols,[dict(zip(order_cols,['ALDO_CA','O1','2024-12-20 00:00:00',s,'TestStyle','8','Shoes',1,1])) for s in ['SKU1','SKU2']])
    exch_cols=['Exchange_Confidence','transactions_businessdaydate','transactions_transnumber','Original Order Number',
               'Exchange SKU','Exchange QTY','Return store','Sales']
    csv_file(folder/'exchanges.csv',exch_cols,[
        dict(zip(exch_cols,['CONFIRMED','1/3/2025','TX1','O1','SKU2',1,'STORE1','50'])),
        dict(zip(exch_cols,['ASSUMED','2/1/2025','TX2','O1','SKU2',1,'STORE1','50']))])
    txn_cols=['banner','site_id','region_name','state_code','city_name','postal_code','store_type_description',
              'cluster_group_name','business_date','brand_description','merchandise_category_name','style_name',
              'color_name','main_material_description','fashion_fabric_description','size_value','article_image_url',
              'country_of_origin','transaction_number','consumer_profile_guid','original_transaction_number',
              'original_site_id','channel','return_reason','in_store_return_indicator','return_indicator','price_group',
              'Net_Sales_Retail_Amount','Net_Sales_Units','Net_Sales_Cost_Amount','Gross_Margin_Amount']
    txn=[]
    for date,num,indicator,qty in [('2025-01-01','TX1',0,1),('2025-02-01','TX2',1,-1)]:
        row={c:'value' for c in txn_cols}
        row.update(banner='ALDO_CA',site_id='STORE1',business_date=date,style_name='TestStyle',
                   transaction_number=num,original_transaction_number='TX1',consumer_profile_guid='private-consumer',
                   article_image_url='https://example.com/product.jpg?tracking=private#fragment',
                   in_store_return_indicator='true',return_indicator=indicator,Net_Sales_Retail_Amount='50.125000',
                   Net_Sales_Units=qty,Net_Sales_Cost_Amount='20.125000',Gross_Margin_Amount='30.000000')
        txn.append(row)
    csv_file(folder/'transactions.csv',txn_cols,txn)


class OfficialDataTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        cls.folder=Path(cls.tmp.name)
        fixture(cls.folder)
        cls.key=cls.folder/'test.key'
        cls.key.write_bytes(b'test-only-fixture-key-never-a-secret'*2)
        cls.out=cls.folder/'output'
        args={n:str(cls.folder/(n+'.csv')) for n in ['oms','flags','fees','exchanges','orders','transactions']}
        cls.args=argparse.Namespace(**args,key_file=str(cls.key),out=str(cls.out),work_dir=str(cls.folder/'work'),legacy_dir=None)
        cls.manifest,cls.quality=build(cls.args)
        cls.env={k:os.environ.get(k) for k in ['RD_BACKEND','RD_DATA_DIR','RD_RUNTIME_DIR','RD_DATASET_VERSION']}
        os.environ.update(RD_BACKEND='duckdb',RD_DATA_DIR=str(cls.out),RD_RUNTIME_DIR=str(cls.folder/'runtime'),RD_DATASET_VERSION='2')
        for name in list(sys.modules):
            if name=='rd' or name.startswith('rd.'):
                del sys.modules[name]
        cls.data=importlib.import_module('rd.data')
        cls.tools=importlib.import_module('rd.tools')

    @classmethod
    def tearDownClass(cls):
        for key,value in cls.env.items():
            if value is None: os.environ.pop(key,None)
            else: os.environ[key]=value
        for name in list(sys.modules):
            if name=='rd' or name.startswith('rd.'):
                del sys.modules[name]
        cls.tmp.cleanup()

    def test_all_sources_reconcile_and_validate(self):
        validate(self.out,verbose=False)
        for v in self.quality['source_coverage'].values():
            self.assertEqual(v['source_rows'],v['output_rows'])

    def test_daily_workflow_keeps_invalid_returns_out_of_normal_count(self):
        workflow=importlib.import_module('rd.workflow')
        self.tools.store.reset()
        report=workflow.process_day('2025-01-02')
        self.assertEqual(report['counts']['total'],1)
        self.assertEqual(report['counts']['insufficient'],1)
        self.assertEqual(report['counts']['normal'],0)
        self.assertEqual(report['model_calls'],0)

    def test_daily_workflow_baseline_excludes_current_and_future_days(self):
        workflow=importlib.import_module('rd.workflow')
        self.tools.store.reset()
        report=workflow.process_day('2025-01-01')
        self.assertTrue(report['screens'])
        self.assertTrue(all(s['company_baseline_share']==0 for s in report['screens']))

    def test_fee_is_once_per_transaction_and_not_per_reason(self):
        self.assertEqual(self.data.one('select sum(fee_amount) as n from return_fees')['n'],11.95)
        self.assertEqual(self.data.one('select max(distinct_categories) as n from return_fees')['n'],2)
        self.tools.AS_OF.set('2025-01-05')
        audit=json.loads(self.tools.fee_audit('TestStyle','Quality'))
        self.assertEqual(audit['related_return_transactions'],1)
        self.assertFalse(audit['historical_fee_evidence_available'])
        self.assertIsNone(audit['charged'])
        self.assertIsNone(audit['fees'])
        self.assertEqual(self.data.one('''select sum(fee_amount) as amount from return_fees f join
            (select distinct return_order_number from returns where qty>0) r using(return_order_number)''')['amount'],5)

    def test_undated_financial_facts_cannot_authorize_refund(self):
        self.tools.AS_OF.set('2025-01-05')
        record=json.loads(self.tools.get_return(1))
        self.assertIsNone(record['status'])
        self.assertIsNone(record['refund'])
        self.assertIsNone(record['final_sale'])
        c=self.tools.store.open_case('TestStyle','Quality','2025-01-05','summary','evidence')
        self.tools.store.update_case(c['case_id'],confidence='High')
        result=json.loads(self.tools.waive_restocking_fees(c['case_id']))
        self.assertFalse(result['executed'])
        self.assertIn('refused',result)

    def test_zero_and_missing_facts_survive_without_becoming_false(self):
        row=self.data.one('select * from returns where return_id=3')
        self.assertTrue(row['missing_style'])
        self.assertTrue(row['invalid_quantity'])
        self.assertIsNone(row['final_sale'])
        self.assertFalse(row['eligible_for_detection'])

    def test_cutoff_prevents_future_return_exchange_and_transaction(self):
        self.tools.AS_OF.set('2025-01-01')
        self.assertIn('error',json.loads(self.tools.get_return(3)))
        self.tools.AS_OF.set('2025-01-05')
        exchange=json.loads(self.tools.exchange_evidence('TestStyle'))['evidence']
        self.assertEqual(sum(x['exchange_lines'] for x in exchange),1)
        self.assertEqual(exchange[0]['confidence'],'CONFIRMED')
        transactions=json.loads(self.tools.transaction_context('TestStyle'))['groups']
        self.assertEqual(sum(x['transaction_lines'] for x in transactions),1)

    def test_baseline_excludes_same_day_and_future(self):
        self.assertEqual(self.data.baseline_share('Quality','2025-01-01'),0)
        self.assertEqual(self.data.baseline_share('Quality','2025-01-02'),0.5)
        self.assertRaises(ValueError,self.data.baseline_share,'Quality')

    def test_population_rate_is_unavailable_for_partial_sales(self):
        self.tools.AS_OF.set('2025-01-05')
        result=json.loads(self.tools.sku_return_rate('TestStyle'))
        self.assertFalse(result['population_return_rate_available'])
        self.assertTrue(all(x['return_rate'] is None for x in result['skus']))

    def test_bad_record_is_data_insufficient_not_isolated(self):
        offline=importlib.import_module('rd.offline')
        result=offline.run_scripted(3,'2025-01-05',lambda event:None)
        self.assertEqual(result['triage']['decision'],'DATA_INSUFFICIENT')

    def test_private_identifiers_and_url_tracking_removed(self):
        row=self.data.one('select * from transactions limit 1')
        self.assertNotIn('consumer_profile_guid',row)
        self.assertNotIn('postal_code',row)
        self.assertEqual(row['article_image_url'],'https://example.com/product.jpg')
        self.assertTrue(row['transaction_number'].startswith('RD-TXN-'))

    def test_rebuild_preserves_published_ids_and_tokens(self):
        args=argparse.Namespace(**vars(self.args))
        args.out=str(self.folder/'rebuilt')
        args.work_dir=str(self.folder/'rebuilt-work')
        args.legacy_dir=str(self.out)
        manifest,_=build(args)
        self.assertTrue(manifest['legacy_return_ids_preserved'])
        import duckdb
        c=duckdb.connect()
        diff=c.execute(f"""select count(*) from (
            select return_id,source_record_id,order_number,return_order_number from read_parquet('{self.out}/returns.parquet')
            except all select return_id,source_record_id,order_number,return_order_number from read_parquet('{args.out}/returns.parquet'))""").fetchone()[0]
        self.assertEqual(diff,0)

    def test_manifest_tampering_is_detected(self):
        path=self.out/'manifest.json'
        original=path.read_text()
        altered=json.loads(original)
        altered['tables']['returns']['files'][0]['sha256']='0'*64
        try:
            path.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError,'checksum mismatch'):
                validate(self.out,verbose=False)
        finally:
            path.write_text(original)

    def test_aws_layout_separates_schemas_and_registers_month_partitions(self):
        ddl=make_ddl(self.manifest,'example-private-bucket','curated/aldo_v2','aldo_returns_v2')
        self.assertIn('PARTITIONED BY (`business_month` string)',ddl)
        self.assertIn('MSCK REPAIR TABLE aldo_returns_v2.transactions',ddl)
        self.assertIn('`fee_amount` decimal(18,2)',ddl)
        plan=upload_plan(self.out,self.manifest,'curated/aldo_v2')
        keys=[key for _,key in plan]
        self.assertIn('curated/aldo_v2/returns/returns.parquet',keys)
        self.assertTrue(any('transactions/business_month=2025-01/' in k for k in keys))


if __name__=='__main__':
    unittest.main()
