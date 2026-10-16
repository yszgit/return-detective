"""Operations screens for the Streamlit app; technical traces stay in drawers."""
import datetime as dt
import html
import json
import os
from pathlib import Path
import queue
import threading
import time

import pandas as pd
import streamlit as st

from . import store, workflow
from .config import BACKEND, RUNTIME_DIR, data_available, is_synthetic
from .scenarios import SCENARIOS

PAGES = ['Returns monitor', 'Case workspace', 'Approvals & follow-up']
STATUSES = {'OPEN': 'Open', 'AWAITING_APPROVAL': 'Awaiting approval', 'ACTIONED': 'Action recorded',
            'DECLINED': 'Proposals declined', 'REOPENED': 'Reopened', 'CLOSED': 'Closed'}


def _escape(value):
    return html.escape(str(value))


def _heading(kicker, title, description):
    st.markdown(f'<div class="rd-label bare">{_escape(kicker)}</div><h1>{_escape(title)}</h1>'
                f'<p class="rd-sub">{_escape(description)}</p>', unsafe_allow_html=True)


def _tiles(items):
    for column, (label, value) in zip(st.columns(len(items)), items):
        column.metric(label, value)


def _detail(value):
    if isinstance(value, dict):
        return '\n\n'.join(str(value[key]) for key in ('scope', 'draft', 'offer', 'proposed_text', 'message') if value.get(key)) or 'See technical details.'
    return str(value or '')


@st.cache_data(ttl=600, show_spinner=False)
def _coverage(key):
    return workflow.coverage()


def _run_task(operation, label, case_id=None):
    """Stream progress without making raw model/tool output the main interface."""
    messages, events, output, errors = queue.Queue(), [], [], []

    def worker():
        try:
            output.append(operation(messages.put))
        except Exception as exc:
            errors.append(str(exc))
        finally:
            messages.put(None)

    started = time.monotonic()
    threading.Thread(target=worker, daemon=True).start()
    with st.status(label, expanded=True) as status:
        progress = st.empty()
        while True:
            try:
                event = messages.get(timeout=0.25)
            except queue.Empty:
                progress.caption(f'Working · {time.monotonic() - started:.0f}s')
                continue
            if event is None:
                break
            events.append(event)
            if event['type'] == 'stage':
                st.write(event['text'])
            elif event['type'] == 'tool_call':
                progress.caption(f"{event['agent']} is gathering evidence or recording the next step.")
        progress.empty()
        status.update(label='Needs attention' if errors else 'Completed', state='error' if errors else 'complete')
    result = output[0] if output else {}
    case_id = (result or {}).get('case_id') or case_id
    trace = {'events': events, 'result': result, 'error': errors[0] if errors else None,
             'case_id': case_id, 'source_key': workflow.source_key(),
             'namespace': store._NAMESPACE, 'mode': st.session_state.investigation_mode,
             'seconds': round(time.monotonic() - started, 2)}
    directory = Path(RUNTIME_DIR) / 'traces' / workflow.source_key()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f'run-{time.time_ns()}.json'
    path.write_text(json.dumps(trace, default=str, ensure_ascii=False), encoding='utf-8')
    st.session_state.events = events
    st.session_state.last_trace = str(path)
    if case_id:
        st.session_state.selected_case_id = case_id
    if errors:
        st.error(errors[0])
        return None
    outcome = (result or {}).get('outcome')
    if outcome and outcome not in ('INVESTIGATED', 'ATTACHED_TO_CASE'):
        st.session_state.notice = {'text': outcome.replace('_', ' ').title() +
            (f" · {result['message']}" if result.get('message') else '') +
            (f" · Due {result['due_on']}" if result.get('due_on') else ''),
            'tone': 'success' if outcome in ('REOPENED', 'SIGNAL_SUBSIDED') else 'info'}
    else:
        st.session_state.notice = f"Completed · {case_id}" if case_id else 'Completed. Open Case workspace to review the result.'
        if case_id:
            st.session_state.next_page = PAGES[1]
    st.rerun()


def _technical(render_event, pair_tool_calls, case=None):
    with st.expander('Technical details', expanded=False):
        if case:
            st.json(case)
        if st.checkbox('Show agent tool calls and full output', key='show_trace_' + (case or {}).get('case_id', 'monitor')):
            events = st.session_state.get('events', [])
            directory = Path(RUNTIME_DIR) / 'traces' / workflow.source_key()
            paths = sorted(directory.glob('run-*.json'), reverse=True) if directory.exists() else []
            if case:
                events = []
                for path in paths:
                    trace = json.loads(path.read_text(encoding='utf-8'))
                    if trace.get('case_id') == case['case_id']:
                        events = trace['events']
                        break
            if not events:
                st.caption('No saved agent trace for this selection in this workspace.')
            box = st.container()
            for event in pair_tool_calls(events):
                render_event(event, box)


def _examples(available, scripted, render_event, pair_tool_calls):
    with st.expander('Prepared examples', expanded=False):
        st.caption('Backup examples for the pitch. Daily processing above is the main entry point.')
        scenarios = {value['label']: dict(value, key=key) for key, value in SCENARIOS.items()
                     if value['synthetic'] == is_synthetic()}
        if not scenarios:
            return
        label = st.selectbox('Incoming return', list(scenarios))
        scenario = scenarios[label]
        st.caption(f"{scenario['blurb']} · Replay date {scenario['as_of']}")
        if st.button('Run prepared example', disabled=not available or (not scripted and not os.environ.get('RD_MODEL_ID'))):
            _run_task(lambda emit: workflow.run_example(scenario['return_id'], scenario['as_of'], emit,
                                                       scripted=scripted), 'Running prepared example')
        old_trace = Path(RUNTIME_DIR) / 'traces' / f"{scenario['key']}.json"
        if st.button('Replay saved example', disabled=not old_trace.is_file()):
            saved = json.loads(old_trace.read_text(encoding='utf-8'))
            st.session_state.events = saved['events']
            st.info('Saved playback. Current cases and approvals are preserved.')
            box = st.container()
            for event in pair_tool_calls(saved['events']):
                render_event(event, box)


def monitor(date, snapshot, available, scripted, render_event, pair_tool_calls):
    _heading('01 / Daily operations', 'Every return. One clear queue.',
             'Replay a day of returns, spot unusual patterns, and send only new signals for investigation.')
    control, description = st.columns([1, 2])
    with control:
        if st.button("Process day's returns", type='primary', width='stretch', disabled=not available):
            try:
                with st.spinner('Screening the day with grouped statistics...'):
                    workflow.process_day(date)
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    with description:
        st.caption('No model calls during screening. Existing cases receive related returns; new signals enter the investigation queue.')
    report = workflow.load_day(date)
    if not report:
        st.info('Choose a replay date and process the day to populate this monitor.')
    else:
        counts = report['counts']
        open_cases = {(case['style'], case['category']): case for case in snapshot['cases'].values()
                      if case['status'] != 'CLOSED'}
        linked_count = sum(bool(r['case_id'] or open_cases.get((r['style'], r['signal_category'])))
                           for r in report['records'] if r['level'] == 'SIGNAL')
        _tiles([('Processed', f"{counts['total']:,}"), ('Normal', counts['normal']), ('Watch', counts['watch']),
                ('Signal', counts['signal']), ('Needs data', counts['insufficient'])])
        st.caption(f"{linked_count} signal returns linked to cases · Screened as of {date} · 0 model calls during screening")
        st.divider()
        st.subheader('New signals to investigate')
        candidates = [candidate for candidate in report['candidates']
                      if (candidate['style'], candidate['category']) not in open_cases
                      or open_cases[(candidate['style'], candidate['category'])].get('workflow_error')]
        if candidates:
            frame = pd.DataFrame([{'Style': c['style'], 'Signal': c['category'], 'Today': len(c['return_ids']),
                '28-day category count': c['category_returns'], '28-day style count': c['style_returns'],
                'Category share': f"{c['category_share']:.1%}", 'Company baseline': f"{c['company_baseline_share']:.1%}",
                'Lift': f"{c['lift_vs_baseline']:.1f}×"} for c in candidates])
            st.dataframe(frame, hide_index=True, width='stretch')
            index = st.selectbox('Select signal', range(len(candidates)),
                                 format_func=lambda i: f"{candidates[i]['style']} · {candidates[i]['category']}")
            candidate = candidates[index]
            if st.button('Start investigation', type='primary', disabled=not scripted and not os.environ.get('RD_MODEL_ID')):
                _run_task(lambda emit: workflow.investigate_signal(candidate, date, emit, scripted=scripted),
                          'Investigating the selected signal')
        else:
            st.info('No new investigation is waiting for this day. Signals with open cases are already being tracked.')
        st.subheader('Returns processed today')
        choice = st.selectbox('Show returns', ['Signals', 'All records', 'Watch', 'Needs data', 'Linked to case'])
        records = [{**r, 'case_id': r['case_id'] or
                    (open_cases.get((r['style'], r['signal_category'])) or {}).get('case_id')}
                   for r in report['records']]
        records = [r for r in records if choice == 'All records' or
                   (choice == 'Signals' and r['level'] == 'SIGNAL') or
                   (choice == 'Watch' and r['level'] == 'WATCH') or
                   (choice == 'Needs data' and r['level'] == 'DATA_INSUFFICIENT') or
                   (choice == 'Linked to case' and r['case_id'])]
        if records:
            frame = pd.DataFrame([{'Return': r['return_id'], 'Style': r['style'], 'Return category': r['category'],
                'Screen': r['level'].replace('_', ' ').title(), 'Investigate category': r['signal_category'],
                'Case': r['case_id'] or '—'}
                for r in records])
            st.dataframe(frame, hide_index=True, width='stretch')
        else:
            st.caption('No returns match this filter.')
    _examples(available, scripted, render_event, pair_tool_calls)
    _technical(render_event, pair_tool_calls)


def _case_picker(snapshot, label='Select case'):
    cases = sorted(snapshot['cases'].values(), key=lambda c: (c['opened_as_of'], c['case_id']), reverse=True)
    if not cases:
        st.info('No cases in this workspace yet. Process a day and investigate a new signal first.')
        return None
    ids = [case['case_id'] for case in cases]
    selected = st.session_state.get('selected_case_id')
    index = ids.index(selected) if selected in ids else 0
    selected = st.selectbox(label, ids, index=index, format_func=lambda cid:
                            f"{snapshot['cases'][cid]['style']} · {snapshot['cases'][cid]['category']} · {cid}")
    st.session_state.selected_case_id = selected
    return snapshot['cases'][selected]


def _timeline(case, snapshot):
    approvals = [a for a in snapshot['approvals'] if a['case_id'] == case['case_id']]
    planned = case.get('verification') or {}
    decided = sum(a['status'] != 'PENDING' for a in approvals)
    stages = [('Signal detected', case['opened_as_of']),
              ('Investigation', 'Findings recorded' if case.get('root_cause') else 'In progress'),
              ('Human decision', f'{decided}/{len(approvals)} resolved' if approvals else 'No proposals'),
              ('Follow-up', planned.get('due_on', 'Not scheduled')),
              ('Resolution', 'Closed' if case['status'] == 'CLOSED' else 'Open')]
    st.subheader('Case journey')
    for column, (stage, text) in zip(st.columns(5), stages):
        column.markdown(f'**{stage}**')
        column.caption(text)
    with st.expander('Activity history', expanded=False):
        history = []
        for event in case.get('history', []):
            text = event['event']
            if text.startswith('Updated:'):
                if 'root_cause' in text:
                    text = 'Investigation findings recorded'
                elif 'verification_checks' in text:
                    text = 'Follow-up observation recorded'
                elif 'screen_evidence' in text:
                    text = 'Daily screening evidence attached'
                else:
                    continue
            history.append({'Recorded at': event['at'], 'Activity': text})
        st.caption('Replay dates describe the historical observations. Activity timestamps describe when this demo recorded a step.')
        st.dataframe(pd.DataFrame(history), hide_index=True, width='stretch')


def case_workspace(snapshot, scripted, render_event, pair_tool_calls):
    _heading('02 / Case workspace', 'From a signal to a next step.',
             'See why a case was found, what supports it, and who needs to decide what happens next.')
    case = _case_picker(snapshot)
    if not case:
        return
    cid = case['case_id']
    st.subheader(f"{case['style']} · {case['category']}")
    st.caption(f"{cid} · {STATUSES.get(case['status'], case['status'])} · Observations as of {case['opened_as_of']}")
    left, right = st.columns([1.5, 1], gap='large')
    with left:
        st.markdown('### Why this was found')
        signal = case.get('screen_evidence')
        if signal:
            _tiles([('Category returns', f"{signal['category_returns']} / {signal['style_returns']}"),
                    ('Category share', f"{signal['category_share']:.1%}"),
                    ('Company baseline', f"{signal['company_baseline_share']:.1%}")])
            st.caption(f"28-day window ending {signal['as_of']} · {signal['distinct_locations']} locations · This is a category share among returns, not a population return rate.")
        st.write(case.get('evidence') or case.get('summary') or 'Evidence is still being gathered.')
        st.markdown('### Current likely explanation')
        st.write(case.get('root_cause') or 'Investigation in progress; an explanation has not been recorded yet.')
        st.caption(f"Assessment confidence: {case.get('confidence') or 'Not assessed'} · Physical inspection has not been established by this dataset.")
        st.markdown('### Evidence and competing explanations')
        if case.get('hypotheses'):
            st.dataframe(pd.DataFrame([{'Explanation': h.get('hypothesis'), 'Assessment': h.get('verdict'),
                                      'Evidence': h.get('evidence')} for h in case['hypotheses']]),
                         hide_index=True, width='stretch')
        else:
            st.caption('No hypotheses have been recorded yet.')
    with right:
        with st.container(border=True):
            st.markdown('### Who should do what')
            st.write(f"**Owner:** {case.get('owner_team') or 'Not assigned'}")
            pending = [a for a in snapshot['approvals'] if a['case_id'] == cid and a['status'] == 'PENDING']
            for approval in pending:
                st.markdown(f"**{approval['action']}**")
                st.caption(f"Decision needed from {approval['approver']}")
            if not pending:
                st.caption('No approval proposal is waiting.')
            st.caption('Review proposals on Approvals & follow-up.')
        st.markdown('#### Evidence still needed')
        st.write('Product inspection, batch and supplier records, and verified sales coverage are needed to establish a specific cause or population return rate.')
        st.caption('Notifications and retail actions in this prototype are recorded simulations.')
        if case.get('workflow_error'):
            st.warning('The previous investigation was interrupted. Recorded case history is preserved.')
            if st.button('Retry investigation', disabled=not scripted and not os.environ.get('RD_MODEL_ID')):
                _run_task(lambda emit: workflow.investigate_signal(
                    {'style': case['style'], 'category': case['category']}, case['opened_as_of'], emit,
                    scripted=scripted), 'Resuming investigation', cid)
    st.divider()
    _timeline(case, snapshot)
    _technical(render_event, pair_tool_calls, case)


def approvals_and_followup(snapshot, scripted, render_event, pair_tool_calls):
    _heading('03 / Approvals & follow-up', 'Decisions that move a case forward.',
             'Review the proposed action, record a human decision, then check what the next observations show.')
    pending = [a for a in snapshot['approvals'] if a['status'] == 'PENDING']
    _tiles([('Awaiting decisions', len(pending)),
            ('Follow-ups scheduled', sum(bool(c.get('verification', {}).get('due_on')) and c['status'] != 'CLOSED' for c in snapshot['cases'].values())),
            ('Cases closed', sum(c['status'] == 'CLOSED' for c in snapshot['cases'].values()))])
    st.subheader('Approval queue')
    st.caption('Demo decisions are recorded under the reviewer name entered here; retail actions remain simulated.')
    reviewer = st.text_input('Reviewer name', placeholder='Enter your name before recording a decision')
    if not pending:
        st.info('No pending approval requests.')
    for approval in pending:
        case = snapshot['cases'].get(approval['case_id'], {})
        with st.container(border=True):
            st.markdown(f"#### {approval['action']}")
            st.caption(f"{case.get('style', '')} · {approval['case_id']} · {approval['approver']}")
            st.write(_detail(approval.get('detail')))
            approve, reject = st.columns(2)
            for column, label, decision in [(approve, 'Approve proposal', True), (reject, 'Reject proposal', False)]:
                if column.button(label, key=f"decision_{decision}_{approval['approval_id']}",
                                 type='primary' if decision else 'secondary', disabled=not reviewer.strip()):
                    store.decide_approval(approval['approval_id'], decision, reviewer.strip())
                    st.session_state.notice = 'Decision recorded. The case timeline has been updated.'
                    st.rerun()
    st.divider()
    st.subheader('Follow-up desk')
    case = _case_picker(snapshot, 'Case to review')
    if not case:
        return
    cid = case['case_id']
    planned = case.get('verification') or {}
    _timeline(case, snapshot)
    if not planned.get('due_on'):
        if case['status'] != 'CLOSED' and st.button('Schedule follow-up'):
            from .verification import schedule
            with workflow.exclusive_run():
                schedule(cid, case['opened_as_of'])
            st.rerun()
    else:
        chosen = st.date_input('Observation date', dt.date.fromisoformat(planned['due_on']))
        st.caption(f"Due {planned['due_on']}. A persistent signal reopens the case for review. Fewer returns alone do not establish that an action caused an improvement.")
        remaining = any(a['case_id'] == cid for a in pending)
        if remaining:
            st.caption('Resolve this case’s pending proposals before running follow-up.')
        disabled = remaining or case['status'] == 'CLOSED' or (not scripted and not os.environ.get('RD_MODEL_ID'))
        retry = bool(case.get('review_error_as_of'))
        if st.button('Retry follow-up' if retry else 'Check outcome', disabled=disabled, type='primary'):
            _run_task(lambda emit: workflow.review_case(cid, chosen.isoformat(), emit,
                      scripted=scripted, retry_review=retry), 'Checking follow-up observations', cid)
        if case.get('verification_checks'):
            latest = case['verification_checks'][-1]
            st.write(f"Latest observation: **{latest['outcome'].replace('_', ' ').title()}** on {latest['as_of']}")
    _technical(render_event, pair_tool_calls, case)


def render_workspace(render_event, pair_tool_calls, supporting_analysis):
    st.session_state.setdefault('events', [])
    st.markdown('<div class="rd-bar">ALDO · RETURNS INTELLIGENCE · HISTORICAL REPLAY</div>'
                '<div class="rd-mast"><div class="rd-wordmark">Return Detective</div></div>', unsafe_allow_html=True)
    available, connection_error, bounds = data_available(), None, {}
    snapshot = {'cases': {}, 'actions': [], 'approvals': []}
    if available:
        try:
            bounds = _coverage(workflow.source_key())
            snapshot = store.snapshot()
        except Exception as exc:
            available, connection_error = False, str(exc)
    target = st.session_state.pop('next_page', None)
    if target:
        st.session_state.workspace_page = target
    with st.sidebar:
        st.markdown('### Return operations')
        page = st.radio('Workspace', PAGES, label_visibility='collapsed', key='workspace_page')
        minimum = dt.date.fromisoformat(bounds['first_date']) if bounds.get('first_date') else None
        maximum = dt.date.fromisoformat(bounds['last_date']) if bounds.get('last_date') else None
        default = dt.date(2026, 1, 31) if is_synthetic() else dt.date(2024, 11, 23)
        latest = workflow.latest_case_date(snapshot['cases'].values())
        if latest:
            default = max(default, dt.date.fromisoformat(latest))
        if minimum and maximum:
            default = min(max(default, minimum), maximum)
        chosen = st.date_input('Replay date', default, min_value=minimum, max_value=maximum)
        modes = ['Live agents (Bedrock)', 'Scripted baseline (no model)']
        mode = st.selectbox('Investigation mode', modes, index=0 if os.environ.get('RD_MODEL_ID') else 1,
                            key='investigation_mode')
        scripted = mode == modes[1]
        st.caption('Screening is statistical in both modes. The mode only changes investigations and follow-up.')
        st.divider()
        st.caption('Synthetic dataset' if is_synthetic() else 'Authorized ALDO historical data')
        st.caption('AWS data & case storage' if BACKEND == 'athena' and store.STORE_BACKEND == 'dynamodb' else 'Local data or case storage')
        st.caption('Replay workspace · ' + (store._NAMESPACE or 'local'))
        if bounds.get('last_date'):
            st.caption(f"Snapshot covers {bounds['first_date']} to {bounds['last_date']}")
        st.caption('This prototype records proposed and simulated actions.')
    if connection_error:
        st.error('The configured data or case store could not be reached. Check the connection before processing returns.')
        with st.expander('Connection details'):
            st.code(connection_error)
    elif not available:
        st.info('Prepared data is unavailable. Generate synthetic data or configure the authorized dataset to continue.')
    notice = st.session_state.pop('notice', None)
    if notice:
        if isinstance(notice, dict):
            getattr(st, notice['tone'])(notice['text'])
        else:
            st.success(notice)
    date = chosen.isoformat()
    if page == PAGES[0]:
        monitor(date, snapshot, available, scripted, render_event, pair_tool_calls)
    elif page == PAGES[1]:
        case_workspace(snapshot, scripted, render_event, pair_tool_calls)
    else:
        approvals_and_followup(snapshot, scripted, render_event, pair_tool_calls)
    with st.expander('Supporting analysis & architecture', expanded=False):
        if st.checkbox('Load supporting analysis'):
            selection = st.selectbox('Supporting view', list(supporting_analysis))
            supporting_analysis[selection]()
