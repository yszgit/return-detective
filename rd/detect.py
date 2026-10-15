"""Cheap statistical screen used by the Triage Agent (and by the backtest).

A (style, category) pair raises a signal when, over the trailing window:
  * the count of returns in that category reaches a minimum,
  * the category's share of the style's returns is several times the company baseline,
  * and the excess is statistically significant (binomial z-score).
Statistics only raise a flag; the agents decide what it means.
"""
import math
from .data import one, baseline_share

WINDOW_DAYS = 28
MIN_COUNT = {"Quality": 5, "Fit: too small": 10, "Fit: too big": 10, "Fit: uncomfortable": 8,
             "Expectation gap": 6, "Fulfilment error": 6, "Damaged in transit": 5}
MIN_LIFT = {"Quality": 4, "Fit: too small": 2.5, "Fit: too big": 2.5, "Fit: uncomfortable": 3,
            "Expectation gap": 3, "Fulfilment error": 3, "Damaged in transit": 4}
MIN_Z = 4.0
WATCHED = list(MIN_COUNT)


def screen(style, category, as_of, window_days=WINDOW_DAYS):
    r = one(
        """select count(*) as style_returns,
                  coalesce(sum((category = ?)::int), 0) as category_returns,
                  count(distinct coalesce(store, channel)) as locations
           from returns
           where style = ? and return_date > cast(? as date) - ?::int and return_date <= cast(? as date)""",
        [category, style, as_of, window_days, as_of],
    )
    n, k = r["style_returns"], r["category_returns"]
    p = baseline_share(category)
    share = k / n if n else 0.0
    z = (k - n * p) / math.sqrt(n * p * (1 - p)) if n and 0 < p < 1 else 0.0
    lift = share / p if p else 0.0
    watched = category in MIN_COUNT
    signal = watched and k >= MIN_COUNT[category] and lift >= MIN_LIFT[category] and z >= MIN_Z
    watch = watched and not signal and k >= max(2, MIN_COUNT[category] // 2) and lift >= 2
    return {
        "style": style, "category": category, "as_of": str(as_of), "window_days": window_days,
        "style_returns": n, "category_returns": k, "category_share": round(share, 3),
        "company_baseline_share": round(p, 3), "lift_vs_baseline": round(lift, 1), "z_score": round(z, 1),
        "distinct_locations": r["locations"],
        "level": "SIGNAL" if signal else ("WATCH" if watch else "NORMAL"),
        "thresholds": {"min_count": MIN_COUNT.get(category), "min_lift": MIN_LIFT.get(category), "min_z": MIN_Z},
    }
