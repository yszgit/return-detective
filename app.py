"""Return Detective - demo UI (Streamlit).

  streamlit run app.py

Daily grouped statistics screen every supplied return without model calls. Selected signals
reuse the existing Investigator and Response agents; single-return examples retain Triage.
The operations workspace separates monitoring, case evidence, and approvals/follow-up.
"""
import html
import json
import re

import pandas as pd
import streamlit as st

from rd import store
# Agent identity: roman numeral + short name (no colour coding, no icons).
AGENT_STYLE = {"Triage Agent": ("I", "Triage"), "Investigator Agent": ("II", "Investigator"),
               "Response Agent": ("III", "Response"), "System": ("", "System")}

# Browser-tab icon: white "ALDO" on a black tile (inline SVG data URI, no extra file).
ALDO_ICON = ("data:image/svg+xml;base64,PHN2ZyB4bWxucz0naHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmcnIHZpZXdCb3g9JzAgMCA2NCA2NCc+PHJlY3Qgd2lkdGg9JzY0JyBoZWlnaHQ9JzY0JyByeD0nMTAnIGZpbGw9J2JsYWNrJy8+PHRleHQgeD0nMzInIHk9JzQwJyBmb250LWZhbWlseT0nQXJpYWwsSGVsdmV0aWNhLHNhbnMtc2VyaWYnIGZvbnQtd2VpZ2h0PSc3MDAnIGZvbnQtc2l6ZT0nMTgnIHRleHQtYW5jaG9yPSdtaWRkbGUnIGZpbGw9J3doaXRlJz5BTERPPC90ZXh0Pjwvc3ZnPg==")
st.set_page_config(page_title="Return Detective", page_icon=ALDO_ICON, layout="wide")
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Jost:wght@300;400;500;600&display=swap');
:root {--white:#FFFFFF; --ink:#000000; --char:#333333; --grey:#767676; --dash:#BDBDBD; --hair:#E6E6E6; --fill:#F5F5F5;}

/* ---------- base ---------- */
.stApp {background: var(--white); color: var(--ink); font-family: 'Jost', sans-serif; accent-color: var(--ink);}
.stApp button, .stApp input, .stApp textarea, .stApp select {font-family: 'Jost', sans-serif;}
header[data-testid="stHeader"] {background: var(--white);}
.block-container {padding: 3.25rem 3rem 4rem 3rem !important; max-width: none;}
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
.rd-mast {margin: 0 -3rem 0.8rem -3rem; padding: 0.65rem 3rem; border-bottom: 1px solid var(--hair); text-align: center;}
.rd-wordmark {font-family: 'Jost', sans-serif; font-weight: 600; font-size: 1.45rem; line-height: 1; letter-spacing: 0.04em;
              text-transform: uppercase; color: var(--ink);}
@media (max-width: 640px) {
  .block-container {padding-left: 1rem !important; padding-right: 1rem !important;}
  .rd-bar {margin: 0 -1rem; padding-left: 1rem; padding-right: 1rem;}
  .rd-mast {margin-left: -1rem; margin-right: -1rem; padding-left: 1rem; padding-right: 1rem;}
  .rd-wordmark {font-size: 1.8rem;}
}
.rd-sub {font-size: 0.95rem; font-weight: 400; color: var(--char); max-width: 880px; line-height: 1.5; margin: 0 0 0.65rem 0;}
.rd-page-title {font-size: 1.8rem !important; margin: 0.15rem 0 0.4rem !important; padding: 0 !important;}
.rd-kpis {display:grid; grid-template-columns:repeat(var(--count),minmax(0,1fr)); gap:12px; margin:0.6rem 0;}
.rd-kpi-label {font-size:0.8rem; line-height:1.3; min-height:2.4em; color:var(--char);}
.rd-kpi-value {font-size:2rem; line-height:1.15; font-weight:400; overflow-wrap:anywhere;}
@media (max-width:600px) {
  .rd-kpis {gap:8px;}
  .rd-kpi-label {font-size:0.68rem;}
  .rd-kpi-value {font-size:1.35rem;}
}
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
[data-testid="stExpander"] {margin-top: -0.5rem;}
[data-testid="stExpander"] details {border: none !important; border-left: 1px solid var(--hair) !important; border-radius: 0 !important; background: transparent;}
[data-testid="stExpander"] summary {padding: 0.2rem 0.8rem; border-radius: 0 !important;}
[data-testid="stExpander"] summary:hover {background: transparent;}
[data-testid="stExpander"] summary p {font-size: 0.78rem; color: var(--grey);}
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
.rd-stage {display: flex; align-items: baseline; gap: 0.9rem; margin: 0.9rem 0 0.4rem 0; padding-top: 0.4rem;
           border-top: 1px solid var(--hair);}
.rd-stage .m {display: none;}
.rd-stage .t {font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--ink); font-weight: 500;}
.rd-agent {display: flex; align-items: baseline; gap: 0.6rem; margin: 0.8rem 0 0.1rem 0;}
.rd-agent .n {font-family: 'Jost', sans-serif; font-size: 1rem; font-weight: 300; color: var(--ink); min-width: 1.6rem;}
.rd-agent .t {font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--char); font-weight: 500;}
[data-testid="stElementContainer"]:has(.rd-agent) + [data-testid="stElementContainer"] .stMarkdown p {margin: 0 0 0.5rem 0;}

/* ---------- notices (replace st.error / success / warning / info) ---------- */
.rd-note {background: var(--white); border: none; border-left: 2px solid var(--dash); padding: 0.6rem 1rem;
          margin: 0.6rem 0;}
.rd-note.neutral {background: var(--fill); border: none;}
.rd-note.investigate {border-left: 2px solid var(--ink);}
.rd-note.isolated {border-left: 2px solid var(--dash);}
.rd-note .k {font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--char); font-weight: 500;}
.rd-note .h {font-family: 'Jost', sans-serif; font-size: 1.2rem; font-weight: 300; color: var(--ink);
             line-height: 1.25; margin: 0.25rem 0 0.35rem 0;}
.rd-note .h .v {display: inline-block; font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; font-weight: 500;
                line-height: 1; padding: 0.4rem 0.75rem; border: 1px solid var(--ink); color: var(--ink);}
.rd-note.investigate .h .v {background: var(--ink); color: var(--white); border-color: var(--ink);}
.rd-note.isolated .h .v {background: transparent; color: var(--char); border-color: var(--dash);}
.rd-note .m {font-size: 0.75rem; letter-spacing: 0.08em; text-transform: uppercase; color: var(--char); margin-bottom: 0.6rem;}
.rd-note .b {font-size: 0.92rem; line-height: 1.7; color: var(--char);}
.rd-note .b b {color: var(--ink); font-weight: 500;}
.rd-note.plain {background: transparent; border: none; border-left: 3px solid var(--hair); padding: 0.4rem 0 0.4rem 1.2rem;}

/* ---------- case file ---------- */
.rd-case {background: var(--white); border: 1px solid var(--hair); padding: 1.1rem 1.3rem; margin: 0 0 1rem 0;}
.rd-case h4 {font-family: 'Jost', sans-serif !important; font-size: 1.6rem; font-weight: 400 !important;
             line-height: 1.2; margin: 0.5rem 0 0.9rem 0; padding: 0;}
.rd-case h4 .id {color: var(--char); font-weight: 300;}
.rd-chip {display: inline-block; padding: 4px 10px; border: 1px solid var(--hair); font-size: 0.65rem; letter-spacing: 0.12em;
          text-transform: uppercase; color: var(--char); margin: 0 6px 6px 0; font-weight: 500;}
.rd-chip.high {background: var(--ink); border-color: var(--ink); color: var(--white);}
.rd-chip.medium {border-color: var(--ink); color: var(--ink);}
.rd-chip.low {border-color: var(--dash); color: var(--char);}
.rd-field {margin-top: 0.7rem; padding-top: 0.6rem; border-top: 1px solid var(--hair);}
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
.rd-metric {border-top: 1px solid var(--hair); padding-top: 0.8rem; margin: 0 0 1.3rem 0;}
.rd-metric .big {font-family: 'Jost', sans-serif; font-weight: 300; font-size: 2.6rem; line-height: 1; color: var(--ink);
                 letter-spacing: -0.01em;}
.rd-metric .cap {font-size: 0.88rem; color: var(--ink); margin-top: 0.75rem; line-height: 1.5;}
.rd-metric .sub {font-size: 0.78rem; color: var(--grey); margin-top: 0.3rem; line-height: 1.5;}
.rd-metric .plus {font-family: 'Jost', sans-serif; font-weight: 300; font-size: 1.8rem; color: var(--ink);
                  margin-top: 1.1rem; padding-top: 0.9rem; border-top: 1px solid var(--hair);}
.rd-h {font-family: 'Jost', sans-serif; font-weight: 400; font-size: 1.6rem; line-height: 1.25; color: var(--ink);
       margin: 1.8rem 0 0.3rem 0;}
.rd-h-sub {font-size: 0.7rem; letter-spacing: 0.12em; text-transform: uppercase; color: var(--char); margin-bottom: 1.2rem;}
</style>""", unsafe_allow_html=True)

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
            # Display only: drop a trailing JSON block (starts at a line beginning with "{"); the decision card shows it.
            st.markdown(re.sub(r"^\{.*\Z", "", clean(e["text"]), flags=re.M | re.S).rstrip())
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
            if agent == "Triage Agent" or "decision" in d:
                dec = d.get("decision", "?")
                tone = "investigate" if dec == "INVESTIGATE" else "isolated" if dec == "ISOLATED" else "neutral"
                meta = " · ".join(_esc(x) for x in (d.get("style", ""), d.get("category", "")) if x)
                st.markdown(_notice(_esc(d.get("rationale", "")), tone, kicker="Triage decision" if agent == "Triage Agent" else "Statistical screening",
                                    heading=f'<span class="v">{_esc(dec)}</span>', meta=meta),
                            unsafe_allow_html=True)
            else:
                st.markdown(_notice(f"<b>Likely explanation.</b> {_esc(d.get('root_cause', ''))}", "neutral",
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
        elif kind == 'verification':
            d = e['data']
            st.info(f"Verification: {d['outcome'].replace('_', ' ')} · {d['as_of']}")
            st.caption('Observed change in the signal; causal savings have not been established.')
        elif kind == 'usage':
            d = e['data']
            st.caption(f"{short}: {d['seconds']}s · input tokens {d.get('input_tokens', 'unknown')} · "
                       f"output tokens {d.get('output_tokens', 'unknown')}")


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


def agent_evaluation_panel():
    from rd.ui_evaluation import render_comparison
    render_comparison()


def impact_tab():
    from rd.ui_evaluation import render_historical_replay
    render_historical_replay()


def architecture_tab():
    st.markdown('<div class="rd-h" style="margin-top:0">Built on AWS</div>'
                '<div class="rd-h-sub">Services and their role in Return Detective</div>', unsafe_allow_html=True)
    st.caption("Retail actions, notifications and verification schedules are local simulations. No production retail system is connected.")
    case_storage = "Amazon DynamoDB" if store.STORE_BACKEND == "dynamodb" else "Local JSON"
    st.markdown(f"""
| Layer | AWS service | Role in Return Detective |
|---|---|---|
| Data | **DuckDB** locally; **Amazon S3 + Glue + Athena** adapter | Query the configured prepared dataset with SQL |
| Reasoning | **Amazon Bedrock (Anthropic Claude)** | Triage, Investigator and Response agents |
| Agent framework | **Strands Agents SDK** | Tool use, multi-agent pipeline, hooks for the live trace |
| Policy | Playbook document read by the agents | Root-cause classes, confidence levels, authority matrix |
| Guardrails | Tool authority checks; optional Bedrock Guardrail | Prototype fee authority and approvals for stock holds, claims and outreach |
| Case memory | **{case_storage}** | Cases, simulated actions, approval queue and audit trail |
| Notifications | **Local simulation**; SNS planned | Record owner notifications and approval proposals |
| Verification | Due dates and checks triggered from UI/CLI | Reopen persistent signals; give prior evidence to Investigator; close observed normal cases |
| Build | **Kiro** | AI IDE used to build the prototype |
""")
    st.markdown('<div class="rd-h">Where the expensive model runs</div>'
                '<div class="rd-h-sub">Model tiering by pipeline stage</div>', unsafe_allow_html=True)
    st.markdown("""
| Stage | When it runs | Model |
|---|---|---|
| Daily statistical screen | All supplied returns on the selected date, grouped SQL | No model calls |
| Triage | Prepared single-return examples | RD_FAST_MODEL_ID, or RD_MODEL_ID |
| Investigator | Explicitly selected daily signal, or Triage INVESTIGATE | **RD_MODEL_ID** |
| Response | After an investigation completes | RD_FAST_MODEL_ID, or RD_MODEL_ID |
""")
    st.caption("The daily screen uses grouped SQL and zero model calls. An explicit signal selection starts Investigator and Response. Each role may make multiple model requests; historical signal counts are not measured model-call volumes or costs.")


# ------------------------------------------------------------------ operations workspace
from rd.ui import render_workspace

render_workspace(render_event, pair_tool_calls, {
    'Historical rule replay': impact_tab,
    'Agent evaluation': agent_evaluation_panel,
    'AWS architecture': architecture_tab,
})
