import datetime as dt
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import duckdb
from rd import data, store

def make_fixture(directory):
    connection = duckdb.connect()
    connection.execute("""create table returns (
        return_id bigint, banner varchar, order_number varchar, sku varchar, style varchar,
        return_order_number varchar, channel varchar, return_date date, status varchar,
        refund double, qty integer, raw_reason varchar, store varchar, category varchar,
        restocking_fee double, final_sale boolean, aldo_fault boolean)""")
    records = []
    def add(rid, style, category, day, fee=0, order=None):
        records.append((rid, "TEST", "ORDER-"+str(rid), style+"-SKU", style, order or "RETURN-"+str(rid),
            "online", day, "completed", 80., 1, category, "STORE-"+str(rid%8), category, fee, False, category=="Quality"))
    for i in range(200):
        add(i+1, "Background", "Preference", "2024-08-01")
    for i in range(5):
        add(1000+i, "Background", "Quality", "2024-08-01")
    add(212632, "Glindafied", "Quality", "2024-10-22")
    for i in range(4):
        add(243466+i, "Glindafied", "Quality", f"2024-11-0{i+1}", 300 if i<2 else 0,
            "DUPLICATED-FEE-ORDER" if i<2 else None)
    add(243470, "Glindafied", "Quality", "2024-11-23", 200)
    add(999999, "Glindafied", "Quality", "2025-01-01", 100)
    for i in range(20):
        add(165698+i, "Wellsloafer_wm", "Fit: too big", (dt.date(2024,8,13)+dt.timedelta(days=i)).isoformat())
    for i in range(5):
        add(165600+i, "Wellsloafer_wm", "Preference", "2024-08-20")
    connection.executemany("insert into returns values ("+",".join(["?"]*17)+")", records)
    connection.execute("create table sku_sales as select distinct sku, 100000 as lines_sold from returns")
    connection.execute("create table exchanges(exchange_date date, order_number varchar, qty integer)")
    connection.execute("create table baseline as select 'Quality' as category, .99 as share")
    for table in data.TABLES:
        path=str(directory / (table+".parquet")).replace("'", "''")
        connection.execute(f"copy {table} to '{path}' (format parquet)")
    connection.close()

class FixtureTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="rd-tests-")
        self.root = Path(self.temporary.name)
        make_fixture(self.root)
        self.patches = [patch.object(data,"BACKEND","duckdb"), patch.object(data,"DATA_DIR",str(self.root)),
                        patch.object(store,"RUNTIME_DIR",str(self.root/"runtime"))]
        for item in self.patches:
            item.start()
        self.addCleanup(self.temporary.cleanup)
        for item in self.patches:
            self.addCleanup(item.stop)
