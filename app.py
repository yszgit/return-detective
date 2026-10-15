"""Return Detective - demo UI (Streamlit).

  streamlit run app.py

Live mode runs the three Strands agents on Amazon Bedrock against the Athena data.
Every live run is saved, so it can be replayed instantly (no model calls) if the network
or the model is slow during the pitch.
"""
import html
import json
import os
import queue
import threading
import time

import pandas as pd
import streamlit as st

from rd import store, tools
from rd.data import rows, lit
from rd.config import BACKEND, BACKTEST_PATH, data_available, is_synthetic
from rd.scenarios import SCENARIOS as ALL_SCENARIOS

TRACE_DIR = os.path.join(store.RUNTIME_DIR, "traces")
BACKTEST = BACKTEST_PATH

SYNTHETIC = is_synthetic() or (BACKEND == "duckdb" and not data_available())
SCENARIOS = {s["label"]: dict(s, key=key) for key, s in ALL_SCENARIOS.items()
             if s["synthetic"] == SYNTHETIC}
AGENT_STYLE = {"Triage Agent": ("🔎", "#2a78d6"), "Investigator Agent": ("🕵️", "#6250d6"),
               "Response Agent": ("⚖️", "#eb6834"), "System": ("📥", "#52514e")}

st.set_page_config(page_title="Return Detective", page_icon="🕵️", layout="wide")
st.markdown("""
<style>
.block-container {padding-top: 3.2rem; max-width: 1500px;}
.rd-hero {font-size: 2.1rem; font-weight: 800; margin: 0; letter-spacing: -0.5px;}
.rd-sub {color: #52514e; margin: 0 0 0.6rem 0; font-size: 1.05rem;}
.rd-stage {margin: 0.9rem 0 0.3rem 0; padding: 0.35rem 0.7rem; border-radius: 6px; background: #f1f0ec;
           font-weight: 700; color: #0b0b0b;}
.rd-agent {font-weight: 700;}
.rd-chip {display:inline-block; padding:2px 9px; border-radius:12px; font-size:0.8rem; font-weight:700; margin-right:6px;}
.rd-case {border:1px solid #dddbd3; border-radius:10px; padding:0.8rem 1rem; background:#fcfcfb;}
.rd-tag {font-size:0.75rem; color:#52514e; text-transform:uppercase; letter-spacing:0.6px; font-weight:700;}
</style>""", unsafe_allow_html=True)

if "events" not in st.session_state:
    st.session_state.events = []
    st.session_state.scenario = list(SCENARIOS)[0]
    st.session_state.mode = None


def clean(s):
    return html.unescape(str(s))


# ------------------------------------------------------------------ rendering
def render_event(e, box):
    agent, kind = e.get("agent", "System"), e["type"]
    icon, color = AGENT_STYLE.get(agent, ("•", "#52514e"))
    with box:
        if kind == "stage":
            st.markdown(f'<div class="rd-stage">{icon} {clean(e["text"])}</div>', unsafe_allow_html=True)
        elif kind == "thought":
            st.markdown(f'<span class="rd-agent" style="color:{color}">{icon} {agent}</span>', unsafe_allow_html=True)
            st.markdown(clean(e["text"]))
        elif kind == "tool_result":
            inp = e.get("input")
            label = f"🔧 {agent.split()[0]} · `{e['tool']}`"
            with st.expander(label, expanded=False):
                if inp:
                    st.caption("Input")
                    st.json(inp)
                st.caption("Result (data the agent saw)")
                out = e.get("output", "")
                try:
                    st.json(json.loads(out))
                except Exception:
                    st.code(out[:3000])
        elif kind == "decision":
            d = e.get("data") or {}
            if agent == "Triage Agent":
                dec = d.get("decision", "?")
                fn = st.error if dec == "INVESTIGATE" else st.success if dec == "ISOLATED" else st.warning
                fn(f"**Triage decision: {dec}** · {d.get('style', '')} · {d.get('category', '')}\n\n{clean(d.get('rationale', ''))}")
            else:
                st.info(f"**Investigation result · confidence {d.get('confidence', '?')}**\n\n"
                        f"**Root cause:** {clean(d.get('root_cause', ''))}")
                hyps = d.get("hypotheses") or []
                if hyps:
                    st.dataframe(pd.DataFrame(hyps), hide_index=True, width="stretch")
        elif kind == "briefing":
            st.markdown(f'<span class="rd-agent" style="color:{color}">{icon} Briefing for the owner team</span>',
                        unsafe_allow_html=True)
            st.markdown(clean(e["text"]))


def pair_tool_calls(events):
    """Attach each tool_call's input to the following tool_result so they render as one expander."""
    out, pending = [], {}
    for e in events:
        if e["type"] == "tool_call":
            pending[(e["agent"], e["tool"])] = e.get("input")
            continue
        if e["type"] == "tool_result":
            e = dict(e, input=pending.pop((e["agent"], e["tool"]), None))
        out.append(e)
    return out


# ------------------------------------------------------------------ runs
def trace_path(key):
    return os.path.join(TRACE_DIR, f"{key}.json")


def run_live(sc, box, scripted=False):
    store.reset()
    q, events, err = queue.Queue(), [], []

    def worker():
        try:
            if scripted:
                from rd.offline import run_scripted
                run_scripted(sc["return_id"], sc["as_of"], q.put)
            else:
                from rd.agents import run_pipeline
                run_pipeline(sc["return_id"], sc["as_of"], q.put)
        except Exception as ex:  # surface errors in the UI
            err.append(repr(ex))
        finally:
            q.put(None)

    th = threading.Thread(target=worker, daemon=True)
    th.start()
    status = box.empty()
    t0, pending = time.time(), {}
    while True:
        try:
            e = q.get(timeout=0.5)
        except queue.Empty:
            status.caption(f"⏳ agents working… {time.time() - t0:.0f}s")
            continue
        if e is None:
            break
        events.append(e)
        if e["type"] == "tool_call":
            pending[(e["agent"], e["tool"])] = e.get("input")
            status.caption(f"⏳ {e['agent']} is calling `{e['tool']}`…")
            continue
        if e["type"] == "tool_result":
            e = dict(e, input=pending.pop((e["agent"], e["tool"]), None))
        render_event(e, box)
    status.empty()
    if err:
        box.error(f"Run failed: {err[0]}")
    os.makedirs(TRACE_DIR, exist_ok=True)
    if not err and not scripted:
        with open(trace_path(sc["key"]), "w", encoding="utf-8") as f:
            json.dump({"events": events, "store": store.snapshot(), "seconds": round(time.time() - t0)}, f, default=str)
    return events


def replay(sc, box, speed=0.35):
    with open(trace_path(sc["key"]), encoding="utf-8") as f:
        saved = json.load(f)
    store.restore(saved["store"])
    evs = pair_tool_calls(saved["events"])
    for e in evs:
        render_event(e, box)
        time.sleep(speed if e["type"] != "tool_result" else speed / 3)
    return saved["events"]


# ------------------------------------------------------------------ case panel
def case_panel():
    db = store.snapshot()
    if not db["cases"]:
        st.caption("No case open. Isolated returns are handled normally and only logged.")
        return
    for c in db["cases"].values():
        conf = c.get("confidence") or "—"
        cc = {"High": "#e34948", "Medium": "#eda100", "Low": "#2a78d6"}.get(conf, "#52514e")
        st.markdown(f"""<div class="rd-case"><div class="rd-tag">Case file</div>
<h4 style="margin:0.1rem 0 0.4rem 0">{c['case_id']} · {clean(c['style'])}</h4>
<span class="rd-chip" style="background:#f1f0ec">{clean(c['category'])}</span>
<span class="rd-chip" style="background:{cc};color:white">Confidence: {conf}</span>
<span class="rd-chip" style="background:#f1f0ec">{c['status'].replace('_', ' ')}</span>
<p style="margin:0.6rem 0 0.2rem 0"><b>Root cause:</b> {clean(c.get('root_cause') or '')}</p>
<p style="margin:0;color:#52514e"><b>Owner:</b> {clean(c.get('owner_team') or '')} · opened as of {c['opened_as_of']}</p>
</div>""", unsafe_allow_html=True)
        acts = [a for a in db["actions"] if a["case_id"] == c["case_id"]]
        if acts:
            st.markdown("**Done automatically (within authority)**")
            for a in acts:
                det = a["detail"]
                extra = ""
                if isinstance(det, dict) and "amount_cad" in det:
                    extra = f" — CA${det['amount_cad']} refunded on {det['returns_refunded']} returns"
                who = "" if a["executed_by"] == "agent" else f" · _{a['executed_by']}_"
                st.markdown(f"✅ **T{a['tier']}** {clean(a['action'])}{extra}{who}")
        aps = [a for a in db["approvals"] if a["case_id"] == c["case_id"]]
        if aps:
            st.markdown("**Waiting for a human decision**")
            for a in aps:
                det = a["detail"] if isinstance(a["detail"], dict) else {}
                body = next((clean(v) for k, v in det.items() if k in ("proposed_text", "draft", "offer", "scope")), "")
                with st.container(border=True):
                    st.markdown(f"**T{a['tier']} · {clean(a['action'])}** → {clean(a['approver'])}")
                    if body:
                        st.caption(body[:600])
                    if a["status"] == "PENDING":
                        b1, b2 = st.columns(2)
                        if b1.button("Approve", key="ap" + a["approval_id"], type="primary", width="stretch"):
                            store.decide_approval(a["approval_id"], True, "Demo reviewer")
                            st.rerun()
                        if b2.button("Reject", key="rj" + a["approval_id"], width="stretch"):
                            store.decide_approval(a["approval_id"], False, "Demo reviewer")
                            st.rerun()
                    else:
                        st.markdown(f"{'✅' if a['status'] == 'APPROVED' else '⛔'} **{a['status']}**")
        if c.get("hypotheses"):
            with st.expander("Hypotheses tested"):
                st.dataframe(pd.DataFrame(c["hypotheses"]), hide_index=True, width="stretch")


# ------------------------------------------------------------------ impact tab
@st.cache_data(show_spinner=False)
def glindafied_weeks():
    r = rows(f"""select date_trunc('week', return_date) as week_start, count(*) as all_returns,
                        sum(case when category = 'Quality' then 1 else 0 end) as quality_returns
                 from returns where style = {lit('Glindafied')}
                   and return_date >= DATE '2024-10-01' and return_date <= DATE '2025-03-31'
                 group by date_trunc('week', return_date) order by week_start""")
    df = pd.DataFrame(r)
    df["week_start"] = pd.to_datetime(df["week_start"].astype(str).str[:10])
    return df


@st.cache_data(show_spinner=False)
def backtest():
    df = pd.read_csv(BACKTEST)
    both = df.dropna(subset=["report_date"]).copy()
    both["lead_days"] = (pd.to_datetime(both.report_date) - pd.to_datetime(both.flag_date)).dt.days
    return df, both


def impact_tab():
    if SYNTHETIC:
        st.info("Synthetic demo data is used for functional checks. Historical ALDO impact numbers do not describe this dataset.")
        st.caption("The existing historical backtest is preserved in evaluation/results/. See evaluation/README.md for its limitations.")
        return
    if not data_available():
        st.info("Prepare local data or configure Athena to explore impact.")
        return
    if not BACKTEST.is_file():
        st.info("No backtest results found. See evaluation/README.md to generate and select a result file.")
        return
    st.caption("Historical retrospective analysis; this reorganization has not revalidated it against the private source data. It is not measured savings.")
    df, both = backtest()
    tiles = [
        (f"#{int(both.returns_at_flag.median())}", "related return at which the agent flags a systemic issue",
         f"vs #{int(both.returns_at_report.median())} with a monthly report"),
        (f"{int(both.lead_days.median())} days", "earlier detection (median)", "same cases, same data"),
        (f"{len(df):,}", "systemic signals found in 2 years", f"{(df.category == 'Quality').sum()} quality, "
         f"{df.category.str.startswith('Fit').sum()} fit"),
        (f"{df.report_date.isna().sum():,}", "signals a monthly report never catches", "too small per month to show up"),
    ]
    cols = st.columns(4)
    for col, (big, label, sub) in zip(cols, tiles):
        col.markdown(f'<div class="rd-case"><div style="font-size:2rem;font-weight:800">{big}</div>'
                     f'<div style="font-weight:600">{label}</div><div style="color:#52514e;font-size:0.85rem">{sub}</div></div>',
                     unsafe_allow_html=True)

    if "sustained_next_28d" in df:
        st.caption(f"Honest signal quality: only {df.sustained_next_28d.mean():.0%} of raw statistical flags are still present "
                   f"28 days later ({df[df.category == 'Quality'].sustained_next_28d.mean():.0%} for quality). That is why a flag "
                   "only opens a case: the Investigator Agent decides confidence, and stock holds, supplier claims and "
                   "customer outreach need High confidence plus human approval.")
    st.markdown("#### Glindafied: when would we have known?")
    import altair as alt
    w = glindafied_weeks()
    marks = pd.DataFrame({"date": pd.to_datetime(["2024-10-28", "2024-12-31"]),
                          "label": ["Return Detective flags (5th defect)", "Monthly report flags (52nd defect)"],
                          "color": ["#eb6834", "#52514e"]})
    bars = alt.Chart(w).mark_bar(color="#2a78d6", size=16, cornerRadiusTopLeft=4, cornerRadiusTopRight=4).encode(
        x=alt.X("week_start:T", title="Week"), y=alt.Y("quality_returns:Q", title="'Defective / poor quality' returns"),
        tooltip=[alt.Tooltip("week_start:T", title="Week of"), alt.Tooltip("quality_returns:Q", title="Quality returns"),
                 alt.Tooltip("all_returns:Q", title="All returns")])
    rules = alt.Chart(marks).mark_rule(strokeWidth=2.5, strokeDash=[6, 4]).encode(
        x="date:T", tooltip=["label:N", alt.Tooltip("date:T", title="Date")],
        color=alt.Color("label:N", scale=alt.Scale(domain=list(marks.label), range=list(marks.color)),
                        legend=alt.Legend(title=None, orient="top", labelLimit=400, labelFontSize=13)))
    st.altair_chart((bars + rules).properties(height=300).configure_axis(gridColor="#ecebe6", domainColor="#c3c2b7"),
                    width="stretch")
    st.caption("Real ALDO return data. The agent's screen fires 64 days before a month-end report would, with 47 fewer defective pairs returned.")

    st.markdown("#### Value of earlier detection (illustrative, adjust the assumptions)")
    c1, c2, c3 = st.columns(3)
    cost = c1.slider("Cost of one avoidable return to ALDO (CA$)", 10, 80, 30)
    prevent = c2.slider("Share of returns avoided once the cause is fixed early", 10, 80, 40, format="%d%%")
    gap = int(both.returns_at_report.sum() - both.returns_at_flag.sum())
    value = gap * cost * prevent / 100 / 2  # two years of data -> per year
    never = df[df.report_date.isna()]
    if "sustained_next_28d" in df:
        never = never[never.sustained_next_28d]
    upside = int(never.after_flag.sum()) * cost * prevent / 100 / 2
    c3.markdown(f'<div class="rd-case"><div style="font-size:2rem;font-weight:800">CA${value:,.0f} / yr</div>'
                f'<div style="color:#52514e;font-size:0.85rem">conservative: {gap:,} returns happened between the agent flag and the '
                f'monthly-report flag (2 yrs)</div><div style="margin-top:6px;font-weight:600">+ up to CA${upside:,.0f} / yr</div>'
                f'<div style="color:#52514e;font-size:0.85rem">from sustained signals a monthly report never catches</div></div>',
                unsafe_allow_html=True)
    st.caption("Plus customer fairness: 26-41% of online customers returning for quality, wrong item or transit damage were still charged a restocking fee.")
    with st.expander("Backtest by category"):
        t = both.groupby("category").agg(cases=("style", "size"), agent_flags_at=("returns_at_flag", "median"),
                                          report_flags_at=("returns_at_report", "median"), days_earlier=("lead_days", "median"))
        st.dataframe(t, width="stretch")


def architecture_tab():
    st.markdown("""
| Layer | AWS service | Role in Return Detective |
|---|---|---|
| Data | **DuckDB locally; Amazon S3 + Glue + Athena for AWS** | Synthetic or authorized private Parquet data; replay-date filters in evidence tools |
| Reasoning | **Amazon Bedrock (Anthropic Claude)** | Triage, Investigator and Response agents |
| Agent framework | **Strands Agents SDK** | Tool use, multi-agent pipeline, hooks for the live trace |
| Policy | Playbook document read by the agents | Root-cause classes, confidence levels, authority matrix |
| Guardrails | Authority limits in tool code; optional Bedrock Guardrails | Demo fee-waiver authority ≤ CA$500; approval queues for higher tiers |
| Case memory | Case store (→ **Amazon DynamoDB**) | Cases, actions, approval queue, audit trail |
| Notifications | (→ **Amazon SNS**) | Approval requests to owner teams |
""")
    st.caption("Actions and approvals currently update a local JSON demo store. Retail execution, SNS notifications and DynamoDB persistence need adapters.")


# ------------------------------------------------------------------ layout
st.markdown('<div class="rd-hero">🕵️ Return Detective</div>', unsafe_allow_html=True)
st.markdown('<div class="rd-sub">Every return is a clue. Three AI agents read each ALDO return, decide whether it is '
            'an isolated case or an emerging problem, investigate the cause and act within a written authority matrix.</div>',
            unsafe_allow_html=True)

with st.sidebar:
    st.caption("Synthetic data" if SYNTHETIC else "Authorized ALDO data")
    if not data_available():
        st.info("Generate the local demo data first: python scripts/generate_synthetic_data.py")
    st.caption("Actions update the local demo store; no retail system is connected.")
    st.header("Scenario")
    if st.session_state.scenario not in SCENARIOS:
        st.session_state.scenario = list(SCENARIOS)[0]
    name = st.radio("Incoming return", list(SCENARIOS), index=list(SCENARIOS).index(st.session_state.scenario))
    st.session_state.scenario = name
    sc = SCENARIOS[name]
    st.caption(sc["blurb"])
    st.markdown(f"**Return #{sc['return_id']}** · replay date **{sc['as_of']}**")
    has_trace = os.path.exists(trace_path(sc["key"]))
    mode = st.radio("Mode", ["Live (Bedrock)", "Replay saved live run", "Scripted (no LLM)"],
                    index=2 if SYNTHETIC else 0, help="Every live run is saved. Replay shows a previous live run instantly.")
    go = st.button("▶ Run", type="primary", width="stretch",
                   disabled=(mode == "Replay saved live run" and not has_trace) or not data_available()
                   or (mode == "Live (Bedrock)" and not os.environ.get("RD_MODEL_ID")))
    if mode == "Live (Bedrock)" and not os.environ.get("RD_MODEL_ID"):
        st.caption("Set RD_MODEL_ID and AWS credentials before a live run.")
    if mode == "Replay saved live run" and not has_trace:
        st.caption("No saved live run yet for this scenario.")
    st.divider()
    st.caption(f"Data: {BACKEND} · Model: {os.environ.get('RD_MODEL_ID', 'not configured')}"
               + (f" · Fast: {os.environ['RD_FAST_MODEL_ID']}" if os.environ.get("RD_FAST_MODEL_ID") else ""))
    if st.button("Reset case store", width="stretch"):
        store.reset()
        st.session_state.events = []
        st.rerun()

tab1, tab2, tab3 = st.tabs(["🕵️ Live investigation", "📈 Business impact", "🏗️ AWS architecture"])
with tab1:
    left, right = st.columns([1.55, 1], gap="large")
    with left:
        st.markdown("##### Agent reasoning and tool calls")
        box = st.container()
        if go:
            if mode == "Replay saved live run":
                st.session_state.events = replay(sc, box)
            else:
                st.session_state.events = run_live(sc, box, scripted=(mode == "Scripted (no LLM)"))
            st.session_state.mode = mode
            st.rerun()
        elif st.session_state.events:
            if st.session_state.mode == "Scripted (no LLM)":
                box.caption("Scripted run: tools called in a fixed order, no language model.")
            for e in pair_tool_calls(st.session_state.events):
                render_event(e, box)
        else:
            box.info("Pick a scenario on the left and press **Run**.")
    with right:
        st.markdown("##### Case file, actions and approvals")
        case_panel()
with tab2:
    impact_tab()
with tab3:
    architecture_tab()
