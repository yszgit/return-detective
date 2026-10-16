"""Historical operations entry points, reusing the existing tools and agents.

A day is screened with grouped SQL and no model calls. Investigations are explicit
and deduplicated by style/category. One process runs one dated action at a time.
"""
from collections import Counter, defaultdict
from contextlib import contextmanager
import datetime as dt
import hashlib
import json
from pathlib import Path
import threading

from . import data, detect, store, tools
from .config import BACKEND, DATA_DIR, DATASET_VERSION, RUNTIME_DIR

_RUN_LOCK = threading.Lock()


@contextmanager
def exclusive_run():
    if not _RUN_LOCK.acquire(blocking=False):
        raise ValueError("Another investigation or follow-up is running. Wait for it to finish.")
    try:
        yield
    finally:
        _RUN_LOCK.release()


def source_key():
    values = [BACKEND, str(DATA_DIR), DATASET_VERSION, data.ATHENA_DB, store.STORE_BACKEND,
              store.STATE_TABLE, store._NAMESPACE]
    return hashlib.sha256(json.dumps(values).encode()).hexdigest()[:16]


def coverage():
    result = data.one("select min(return_date) as first_date, max(return_date) as last_date from returns")
    return {key: str(value)[:10] if value is not None else None for key, value in result.items()}


def latest_case_date(cases):
    dates = []
    for case in cases:
        dates.append(case['opened_as_of'])
        dates.extend(check['as_of'] for check in case.get('verification_checks', []))
        planned = case.get('verification') or {}
        if planned.get('scheduled_as_of'):
            dates.append(planned['scheduled_as_of'])
    return max(dates, default=None)


def require_forward_date(as_of, cases):
    latest = latest_case_date(cases)
    if latest and as_of < latest:
        raise ValueError(f"This workspace already has case activity as of {latest}. Choose that date or later, "
                         "or use a separate workspace for an earlier replay.")


def _open_cases(snapshot):
    return {(case['style'], case['category']): case
            for case in snapshot['cases'].values() if case['status'] != 'CLOSED'}


def _report_path(as_of):
    return Path(RUNTIME_DIR) / 'monitor' / source_key() / f'{dt.date.fromisoformat(as_of).isoformat()}.json'


def load_day(as_of):
    path = _report_path(as_of)
    return json.loads(path.read_text(encoding='utf-8')) if path.is_file() else None


def _write_report(report):
    path = _report_path(report['as_of'])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, default=str, ensure_ascii=False), encoding='utf-8')
    temporary.replace(path)


def process_day(as_of):
    """Screen every supplied return dated on this day; link existing cases once.

    No new case or approval is created here. Invalid records have a separate
    DATA_INSUFFICIENT count, rather than being labelled normal.
    """
    as_of = dt.date.fromisoformat(str(as_of)).isoformat()
    with exclusive_run():
        snapshot = store.snapshot()
        require_forward_date(as_of, snapshot['cases'].values())
        daily = data.rows(f"""select return_id, style, category, channel, store,
            {data.detection_filter()} as eligible from returns where return_date={data.dlit(as_of)}
            order by return_id""")
        report = {'as_of': as_of, 'source_key': source_key(), 'model_calls': 0,
                  'records': [], 'candidates': [], 'counts': {}, 'screens': []}
        if not daily:
            report['counts'] = dict(total=0, normal=0, watch=0, signal=0, insufficient=0,
                                    linked_returns=0, investigations=0)
            _write_report(report)
            return report

        # Group once across all styles appearing today; never query per return.
        aggregate = data.rows(f"""with active_styles as (
            select distinct style from returns where return_date={data.dlit(as_of)}
            and {data.detection_filter()} and style is not null
        ), windowed as (
            select r.style,r.category,coalesce(r.store,r.channel) as location
            from returns r join active_styles a on r.style=a.style
            where {detect.window_sql(as_of, detect.WINDOW_DAYS)}
        ), counts as (select style,category,count(*) as n from windowed group by style,category),
        locations as (select style,count(distinct location) as locations from windowed group by style)
        select c.style,c.category,c.n,l.locations from counts c join locations l on c.style=l.style""")
        if data.CURATED:
            history = data.rows(f"""select category,sum(n) as n from company_daily
                where return_date<{data.dlit(as_of)} group by category""")
            denominator = sum(row['n'] for row in history)
            baseline = {row['category']: row['n'] / denominator if denominator else 0 for row in history}
        else:
            baseline = {row['category']: row['share'] for row in data.rows('select category,share from baseline')}
        counts, locations = defaultdict(dict), {}
        for row in aggregate:
            counts[row['style']][row['category']] = row['n']
            locations[row['style']] = row['locations']
        screens = {}
        for style, values in counts.items():
            screens[style] = [detect.assess_window(style, category, as_of, values, locations[style],
                              baseline.get(category, 0)) for category in detect.WATCHED]
            screens[style].sort(key=lambda s: ({'SIGNAL': 0, 'WATCH': 1, 'NORMAL': 2}[s['level']], -s['z_score']))
        report['screens'] = [screen for group in screens.values() for screen in group]
        existing = _open_cases(snapshot)
        candidates, linked = {}, defaultdict(list)
        for row in daily:
            item = dict(row, level='DATA_INSUFFICIENT', case_id=None, signal_category=None)
            if row['eligible'] and row['style']:
                style_screens = screens.get(row['style'], [])
                mine = next((s for s in style_screens if s['category'] == row['category']), None)
                target = mine if mine and mine['level'] == 'SIGNAL' else next(
                    (s for s in style_screens if s['level'] == 'SIGNAL'), None)
                item['level'] = 'SIGNAL' if target else mine['level'] if mine else 'NORMAL'
                if target:
                    key = (row['style'], target['category'])
                    item['signal_category'] = target['category']
                    if key in existing:
                        item['case_id'] = existing[key]['case_id']
                        linked[item['case_id']].append(row['return_id'])
                    if key not in existing or existing[key].get('workflow_error'):
                        candidate = candidates.setdefault(key, {**target, 'return_ids': [],
                            'representative_return_id': row['return_id']})
                        candidate['return_ids'].append(row['return_id'])
            report['records'].append(item)
        for case_id, return_ids in linked.items():
            store.link_returns(case_id, return_ids)
            store.log_action(case_id, 0, 'Daily screen: attach returns', {'as_of': as_of, 'return_ids': return_ids})
        report['candidates'] = sorted(candidates.values(), key=lambda c: (-c['z_score'], c['style'], c['category']))
        levels = Counter(row['level'] for row in report['records'])
        report['counts'] = {'total': len(daily), 'normal': levels['NORMAL'], 'watch': levels['WATCH'],
            'signal': levels['SIGNAL'], 'insufficient': levels['DATA_INSUFFICIENT'],
            'linked_returns': sum(map(len, linked.values())), 'investigations': len(candidates)}
        _write_report(report)
        return report


def investigate_signal(candidate, as_of, emit, *, scripted=False):
    """Only an explicitly selected, still-valid signal reaches existing agents."""
    as_of = dt.date.fromisoformat(str(as_of)).isoformat()
    with exclusive_run():
        snapshot = store.snapshot()
        require_forward_date(as_of, snapshot['cases'].values())
        saved = load_day(as_of)
        matching = next((row for row in (saved or {}).get('candidates', [])
                         if (row['style'], row['category']) == (candidate['style'], candidate['category'])), None)
        if not matching:
            raise ValueError("Process this day's returns before starting this investigation.")
        style, category = matching['style'], matching['category']
        existing = store.find_open_case(style, category)
        if existing and not existing.get('workflow_error'):
            store.link_returns(existing['case_id'], matching['return_ids'])
            return {'case_id': existing['case_id'], 'outcome': 'ATTACHED_TO_CASE', 'model_calls': 0}
        signal = detect.screen(style, category, as_of)
        if signal['level'] != 'SIGNAL':
            raise ValueError('The selected item is no longer at SIGNAL; screen the day again.')
        tools.AS_OF.set(as_of)
        emit({'agent': 'System', 'type': 'decision', 'data': {'decision': 'INVESTIGATE', **signal}})
        note = (f"The daily statistical screen flagged {style}, {category}, on {as_of}: "
                f"{signal['category_returns']} of {signal['style_returns']} returns in 28 days; "
                f"category share {signal['category_share']}, prior company baseline {signal['company_baseline_share']}, "
                f"lift {signal['lift_vs_baseline']}, z {signal['z_score']}. "
                f"Today's associated return IDs: {matching['return_ids'][:30]}. "
                "This is an anomaly, not a confirmed root cause or a population return rate.")
        evidence = {**signal, 'return_ids': matching['return_ids'],
                    'screening_method': 'Grouped daily SQL; zero model calls'}
        try:
            if scripted:
                from .offline import investigate_scripted
                result = investigate_scripted(style, category, emit,
                                             case_id=existing['case_id'] if existing else None)
            else:
                from .agents.pipeline import investigate_and_respond
                context = {'prior_case': existing,
                           'prior_actions': [a for a in snapshot['actions'] if existing and a['case_id'] == existing['case_id']],
                           'prior_approvals': [a for a in snapshot['approvals'] if existing and a['case_id'] == existing['case_id']]}
                result = investigate_and_respond(style, category, as_of, emit, note,
                    case_id=existing['case_id'] if existing else None, context=context if existing else None)
        except Exception as exc:
            partial = store.find_open_case(style, category)
            if partial:
                store.update_case(partial['case_id'], workflow_error=str(exc), screen_evidence=evidence)
            raise
        case = store.find_open_case(style, category)
        if not case:
            raise ValueError('The investigation did not persist a case. Inspect technical details before retrying.')
        store.link_returns(case['case_id'], matching['return_ids'])
        finding = result.get('finding') or {}
        store.update_case(case['case_id'], screen_evidence=evidence, workflow_error='',
                          key_evidence=finding.get('key_evidence', []),
                          recommended_actions=finding.get('recommended_actions', []),
                          investigation_briefing=result.get('briefing'),
                          assessment_as_of=as_of,
                          investigation_mode='scripted' if scripted else 'bedrock')
        return {'case_id': case['case_id'], 'outcome': 'INVESTIGATED', **result}


def run_example(return_id, as_of, emit, *, scripted=False):
    with exclusive_run():
        require_forward_date(as_of, store.snapshot()['cases'].values())
        if scripted:
            from .offline import run_scripted as run
        else:
            from .agents import run_pipeline as run
        return run(return_id, as_of, emit)


def review_case(case_id, as_of, emit, *, scripted=False, retry_review=False):
    with exclusive_run():
        require_forward_date(as_of, store.snapshot()['cases'].values())
        from .verification import check_case
        return check_case(case_id, as_of, emit, scripted=scripted, retry_review=retry_review)
