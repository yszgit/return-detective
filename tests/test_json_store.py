"""Local case writes tolerate brief Windows locks and preserve old data on failure."""
import importlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class JsonStoreTests(unittest.TestCase):
    def test_transient_destination_lock_recovers_without_losing_the_new_store(self):
        store = importlib.import_module('rd.store')
        replace = store.os.replace
        calls = 0

        def briefly_locked(source, target):
            nonlocal calls
            calls += 1
            if calls < 3:
                raise PermissionError('temporary destination lock')
            replace(source, target)

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cases.json'
            path.write_text('{"old": true}')
            state = {'cases': {'CASE-TEST': {'case_id': 'CASE-TEST'}}, 'approvals': [], 'actions': []}
            with patch.multiple(store, STORE_BACKEND='json', RUNTIME_DIR=folder, _PATH=str(path)), \
                 patch.object(store.os, 'replace', side_effect=briefly_locked), patch.object(store.time, 'sleep'):
                store.restore(state)
                self.assertEqual(store.snapshot(), state)
            self.assertEqual(calls, 3)

    def test_persistent_lock_keeps_the_previous_complete_file(self):
        store = importlib.import_module('rd.store')
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'cases.json'
            previous = {'cases': {'original': {}}, 'actions': [], 'approvals': []}
            path.write_text(json.dumps(previous))
            with patch.multiple(store, STORE_BACKEND='json', RUNTIME_DIR=folder, _PATH=str(path)), \
                 patch.object(store.os, 'replace', side_effect=PermissionError('persistent lock')) as replace, \
                 patch.object(store.time, 'sleep'):
                with self.assertRaises(PermissionError):
                    store.reset()
            self.assertEqual(json.loads(path.read_text()), previous)
            self.assertEqual(replace.call_count, 6)
