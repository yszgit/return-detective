"""Generate SYNTHETIC Return Detective data for the local DuckDB backend.

This writes four Parquet files into ``data/synthetic/`` with the exact schemas the
agent tools, the statistical screen and the backtest expect:

  returns.parquet, sku_sales.parquet, baseline.parquet, exchanges.parquet

Everything produced here is clearly fake: styles are prefixed ``SYNTH-``, SKUs ``SYN-``,
orders ``SYNTH-ORD-``, returns ``SYNTH-RET-``, stores ``SYNTH-STORE-NN``. No customer
identifier column is generated at all, so no real ALDO customer data can leak.

The data is deterministic (fixed RNG seed, fixed as-of date 2026-01-31) and is designed
so that three seeded scenarios cross the UNCHANGED detection thresholds in rd/detect.py:

  * SYNTH-RiverLoafer   -> Quality defect           (category "Quality"            -> SIGNAL)
  * SYNTH-TrailRunner   -> Fit issue, runs big      (category "Fit: too big"       -> SIGNAL)
  * SYNTH-CoastalBoot   -> Transit/operational dmg  (category "Damaged in transit" -> SIGNAL)
  * SYNTH-EverydaySneaker -> negative control        (never SIGNAL)

Usage:
  python scripts/generate_synthetic_data.py                 # writes to data/synthetic
  python scripts/generate_synthetic_data.py --out /tmp/x    # custom output dir

The script prints each watched category's screen level for the seeded styles so you can
see the signals without changing any thresholds.
"""
import argparse
import datetime as dt
import os
import random

import duckdb

SEED = 20260131
AS_OF = dt.date(2026, 1, 31)
HISTORY_DAYS = 540  # ~18 months of history ending at AS_OF
START = AS_OF - dt.timedelta(days=HISTORY_DAYS)

BANNERS = ["SYNTH-BANNER-A", "SYNTH-BANNER-B"]
STORE_CHANNELS = ["store"]
ONLINE_CHANNELS = ["online", "mail"]
ALL_CHANNELS = STORE_CHANNELS + ONLINE_CHANNELS
STORES = [f"SYNTH-STORE-{i:02d}" for i in range(1, 21)]
ALDO_FAULT = {"Quality", "Fulfilment error", "Damaged in transit", "Delivery failure"}

# Normalized category -> list of messy raw_reason strings (casing/spelling/bilingual/whitespace).
# The category stays correct and normalized; only the free text is inconsistent.
RAW_REASONS = {
    "Preference": ["Changed my mind", "changed my mind ", "Found something else", "j'ai changé d'avis", "gift return"],
    "Fit: too big": ["Too Big", "too big", " runs large", "trop grand", "Size too big!!"],
    "Fit: too small": ["Too small", "runs small", "trop petit", "size too small "],
    "Fit: uncomfortable": ["Uncomfortable", "inconfortable", "hurts my feet", "not comfortable"],
    "Expectation gap": ["Not what I expected", "not as advertised", "colour was off", "ne répond pas à mes attentes"],
    "Quality": ["Defective", "DEFECTIVE!!", "poor quality", "manufacturer defect", "sole separating", "défectueux"],
    "Fulfilment error": ["Wrong item", "wrong size delivered", "missing item", "Wrong item delivered"],
    "Damaged in transit": ["Arrived in poor condition", "arrived damaged", "arrivé en mauvais état", "box crushed"],
    "Delivery failure": ["Arrived too late", "lost in transit", "return to sender"],
    "Admin": ["in-store return", "return extension"],
    "Unknown": ["", "n/a", "other"],
}

# Company-wide category mix for ordinary (non-seeded) returns. Kept realistic so that the
# watched categories (Quality, Fit, damage) have LOW baselines and a style-level spike can
# clear the lift and z thresholds. Baseline shares are recomputed from the real rows later.
NORMAL_MIX = [
    ("Preference", 0.45),
    ("Fit: too small", 0.13),
    ("Fit: too big", 0.12),
    ("Fit: uncomfortable", 0.05),
    ("Expectation gap", 0.08),
    ("Quality", 0.045),
    ("Fulfilment error", 0.035),
    ("Damaged in transit", 0.025),
    ("Delivery failure", 0.015),
    ("Admin", 0.015),
    ("Unknown", 0.015),
]

# ~40 styles total: 4 named (3 seeded + 1 control) + 36 ordinary filler styles.
SEEDED_STYLES = ["SYNTH-RiverLoafer", "SYNTH-TrailRunner", "SYNTH-CoastalBoot", "SYNTH-EverydaySneaker"]
FILLER_STYLES = [f"SYNTH-Style{i:02d}" for i in range(1, 37)]
ALL_STYLES = SEEDED_STYLES + FILLER_STYLES


class Gen:
    def __init__(self):
        self.rng = random.Random(SEED)
        self.rows = []
        self.exchanges = []
        self._rid = 1
        self._ord = 1

    # -- helpers --------------------------------------------------------------
    def _order_number(self):
        n = f"SYNTH-ORD-{self._ord:07d}"
        self._ord += 1
        return n

    def _raw(self, category):
        return self.rng.choice(RAW_REASONS[category])

    def _sku(self, style, variant):
        # Deterministic SKU per style/variant, e.g. SYN-RIVERLOAFER-37
        tag = style.replace("SYNTH-", "").upper()
        return f"SYN-{tag}-{variant}"

    def _add(self, style, category, when, channel, store, *, aldo_fault=None,
             restocking_fee=None, refund=None, qty=1, variant=None, raw=None,
             reuse_order=None, allow_messy=True):
        """Append one return row. Seeded rows pass allow_messy=False so their numeric
        fields are never nulled and detection stays deterministic."""
        if variant is None:
            variant = self.rng.choice([37, 38, 39, 40, 41, 42])
        sku = self._sku(style, variant)
        order_number = reuse_order or self._order_number()
        return_order_number = "SYNTH-RET-" + order_number.split("-")[-1]
        if aldo_fault is None:
            aldo_fault = category in ALDO_FAULT
        if raw is None:
            raw = self._raw(category)
        if refund is None:
            refund = round(self.rng.uniform(35, 160), 2)
        if restocking_fee is None:
            # ordinary rows: usually no fee; online ALDO-fault rows sometimes wrongly charged
            if channel in ONLINE_CHANNELS and category in ALDO_FAULT and self.rng.random() < 0.35:
                restocking_fee = round(self.rng.uniform(8, 20), 2)
            else:
                restocking_fee = 0.0

        # messy-but-contract-safe realism, ordinary rows only
        if allow_messy:
            if self.rng.random() < 0.04:
                refund = None
            if self.rng.random() < 0.03:
                qty = None
            if self.rng.random() < 0.08:
                restocking_fee = None

        row = {
            "return_id": self._rid,
            "banner": self.rng.choice(BANNERS),
            "order_number": order_number,
            "sku": sku,
            "style": style,
            "return_order_number": return_order_number,
            "channel": channel,
            "return_date": when,
            "status": self.rng.choice(["Completed", "Processing", "Received"]),
            "refund": refund,
            "qty": qty,
            "raw_reason": raw,
            "store": store if channel in STORE_CHANNELS else None,
            "category": category,
            "restocking_fee": restocking_fee,
            "final_sale": self.rng.random() < 0.1,
            "aldo_fault": bool(aldo_fault),
        }
        self._rid += 1
        self.rows.append(row)
        return row

    def _rand_date(self, lo, hi):
        span = (hi - lo).days
        return lo + dt.timedelta(days=self.rng.randint(0, span))

    def _window_date(self, days_back_max):
        """A date inside the trailing window before AS_OF (1..days_back_max days ago)."""
        return AS_OF - dt.timedelta(days=self.rng.randint(1, days_back_max))

    # -- ordinary background --------------------------------------------------
    def normal_returns(self, style, n):
        cats, weights = zip(*NORMAL_MIX)
        for _ in range(n):
            category = self.rng.choices(cats, weights=weights, k=1)[0]
            channel = self.rng.choice(ALL_CHANNELS)
            store = self.rng.choice(STORES)
            when = self._rand_date(START, AS_OF)
            self._add(style, category, when, channel, store)

    # -- seeded scenarios -----------------------------------------------------
    def seed_quality(self):
        """SYNTH-RiverLoafer: Quality defect spiking in the trailing 28d window, widespread
        across many stores and both online and mail -> points at the product, not one store."""
        style = "SYNTH-RiverLoafer"
        # modest ordinary background for this style so its total isn't dominated by Quality
        for _ in range(70):
            category = self.rng.choices(["Preference", "Fit: too small", "Fit: too big", "Expectation gap"],
                                        weights=[0.6, 0.18, 0.15, 0.07], k=1)[0]
            self._add(style, category, self._rand_date(START, AS_OF - dt.timedelta(days=40)),
                      self.rng.choice(ALL_CHANNELS), self.rng.choice(STORES))
        # the spike: 16 Quality returns in the last ~24 days, spread widely
        for i in range(16):
            channel = self.rng.choice(["online", "mail", "store", "store"])
            store = self.rng.choice(STORES)  # many distinct stores
            fee = round(self.rng.uniform(10, 18), 2) if (channel in ONLINE_CHANNELS and i % 2 == 0) else 0.0
            self._add(style, "Quality", self._window_date(24), channel, store,
                      aldo_fault=True, restocking_fee=fee, allow_messy=False)

    def seed_fit(self):
        """SYNTH-TrailRunner: runs big. 'Fit: too big' dominates in the window, with matching
        exchanges (customers re-order a size down)."""
        style = "SYNTH-TrailRunner"
        for _ in range(60):
            category = self.rng.choices(["Preference", "Fit: too small", "Expectation gap", "Quality"],
                                        weights=[0.6, 0.2, 0.15, 0.05], k=1)[0]
            self._add(style, category, self._rand_date(START, AS_OF - dt.timedelta(days=40)),
                      self.rng.choice(ALL_CHANNELS), self.rng.choice(STORES))
        for _ in range(20):
            channel = self.rng.choice(ALL_CHANNELS)
            store = self.rng.choice(STORES)
            variant = self.rng.choice([41, 42, 43])  # bought too big
            row = self._add(style, "Fit: too big", self._window_date(26), channel, store,
                            variant=variant, allow_messy=False)
            # matching exchange: re-order one size down
            self.exchanges.append({
                "confidence": self.rng.choice(["High", "Medium"]),
                "exchange_date": row["return_date"],
                "order_number": row["order_number"],
                "exchange_sku": self._sku(style, variant - 1),
                "qty": 1,
                "store": store if channel in STORE_CHANNELS else None,
                "sales": round(self.rng.uniform(60, 130), 2),
            })

    def seed_damage(self):
        """SYNTH-CoastalBoot: 'Damaged in transit' concentrated in mail/online and one banner
        -> transit / fulfilment, not a product defect."""
        style = "SYNTH-CoastalBoot"
        for _ in range(55):
            category = self.rng.choices(["Preference", "Fit: too small", "Fit: too big", "Expectation gap"],
                                        weights=[0.62, 0.18, 0.14, 0.06], k=1)[0]
            self._add(style, category, self._rand_date(START, AS_OF - dt.timedelta(days=40)),
                      self.rng.choice(ALL_CHANNELS), self.rng.choice(STORES))
        for _ in range(12):
            channel = self.rng.choice(["mail", "online"])  # transit concentrated online
            self._add(style, "Damaged in transit", self._window_date(22), channel, None,
                      aldo_fault=True, allow_messy=False)

    def seed_control(self):
        """SYNTH-EverydaySneaker: ordinary returns only; must never SIGNAL."""
        style = "SYNTH-EverydaySneaker"
        for _ in range(90):
            category = self.rng.choices(["Preference", "Fit: too small", "Fit: too big", "Expectation gap", "Quality"],
                                        weights=[0.65, 0.14, 0.12, 0.06, 0.03], k=1)[0]
            self._add(style, category, self._rand_date(START, AS_OF),
                      self.rng.choice(ALL_CHANNELS), self.rng.choice(STORES))

    def add_duplicates(self):
        """A few multi-line returns: a second row sharing an existing return_order_number
        (and its order_number), with a distinct unique return_id."""
        sample = self.rng.sample([r for r in self.rows if r["category"] in ("Preference", "Fit: too small")],
                                 k=min(12, len(self.rows)))
        for base in sample:
            self._add(base["style"], base["category"], base["return_date"], base["channel"],
                      base["store"], reuse_order=base["order_number"])

    def build(self):
        # ordinary filler styles
        for style in FILLER_STYLES:
            self.normal_returns(style, self.rng.randint(140, 210))
        self.seed_quality()
        self.seed_fit()
        self.seed_damage()
        self.seed_control()
        self.add_duplicates()
        self.rng.shuffle(self.rows)
        # reassign return_id after shuffle so it stays a clean unique sequence
        for i, r in enumerate(self.rows, start=1):
            r["return_id"] = i
        return self.rows, self.exchanges

    def sku_sales(self):
        """Units sold per SKU. Seeded SKUs get generous denominators dated Aug-2025+ so
        sku_return_rate has data. Return rate stays plausible (returns << sold)."""
        skus = sorted({r["sku"] for r in self.rows})
        out = []
        for sku in skus:
            lines = self.rng.randint(400, 1200)
            out.append({"sku": sku, "lines_sold": lines,
                        "final_sale_lines": int(lines * self.rng.uniform(0.05, 0.15))})
        return out


def _escape(path):
    return path.replace("'", "''")


def main(a):
    out_dir = a.out
    os.makedirs(out_dir, exist_ok=True)
    g = Gen()
    rows, exchanges = g.build()
    sku_sales = g.sku_sales()

    con = duckdb.connect()

    # returns
    con.execute("""create table returns (
        return_id BIGINT, banner VARCHAR, order_number VARCHAR, sku VARCHAR, style VARCHAR,
        return_order_number VARCHAR, channel VARCHAR, return_date DATE, status VARCHAR,
        refund DOUBLE, qty INTEGER, raw_reason VARCHAR, store VARCHAR, category VARCHAR,
        restocking_fee DOUBLE, final_sale BOOLEAN, aldo_fault BOOLEAN)""")
    con.executemany(
        "insert into returns values ($return_id,$banner,$order_number,$sku,$style,"
        "$return_order_number,$channel,$return_date,$status,$refund,$qty,$raw_reason,"
        "$store,$category,$restocking_fee,$final_sale,$aldo_fault)",
        rows)

    # sku_sales
    con.execute("create table sku_sales (sku VARCHAR, lines_sold INTEGER, final_sale_lines INTEGER)")
    con.executemany("insert into sku_sales values ($sku,$lines_sold,$final_sale_lines)", sku_sales)

    # exchanges
    con.execute("""create table exchanges (confidence VARCHAR, exchange_date DATE, order_number VARCHAR,
        exchange_sku VARCHAR, qty INTEGER, store VARCHAR, sales DOUBLE)""")
    if exchanges:
        con.executemany(
            "insert into exchanges values ($confidence,$exchange_date,$order_number,$exchange_sku,$qty,$store,$sales)",
            exchanges)

    # baseline computed from the actual returns (category_count / total_count)
    con.execute("""create table baseline as
        select category, count(*) as n, count(*) * 1.0 / sum(count(*)) over () as share
        from returns group by category""")

    for name in ("returns", "sku_sales", "exchanges", "baseline"):
        target = os.path.join(out_dir, f"{name}.parquet")
        con.execute(f"COPY {name} TO '{_escape(target)}' (FORMAT parquet)")

    with open(os.path.join(out_dir, "_SYNTHETIC.txt"), "w", encoding="utf-8") as f:
        f.write("SYNTHETIC DATA — generated by scripts/generate_synthetic_data.py.\n"
                "Fake, machine-generated. NOT real ALDO data and contains no customer identifiers.\n"
                f"seed={SEED} as_of={AS_OF.isoformat()} rows={len(rows)}\n")

    total = con.execute("select count(*) from returns").fetchone()[0]
    print(f"[SYNTHETIC] wrote {total} returns, {len(sku_sales)} skus, {len(exchanges)} exchanges to {out_dir}")
    print("[SYNTHETIC] baseline shares (watched categories):")
    for cat, share in con.execute(
            "select category, round(share,4) from baseline order by share desc").fetchall():
        print(f"   {cat:<22} {share}")

    # In-process verification against the UNCHANGED screen (uses the same data via duckdb backend).
    _verify(out_dir)
    con.close()


def _verify(out_dir):
    """Load the generated data through rd.detect and print the screen levels for seeded styles."""
    import sys
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    os.environ["RD_BACKEND"] = "duckdb"
    os.environ["RD_DATA_DIR"] = out_dir
    # fresh import so RD_DATA_DIR is picked up
    for m in list(sys.modules):
        if m == "rd" or m.startswith("rd."):
            del sys.modules[m]
    from rd.detect import screen_all

    print("\n[SYNTHETIC] screen levels as of", AS_OF.isoformat())
    expectations = {
        "SYNTH-RiverLoafer": ("Quality", "SIGNAL"),
        "SYNTH-TrailRunner": ("Fit: too big", "SIGNAL"),
        "SYNTH-CoastalBoot": ("Damaged in transit", "SIGNAL"),
        "SYNTH-EverydaySneaker": (None, "no SIGNAL"),
    }
    for style, (cat, want) in expectations.items():
        res = screen_all(style, AS_OF.isoformat())
        top = res[0]
        signal_cats = [r["category"] for r in res if r["level"] == "SIGNAL"]
        if cat is None:
            ok = not signal_cats
            print(f"   {style:<24} top={top['category']}/{top['level']} "
                  f"z={top['z_score']} lift={top['lift_vs_baseline']} -> "
                  f"{'OK (no SIGNAL)' if ok else 'FAIL (unexpected SIGNAL: ' + ','.join(signal_cats) + ')'}")
        else:
            row = next(r for r in res if r["category"] == cat)
            ok = row["level"] == "SIGNAL"
            print(f"   {style:<24} {cat}: level={row['level']} count={row['category_returns']} "
                  f"lift={row['lift_vs_baseline']} z={row['z_score']} -> {'OK' if ok else 'FAIL (want SIGNAL)'}")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=os.path.join(os.path.dirname(__file__), "..", "data", "synthetic"))
    main(p.parse_args())
