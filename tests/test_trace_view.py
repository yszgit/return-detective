"""Use saved tool facts, preserving window and transaction/return grain."""
import json
import unittest

from rd.trace_view import steps


class TraceViewTests(unittest.TestCase):
    def test_repeated_tools_keep_their_own_window_category_and_result(self):
        events = []
        for days, category, count in [(28, 'Quality', 142), (60, 'No merchandise', 194)]:
            events += [{'type': 'tool_call', 'agent': 'Investigator', 'tool': 'spread_analysis',
                        'input': {'style': 'Fixture', 'category': category, 'days': days}},
                       {'type': 'tool_result', 'agent': 'Investigator', 'tool': 'spread_analysis',
                        'status': 'success', 'output': json.dumps({'total': count})}]
        events += [{'type': 'tool_call', 'agent': 'Response', 'tool': 'fee_audit', 'input': {}},
                   {'type': 'tool_result', 'agent': 'Response', 'tool': 'fee_audit',
                    'output': json.dumps({'related_return_transactions': 194, 'historical_fee_evidence_available': False})}]
        rows = steps({'as_of': '2024-12-14', 'events': events}, {'style': 'Fixture', 'category': 'Quality'})
        self.assertIn('2024-11-17 to 2024-12-14', rows[0]['Evidence scope'])
        self.assertIn('142 Quality return records', rows[0]['Observed count'])
        self.assertIn('No merchandise', rows[1]['Evidence scope'])
        self.assertIn('194 related return transactions', rows[2]['Observed count'])
        self.assertEqual(rows[2]['Outcome'], 'Historical fee evidence withheld')

    def test_unfinished_or_truncated_output_is_not_invented_as_a_count(self):
        trace = {'events': [{'type': 'tool_call', 'agent': 'Investigator', 'tool': 'style_reason_mix', 'input': {}},
                            {'type': 'tool_result', 'agent': 'Investigator', 'tool': 'style_reason_mix', 'output': '{"truncated"'}]}
        row = steps(trace, {'style': 'Fixture'})[0]
        self.assertIn('cutoff not recorded', row['Evidence scope'])
        self.assertNotIn('Observed count', row)
