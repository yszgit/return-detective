"""Workspace deletion must be scoped, backed up, and reversible."""
import importlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


class WorkspaceStateTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.folder = Path(self.temp.name)
        self.env = patch.dict(os.environ, RD_BACKEND='duckdb', RD_DATASET_VERSION='1',
                              RD_STORE_BACKEND='json', RD_STATE_TABLE='', RD_STORE_NAMESPACE='delete-fixture',
                              RD_RUNTIME_DIR=str(self.folder / 'runtime'))
        self.env.start()
        for name in list(sys.modules):
            if name == 'rd' or name.startswith('rd.'):
                del sys.modules[name]
        self.module = importlib.import_module('rd.workspace_state')
        self.store = self.module.store
        case = self.store.open_case('Fixture', 'Quality', '2025-02-27', 'fixture', 'fixture')
        self.store.request_approval(case['case_id'], 4, 'Fixture action', {}, 'Fixture reviewer')
        self.store.log_action(case['case_id'], 0, 'Fixture history', {})
        self.report = self.module._report_path('2025-02-27.json')
        self.report.parent.mkdir(parents=True)
        self.report.write_text(json.dumps({'source_key': self.module.workflow.source_key(),
                                          'records': [{'case_id': case['case_id']}]}), encoding='utf-8')

    def tearDown(self):
        self.env.stop()
        self.temp.cleanup()

    def test_clear_and_restore_preserve_every_record_and_other_files(self):
        before = self.store.snapshot()
        unrelated = self.folder / 'runtime' / 'monitor' / 'other-workspace' / '2025-02-27.json'
        unrelated.parent.mkdir(parents=True)
        unrelated.write_text('unrelated', encoding='utf-8')
        source = self.folder / 'source.parquet'
        source.write_bytes(b'source data')
        result = self.module.clear_saved_cases()
        self.assertEqual(result['deleted'], {'cases': 1, 'approvals': 1, 'actions': 1})
        self.assertEqual(self.store.snapshot(), {'cases': {}, 'actions': [], 'approvals': []})
        self.assertFalse(self.report.exists(), 'Old report links must not point at deleted cases')
        self.assertEqual(source.read_bytes(), b'source data')
        self.assertEqual(unrelated.read_text(), 'unrelated')
        self.assertEqual(self.module.read_backup(result['backup_path'])['state'], before)
        self.module.restore_backup(result['backup_path'])
        self.assertEqual(self.store.snapshot(), before)
        self.assertTrue(self.report.is_file())

    def test_failed_backup_does_not_delete_any_state(self):
        before = self.store.snapshot()
        with patch.object(self.module, '_write_json', side_effect=OSError('fixture disk full')), \
             patch.object(self.store, 'reset', wraps=self.store.reset) as reset:
            with self.assertRaises(OSError):
                self.module.clear_saved_cases()
        reset.assert_not_called()
        self.assertEqual(self.store.snapshot(), before)
        self.assertTrue(self.report.exists())

    def test_clear_cancels_cloud_reminders_and_restore_does_not_rearm_them(self):
        reminders = importlib.import_module('rd.reminders')
        cid = next(iter(self.store.snapshot()['cases']))
        plan = {'email_delivery': 'SCHEDULED', 'reminder': {'name': 'fixture', 'state': 'SCHEDULED'}}
        self.store.update_case(cid, review_plan=plan)
        def cancel(case):
            changed = {**case['review_plan'], 'email_delivery': 'CANCELLED',
                       'reminder': {'name': 'fixture', 'state': 'CANCELLED'}}
            self.store.update_case(case['case_id'], review_plan=changed)
        with patch.object(reminders, 'cancel', side_effect=cancel) as cancelled:
            result = self.module.clear_saved_cases()
        cancelled.assert_called_once()
        self.module.restore_backup(result['backup_path'])
        self.assertEqual(self.store.get_case(cid)['review_plan']['email_delivery'], 'CANCELLED')

    def test_reminder_cancellation_failure_stops_case_deletion(self):
        reminders = importlib.import_module('rd.reminders')
        cid = next(iter(self.store.snapshot()['cases']))
        self.store.update_case(cid, review_plan={'email_delivery': 'SCHEDULED', 'reminder': {'name': 'fixture'}})
        before = self.store.snapshot()
        with patch.object(reminders, 'cancel', side_effect=ValueError('fixture AWS cancellation failed')), \
             patch.object(self.store, 'reset', wraps=self.store.reset) as reset:
            with self.assertRaisesRegex(ValueError, 'cancellation failed'):
                self.module.clear_saved_cases()
        reset.assert_not_called()
        self.assertEqual(self.store.snapshot(), before)
        self.assertIsNotNone(self.module.latest_backup())

    def test_restore_refuses_another_workspace_or_nonempty_store(self):
        result = self.module.clear_saved_cases()
        with patch.object(self.store, '_NAMESPACE', 'other-workspace'), self.assertRaises(ValueError):
            self.module.restore_backup(result['backup_path'])
        self.store.open_case('New fixture', 'Quality', '2025-03-01', 'new', 'new')
        with self.assertRaisesRegex(ValueError, 'only while'):
            self.module.restore_backup(result['backup_path'])
        self.assertEqual(len(self.store.snapshot()['cases']), 1)

    def test_restore_rejects_report_path_outside_workspace(self):
        result = self.module.clear_saved_cases()
        path = Path(result['backup_path'])
        bundle = json.loads(path.read_text(encoding='utf-8'))
        bundle['day_reports'][0]['name'] = '../../2025-02-27.json'
        path.write_text(json.dumps(bundle), encoding='utf-8')
        with self.assertRaises(ValueError):
            self.module.restore_backup(path)
        self.assertFalse(any(self.module.counts(self.store.snapshot()).values()))
