import unittest

from rd.approval_view import approval_notice


class ApprovalViewTests(unittest.TestCase):
    def case(self, category='Quality', confidence='Medium', **fields):
        return {'case_id': 'CASE-FIXTURE', 'category': category, 'confidence': confidence,
                'root_cause': 'Recorded hypothesis', **fields}

    def test_low_confidence_explains_gate_without_creating_requests(self):
        approvals = []
        tone, text = approval_notice(self.case('Damaged in transit', 'Low'), approvals)
        self.assertEqual(tone, 'info')
        self.assertIn('confidence is Low', text)
        self.assertEqual(approvals, [])

    def test_completed_decisions_are_not_treated_as_missing(self):
        approvals = [{'case_id': 'CASE-FIXTURE', 'status': 'APPROVED'},
                     {'case_id': 'CASE-FIXTURE', 'status': 'REJECTED'},
                     {'case_id': 'CASE-OTHER', 'status': 'PENDING'}]
        tone, text = approval_notice(self.case('Fit: too big'), approvals)
        self.assertEqual(tone, 'info')
        self.assertIn('1 approved and 1 rejected', text)

    def test_missing_eligible_proposal_is_flagged_for_review(self):
        for case in (self.case('Fit: too big'), self.case('Quality', 'High')):
            with self.subTest(category=case['category']):
                tone, text = approval_notice(case, [])
                self.assertEqual(tone, 'warning')
                self.assertIn('No approval request recorded', text)

    def test_medium_quality_and_interrupted_run_have_distinct_explanations(self):
        tone, text = approval_notice(self.case(), [])
        self.assertEqual(tone, 'info')
        self.assertIn('High confidence', text)
        tone, text = approval_notice(self.case(workflow_error='interrupted'), [])
        self.assertEqual(tone, 'warning')
        self.assertIn('incomplete or interrupted', text)
