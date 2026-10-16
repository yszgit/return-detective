"""Calendar validation must not alter historical evidence or promise email delivery."""
import datetime as dt
import unittest
from unittest.mock import patch

from rd import review_plans, workflow


class ReviewPlanTests(unittest.TestCase):
    now = dt.datetime(2026, 10, 16, 12, tzinfo=dt.timezone.utc)

    def test_toronto_plan_is_saved_in_utc_without_enabling_delivery(self):
        case = {'case_id': 'CASE-FIXTURE', 'status': 'OPEN', 'opened_as_of': '2024-11-23'}
        with patch.object(review_plans.store, 'get_case', return_value=case), \
             patch.object(review_plans.store, 'update_case', return_value=case) as save:
            plan = review_plans.save_plan(case['case_id'], dt.date(2026, 10, 23), dt.time(9, 30),
                                         'America/Toronto', 'reviewer@example.com', now=self.now)
        self.assertEqual(plan['review_at_utc'], '2026-10-23T13:30:00+00:00')
        self.assertEqual(plan['email_delivery'], 'NOT_ENABLED')
        self.assertFalse(plan['automatic_run'])
        save.assert_called_once_with(case['case_id'], review_plan=plan)
        self.assertEqual(workflow.latest_case_date([{**case, 'review_plan': plan}]), '2024-11-23')

    def test_bad_email_past_date_and_clock_changes_are_rejected(self):
        inputs = [
            (dt.date(2026, 10, 23), dt.time(9), 'bad-email'),
            (dt.date(2026, 10, 15), dt.time(9), ''),
            (dt.date(2026, 11, 1), dt.time(1, 30), ''),  # repeated local time
            (dt.date(2027, 3, 14), dt.time(2, 30), ''),  # missing local time
        ]
        for date, time, email in inputs:
            with self.subTest(date=date, time=time), self.assertRaises(ValueError):
                review_plans.build_plan(date, time, 'America/Toronto', email, now=self.now)

    def test_unknown_or_closed_case_cannot_be_scheduled(self):
        for case in (None, {'status': 'CLOSED'}):
            with patch.object(review_plans.store, 'get_case', return_value=case), \
                 patch.object(review_plans.store, 'update_case') as save, self.assertRaises(ValueError):
                review_plans.save_plan('CASE-FIXTURE', dt.date(2026, 10, 23), dt.time(9), 'UTC', now=self.now)
            save.assert_not_called()
