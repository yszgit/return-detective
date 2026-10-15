import concurrent.futures
import json
from types import SimpleNamespace
from unittest.mock import patch
from rd import agents, data, store, tools
from tests.support import FixtureTest

class ReplayTests(FixtureTest):
    def test_future_return_is_not_visible(self):
        with tools.replay_context("2024-10-22"):
            self.assertIn("error",json.loads(tools.get_return(return_id=243470)))
            self.assertEqual(json.loads(tools.get_return(return_id=212632))["return_date"],"2024-10-22")

    def test_baseline_uses_only_observed_records(self):
        expected=data.one("select sum(case when category='Quality' then 1 else 0 end)*1.0/count(*) as p from returns where return_date<=DATE '2024-10-22'")["p"]
        self.assertAlmostEqual(data.baseline_share("Quality","2024-10-22"),expected,places=6)
        self.assertNotAlmostEqual(expected,.99)

    def test_worker_threads_see_replay_date_and_context_restores(self):
        previous=tools.AS_OF.get()
        with tools.replay_context("2024-10-22"):
            with concurrent.futures.ThreadPoolExecutor(1) as pool:
                self.assertEqual(pool.submit(tools._asof).result(),"2024-10-22")
        self.assertEqual(tools.AS_OF.get(),previous)

    def test_unmatched_sales_cohort_never_returns_a_rate(self):
        with tools.replay_context("2024-11-23"):
            result=json.loads(tools.sku_return_rate(style="Glindafied"))
        self.assertTrue(result["skus"])
        self.assertTrue(all(row["return_rate"] is None and row["lines_sold"] is None for row in result["skus"]))

    def test_offline_preview_does_not_create_cases(self):
        isolated=agents.preview_return(212632,"2024-10-22")
        quality=agents.preview_return(243470,"2024-11-23")
        fit=agents.preview_return(165717,"2024-09-01")
        self.assertEqual(isolated["triage"]["decision"],"ISOLATED")
        self.assertEqual(quality["triage"]["decision"],"INVESTIGATE")
        self.assertEqual(fit["triage"]["category"],"Fit: too big")
        self.assertEqual(store.snapshot()["cases"],{})

class ApprovalTests(FixtureTest):
    def make_case(self):
        case=store.open_case("Glindafied","Quality","2024-11-23","test","evidence")
        store.update_case(case["case_id"],confidence="High")
        return case["case_id"]

    def test_rejection_never_marks_case_executed(self):
        cid=self.make_case()
        approval=store.request_approval(cid,4,"Hold stock",{},"Quality")
        store.decide_approval(approval["approval_id"],False)
        self.assertEqual(store.get_case(cid)["status"],"REJECTED")
        self.assertEqual(store.snapshot()["actions"],[])

    def test_approval_records_one_simulation_even_after_repeated_click(self):
        cid=self.make_case()
        approval=store.request_approval(cid,4,"Hold stock",{},"Quality")
        store.decide_approval(approval["approval_id"],True)
        store.decide_approval(approval["approval_id"],True)
        records=store.snapshot()["actions"]
        self.assertEqual(len(records),1)
        self.assertFalse(records[0]["executed"])
        self.assertEqual(store.get_case(cid)["status"],"APPROVED")

    def test_pending_approval_keeps_case_waiting(self):
        cid=self.make_case()
        first=store.request_approval(cid,4,"Hold",{},"Quality")
        store.request_approval(cid,5,"Outreach",{},"Care")
        store.decide_approval(first["approval_id"],False)
        self.assertEqual(store.get_case(cid)["status"],"AWAITING_APPROVAL")

    def test_duplicate_request_is_not_queued_twice(self):
        cid=self.make_case()
        first=store.request_approval(cid,4,"Hold",{},"Quality")
        second=store.request_approval(cid,4,"Hold",{},"Quality")
        self.assertEqual(first["approval_id"],second["approval_id"])
        self.assertEqual(len(store.snapshot()["approvals"]),1)

    def test_fees_deduplicate_order_rows_and_include_authority_boundary(self):
        cid=self.make_case()
        with tools.replay_context("2024-11-23"):
            audit=json.loads(tools.fee_audit(style="Glindafied",category="Quality"))
            first=json.loads(tools.waive_restocking_fees(case_id=cid))
            second=json.loads(tools.waive_restocking_fees(case_id=cid))
        self.assertEqual(audit["fees"],500)
        self.assertEqual(first["amount_cad"],500)
        self.assertTrue(first["within_authority"])
        self.assertFalse(first["executed"])
        self.assertEqual(first["action_id"],second["action_id"])
        self.assertEqual(len(store.snapshot()["actions"]),1)

    def test_amount_above_authority_requires_approval(self):
        cid=self.make_case()
        with tools.replay_context("2025-01-01"):
            result=json.loads(tools.waive_restocking_fees(case_id=cid))
        self.assertEqual(result["amount_cad"],600)
        self.assertIn("approval_requested",result)
        self.assertEqual(store.snapshot()["actions"],[])

    def test_plan_is_dated_but_not_a_cloud_schedule(self):
        cid=self.make_case()
        with tools.replay_context("2024-11-23"):
            result=json.loads(tools.schedule_verification(case_id=cid))
        self.assertEqual(result["due_date"],"2024-12-14")
        self.assertFalse(result["scheduled"])

class PipelineTests(FixtureTest):
    def finding(self):
        return {"root_cause_class":"Product quality defect","root_cause":"A candidate explanation",
                "confidence":"Low","owner_team":"Quality",
                "hypotheses":[{"hypothesis":name,"verdict":"inconclusive","evidence":"Observed test evidence"}
                              for name in ["quality","fit","handling"]],
                "key_evidence":["return #243470"],"recommended_actions":["Review evidence"]}

    def fake_factory(self, decision="INVESTIGATE", finding=None):
        def factory(name,*args,**kwargs):
            def call(prompt,structured_output_model=None):
                if name=="Triage Agent":
                    value={"decision":decision,"style":"Glindafied","category":"Quality","rationale":"Observed SIGNAL"}
                elif name=="Investigator Agent":
                    value=finding or self.finding()
                else:
                    return "Response proposals are simulations."
                return SimpleNamespace(structured_output=value)
            return call
        return factory

    def test_nested_findings_survive_entire_handoff(self):
        with patch.object(agents,"make_agent",side_effect=self.fake_factory()):
            result=agents.run_pipeline(243470,"2024-11-23",lambda event:None)
        self.assertEqual(result["finding"]["confidence"],"Low")
        self.assertEqual(len(result["finding"]["hypotheses"]),3)
        case=store.get_case(result["case_id"])
        self.assertEqual(case["linked_return_ids"],[243470])
        self.assertEqual(case["verification_due_date"],"2024-12-14")

    def test_existing_case_is_linked_and_not_reinvestigated(self):
        case=store.open_case("Glindafied","Quality","2024-11-20","test","evidence")
        with patch.object(agents,"make_agent",side_effect=self.fake_factory("ATTACH_TO_CASE")) as factory:
            result=agents.run_pipeline(243470,"2024-11-23",lambda event:None)
        self.assertEqual(result["case_id"],case["case_id"])
        self.assertEqual(factory.call_count,1)
        self.assertEqual(store.get_case(case["case_id"])["linked_return_ids"],[243470])

    def test_invalid_confidence_stops_before_case_creation(self):
        bad=self.finding();bad["confidence"]="Definitely"
        with patch.object(agents,"make_agent",side_effect=self.fake_factory(finding=bad)):
            with self.assertRaises(ValueError):
                agents.run_pipeline(243470,"2024-11-23",lambda event:None)
        self.assertEqual(store.snapshot()["cases"],{})

    def test_future_case_is_not_reused_in_historical_investigation(self):
        future=store.open_case("Glindafied","Quality","2025-01-01","future findings","future evidence")
        with patch.object(agents,"make_agent",side_effect=self.fake_factory()):
            result=agents.run_pipeline(243470,"2024-11-23",lambda event:None)
        self.assertNotEqual(result["case_id"],future["case_id"])
        self.assertEqual(store.get_case(future["case_id"])["linked_return_ids"],[])

    def test_future_return_stops_before_model_call(self):
        with patch.object(agents,"make_agent") as factory:
            with self.assertRaises(ValueError):
                agents.run_pipeline(243470,"2024-10-22",lambda event:None)
        factory.assert_not_called()

class AthenaAdapterTests(FixtureTest):
    def test_paginated_results_keep_first_data_row_and_convert_decimal(self):
        class Client:
            def start_query_execution(self,**kwargs):return {"QueryExecutionId":"test"}
            def get_query_execution(self,**kwargs):return {"QueryExecution":{"Status":{"State":"SUCCEEDED"}}}
            def get_query_results(self,**kwargs):
                meta={"ColumnInfo":[{"Name":"amount","Type":"decimal(10,2)"}]}
                if "NextToken" not in kwargs:
                    return {"ResultSet":{"ResultSetMetadata":meta,"Rows":[{"Data":[{"VarCharValue":"amount"}]},{"Data":[{"VarCharValue":"12.50"}]}]},"NextToken":"next"}
                return {"ResultSet":{"ResultSetMetadata":meta,"Rows":[{"Data":[{"VarCharValue":"20.25"}]}]}}
        with patch.object(data,"_athena",return_value=Client()):
            self.assertEqual(data._rows_athena("select amount"),[{"amount":12.5},{"amount":20.25}])

    def test_timeout_requests_query_cancellation(self):
        class Client:
            cancelled=False
            def start_query_execution(self,**kwargs):return {"QueryExecutionId":"test"}
            def get_query_execution(self,**kwargs):return {"QueryExecution":{"Status":{"State":"RUNNING"}}}
            def stop_query_execution(self,**kwargs):self.cancelled=True
        client=Client()
        with patch.object(data,"_athena",return_value=client),patch.object(data.time,"monotonic",side_effect=[0,121]):
            with self.assertRaises(TimeoutError):
                data._rows_athena("select 1")
        self.assertTrue(client.cancelled)
