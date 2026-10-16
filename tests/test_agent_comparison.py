"""Acceptance scoring must reject unsafe actions and preserve missing telemetry."""
import importlib
import unittest
from types import SimpleNamespace

from evaluation.compare_agents import score


class AgentComparisonTests(unittest.TestCase):
    def test_matching_triage_cannot_hide_an_unapproved_high_tier_action(self):
        spec = {'expected_decision': 'INVESTIGATE', 'expected_case': True}
        db = {'cases': {'c': {'owner_team': 'Quality'}}, 'approvals': [],
              'actions': [{'tier': 4, 'executed_by': 'agent'}]}
        checks = score(spec, {'triage': {'decision': 'INVESTIGATE'}}, db)
        self.assertTrue(checks['decision'])
        self.assertFalse(checks['high_tier_actions_require_human_approval'])

    def test_sdk_usage_is_measured_and_missing_usage_remains_unknown(self):
        shared = importlib.import_module('rd.agents.shared')
        events = []
        shared.invoke_agent(lambda _: 'answer', 'prompt', 'Investigator Agent', events.append)
        self.assertIsNone(events[-1]['data']['input_tokens'])
        result = SimpleNamespace(metrics=SimpleNamespace(get_summary=lambda: {
            'total_cycles': 2, 'accumulated_usage': {'inputTokens': 100, 'outputTokens': 25}}))
        shared.invoke_agent(lambda _: result, 'prompt', 'Investigator Agent', events.append)
        self.assertEqual(events[-1]['data']['input_tokens'], 100)
        self.assertEqual(events[-1]['data']['model_cycles'], 2)


if __name__ == '__main__':
    unittest.main()
