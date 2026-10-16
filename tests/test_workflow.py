"""Daily screening, deduplication and replay-date guards, without AWS/models."""
import contextlib
import importlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


class WorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.tmp.name)
        from scripts.generate_synthetic_data import main
        with contextlib.redirect_stdout(io.StringIO()):
            main(type('Args', (), {'out': str(cls.folder / 'data')}))
        cls.env = patch.dict(os.environ, RD_BACKEND='duckdb', RD_DATASET_VERSION='1',
                             RD_DATA_DIR=str(cls.folder / 'data'), RD_RUNTIME_DIR=str(cls.folder / 'runtime'),
                             RD_STORE_BACKEND='json', RD_STATE_TABLE='', RD_STORE_NAMESPACE='workflow-test')
        cls.env.start()
        for name in list(sys.modules):
            if name == 'rd' or name.startswith('rd.'):
                del sys.modules[name]
        cls.workflow = importlib.import_module('rd.workflow')
        cls.store = importlib.import_module('rd.store')
        cls.data = importlib.import_module('rd.data')
        cls.detect = importlib.import_module('rd.detect')

    @classmethod
    def tearDownClass(cls):
        cls.env.stop()
        cls.tmp.cleanup()

    def setUp(self):
        self.store.reset()

    def test_grouped_screen_matches_existing_policy_and_queries_are_bounded(self):
        with patch.object(self.data, 'rows', wraps=self.data.rows) as query:
            report = self.workflow.process_day('2026-01-30')
        self.assertLessEqual(query.call_count, 3)
        self.assertEqual(report['model_calls'], 0)
        self.assertGreater(report['counts']['total'], 0)
        self.assertEqual(sum(report['counts'][key] for key in ('normal', 'watch', 'signal', 'insufficient')),
                         report['counts']['total'])
        for expected in report['screens']:
            actual = self.detect.screen(expected['style'], expected['category'], '2026-01-30')
            self.assertEqual(actual, expected)
        pairs = [(c['style'], c['category']) for c in report['candidates']]
        self.assertEqual(len(set(pairs)), len(pairs))
        self.assertIn(('SYNTH-RiverLoafer', 'Quality'), pairs)
        self.assertEqual(self.store.snapshot()['cases'], {})

    def test_existing_case_links_once_without_opening_another(self):
        case = self.store.open_case('SYNTH-RiverLoafer', 'Quality', '2026-01-30', 'case', 'evidence')
        first = self.workflow.process_day('2026-01-30')
        count = len(self.store.snapshot()['actions'])
        second = self.workflow.process_day('2026-01-30')
        self.assertGreater(first['counts']['linked_returns'], 0)
        self.assertEqual(len(self.store.snapshot()['actions']), count)
        self.assertEqual(len(self.store.snapshot()['cases']), 1)
        self.assertEqual(first['counts'], second['counts'])
        self.assertTrue(self.store.get_case(case['case_id'])['linked_return_ids'])
        self.assertNotIn(('SYNTH-RiverLoafer', 'Quality'), [(c['style'], c['category']) for c in second['candidates']])

    def test_explicit_investigation_persists_evidence_and_does_not_duplicate(self):
        report = self.workflow.process_day('2026-01-30')
        candidate = next(c for c in report['candidates'] if c['category'] == 'Quality')
        events = []
        result = self.workflow.investigate_signal(candidate, report['as_of'], events.append, scripted=True)
        case = self.store.get_case(result['case_id'])
        self.assertEqual(case['screen_evidence']['return_ids'], candidate['return_ids'])
        self.assertTrue(set(candidate['return_ids']).issubset(case['linked_return_ids']))
        actions = len(self.store.snapshot()['actions'])
        again = self.workflow.investigate_signal(candidate, report['as_of'], events.append, scripted=True)
        self.assertEqual(again['outcome'], 'ATTACHED_TO_CASE')
        self.assertEqual(again['model_calls'], 0)
        self.assertEqual(len(self.store.snapshot()['actions']), actions)
        self.assertEqual(len(self.store.snapshot()['cases']), 1)

    def test_unprocessed_signal_and_earlier_replay_are_rejected(self):
        with self.assertRaises(ValueError):
            self.workflow.investigate_signal({'style': 'SYNTH-RiverLoafer', 'category': 'Quality'},
                                             '2026-01-29', lambda e: None, scripted=True)
        self.store.open_case('Future', 'Quality', '2026-01-30', '', '')
        with self.assertRaisesRegex(ValueError, 'separate workspace'):
            self.workflow.process_day('2026-01-29')

    def test_failed_partial_case_can_be_retried_without_duplicates(self):
        report = self.workflow.process_day('2026-01-30')
        candidate = next(c for c in report['candidates'] if c['category'] == 'Quality')
        offline = importlib.import_module('rd.offline')
        def interrupted(style, category, emit, **kwargs):
            self.store.open_case(style, category, report['as_of'], 'partial', 'evidence')
            raise RuntimeError('fixture interruption')
        with patch.object(offline, 'investigate_scripted', side_effect=interrupted):
            with self.assertRaisesRegex(RuntimeError, 'fixture interruption'):
                self.workflow.investigate_signal(candidate, report['as_of'], lambda e: None, scripted=True)
        partial = next(iter(self.store.snapshot()['cases'].values()))
        self.assertTrue(partial['workflow_error'])
        refreshed = self.workflow.process_day(report['as_of'])
        self.assertIn((candidate['style'], candidate['category']),
                      [(c['style'], c['category']) for c in refreshed['candidates']])
        result = self.workflow.investigate_signal(candidate, report['as_of'], lambda e: None, scripted=True)
        self.assertEqual(result['case_id'], partial['case_id'])
        self.assertFalse(self.store.get_case(partial['case_id'])['workflow_error'])
        self.assertEqual(len(self.store.snapshot()['cases']), 1)

    def test_empty_day_is_a_zero_model_result(self):
        report = self.workflow.process_day('2030-01-01')
        self.assertEqual(report['counts']['total'], 0)
        self.assertEqual(report['model_calls'], 0)

    def test_a_running_dated_operation_cannot_be_overlapped(self):
        with self.workflow.exclusive_run():
            with self.assertRaisesRegex(ValueError, 'Another investigation'):
                self.workflow.process_day('2026-01-30')


if __name__ == '__main__':
    unittest.main()
