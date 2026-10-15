"""Chronological evaluation must resist future baseline changes and incomplete follow-up."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from evaluation import chronological


class ChronologicalTests(unittest.TestCase):
    def test_future_category_surge_cannot_change_earlier_signal(self):
        records=[{'style':'Background','category':'Preference','return_date':'2024-12-01','n':100},
                 {'style':'Background','category':'Quality','return_date':'2024-12-01','n':1},
                 {'style':'Target','category':'Quality','return_date':'2025-01-01','n':5},
                 {'style':'Future','category':'Quality','return_date':'2025-01-02','n':10000},
                 {'style':'Target','category':'Quality','return_date':'2025-01-05','n':4},
                 {'style':'Background','category':'Preference','return_date':'2025-01-31','n':1}]
        with tempfile.TemporaryDirectory() as temp,patch.object(chronological,'rows',return_value=records):
            df,summary=chronological.run(Path(temp)/'result.csv',start='2025-01-01',end='2025-01-31')
        target=df[df['style']=='Target'].iloc[0]
        self.assertEqual(target.flag_date,'2025-01-01')
        self.assertAlmostEqual(target.baseline_share_at_flag,0.0099)
        self.assertTrue(target.followup_complete)
        self.assertEqual(summary['model_calls'],0)

    def test_tail_cases_do_not_count_as_failed_followup(self):
        records=[{'style':'Background','category':'Preference','return_date':'2025-01-01','n':100},
                 {'style':'Background','category':'Quality','return_date':'2025-01-01','n':1},
                 {'style':'Late','category':'Quality','return_date':'2025-01-31','n':5}]
        with tempfile.TemporaryDirectory() as temp,patch.object(chronological,'rows',return_value=records):
            df,summary=chronological.run(Path(temp)/'result.csv')
        late=df[df['style']=='Late'].iloc[0]
        self.assertFalse(late.followup_complete)
        self.assertIsNone(late.sustained_next_28d)
        self.assertEqual(summary['complete_followup_cases'],0)
        self.assertIsNone(summary['persistence_proxy'])

    def test_empty_eligible_dataset_fails_explicitly(self):
        with tempfile.TemporaryDirectory() as temp,patch.object(chronological,'rows',return_value=[]):
            with self.assertRaisesRegex(ValueError,'No eligible records'):
                chronological.run(Path(temp)/'result.csv')
