import json
from pathlib import Path
import tempfile
import unittest

from evaluation.export_comparison import export_bundle


class ComparisonExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        for mode in ('rules', 'agent'):
            folder = self.root / mode
            folder.mkdir()
            (folder / 'summary.json').write_text(json.dumps({'dataset_sha256': 'same',
                'results': [{'name': 'fit'}]}))
            report = {'name': 'fit', 'checks': {'completed_without_error': True, 'owner': False},
                'case_store': {'cases': {'c': {'owner_team': 'Merchandising (product content)'}}},
                'events': [], 'result': {}, 'input_tokens': None}
            (folder / 'fit.json').write_text(json.dumps(report))

    def test_alias_normalization_keeps_raw_failure_and_missing_usage(self):
        bundle = export_bundle(self.root)
        result = bundle['modes']['agent']['results'][0]
        self.assertTrue(result['passed'])
        self.assertFalse(result['original_checks']['owner'])
        self.assertTrue(result['scoring_notes'])
        self.assertIsNone(result['input_tokens'])
        self.assertFalse(bundle['explanation_quality_reviewed'])

    def test_different_datasets_are_rejected(self):
        path = self.root / 'agent/summary.json'
        report = json.loads(path.read_text())
        report['dataset_sha256'] = 'other'
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'Different data'):
            export_bundle(self.root)

    def test_different_case_sets_are_rejected(self):
        path = self.root / 'agent/summary.json'
        report = json.loads(path.read_text())
        report['results'] = [{'name': 'quality'}]
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError, 'same nonempty case set'):
            export_bundle(self.root)
