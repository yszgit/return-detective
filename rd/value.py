"""Explicit planning assumptions, independent of undated source financial facts."""
import math


def estimate_case_value(*, future_returns, avoidance_share, unit_cost, hours_saved,
                        hourly_cost, intervention_cost, model_cost):
    values = [future_returns, avoidance_share, unit_cost, hours_saved,
              hourly_cost, intervention_cost, model_cost]
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError('Planning inputs must be finite and nonnegative.')
    if avoidance_share > 1:
        raise ValueError('Avoidance share must be between zero and one.')
    avoided = future_returns * avoidance_share
    gross = avoided * unit_cost
    labor = hours_saved * hourly_cost
    costs = intervention_cost + model_cost
    return {'avoided_returns': round(avoided, 2), 'return_cost_avoided': round(gross, 2),
            'labor_capacity_value': round(labor, 2), 'intervention_and_model_cost': round(costs, 2),
            'net_planning_value': round(gross + labor - costs, 2),
            'break_even_avoided_returns': round(max(0, costs - labor) / unit_cost, 2) if unit_cost else None}
