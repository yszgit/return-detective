"""Backtest of the Triage screen on two years of real ALDO returns.

  RD_BACKEND=duckdb python evaluation/backtest.py      (needs the Parquet files in ./data)

Uses exactly the thresholds of rd/detect.py, so the numbers match what the Triage Agent sees.
For every (style, category) it finds the first day the screen reaches SIGNAL and compares it with a
"monthly report" baseline: at each month end, flag when that month has >= 30 returns in the category
and the category share is at least the same lift over the company baseline.

Also reports a false-alarm proxy (there is no ground truth for 'real problem'): a flag is SUSTAINED
if, in the 28 days after the flag, the category still has >= 3 returns and >= 2x the company share.

Writes evaluation/cases_backtest.csv and prints the summary used in the pitch.
"""
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
os.environ.setdefault("RD_BACKEND", "duckdb")
from rd.data import rows  # noqa: E402
from rd.detect import MIN_COUNT, MIN_LIFT, MIN_Z, WINDOW_DAYS  # noqa: E402

REPORT_MIN = 30
OUT = os.path.join(os.path.dirname(__file__), "cases_backtest.csv")


def main():
    base = pd.DataFrame(rows("select category, share from baseline")).set_index("category")["share"]
    d = pd.DataFrame(rows("""select style, category, return_date, count(*) as n from returns
                              where style is not null group by style, category, return_date"""))
    d["return_date"] = pd.to_datetime(d["return_date"])
    tot = d.groupby(["style", "return_date"])["n"].sum().rename("tot").reset_index()
    days = pd.date_range(d.return_date.min(), d.return_date.max())
    out = []
    for cat in MIN_COUNT:
        p = base.get(cat, 0.0)
        c = d[d.category == cat][["style", "return_date", "n"]]
        styles = c["style"].unique()
        m = tot[tot["style"].isin(styles)].merge(c, on=["style", "return_date"], how="left").fillna({"n": 0})
        idx = pd.MultiIndex.from_product([styles, days], names=["style", "return_date"])
        full = m.set_index(["style", "return_date"])[["tot", "n"]].reindex(idx, fill_value=0)
        cum = full.groupby(level="style").cumsum()
        prev = cum.groupby(level="style").shift(WINDOW_DAYS).fillna(0)
        nxt = cum.groupby(level="style").shift(-WINDOW_DAYS)
        nxt = nxt.fillna(cum.groupby(level="style").transform("last"))
        r = cum - prev                 # trailing 28 days, inclusive of the day
        fwd = nxt - cum                # the 28 days after the day
        share = r.n / r.tot.replace(0, np.nan)
        z = (r.n - r.tot * p) / np.sqrt(r.tot * p * (1 - p)).replace(0, np.nan)
        hit = (r.n >= MIN_COUNT[cat]) & (share >= MIN_LIFT[cat] * p) & (z >= MIN_Z)
        first = hit[hit].reset_index().groupby("style")["return_date"].min()
        for style, fd in first.items():
            s = full.loc[style]
            cs = s.n.cumsum()
            at_flag = int(cs.loc[fd])
            total = int(cs.iloc[-1])
            f = fwd.loc[(style, fd)]
            sustained = bool(f.n >= 3 and f.tot > 0 and f.n / f.tot >= 2 * p)
            mon = s.resample("ME").sum()
            rep = mon[(mon.n >= REPORT_MIN) & (mon.n / mon.tot.replace(0, np.nan) >= MIN_LIFT[cat] * p)]
            rep_date = rep.index[0] if len(rep) else None
            out.append(dict(style=style, category=cat, flag_date=fd.date(), returns_at_flag=at_flag,
                            after_flag=total - at_flag, total=total, sustained_next_28d=sustained,
                            report_date=rep_date.date() if rep_date is not None else None,
                            returns_at_report=int(cs.loc[rep_date]) if rep_date is not None else None))
    df = pd.DataFrame(out)
    df.to_csv(OUT, index=False)
    both = df.dropna(subset=["report_date"]).copy()
    both["lead_days"] = (pd.to_datetime(both.report_date) - pd.to_datetime(both.flag_date)).dt.days
    print(f"signals: {len(df)}  | also caught by monthly report: {len(both)}  | never caught: {df.report_date.isna().sum()}")
    print(f"comparable cases: agent flags at return #{both.returns_at_flag.median():.0f} (median) vs "
          f"#{both.returns_at_report.median():.0f} for the report, {both.lead_days.median():.0f} days earlier")
    print(f"sustained 28 days after the flag (false-alarm proxy): {df.sustained_next_28d.mean():.0%} overall")
    print(df.groupby("category").agg(signals=("style", "size"), sustained=("sustained_next_28d", "mean")).round(2))


if __name__ == "__main__":
    main()
