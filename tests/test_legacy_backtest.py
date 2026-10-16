"""Legacy entry points should also handle no signals and partial month coverage."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation import backtest


class LegacyBacktestTests(unittest.TestCase):
    def run_fixture(self, records):
        with tempfile.TemporaryDirectory() as folder, patch.object(backtest, 'CURATED', False), \
             patch.object(backtest, 'rows', side_effect=[
                 [{'category': 'Quality', 'share': 0.01}], records]), \
             contextlib.redirect_stdout(io.StringIO()):
            output = Path(folder) / 'result.csv'
            result = backtest.main(output)
            self.assertTrue(output.is_file())
            return result

    def test_no_signals_produces_an_empty_table_with_the_documented_columns(self):
        result = self.run_fixture([
            {'style': 'Control', 'category': 'Preference', 'return_date': '2025-01-01', 'n': 100}])
        self.assertTrue(result.empty)
        self.assertEqual(list(result.columns), backtest.COLUMNS)

    def test_partial_final_month_is_not_a_future_report_or_complete_followup(self):
        result = self.run_fixture([
            {'style': 'Target', 'category': 'Quality', 'return_date': '2025-01-01', 'n': 40},
            {'style': 'Target', 'category': 'Preference', 'return_date': '2025-01-15', 'n': 1}])
        self.assertEqual(len(result), 1)
        self.assertIsNone(result.iloc[0].report_date)
        self.assertIsNone(result.iloc[0].sustained_next_28d)

    def test_empty_input_fails_explicitly(self):
        with self.assertRaisesRegex(ValueError, 'No eligible records'):
            self.run_fixture([])
