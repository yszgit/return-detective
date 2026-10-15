"""Return Detective - demo UI (Streamlit).

  streamlit run app.py

Live mode runs three Strands agents on Amazon Bedrock against the configured local or Athena data.
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
# Agent identity: roman numeral + short name (no colour coding, no icons).
AGENT_STYLE = {"Triage Agent": ("I", "Triage"), "Investigator Agent": ("II", "Investigator"),
               "Response Agent": ("III", "Response"), "System": ("", "System")}

# Palette (strict monochrome)
BLACK, CHARCOAL, GREY, DASH, HAIR, FILL, WHITE = "#000000", "#333333", "#767676", "#BDBDBD", "#E6E6E6", "#F5F5F5", "#FFFFFF"

st.set_page_config(page_title="Return Detective", layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Jost:wght@300;400;500;600&display=swap');
:root {--white:#FFFFFF; --ink:#000000; --char:#333333; --grey:#767676; --dash:#BDBDBD; --hair:#E6E6E6; --fill:#F5F5F5;}

/* ---------- base ---------- */
.stApp {background: var(--white); color: var(--ink); font-family: 'Jost', sans-serif; accent-color: var(--ink);}
.stApp button, .stApp input, .stApp textarea, .stApp select {font-family: 'Jost', sans-serif;}
header[data-testid="stHeader"] {background: var(--white);}
.block-container {padding: 3.75rem 3rem 6rem 3rem !important; max-width: none;}
h1, h2, h3, h4, h5, h6 {font-family: 'Jost', sans-serif !important; font-weight: 400 !important;
                        color: var(--ink) !important; letter-spacing: 0 !important;}
.stMarkdown p, .stMarkdown li {font-family: 'Jost', sans-serif; font-weight: 400; line-height: 1.7; color: var(--ink);}
.stMarkdown strong {font-weight: 600;}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {color: var(--grey) !important;
                        font-size: 0.82rem; line-height: 1.65;}
a {color: var(--ink) !important; text-decoration: underline;}
hr {border: none !important; border-top: 1px solid var(--hair) !important; margin: 1.6rem 0 !important;}
code {color: var(--ink) !important; background: var(--fill) !important; font-size: 0.82em; border-radius: 0 !important;}
.stApp :focus-visible {outline: 2px solid var(--ink) !important; outline-offset: 2px;}
/* Streamlit icons are Material Symbols ligatures: keep their icon font so they never render as text. */
span[data-testid="stIconMaterial"], [class*="material-symbols"], [class*="MaterialIcon"] {
        font-family: 'Material Symbols Rounded', 'Material Symbols Outlined' !important;}

/* ---------- sidebar ---------- */
section[data-testid="stSidebar"] {background: var(--white); border-right: 1px solid var(--hair);}
section[data-testid="stSidebar"] .block-container, [data-testid="stSidebarUserContent"] {padding-top: 2.4rem;}
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"],
section[data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {color: var(--char) !important;}

/* ---------- labels ---------- */
.rd-label, [data-testid="stWidgetLabel"] p {font-family: 'Jost', sans-serif !important; font-size: 0.7rem !important;
        letter-spacing: 0.12em; text-transform: uppercase; color: var(--char) !important; font-weight: 500 !important;}
section[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {color: var(--grey) !important;}
.rd-label {margin: 0 0 0.9rem 0; padding-bottom: 0.7rem; border-bottom: 1px solid var(--hair); color: var(--grey) !important;}
.rd-label.bare {border-bottom: none; padding-bottom: 0; margin-bottom: 0.4rem;}

/* ---------- announcement bar + masthead ---------- */
.rd-bar {background: var(--ink); color: var(--white); margin: 0 -3rem; padding: 0.55rem 3rem; text-align: center;
         font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; font-weight: 400; line-height: 1.4;}
.rd-bar .dot {padding: 0 0.7rem;}
.rd-mast {margin: 0 -3rem 2.2rem -3rem; padding: 1.7rem 3rem 1.5rem 3rem; border-bottom: 1px solid var(--hair); text-align: center;}
.rd-wordmark {font-family: 'Jost', sans-serif; font-weight: 600; font-size: 2.6rem; line-height: 1; letter-spacing: 0.04em;
              text-transform: uppercase; color: var(--ink);}
@media (max-width: 640px) {
  .block-container {padding-left: 1rem !important; padding-right: 1rem !important;}
  .rd-bar {margin: 0 -1rem; padding-left: 1rem; padding-right: 1rem;}
  .rd-mast {margin-left: -1rem; margin-right: -1rem; padding-left: 1rem; padding-right: 1rem;}
  .rd-wordmark {font-size: 1.8rem;}
}
.rd-sub {font-size: 1rem; font-weight: 300; color: var(--char); max-width: 780px; line-height: 1.75; margin: 0 0 2.2rem 0;}
.rd-agents {display: flex; flex-wrap: wrap; gap: 3rem; border-top: 1px solid var(--ink); border-bottom: 1px solid var(--hair);
            padding: 1rem 0; margin: 0 0 2.2rem 0;}
.rd-agents .a {display: flex; align-items: baseline; gap: 0.7rem;}
.rd-agents .n {font-family: 'Jost', sans-serif; font-size: 1.5rem; font-weight: 300; color: var(--ink);}
.rd-agents .t {font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink); font-weight: 500;}
.rd-agents .d {font-size: 0.8rem; color: var(--char); font-weight: 400;}

/* ---------- tabs: plain black nav, 1px black underline on the selected tab, no accent ---------- */
.stTabs [data-baseweb="tab-list"], [data-testid="stTabs"] [role="tablist"] {gap: 2.5rem !important;}
.stTabs [data-baseweb="tab"], [data-testid="stTabs"] [role="tab"] {padding: 0 0 .7rem 0 !important; margin: 0 !important;}
[data-testid="stTabs"] [role="tablist"]::after {background-color: var(--hair) !important; height: 1px !important; border-radius: 0 !important;}
[data-testid="stTabs"] [role="tab"] {background: transparent !important; border-radius: 0; color: var(--char) !important;
        box-shadow: none !important;}
[data-testid="stTabs"] [role="tab"] p {font-size: 0.75rem !important; letter-spacing: 0.12em; text-transform: uppercase;
        font-weight: 500; color: inherit !important;}
[data-testid="stTabs"] [role="tab"]:hover, [data-testid="stTabs"] [role="tab"][data-hovered] {color: var(--ink) !important;}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] {color: var(--ink) !important;}
[data-testid="stTabs"] [role="tab"][data-focus-visible] {outline: 2px solid var(--ink) !important; outline-offset: -2px;}
[data-testid="stTabs"] .react-aria-SelectionIndicator {height: 1px !important; border-radius: 0 !important;}
[data-testid="stTabs"] [role="tab"][aria-selected="true"] .react-aria-SelectionIndicator {background-color: var(--ink) !important;}
[data-baseweb="tab-highlight"] {background-color: var(--ink) !important; height: 1px !important;}
[data-baseweb="tab-border"] {background-color: var(--hair) !important; height: 1px !important;}
[data-testid="stTabPanel"] {padding-top: 2.2rem;}

/* ---------- buttons: square; primary solid black, secondary outlined ---------- */
.stButton > button, .stDownloadButton > button, .stFormSubmitButton > button {border-radius: 0 !important;
        box-shadow: none !important; padding: 0.7rem 1.4rem; min-height: 2.75rem; font-family: 'Jost', sans-serif;
        text-transform: uppercase; letter-spacing: 0.12em; font-size: 0.75rem; font-weight: 500;
        transition: background-color .2s ease, color .2s ease, border-color .2s ease;}
.stButton > button p, .stDownloadButton > button p, .stFormSubmitButton > button p {font-size: inherit !important;
        letter-spacing: inherit; font-weight: inherit;}
/* Labels sit in child p/span elements with their own colour, so every state sets the children too. */
/* secondary (default): white fill, 1px black border, black label */
.stButton button, .stButton button *, .stDownloadButton button, .stDownloadButton button *,
.stFormSubmitButton button, .stFormSubmitButton button * {background: var(--white) !important; color: var(--ink) !important;}
.stButton button, .stDownloadButton button, .stFormSubmitButton button {border: 1px solid var(--ink) !important;}
.stButton button *, .stDownloadButton button *, .stFormSubmitButton button * {background: transparent !important;}
.stButton button:hover, .stButton button:hover *, .stButton button:focus-visible, .stButton button:focus-visible *,
.stDownloadButton button:hover, .stDownloadButton button:hover *,
.stFormSubmitButton button:hover, .stFormSubmitButton button:hover * {background: var(--ink) !important; color: var(--white) !important;}
.stButton button:hover *, .stButton button:focus-visible *, .stDownloadButton button:hover *,
.stFormSubmitButton button:hover * {background: transparent !important;}
/* primary: solid black fill, white label; hover charcoal */
.stButton button[kind="primary"], .stButton button[kind="primary"] *,
.stButton button[data-testid="stBaseButton-primary"], .stButton button[data-testid="stBaseButton-primary"] *,
.stDownloadButton button[kind="primary"], .stDownloadButton button[kind="primary"] *,
.stDownloadButton button[data-testid="stBaseButton-primary"], .stDownloadButton button[data-testid="stBaseButton-primary"] *,
.stFormSubmitButton button[kind^="primary"], .stFormSubmitButton button[kind^="primary"] *,
.stFormSubmitButton button[data-testid="stBaseButton-primaryFormSubmit"],
.stFormSubmitButton button[data-testid="stBaseButton-primaryFormSubmit"] * {background: var(--ink) !important; color: var(--white) !important;}
.stButton button[kind="primary"], .stButton button[data-testid="stBaseButton-primary"],
.stDownloadButton button[kind="primary"], .stDownloadButton button[data-testid="stBaseButton-primary"],
.stFormSubmitButton button[kind^="primary"], .stFormSubmitButton button[data-testid="stBaseButton-primaryFormSubmit"] {
        border: 1px solid var(--ink) !important;}
.stButton button[kind="primary"]:hover, .stButton button[kind="primary"]:focus-visible,
.stButton button[data-testid="stBaseButton-primary"]:hover, .stButton button[data-testid="stBaseButton-primary"]:focus-visible,
.stDownloadButton button[kind="primary"]:hover, .stDownloadButton button[data-testid="stBaseButton-primary"]:hover,
.stFormSubmitButton button[kind^="primary"]:hover, .stFormSubmitButton button[data-testid="stBaseButton-primaryFormSubmit"]:hover {
        background: var(--char) !important; border-color: var(--char) !important; color: var(--white) !important;}
.stButton button[kind="primary"]:hover *, .stButton button[kind="primary"]:focus-visible *,
.stButton button[data-testid="stBaseButton-primary"]:hover *, .stButton button[data-testid="stBaseButton-primary"]:focus-visible *,
.stDownloadButton button[kind="primary"]:hover *, .stDownloadButton button[data-testid="stBaseButton-primary"]:hover *,
.stFormSubmitButton button[kind^="primary"]:hover *,
.stFormSubmitButton button[data-testid="stBaseButton-primaryFormSubmit"]:hover * {background: transparent !important; color: var(--white) !important;}
.stButton button[kind="primary"] *, .stButton button[data-testid="stBaseButton-primary"] *,
.stDownloadButton button[kind="primary"] *, .stDownloadButton button[data-testid="stBaseButton-primary"] *,
.stFormSubmitButton button[kind^="primary"] *, .stFormSubmitButton button[data-testid="stBaseButton-primaryFormSubmit"] * {
        background: transparent !important;}
.stButton > button:focus:not(:focus-visible) {box-shadow: none !important;}
/* disabled (e.g. Run with no saved trace) */
.stButton button:disabled, .stButton button:disabled:hover, .stButton button:disabled *, .stButton button:disabled:hover * {
        background: var(--fill) !important; color: var(--grey) !important; cursor: not-allowed;}
.stButton button:disabled, .stButton button:disabled:hover {border-color: var(--hair) !important;}
.stButton button:disabled *, .stButton button:disabled:hover * {background: transparent !important;}

/* ---------- inputs: no accent colour ---------- */
[data-baseweb="select"] > div, [data-baseweb="input"], [data-baseweb="textarea"] {border-radius: 0 !important;}
[data-testid="stSlider"] [role="slider"] {background-color: var(--ink) !important; box-shadow: none !important;}

/* ---------- expanders, containers, tables ---------- */
[data-testid="stExpander"] details {border: 1px solid var(--hair) !important; border-radius: 0 !important; background: var(--white);}
[data-testid="stExpander"] summary {padding: 0.6rem 0.9rem; border-radius: 0 !important;}
[data-testid="stExpander"] summary:hover {background: var(--fill);}
[data-testid="stExpander"] summary p {font-size: 0.82rem; color: var(--char);}
[data-testid="stExpander"] summary:hover p {color: var(--ink);}
[class*="st-key-rdcard"] {background: var(--white); border: 1px solid var(--hair) !important; border-radius: 0 !important;
        padding: 1.3rem 1.4rem !important; box-shadow: none !important;}
.stMarkdown table {border-collapse: collapse; width: 100%; margin: 0.4rem 0 1rem 0; background: transparent;}
.stMarkdown th {font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--char); font-weight: 500;
        text-align: left; border: none !important; border-bottom: 1px solid var(--ink) !important; padding: 0.8rem 1rem 0.8rem 0;
        background: transparent !important;}
.stMarkdown td {border: none !important; border-bottom: 1px solid var(--hair) !important; padding: 1rem 1rem 1rem 0;
        font-size: 0.9rem; vertical-align: top; background: transparent !important;}
.stMarkdown tr {background: transparent !important;}

/* ---------- trace ---------- */
.rd-stage {display: flex; align-items: baseline; gap: 0.9rem; margin: 2.2rem 0 1rem 0; padding-top: 0.9rem;
           border-top: 1px solid var(--ink);}
.rd-stage .m {width: 1.4rem; border-top: 2px solid var(--ink); transform: translateY(-0.25rem);}
.rd-stage .t {font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink); font-weight: 500;}
.rd-agent {display: flex; align-items: baseline; gap: 0.6rem; margin: 1.3rem 0 0.2rem 0;}
.rd-agent .n {font-family: 'Jost', sans-serif; font-size: 1.25rem; font-weight: 300; color: var(--ink); min-width: 1.6rem;}
.rd-agent .t {font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--char); font-weight: 500;}

/* ---------- notices (replace st.error / success / warning / info) ---------- */
.rd-note {background: var(--white); border: 1px solid var(--hair); border-left: 3px solid var(--dash); padding: 1.15rem 1.4rem;
          margin: 1rem 0;}
.rd-note.neutral {background: var(--fill); border: none;}
.rd-note.investigate {border-left: 3px solid var(--ink);}
.rd-note.isolated {border-left: 3px solid var(--dash);}
.rd-note .k {font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--char); font-weight: 500;}
.rd-note .h {font-family: 'Jost', sans-serif; font-size: 1.5rem; font-weight: 300; color: var(--ink);
             line-height: 1.25; margin: 0.4rem 0 0.5rem 0;}
.rd-note .h .v {display: inline-block; font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; font-weight: 500;
                line-height: 1; padding: 0.4rem 0.75rem; border: 1px solid var(--ink); color: var(--ink);}
.rd-note.investigate .h .v {background: var(--ink); color: var(--white); border-color: var(--ink);}
.rd-note.isolated .h .v {background: transparent; color: var(--char); border-color: var(--dash);}
.rd-note .m {font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--char); margin-bottom: 0.6rem;}
.rd-note .b {font-size: 0.92rem; line-height: 1.7; color: var(--char);}
.rd-note .b b {color: var(--ink); font-weight: 500;}
.rd-note.plain {background: transparent; border: none; border-left: 3px solid var(--hair); padding: 0.4rem 0 0.4rem 1.2rem;}

/* ---------- case file ---------- */
.rd-case {background: var(--white); border: 1px solid var(--hair); padding: 1.7rem 1.8rem; margin: 0 0 1.6rem 0;}
.rd-case h4 {font-family: 'Jost', sans-serif !important; font-size: 1.6rem; font-weight: 400 !important;
             line-height: 1.2; margin: 0.5rem 0 0.9rem 0; padding: 0;}
.rd-case h4 .id {color: var(--char); font-weight: 300;}
.rd-chip {display: inline-block; padding: 4px 10px; border: 1px solid var(--hair); font-size: 0.65rem; letter-spacing: 0.12em;
          text-transform: uppercase; color: var(--char); margin: 0 6px 6px 0; font-weight: 500;}
.rd-chip.high {background: var(--ink); border-color: var(--ink); color: var(--white);}
.rd-chip.medium {border-color: var(--ink); color: var(--ink);}
.rd-chip.low {border-color: var(--dash); color: var(--char);}
.rd-field {margin-top: 1.1rem; padding-top: 0.9rem; border-top: 1px solid var(--hair);}
.rd-field .k {font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--char); font-weight: 500;}
.rd-field .v {font-size: 0.94rem; line-height: 1.65; color: var(--ink); margin-top: 0.25rem;}
.rd-field .v.muted {color: var(--char);}
.rd-act {display: flex; gap: 1rem; padding: 0.7rem 0; border-bottom: 1px solid var(--hair); font-size: 0.9rem; line-height: 1.55;}
.rd-act .tier {font-family: 'Jost', sans-serif; font-weight: 500; font-size: 0.8rem; letter-spacing: 0.06em; color: var(--ink);
               min-width: 2rem;}
.rd-act .who {color: var(--grey);}
.rd-appr-h {font-family: 'Jost', sans-serif; font-size: 1.15rem; font-weight: 400; line-height: 1.3; color: var(--ink);
            margin: 0 0 0.25rem 0;}
.rd-appr-h .tier {color: var(--ink); font-weight: 600; margin-right: 0.5rem;}
.rd-appr-to {font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--char); margin-bottom: 0.6rem;}
.rd-decided {font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; font-weight: 500; padding-top: 0.6rem;
             border-top: 1px solid var(--hair); color: var(--ink);}
.rd-decided.rejected {color: var(--char);}

/* ---------- metrics ---------- */
.rd-metric {border-top: 1px solid var(--ink); padding-top: 1.1rem; margin: 0 0 2rem 0;}
.rd-metric .big {font-family: 'Jost', sans-serif; font-weight: 300; font-size: 3.2rem; line-height: 1; color: var(--ink);
                 letter-spacing: -0.01em;}
.rd-metric .cap {font-size: 0.88rem; color: var(--ink); margin-top: 0.75rem; line-height: 1.5;}
.rd-metric .sub {font-size: 0.78rem; color: var(--grey); margin-top: 0.3rem; line-height: 1.5;}
.rd-metric .plus {font-family: 'Jost', sans-serif; font-weight: 300; font-size: 1.8rem; color: var(--ink);
                  margin-top: 1.1rem; padding-top: 0.9rem; border-top: 1px solid var(--hair);}
.rd-h {font-family: 'Jost', sans-serif; font-weight: 400; font-size: 1.6rem; line-height: 1.25; color: var(--ink);
       margin: 2.6rem 0 0.3rem 0;}
.rd-h-sub {font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--char); margin-bottom: 1.2rem;}
</style>""", unsafe_allow_html=True)

if "events" not in st.session_state:
    st.session_state.events = []
    st.session_state.scenario = list(SCENARIOS)[0]
    st.session_state.mode = None


def clean(s):
    return html.unescape(str(s))


def _esc(s):
    """Clean, then HTML-escape dynamic text before it is injected into markup."""
    return html.escape(clean(s))


def _notice(body, tone="neutral", kicker="", heading="", meta=""):
    """Editorial notice block used instead of st.error / st.success / st.warning / st.info.
    All arguments except `tone` must already be HTML-escaped."""
    parts = [f'<div class="rd-note {tone}">']
    if kicker:
        parts.append(f'<div class="k">{kicker}</div>')
    if heading:
        parts.append(f'<div class="h">{heading}</div>')
    if meta:
        parts.append(f'<div class="m">{meta}</div>')
    if body:
        parts.append(f'<div class="b">{body}</div>')
    parts.append("</div>")
    return "".join(parts)


def _label(text, bare=False):
    return f'<div class="rd-label{" bare" if bare else ""}">{html.escape(text)}</div>'


def _metric(big, cap, sub="", extra=""):
    return (f'<div class="rd-metric"><div class="big">{big}</div><div class="cap">{cap}</div>'
            + (f'<div class="sub">{sub}</div>' if sub else "") + extra + "</div>")


# ------------------------------------------------------------------ rendering
def render_event(e, box):
    agent, kind = e.get("agent", "System"), e["type"]
    num, short = AGENT_STYLE.get(agent, ("", agent))
    with box:
        if kind == "stage":
            st.markdown(f'<div class="rd-stage"><span class="m"></span><span class="t">{_esc(e["text"])}</span></div>',
                        unsafe_allow_html=True)
        elif kind == "thought":
            st.markdown(f'<div class="rd-agent"><span class="n">{num}</span><span class="t">{html.escape(short)}</span></div>',
                        unsafe_allow_html=True)
            st.markdown(clean(e["text"]))
        elif kind == "tool_result":
            inp = e.get("input")
            label = f"{num} · {short} · `{e['tool']}`" if num else f"{short} · `{e['tool']}`"
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
                tone = "investigate" if dec == "INVESTIGATE" else "isolated" if dec == "ISOLATED" else "neutral"
                meta = " · ".join(_esc(x) for x in (d.get("style", ""), d.get("category", "")) if x)
                st.markdown(_notice(_esc(d.get("rationale", "")), tone, kicker=f"{num} · Triage decision",
                                    heading=f'<span class="v">{_esc(dec)}</span>', meta=meta),
                            unsafe_allow_html=True)
            else:
                st.markdown(_notice(f"<b>Root cause.</b> {_esc(d.get('root_cause', ''))}", "neutral",
                                    kicker=f"{num} · Investigation result" if num else "Investigation result",
                                    heading=f"Confidence: {_esc(d.get('confidence', '?'))}"),
                            unsafe_allow_html=True)
                hyps = d.get("hypotheses") or []
                if hyps:
                    st.dataframe(pd.DataFrame(hyps), hide_index=True, width="stretch")
        elif kind == "briefing":
            st.markdown(f'<div class="rd-agent"><span class="n">{num}</span>'
                        f'<span class="t">Briefing for the owner team</span></div>', unsafe_allow_html=True)
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
            status.caption(f"Agents working · {time.time() - t0:.0f}s")
            continue
        if e is None:
            break
        events.append(e)
        if e["type"] == "tool_call":
            pending[(e["agent"], e["tool"])] = e.get("input")
            status.caption(f"{e['agent']} is calling `{e['tool']}`")
            continue
        if e["type"] == "tool_result":
            e = dict(e, input=pending.pop((e["agent"], e["tool"]), None))
        render_event(e, box)
    status.empty()
    if err:
        box.markdown(_notice(html.escape(err[0]), "investigate", kicker="Run failed"), unsafe_allow_html=True)
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
        st.markdown(_notice("No case open. Isolated returns are handled normally and only logged.", "plain"),
                    unsafe_allow_html=True)
        return
    for c in db["cases"].values():
        conf = c.get("confidence") or "—"
        cc = {"High": "high", "Medium": "medium", "Low": "low"}.get(conf, "")
        st.markdown(f"""<div class="rd-case"><div class="rd-label bare">Case file</div>
<h4><span class="id">{_esc(c['case_id'])}</span> &nbsp;{_esc(c['style'])}</h4>
<span class="rd-chip">{_esc(c['category'])}</span><span class="rd-chip {cc}">Confidence &middot; {_esc(conf)}</span><span class="rd-chip">{_esc(c['status'].replace('_', ' '))}</span>
<div class="rd-field"><div class="k">Root cause</div><div class="v">{_esc(c.get('root_cause') or '')}</div></div>
<div class="rd-field"><div class="k">Owner</div><div class="v muted">{_esc(c.get('owner_team') or '')} &middot; opened as of {_esc(c['opened_as_of'])}</div></div>
</div>""", unsafe_allow_html=True)
        acts = [a for a in db["actions"] if a["case_id"] == c["case_id"]]
        if acts:
            st.markdown(_label("Recorded demo actions"), unsafe_allow_html=True)
            for a in acts:
                det = a["detail"]
                extra = ""
                if isinstance(det, dict) and "amount_cad" in det:
                    extra = f" — CA${_esc(det['amount_cad'])} in simulated fee waivers for {_esc(det['returns_refunded'])} returns"
                who = "" if a["executed_by"] == "agent" else f' <span class="who">· {_esc(a["executed_by"])}</span>'
                st.markdown(f'<div class="rd-act"><span class="tier">T{_esc(a["tier"])}</span>'
                            f'<span>{_esc(a["action"])}{extra}{who}</span></div>', unsafe_allow_html=True)
        aps = [a for a in db["approvals"] if a["case_id"] == c["case_id"]]
        if aps:
            st.markdown('<div style="height:1.6rem"></div>' + _label("Waiting for a human decision"), unsafe_allow_html=True)
            for a in aps:
                det = a["detail"] if isinstance(a["detail"], dict) else {}
                body = next((clean(v) for k, v in det.items() if k in ("proposed_text", "draft", "offer", "scope")), "")
                with st.container(border=True, key="rdcard" + a["approval_id"]):
                    st.markdown(f'<div class="rd-appr-h"><span class="tier">T{_esc(a["tier"])}</span>{_esc(a["action"])}</div>'
                                f'<div class="rd-appr-to">For {_esc(a["approver"])}</div>', unsafe_allow_html=True)
                    if body:
                        st.caption(body[:600])
                    if a["status"] == "PENDING":
                        b1, b2 = st.columns(2)
                        if b1.button("Approve", key="ap" + a["approval_id"], type="primary", width="stretch"):
                            store.decide_approval(a["approval_id"], True, "Demo reviewer")
                            st.rerun()
                        if b2.button("Decline", key="rj" + a["approval_id"], width="stretch"):
                            store.decide_approval(a["approval_id"], False, "Demo reviewer")
                            st.rerun()
                    else:
                        tone = "" if a["status"] == "APPROVED" else " rejected"
                        st.markdown(f'<div class="rd-decided{tone}">{_esc(a["status"])}</div>', unsafe_allow_html=True)
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
        st.markdown(_notice("Synthetic demo data is used for functional checks. Historical ALDO impact numbers do not describe this dataset.", "plain"), unsafe_allow_html=True)
        st.caption("The historical backtest is preserved in evaluation/results/. See evaluation/README.md for its limitations.")
        return
    if not data_available():
        st.markdown(_notice("Prepare local data or configure Athena to explore impact.", "plain"), unsafe_allow_html=True)
        return
    if not BACKTEST.is_file():
        st.markdown(_notice("No backtest results found. See evaluation/README.md to generate and select a result file.", "plain"), unsafe_allow_html=True)
        return
    st.caption("Historical retrospective analysis; these figures are not measured savings. See evaluation/README.md for methodology and limitations.")
    df, both = backtest()
    tiles = [
        (f"#{int(both.returns_at_flag.median())}", "related return at which the agent flags a systemic issue",
         f"vs #{int(both.returns_at_report.median())} with a monthly report"),
        (f"{int(both.lead_days.median())} days", "earlier detection (median)", "same cases, same data"),
        (f"{len(df):,}", "systemic signals found in 2 years", f"{(df.category == 'Quality').sum()} quality, "
         f"{df.category.str.startswith('Fit').sum()} fit"),
        (f"{df.report_date.isna().sum():,}", "signals a monthly report never catches", "too small per month to show up"),
    ]
    st.markdown(_label("Backtest on two years of returns"), unsafe_allow_html=True)
    cols = st.columns(4, gap="large")
    for col, (big, label, sub) in zip(cols, tiles):
        col.markdown(_metric(html.escape(big), html.escape(label), html.escape(sub)), unsafe_allow_html=True)

    if "sustained_next_28d" in df:
        st.caption(f"Honest signal quality: only {df.sustained_next_28d.mean():.0%} of raw statistical flags are still present "
                   f"28 days later ({df[df.category == 'Quality'].sustained_next_28d.mean():.0%} for quality). That is why a flag "
                   "only opens a case: the Investigator Agent decides confidence, and stock holds, supplier claims and "
                   "customer outreach need High confidence plus human approval.")
    st.markdown('<div class="rd-h">Glindafied: when would we have known?</div>'
                '<div class="rd-h-sub">Weekly defective returns, October 2024 to March 2025</div>', unsafe_allow_html=True)
    import altair as alt
    w = glindafied_weeks()
    marks = pd.DataFrame({"date": pd.to_datetime(["2024-10-28", "2024-12-31"]),
                          "label": ["Return Detective flags (5th defect)", "Monthly report flags (52nd defect)"],
                          "color": [BLACK, GREY]})
    bars = alt.Chart(w).mark_bar(color=CHARCOAL, size=14).encode(
        x=alt.X("week_start:T", title="Week"), y=alt.Y("quality_returns:Q", title="'Defective / poor quality' returns"),
        tooltip=[alt.Tooltip("week_start:T", title="Week of"), alt.Tooltip("quality_returns:Q", title="Quality returns"),
                 alt.Tooltip("all_returns:Q", title="All returns")])
    rules = alt.Chart(marks).mark_rule(strokeWidth=1.5).encode(
        x="date:T", tooltip=["label:N", alt.Tooltip("date:T", title="Date")],
        color=alt.Color("label:N", scale=alt.Scale(domain=list(marks.label), range=list(marks.color)),
                        legend=alt.Legend(title=None, orient="top", labelLimit=400, labelFontSize=12,
                                          symbolType="stroke", symbolStrokeWidth=2)),
        strokeDash=alt.StrokeDash("label:N", scale=alt.Scale(domain=list(marks.label), range=[[1, 0], [6, 4]]),
                                  legend=alt.Legend(title=None, orient="top", labelLimit=400, labelFontSize=12,
                                                    symbolType="stroke", symbolStrokeWidth=2)))
    chart = ((bars + rules).properties(height=320, background="transparent")
             .configure(font="Jost")
             .configure_view(strokeWidth=0)
             .configure_axis(gridColor=HAIR, domainColor=DASH, tickColor=DASH, labelColor=GREY, titleColor=CHARCOAL,
                             labelFont="Jost", titleFont="Jost", labelFontSize=11, titleFontSize=11,
                             titleFontWeight=400, titlePadding=12)
             .configure_axisX(grid=False)
             .configure_legend(labelFont="Jost", labelColor=CHARCOAL, padding=0, offset=18))
    st.altair_chart(chart, width="stretch")
    st.caption("Real ALDO return data. The agent's screen fires 64 days before a month-end report would, with 47 fewer defective pairs returned.")

    st.markdown('<div class="rd-h">Value of earlier detection</div>'
                '<div class="rd-h-sub">Illustrative. Adjust the assumptions.</div>', unsafe_allow_html=True)
    c1, c2, c3 = st.columns(3, gap="large")
    cost = c1.slider("Cost of one avoidable return to ALDO (CA$)", 10, 80, 30)
    prevent = c2.slider("Share of returns avoided once the cause is fixed early", 10, 80, 40, format="%d%%")
    gap = int(both.returns_at_report.sum() - both.returns_at_flag.sum())
    value = gap * cost * prevent / 100 / 2  # two years of data -> per year
    never = df[df.report_date.isna()]
    if "sustained_next_28d" in df:
        never = never[never.sustained_next_28d]
    upside = int(never.after_flag.sum()) * cost * prevent / 100 / 2
    c3.markdown(_metric(f"CA${value:,.0f} / yr",
                        f"conservative: {gap:,} returns happened between the agent flag and the monthly-report flag (2 yrs)",
                        extra=f'<div class="plus">+ up to CA${upside:,.0f} / yr</div>'
                              '<div class="sub">from sustained signals a monthly report never catches</div>'),
                unsafe_allow_html=True)
    st.caption("Plus customer fairness: 26-41% of online customers returning for quality, wrong item or transit damage were still charged a restocking fee.")
    with st.expander("Backtest by category"):
        t = both.groupby("category").agg(cases=("style", "size"), agent_flags_at=("returns_at_flag", "median"),
                                          report_flags_at=("returns_at_report", "median"), days_earlier=("lead_days", "median"))
        st.dataframe(t, width="stretch")


def architecture_tab():
    st.markdown('<div class="rd-h" style="margin-top:0">Built on AWS</div>'
                '<div class="rd-h-sub">Services and their role in Return Detective</div>', unsafe_allow_html=True)
    st.caption("Retail actions, notifications and verification schedules are local simulations. No production retail system is connected.")
    st.markdown("""
| Layer | AWS service | Role in Return Detective |
|---|---|---|
| Data | **DuckDB** locally; **Amazon S3 + Glue + Athena** adapter | Query the configured prepared dataset with SQL |
| Reasoning | **Amazon Bedrock (Anthropic Claude)** | Triage, Investigator and Response agents |
| Agent framework | **Strands Agents SDK** | Tool use, multi-agent pipeline, hooks for the live trace |
| Policy | Playbook document read by the agents | Root-cause classes, confidence levels, authority matrix |
| Guardrails | Tool authority checks; optional Bedrock Guardrail | Prototype fee authority and approvals for stock holds, claims and outreach |
| Case memory | **Local JSON**; DynamoDB planned | Cases, simulated actions, approval queue and audit trail |
| Notifications | **Local simulation**; SNS planned | Record owner notifications and approval proposals |
| Build | **Kiro** | AI IDE used to build the prototype |
""")
    st.markdown('<div class="rd-h">Where the expensive model runs</div>'
                '<div class="rd-h-sub">Model tiering by pipeline stage</div>', unsafe_allow_html=True)
    st.markdown("""
| Stage | When it runs | Model |
|---|---|---|
| Statistical screen, SQL on configured backend | Called by Triage through screen_style | No model inside the screen |
| Triage | Each selected incoming return in this prototype | RD_FAST_MODEL_ID, or RD_MODEL_ID |
| Investigator | When Triage returns INVESTIGATE | **RD_MODEL_ID** |
| Response | After an investigation completes | RD_FAST_MODEL_ID, or RD_MODEL_ID |
""")
    st.caption("Each agent can make multiple model requests while using tools. Historical signal counts are not measured daily model-call volumes or costs; automatic pre-screening before Triage is not implemented.")


# ------------------------------------------------------------------ layout
st.markdown('<div class="rd-bar">ALDO<span class="dot">·</span>Returns intelligence<span class="dot">·</span>Internal</div>'
            '<div class="rd-mast"><div class="rd-wordmark">Return Detective</div></div>', unsafe_allow_html=True)
st.markdown('<div class="rd-sub">Every return is a clue. Three AI agents read each ALDO return, decide whether it is '
            'an isolated case or an emerging problem, investigate the cause and act within a written authority matrix.</div>',
            unsafe_allow_html=True)
st.markdown('<div class="rd-agents">'
            '<div class="a"><span class="n">I</span><span class="t">Triage</span><span class="d">isolated or pattern</span></div>'
            '<div class="a"><span class="n">II</span><span class="t">Investigator</span><span class="d">root cause and confidence</span></div>'
            '<div class="a"><span class="n">III</span><span class="t">Response</span><span class="d">act within authority</span></div>'
            '</div>', unsafe_allow_html=True)

with st.sidebar:
    st.caption("Synthetic data" if SYNTHETIC else "Authorized ALDO data")
    if not data_available():
        st.markdown(_notice("Generate local demo data: python scripts/generate_synthetic_data.py", "plain"), unsafe_allow_html=True)
    st.caption("Actions update the local demo store; no retail system is connected.")
    st.header("Scenario")
    if st.session_state.scenario not in SCENARIOS:
        st.session_state.scenario = list(SCENARIOS)[0]
    name = st.radio("Incoming return", list(SCENARIOS), index=list(SCENARIOS).index(st.session_state.scenario))
    st.session_state.scenario = name
    sc = SCENARIOS[name]
    st.caption(sc["blurb"])
    st.markdown(f'<div class="rd-field" style="margin-bottom:1.4rem"><div class="k">Return</div>'
                f'<div class="v">#{_esc(sc["return_id"])} · {_esc(sc["as_of"])}</div></div>', unsafe_allow_html=True)
    has_trace = os.path.exists(trace_path(sc["key"]))
    mode = st.radio("Mode", ["Live (Bedrock)", "Replay saved live run", "Scripted (no LLM)"],
                    index=2 if SYNTHETIC else 0, help="Every live run is saved. Replay shows a previous live run instantly.")
    go = st.button("Run", type="primary", width="stretch",
                   disabled=(mode == "Replay saved live run" and not has_trace) or not data_available()
                   or (mode == "Live (Bedrock)" and not os.environ.get("RD_MODEL_ID")))
    if mode == "Live (Bedrock)" and not os.environ.get("RD_MODEL_ID"):
        st.caption("Set RD_MODEL_ID and AWS credentials before a live run.")
    if mode == "Replay saved live run" and not has_trace:
        st.caption("No saved live run yet for this scenario.")
    st.divider()
    inv_model = os.environ.get("RD_MODEL_ID") or "not configured"
    fast_model = os.environ.get("RD_FAST_MODEL_ID") or f"{inv_model} (same)"
    st.caption(f"Data · {BACKEND}  \n"
               f"Investigator · {inv_model}  \n"
               f"Triage + Response · {fast_model}")
    if st.button("Reset case store", width="stretch"):
        store.reset()
        st.session_state.events = []
        st.rerun()

tab1, tab2, tab3 = st.tabs(["Live investigation", "Business impact", "AWS architecture"])
with tab1:
    left, right = st.columns([1.55, 1], gap="large")
    with left:
        st.markdown(_label("Agent reasoning and tool calls"), unsafe_allow_html=True)
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
            box.markdown(_notice("Pick a scenario on the left and press <b>Run</b>.", "neutral",
                                 heading="Awaiting an incoming return"), unsafe_allow_html=True)
    with right:
        st.markdown(_label("Case file, actions and approvals"), unsafe_allow_html=True)
        case_panel()
with tab2:
    impact_tab()
with tab3:
    architecture_tab()
