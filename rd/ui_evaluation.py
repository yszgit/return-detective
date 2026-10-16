"""Measured acceptance results and clearly scoped historical replay views."""
import json

import pandas as pd
import streamlit as st

from .config import ROOT, BACKTEST_PATH, is_synthetic


def render_comparison():
    path = ROOT / 'evaluation/results/agent_comparison.json'
    st.subheader('Fixed tools and real Bedrock agents')
    if not path.is_file():
        st.info('No exported paired benchmark is available yet.')
        return
    bundle = json.loads(path.read_text(encoding='utf-8'))
    st.caption('Same six seeded synthetic cases. These checks measure routing, ownership, approval gates and duplicate handling. Explanation quality still requires human review.')
    st.caption('This benchmark exercises the prepared Triage → Investigator → Response pipeline. The daily monitor uses statistical triage before explicitly starting Investigator and Response.')
    rules, agents = bundle['modes']['rules'], bundle['modes']['agent']
    first, second, third = st.columns(3)
    first.metric('Fixed-tool acceptance', f"{rules['passed']} / {rules['cases']}")
    second.metric('Bedrock acceptance', f"{agents['passed']} / {agents['cases']}")
    measured = [r['seconds'] for r in agents['results']]
    third.metric('Median Bedrock case time', f'{pd.Series(measured).median():.1f}s' if any(v is not None for v in measured) else 'Not measured')
    if rules['passed'] == rules['cases'] and agents['passed'] == agents['cases']:
        st.info('Both approaches passed these acceptance cases. The result establishes functional parity on this set; incremental decision quality remains to be evaluated.')
    indexed = {r['name']: r for r in rules['results']}
    rows = []
    for agent in agents['results']:
        rule = indexed[agent['name']]
        rows.append({'Case': agent['name'], 'Fixed tools': 'Pass' if rule['passed'] else 'Fail',
            'Bedrock': 'Pass' if agent['passed'] else 'Fail', 'Fixed time (s)': rule['seconds'],
            'Bedrock time (s)': agent['seconds'], 'Model cycles': agent['model_cycles'],
            'Input tokens': agent['input_tokens'], 'Output tokens': agent['output_tokens']})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width='stretch')
    st.caption('Token usage is measured when supplied by the SDK. Dollar cost is unmeasured. The fit case accepts the playbook’s documented owner alias; the original failed exact-string check remains in the downloadable report.')
    st.markdown('#### Inspect the difference in one case')
    selected = st.selectbox('Comparison case', [r['name'] for r in agents['results']], index=1)
    agent = next(r for r in agents['results'] if r['name'] == selected)
    rule = indexed[selected]
    for column, label, report in zip(st.columns(2), ['Fixed tools and playbook', 'Real Bedrock investigation'], [rule, agent]):
        with column:
            st.markdown(f'**{label}**')
            result = report.get('result') or {}
            finding = result.get('finding') or {}
            st.write(finding.get('root_cause') or (result.get('triage') or {}).get('rationale') or 'No finding recorded.')
            st.caption(f"Owner: {report.get('owner') or 'No case'} · Confidence: {finding.get('confidence') or 'Not assessed'}")
            if finding.get('hypotheses'):
                st.dataframe(pd.DataFrame(finding['hypotheses']), hide_index=True, width='stretch', height=220)
    st.caption('Review whether the evidence supports each explanation, whether another query changed the recommendation, and whether missing evidence was acknowledged. Additional text or tool calls alone do not prove better decisions.')
    st.download_button('Download measured comparison', path.read_text(encoding='utf-8'),
                       file_name='agent-comparison.json', mime='application/json')


def render_historical_replay():
    st.subheader('Historical statistical replay')
    if is_synthetic():
        st.info('Official historical results are separate from the synthetic dataset currently selected.')
        return
    if not BACKTEST_PATH.is_file():
        st.info('No historical replay result is available.')
        return
    frame = pd.read_csv(BACKTEST_PATH)
    comparable = frame.dropna(subset=['report_date']).copy()
    comparable['lead_days'] = (pd.to_datetime(comparable.report_date) - pd.to_datetime(comparable.flag_date)).dt.days
    st.caption(f"Signal dates {frame.flag_date.min()} to {frame.flag_date.max()}. This fixed evaluation range is independent of the sidebar replay date.")
    first, second, third = st.columns(3)
    first.metric('Statistical signals', f'{len(frame):,}')
    second.metric('Comparable monthly-report cases', len(comparable))
    third.metric('Median detection lead', f"{comparable.lead_days.median():.1f} days" if len(comparable) else 'Unavailable')
    if 'sustained_next_28d' in frame:
        observed = frame['sustained_next_28d'].dropna().map(lambda value: str(value).lower() in ('true', '1'))
        if len(observed):
            st.write(f'**{observed.mean():.1%}** of evaluable signals persisted in the follow-up window. Persistence is a proxy, not confirmed problem accuracy.')
    st.bar_chart(frame.groupby('category').size().rename('Signals'))
    st.caption('The month-end comparator uses a different count threshold and cadence. Lead time does not measure the incremental value of an LLM. No avoided returns, causal savings or annual monetary benefit are inferred here; case-level planning assumptions are available in Case workspace.')
    with st.expander('Results by category'):
        if len(comparable):
            st.dataframe(comparable.groupby('category').agg(comparable_cases=('style', 'size'),
                         median_lead_days=('lead_days', 'median')), width='stretch')
