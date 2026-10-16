import unittest

from rd.value import estimate_case_value


class ValueTests(unittest.TestCase):
    def setUp(self):
        self.inputs = dict(future_returns=50, avoidance_share=0.3, unit_cost=30,
                           hours_saved=1, hourly_cost=40, intervention_cost=150, model_cost=5)

    def test_costs_and_labor_are_included_in_case_value(self):
        value = estimate_case_value(**self.inputs)
        self.assertEqual(value['avoided_returns'], 15)
        self.assertEqual(value['net_planning_value'], 335)
        self.assertAlmostEqual(value['break_even_avoided_returns'], 3.83)

    def test_no_avoidance_can_mean_negative_value(self):
        value = estimate_case_value(**{**self.inputs, 'avoidance_share': 0})
        self.assertEqual(value['net_planning_value'], -115)

    def test_zero_unit_cost_does_not_invent_a_break_even_count(self):
        value = estimate_case_value(**{**self.inputs, 'unit_cost': 0})
        self.assertIsNone(value['break_even_avoided_returns'])

    def test_impossible_and_nonfinite_assumptions_are_rejected(self):
        for changes in [{'avoidance_share': 1.1}, {'future_returns': -1}, {'unit_cost': float('nan')}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                estimate_case_value(**{**self.inputs, **changes})
