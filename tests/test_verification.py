"""Exercise real case transitions with isolated storage; no AWS/model requests."""
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch


class VerificationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, RD_BACKEND='duckdb', RD_DATASET_VERSION='1',
                              RD_STORE_BACKEND='json', RD_RUNTIME_DIR=self.tmp.name)
        self.env.start()
        for name in list(sys.modules):
            if name == 'rd' or name.startswith('rd.'):
                del sys.modules[name]
        self.store = importlib.import_module('rd.store')
        self.tools = importlib.import_module('rd.tools')
        self.verification = importlib.import_module('rd.verification')
        self.case = self.store.open_case('Fixture', 'Quality', '2025-01-01', 'fixture', 'synthetic')
        self.cid = self.case['case_id']
        self.store.update_case(self.cid, root_cause='Original quality hypothesis', confidence='High',
                               hypotheses=[{'hypothesis': 'Quality', 'verdict': 'supported', 'evidence': 'old'}])
        self.tools.AS_OF.set('2025-01-01')
        json.loads(self.tools.schedule_verification(self.cid, 21))
        self.coverage = patch.object(self.verification, 'one', return_value={'through_date': '2025-03-31'})
        self.coverage.start()
        self.evidence = patch.object(self.tools, 'verify_case', return_value=json.dumps(self.screens()))
        self.verify_tool = self.evidence.start()

    def tearDown(self):
        self.evidence.stop()
        self.coverage.stop()
        self.env.stop()
        self.tmp.cleanup()

    @staticmethod
    def screens(level='NORMAL', count=20):
        return {'opened': {'level': 'SIGNAL', 'style_returns': 20, 'category_returns': 8},
                'now': {'level': level, 'style_returns': count, 'category_returns': 0 if level == 'NORMAL' else 8}}

    def mitigation(self):
        self.store.log_action(self.cid, 2, 'Waive restocking fees', {'amount_cad': 5, 'return_ids': [1]})

    def test_schedule_is_persisted_and_duplicate_does_not_postpone(self):
        self.tools.AS_OF.set('2025-01-02')
        value = json.loads(self.tools.schedule_verification(self.cid, 21))
        self.assertEqual(value['due_on'], '2025-01-22')
        self.assertEqual(len(self.store.snapshot()['actions']), 1)

    def test_early_and_pending_approval_checks_do_not_close_case(self):
        self.assertEqual(self.verification.check_case(self.cid, '2025-01-02', retry_review=True)['outcome'], 'NOT_DUE')
        self.store.request_approval(self.cid, 4, 'Hold stock', {}, 'QA')
        self.assertEqual(self.verification.check_case(self.cid, '2025-01-22')['outcome'], 'WAITING_APPROVAL')
        self.verify_tool.assert_not_called()

    def test_missing_coverage_and_sparse_evidence_cannot_prove_resolution(self):
        self.assertEqual(self.verification.check_case(self.cid, '2025-04-01')['outcome'], 'DATA_UNAVAILABLE')
        self.verify_tool.return_value = json.dumps(self.screens(count=0))
        self.assertEqual(self.verification.check_case(self.cid, '2025-01-22')['outcome'], 'INSUFFICIENT_EVIDENCE')
        self.assertNotEqual(self.store.get_case(self.cid)['status'], 'CLOSED')

    def test_no_intervention_does_not_become_a_success_claim(self):
        self.assertEqual(self.verification.check_case(self.cid, '2025-01-22')['outcome'], 'NO_RECORDED_INTERVENTION')

    def test_subsided_signal_closes_once_without_claiming_causal_savings(self):
        self.mitigation()
        first = self.verification.check_case(self.cid, '2025-01-22')
        self.assertEqual(first['outcome'], 'SIGNAL_SUBSIDED')
        self.assertFalse(first['causal_effect_established'])
        self.assertEqual(self.store.get_case(self.cid)['status'], 'CLOSED')
        self.assertEqual(self.verification.check_case(self.cid, '2025-01-22')['outcome'], 'ALREADY_CLOSED')
        self.assertEqual(len(self.store.get_case(self.cid)['verification_checks']), 1)

    def test_persistence_reuses_case_and_passes_previous_hypothesis_to_agents(self):
        pipeline = importlib.import_module('rd.agents.pipeline')
        self.verify_tool.return_value = json.dumps(self.screens(level='SIGNAL'))

        def review(*args, **kwargs):
            self.assertEqual(kwargs['case_id'], self.cid)
            self.assertEqual(kwargs['context']['prior_case']['root_cause'], 'Original quality hypothesis')
            self.store.update_case(self.cid, root_cause='Revised handling hypothesis', confidence='Medium')
            self.verification.schedule(self.cid, '2025-01-22')

        with patch.object(pipeline, 'investigate_and_respond', side_effect=review) as investigate:
            result = self.verification.check_case(self.cid, '2025-01-22')
            self.assertEqual(result['outcome'], 'REOPENED')
            self.verification.check_case(self.cid, '2025-01-22')
        investigate.assert_called_once()
        case = self.store.get_case(self.cid)
        self.assertEqual(case['root_cause'], 'Revised handling hypothesis')
        self.assertEqual(case['verification']['due_on'], '2025-02-12')
        self.assertEqual(len(self.store.snapshot()['cases']), 1)

    def test_failed_followup_stays_reopened_and_requires_explicit_retry(self):
        pipeline = importlib.import_module('rd.agents.pipeline')
        self.verify_tool.return_value = json.dumps(self.screens(level='WATCH'))
        with patch.object(pipeline, 'investigate_and_respond', side_effect=RuntimeError('model unavailable')):
            with self.assertRaises(RuntimeError):
                self.verification.check_case(self.cid, '2025-01-22')
        self.assertEqual(self.store.get_case(self.cid)['status'], 'REOPENED')
        with patch.object(pipeline, 'investigate_and_respond') as investigate:
            self.verification.check_case(self.cid, '2025-01-22')
            investigate.assert_not_called()
            self.verification.check_case(self.cid, '2025-01-22', retry_review=True)
            investigate.assert_called_once()
        self.assertEqual(len(self.store.get_case(self.cid)['verification_checks']), 1)

    def test_rejected_and_approved_proposals_cannot_be_replayed_as_new(self):
        a = self.store.request_approval(self.cid, 4, 'Hold stock', {'scope': 'fixture'}, 'QA')
        self.store.decide_approval(a['approval_id'], False)
        repeated = self.store.request_approval(self.cid, 4, 'Hold stock', {'scope': 'fixture'}, 'QA')
        self.assertEqual(repeated['status'], 'REJECTED')
        self.assertEqual(len(self.store.snapshot()['approvals']), 1)

    def test_approved_fee_is_in_ledger_and_cannot_be_waived_twice(self):
        self.store.request_approval(self.cid, 2, 'Waive restocking fees',
                                     {'amount_cad': 600, 'return_ids': [999], 'returns_refunded': 1}, 'Care')
        approval = self.store.snapshot()['approvals'][0]
        self.store.decide_approval(approval['approval_id'], True)
        with patch.object(self.tools, 'rows', return_value=[{'return_id': 999, 'restocking_fee': 600}]):
            value = json.loads(self.tools.waive_restocking_fees(self.cid))
        self.assertTrue(value['already_waived'])
        self.assertEqual(self.store.get_case(self.cid)['fees_waived_cad'], 600)


if __name__ == '__main__':
    unittest.main()
