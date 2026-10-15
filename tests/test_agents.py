"""Check model-free stage handoffs and role permissions after the module split."""
import importlib
import json
import unittest
from unittest.mock import Mock, patch


class AgentPipelineTests(unittest.TestCase):
    def setUp(self):
        self.agents = importlib.import_module("rd.agents")
        self.pipeline = importlib.import_module("rd.agents.pipeline")

    def test_noninvestigation_decisions_stop_before_other_agents(self):
        for decision in ("ISOLATED", "WATCH", "ATTACH_TO_CASE"):
            with self.subTest(decision=decision):
                triage_result = {"decision": decision, "style": "TestStyle", "category": "Quality"}
                triage = Mock(return_value=json.dumps(triage_result))
                events = []
                with patch.object(self.pipeline, "create_triage_agent", return_value=triage), \
                     patch.object(self.pipeline, "create_investigator_agent") as investigator, \
                     patch.object(self.pipeline, "create_response_agent") as response, \
                     patch.object(self.pipeline.tools, "AS_OF") as as_of:
                    result = self.agents.run_pipeline(123, "2026-01-31", events.append)
                self.assertEqual(result, {"triage": triage_result})
                as_of.set.assert_called_once_with("2026-01-31")
                investigator.assert_not_called()
                response.assert_not_called()
                self.assertEqual(events[-1]["data"], triage_result)

    def test_complete_nested_finding_reaches_response_in_stage_order(self):
        triage_result = {"decision": "INVESTIGATE", "style": "TestStyle", "category": "Quality",
                         "rationale": "Several related returns"}
        finding = {"root_cause": "Potential quality defect", "confidence": "High",
                   "owner_team": "Quality & Sourcing", "key_evidence": ["return 123"],
                   "hypotheses": [{"hypothesis": "Product quality", "verdict": "supported",
                                   "evidence": 'A note with {braces} and "quotes"'}]}
        narrative = "Investigation narrative.\n" + json.dumps(finding)
        calls, events = [], []

        def answer(stage, value):
            def invoke(prompt):
                calls.append((stage, prompt))
                return value
            return Mock(side_effect=invoke)

        triage = answer("triage", json.dumps(triage_result))
        investigator = answer("investigator", narrative)
        response = answer("response", "Case recorded; stock hold awaits approval.")
        with patch.object(self.pipeline, "create_triage_agent", return_value=triage), \
             patch.object(self.pipeline, "create_investigator_agent", return_value=investigator), \
             patch.object(self.pipeline, "create_response_agent", return_value=response), \
             patch.object(self.pipeline.tools, "AS_OF"):
            result = self.agents.run_pipeline(123, "2026-01-31", events.append)

        self.assertEqual([stage for stage, _ in calls], ["triage", "investigator", "response"])
        self.assertIn("Several related returns", calls[1][1])
        self.assertIn(json.dumps(finding), calls[2][1])
        self.assertIn(narrative, calls[2][1])
        self.assertEqual(result, {"triage": triage_result, "finding": finding,
                                  "briefing": "Case recorded; stock hold awaits approval."})
        self.assertEqual([event["data"] for event in events if event["type"] == "decision"],
                         [triage_result, finding])
        self.assertEqual(events[-1]["type"], "briefing")

    def test_roles_keep_their_tools_models_and_trace_callback(self):
        shared = importlib.import_module("rd.agents.shared")
        tools = self.pipeline.tools
        emit = Mock()
        instances = [object(), object(), object()]
        with patch.multiple(shared, MODEL_ID="primary-model", FAST_MODEL_ID="fast-model", GUARDRAIL_ID=None), \
             patch.object(shared, "Agent", side_effect=instances) as agent, \
             patch.object(shared, "BedrockModel") as model:
            actual = [self.agents.create_triage_agent(emit), self.agents.create_investigator_agent(emit),
                      self.agents.create_response_agent(emit)]
            self.assertEqual(actual, instances)
            self.assertEqual([call.kwargs["model_id"] for call in model.call_args_list],
                             ["fast-model", "primary-model", "fast-model"])
            for call, name, allowed_tools in zip(agent.call_args_list,
                    ["Triage Agent", "Investigator Agent", "Response Agent"],
                    [tools.TRIAGE_TOOLS, tools.INVESTIGATOR_TOOLS, tools.RESPONSE_TOOLS]):
                self.assertEqual(call.kwargs["name"], name)
                self.assertIs(call.kwargs["tools"], allowed_tools)
                self.assertIs(call.kwargs["hooks"][0].emit, emit)
            self.agents._model("checker-model")
            self.assertEqual(model.call_args.kwargs["model_id"], "checker-model")

    def test_parser_selects_complete_final_object_and_handles_missing_json(self):
        expected = {"confidence": "High", "hypotheses": [{"evidence": 'text } { "quoted"'}]}
        text = 'Narrative {not JSON}. Previous: {"previous": true}\nFinal:\n' + json.dumps(expected)
        self.assertEqual(self.agents.extract_json(text), expected)
        self.assertEqual(self.agents.extract_json("No JSON result."), {})


if __name__ == "__main__":
    unittest.main()
