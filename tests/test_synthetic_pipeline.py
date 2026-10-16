"""No-AWS, no-Bedrock smoke test for the synthetic Return Detective data layer.

It regenerates the synthetic Parquet files into a temp directory, points the DuckDB
backend at them (RD_BACKEND=duckdb, RD_DATA_DIR=<temp>), and checks:

  1. all four Parquet files exist and load through rd.data with the expected columns;
  2. the three seeded scenarios reach SIGNAL on the UNCHANGED thresholds in rd/detect.py,
     and the negative-control style never does;
  3. the get_return tool exposes no customer identifier and return_ids are unique;
  4. the human-approval authority gate in the action tools behaves correctly without any LLM.

Run from the repository root:
    RD_BACKEND=duckdb python -m unittest tests.test_synthetic_pipeline -v
"""
import importlib
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(__file__)
APP = os.path.join(HERE, "..")
SCRIPTS = os.path.join(APP, "scripts")
sys.path.insert(0, os.path.abspath(APP))
sys.path.insert(0, os.path.abspath(SCRIPTS))

AS_OF = "2026-01-31"
EXPECTED_RETURN_COLS = {
    "return_id", "banner", "order_number", "sku", "style", "return_order_number", "channel",
    "return_date", "status", "refund", "qty", "raw_reason", "store", "category",
    "restocking_fee", "final_sale", "aldo_fault",
}


def _reload_rd():
    """Re-import rd.* so RD_DATA_DIR / RD_BACKEND take effect for the module-level globals."""
    for m in [m for m in list(sys.modules) if m == "rd" or m.startswith("rd.")]:
        del sys.modules[m]
    data = importlib.import_module("rd.data")
    detect = importlib.import_module("rd.detect")
    tools = importlib.import_module("rd.tools")
    store = importlib.import_module("rd.store")
    return data, detect, tools, store


class SyntheticPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.data_dir = cls._tmp.name
        # generate into the temp dir
        import generate_synthetic_data as gen
        gen.main(type("A", (), {"out": cls.data_dir}))
        os.environ["RD_BACKEND"] = "duckdb"
        os.environ["RD_DATA_DIR"] = cls.data_dir
        os.environ["RD_RUNTIME_DIR"] = os.path.join(cls.data_dir, "runtime")
        cls.data, cls.detect, cls.tools, cls.store = _reload_rd()

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def test_parquet_files_exist(self):
        for name in ("returns", "sku_sales", "exchanges", "baseline"):
            self.assertTrue(os.path.exists(os.path.join(self.data_dir, f"{name}.parquet")), name)
        self.assertTrue(os.path.exists(os.path.join(self.data_dir, "_SYNTHETIC.txt")))

    def test_returns_schema_loads(self):
        row = self.data.one("select * from returns limit 1")
        self.assertIsNotNone(row)
        self.assertEqual(EXPECTED_RETURN_COLS, set(row.keys()))

    def test_baseline_matches_returns(self):
        # baseline.share must equal category_count / total over the actual returns
        total = self.data.one("select count(*) as n from returns")["n"]
        for b in self.data.rows("select category, n, share from baseline"):
            self.assertAlmostEqual(b["share"], b["n"] / total, places=4, msg=b["category"])

    def test_quality_scenario_signals(self):
        res = {r["category"]: r for r in self.detect.screen_all("SYNTH-RiverLoafer", AS_OF)}
        self.assertEqual(res["Quality"]["level"], "SIGNAL", res["Quality"])

    def test_fit_scenario_signals(self):
        res = {r["category"]: r for r in self.detect.screen_all("SYNTH-TrailRunner", AS_OF)}
        self.assertEqual(res["Fit: too big"]["level"], "SIGNAL", res["Fit: too big"])

    def test_damage_scenario_signals(self):
        res = {r["category"]: r for r in self.detect.screen_all("SYNTH-CoastalBoot", AS_OF)}
        self.assertEqual(res["Damaged in transit"]["level"], "SIGNAL", res["Damaged in transit"])

    def test_control_never_signals(self):
        res = self.detect.screen_all("SYNTH-EverydaySneaker", AS_OF)
        self.assertEqual([r["category"] for r in res if r["level"] == "SIGNAL"], [])

    def test_isolated_case_not_yet_signal(self):
        # A single early Quality return should screen below SIGNAL.
        s = self.detect.screen("SYNTH-RiverLoafer", "Quality", "2026-01-07")
        self.assertNotEqual(s["level"], "SIGNAL", s)

    def test_get_return_hides_customer_identity(self):
        self.tools.AS_OF.set(AS_OF)
        row = json.loads(self.tools.get_return(940))
        self.assertNotIn("customer_uid", row)
        self.assertNotIn("error", row)

    def test_return_ids_unique(self):
        n = self.data.one("select count(*) as n from returns")["n"]
        d = self.data.one("select count(distinct return_id) as n from returns")["n"]
        self.assertEqual(n, d)

    def test_approval_gate_refuses_low_confidence(self):
        self.tools.AS_OF.set(AS_OF)
        self.store.reset()
        c = self.store.open_case("SYNTH-RiverLoafer", "Quality", AS_OF, "seeded", "evidence")
        # No findings recorded yet (confidence is None) -> fee waiver must refuse.
        out = json.loads(self.tools.waive_restocking_fees(c["case_id"]))
        self.assertIn("refused", out, out)

    def test_approval_gate_executes_or_requests_when_authorized(self):
        self.tools.AS_OF.set(AS_OF)
        self.store.reset()
        c = self.store.open_case("SYNTH-RiverLoafer", "Quality", AS_OF, "seeded", "evidence")
        self.store.update_case(c["case_id"], confidence="High", root_cause="defect",
                               owner_team="Quality & Sourcing")
        out = json.loads(self.tools.waive_restocking_fees(c["case_id"]))
        # ALDO-fault + High confidence: either executed within authority or escalated for approval.
        self.assertTrue(out.get("executed") is True or "approval_requested" in out, out)
        self.assertNotIn("refused", out)

    def test_high_stakes_actions_require_approval(self):
        self.tools.AS_OF.set(AS_OF)
        self.store.reset()
        c = self.store.open_case("SYNTH-RiverLoafer", "Quality", AS_OF, "seeded", "evidence")
        self.store.update_case(c["case_id"], confidence="High", root_cause="defect",
                               owner_team="Quality & Sourcing")
        hold = json.loads(self.tools.request_stock_hold(c["case_id"], "all DCs"))
        claim = json.loads(self.tools.draft_supplier_claim(c["case_id"], "claim text"))
        self.assertIn("approval_requested", hold, hold)
        self.assertIn("approval_requested", claim, claim)

    def test_cli_runs_after_relocation_from_another_directory(self):
        result = subprocess.run(
            [sys.executable, os.path.join(APP, "run_demo.py"), "syn_quality", "--scripted"],
            cwd=self.data_dir, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('"decision": "INVESTIGATE"', result.stdout)
        self.assertIn("APPROVAL", result.stdout)

    def test_backtest_keeps_generated_results_out_of_historical_file(self):
        from pathlib import Path
        historical = Path(APP, "evaluation", "results", "cases_backtest.csv")
        original = historical.read_bytes()
        result = subprocess.run(
            [sys.executable, os.path.join(APP, "evaluation", "backtest.py")],
            cwd=self.data_dir, capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue(Path(self.data_dir, "runtime", "evaluation", "cases_backtest.csv").is_file())
        self.assertEqual(historical.read_bytes(), original)

    def test_ui_handles_missing_data_and_scripted_synthetic_run(self):
        code = '''
import os
from streamlit.testing.v1 import AppTest
app = AppTest.from_file(os.environ["RD_TEST_APP"]).run(timeout=30)
assert not app.exception, [e.message for e in app.exception]
if os.environ["RD_TEST_MISSING"] == "1":
    assert next(b for b in app.button if b.label == "Process day's returns").disabled
else:
    assert app.radio[0].options == ['Returns monitor', 'Case workspace', 'Approvals & follow-up']
    import datetime as dt
    next(d for d in app.date_input if d.label == 'Replay date').set_value(dt.date(2026, 1, 30)).run()
    next(b for b in app.button if b.label == "Process day's returns").click().run(timeout=30)
    assert not app.exception, [e.message for e in app.exception]
    assert app.session_state["events"] == [], 'Daily screening must not invoke model agents'
    signal = next(s for s in app.selectbox if s.label == 'Select signal')
    index = next(i for i,label in enumerate(signal.options) if 'RiverLoafer' in label and 'Quality' in label)
    signal.select_index(index).run()
    next(b for b in app.button if b.label == 'Start investigation').click().run(timeout=30)
    assert not app.exception, [e.message for e in app.exception]
    app.radio[0].set_value('Returns monitor').run()
    next(s for s in app.selectbox if s.label == 'Show returns').set_value('Linked to case').run()
    assert any('Case' in frame.value and frame.value['Case'].str.startswith('CASE-').any()
               for frame in app.dataframe), 'Newly investigated returns must appear without reprocessing'
    app.radio[0].set_value('Case workspace').run()
    assert not app.exception, [e.message for e in app.exception]
    assert any('Current likely explanation' in item.value for item in app.markdown)
    app.radio[0].set_value('Approvals & follow-up').run()
    assert not app.exception, [e.message for e in app.exception]
    approve = next(b for b in app.button if b.label == 'Approve proposal')
    assert approve.disabled
    next(t for t in app.text_input if t.label == 'Reviewer name').set_value('Fixture reviewer').run()
    next(b for b in app.button if b.label == 'Approve proposal').click().run()
    assert not app.exception, [e.message for e in app.exception]
    from rd import store
    assert any(a['status'] == 'APPROVED' for a in store.snapshot()['approvals'])
'''
        for missing in (True, False):
            with self.subTest(missing_data=missing):
                env = dict(os.environ, RD_TEST_APP=os.path.abspath(os.path.join(APP, "app.py")),
                           RD_TEST_MISSING="1" if missing else "0",
                           RD_MODEL_ID='', RD_FAST_MODEL_ID='', RD_STORE_BACKEND='json',
                           RD_DATASET_VERSION='1',
                           RD_DATA_DIR=os.path.join(self.data_dir, "missing") if missing else self.data_dir,
                           RD_RUNTIME_DIR=os.path.join(self.data_dir, "ui-runtime"))
                result = subprocess.run([sys.executable, "-c", code], env=env,
                                        capture_output=True, text=True, timeout=90)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
