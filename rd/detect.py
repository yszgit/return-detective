"""Cheap statistical screen used by the Triage Agent (and by the backtest).

A (style, category) pair raises a SIGNAL when, over the trailing window:
  * the count of returns in that category reaches a minimum,
  * the category's share of the style's returns is several times the company baseline,
  * and the excess is statistically significant (binomial z-score).
Statistics only raise a flag; the agents decide what it means.
"""
import math
from .data import one, lit, dlit, days_before, baseline_share

WINDOW_DAYS = 28
MIN_COUNT = {"Quality": 5, "Fit: too small": 10, "Fit: too big": 10, "Fit: uncomfortable": 8,
             "Expectation gap": 6, "Fulfilment error": 6, "Damaged in transit": 5}
MIN_LIFT = {"Quality": 4, "Fit: too small": 2.5, "Fit: too big": 2.5, "Fit: uncomfortable": 3,
            "Expectation gap": 3, "Fulfilment error": 3, "Damaged in transit": 4}
MIN_Z = 4.0
WATCHED = list(MIN_COUNT)


def window_sql(as_of, days):
    return f"return_date > {dlit(days_before(as_of, days))} and return_date <= {dlit(as_of)}"


def style_window_counts(style, as_of, window_days=WINDOW_DAYS):
    """One query: the style's returns per category in the window."""
    from .data import rows
    r = rows(f"""select category, count(*) as n from returns
                 where style = {lit(style)} and {window_sql(as_of, window_days)} group by category""")
    loc = one(f"""select count(distinct coalesce(store, channel)) as locations from returns
                  where style = {lit(style)} and {window_sql(as_of, window_days)}""")
    return {x["category"]: x["n"] for x in r}, loc["locations"] if loc else 0


def screen(style, category, as_of, window_days=WINDOW_DAYS, _counts=None):
    counts, locations = _counts or style_window_counts(style, as_of, window_days)
    n = sum(counts.values())
    k = counts.get(category, 0)
    p = baseline_share(category)
    share = k / n if n else 0.0
    z = (k - n * p) / math.sqrt(n * p * (1 - p)) if n and 0 < p < 1 else 0.0
    lift = share / p if p else 0.0
    watched = category in MIN_COUNT
    signal = watched and k >= MIN_COUNT[category] and lift >= MIN_LIFT[category] and z >= MIN_Z
    watch = watched and not signal and k >= max(2, MIN_COUNT[category] // 2) and lift >= 2
    return {
        "style": style, "category": category, "as_of": str(as_of)[:10], "window_days": window_days,
        "style_returns": n, "category_returns": k, "category_share": round(share, 3),
        "company_baseline_share": round(p, 3), "lift_vs_baseline": round(lift, 1), "z_score": round(z, 1),
        "distinct_locations": locations,
        "level": "SIGNAL" if signal else ("WATCH" if watch else "NORMAL"),
        "thresholds": {"min_count": MIN_COUNT.get(category), "min_lift": MIN_LIFT.get(category), "min_z": MIN_Z},
    }


def screen_all(style, as_of, window_days=WINDOW_DAYS):
    counts = style_window_counts(style, as_of, window_days)
    res = [screen(style, c, as_of, window_days, _counts=counts) for c in WATCHED]
    res.sort(key=lambda r: ({"SIGNAL": 0, "WATCH": 1, "NORMAL": 2}[r["level"]], -r["z_score"]))
    return res
